#!/usr/bin/env python
"""
AI-103 Lesson 17, Beat 3b - the retrieval pipeline becomes an agent tool.

    uv run python m17_agent.py

TWO OBJECTS, AND THE DIFFERENCE BETWEEN THEM IS THE WHOLE MENTAL MODEL
----------------------------------------------------------------------
    KNOWLEDGE SOURCE   the content behind the answer
    KNOWLEDGE BASE     the retrieval CONTRACT over one or more sources

Your agent declares WHAT to ground on. The knowledge base decides HOW the
grounding actually happens. Once you separate those two, every configuration
knob lands somewhere obvious, and an index stops being confused with a
retrieval pipeline.

WHY THIS IS NOT JUST RAG WITH EXTRA STEPS
-----------------------------------------
Classic RAG turns one user question into exactly one search request. Agentic
retrieval plans: it decomposes a compound question into focused subqueries, runs
them in parallel across the knowledge sources, semantically reranks each result
set, and merges the winners. Multi-part questions, follow-ups that depend on
chat history, and typos are precisely the cases a single query cannot handle.

You can watch it happen. The response has three parts -- the merged grounding
content, the references you cite, and an ACTIVITY LOG that shows the query plan
and the token accounting. Retrieval that cannot show its work cannot be
debugged, and this script prints the work.

REASONING EFFORT IS A DIAL, NOT A QUALITY SETTING
-------------------------------------------------
At the lowest setting there is NO language model in the retrieval path at all --
one query, every source searched, predictable latency, no planning tokens.
Higher settings buy query planning, source selection, and an iterative pass when
the first results come back thin. More intelligence is not automatically better;
for a narrow corpus, cheap and deterministic is often the right engineering
answer. This script runs the same question both ways and prints the difference.

OUTPUT MODE DECIDES WHO WRITES THE ANSWER
-----------------------------------------
Extractive mode hands raw grounding chunks to your agent to reason over. Answer
synthesis has the retrieval layer write a finished answer itself. When an agent
is downstream, return extractive data -- turning on synthesis in front of an
agent means two models write the same answer, doubling cost and latency while
stripping the agent of the raw material it needs.

"CONNECT RETRIEVAL PIPELINES DIRECTLY TO AGENT TOOLS" IS THE LITERAL OBJECTIVE
------------------------------------------------------------------------------
Beat 3 does not hand-roll a chat-completions call and describe it as an agent.
It builds a real one on the Microsoft Agent Framework -- an `Agent` over a
`FoundryChatClient` -- and registers the knowledge base as a FUNCTION TOOL. The
model decides whether to call it, the framework runs the tool loop, and the
retrieve body stays visible inside the tool where the JSON is still the lesson.

That distinction is worth saying on camera. A script that retrieves and then
prompts has hard-wired the retrieval: it happens once, always, whether or not
it was needed. An agent with a retrieval TOOL decides. Ask it something the
corpus cannot answer and you can watch it choose -- which is exactly Beat 4.

    --minimal-only   just the low-effort contrast
    --no-cache       every retrieve goes live
"""
from __future__ import annotations

import argparse
import asyncio
import json

import m17_cache
import m17_common as C
from m17_common import (SCOPE_COGNITIVE, Fail, HttpError, Search, banner,
                        head, kv, ok, request, step, warn)

# Three facts, three documents, one sentence. Exactly the shape a single query
# cannot cover: the fee is in the schedule, the waiver is in the SCANNED
# addendum, and the cutoff is in the wire policy.
COMPOUND = ("What is the outgoing domestic wire transfer fee, does a Premier "
            "Household customer actually pay it, and what is the same-day "
            "cutoff time for a domestic wire?")

# Nothing in the corpus answers this. A grounded agent has to say so.
OUT_OF_SCOPE = "What is Woodgrove Bank's policy on cryptocurrency custody?"

GROUNDED_SYSTEM = (
    "You answer only from the SOURCES block. Every factual sentence must end "
    "with a citation in square brackets using the ref_id of the source it came "
    "from. If the SOURCES block does not contain the answer, reply exactly: "
    "I don't know based on the Woodgrove Bank policy content I have. "
    "Never use outside knowledge."
)


def knowledge_source_definition() -> dict:
    """
    The content side. It names ONE index and which fields to work with.

    Semantic reranking is built into the agentic pipeline rather than being
    something you switch on, which makes a semantic configuration plus
    searchable, retrievable text fields a hard ADMISSION REQUIREMENT for any
    index that wants to be a knowledge source. A pure vector index with no
    semantic configuration cannot be used for grounding until it has one.

    `sourceDataFields` is a citation design decision, not a runtime feature.
    Only fields you deliberately expose here can appear in a citation. If
    document name and chunk identifier were not designed into the schema back
    in Beat 2, the agent literally cannot cite them.
    """
    return {
        "name": C.KNOWLEDGE_SOURCE,
        "kind": "searchIndex",
        "description": "Woodgrove Bank consumer banking policy, chunked and vectorized",
        "searchIndexParameters": {
            "searchIndexName": C.INDEX,
            "semanticConfigurationName": C.SEMANTIC_CONFIG,
            # Field references are OBJECTS, not bare strings. Both of these are
            # SearchIndexFieldReference[], so a plain ["title", "chunk"] fails
            # the cast server-side with a message about
            # SearchIndexKnowledgeSourceIndexFieldReference -- a shape error
            # wearing the costume of a type error.
            "sourceDataFields": [{"name": "title"},
                                 {"name": "chunk"},
                                 {"name": "source_kind"}],
            "searchFields": [{"name": "chunk"},
                             {"name": "title"}],
        },
    }


def knowledge_base_definition(s: C.Settings) -> dict:
    """
    The contract side. Sources, an optional model, and default behavior.

    The model here is used for QUERY PLANNING, not for writing an answer --
    outputMode is extractiveData on purpose. Only the gpt-4o, gpt-4.1, and gpt-5
    families are supported for planning; an audio, image, or video deployment is
    rejected outright.

    The search service reaches this model with its OWN managed identity, which
    needs Cognitive Services User on the Foundry resource. That identity is a
    different security principal from the human running this script, so being
    Owner on the subscription grants it exactly nothing.

    Lifecycle rule: create the knowledge source FIRST. Knowledge bases
    reference sources by name, they must live on the same search service, and
    deleting a source means updating or deleting every base that references it.
    """
    return {
        "name": C.KNOWLEDGE_BASE,
        "description": "Woodgrove Bank grounding contract for the support agent",
        "retrievalInstructions": (
            "Answer only from Woodgrove Bank policy content. A product addendum "
            "overrides the published fee schedule where the two disagree."),
        # Extractive: hand the agent raw grounding and let the agent reason.
        "outputMode": "extractiveData",
        "knowledgeSources": [{"name": C.KNOWLEDGE_SOURCE}],
        "models": [{
            "kind": "azureOpenAI",
            "azureOpenAIParameters": {
                "resourceUri": s.foundry_resource_uri,
                "deploymentId": s.chat_deployment,
                "modelName": s.chat_deployment,
            },
        }],
        "retrievalReasoningEffort": {"kind": "medium"},
    }


def print_activity(activity: list) -> int:
    """The query plan, on screen. This is the debuggability argument."""
    head("activity log -- what retrieval actually did")
    subqueries = 0
    for entry in activity or []:
        kind = entry.get("type")
        if kind == "modelQueryPlanning":
            kv("query planning",
               f"{entry.get('modelName')}  in {entry.get('inputTokens')} tok"
               f" / out {entry.get('outputTokens')} tok"
               f"  {entry.get('elapsedMs')} ms")
        elif kind == "searchIndex":
            subqueries += 1
            args = entry.get("searchIndexArguments") or {}
            kv(f"subquery {subqueries}", f"\"{args.get('search')}\"")
            kv("", f"{entry.get('count')} documents ranked  "
                   f"(semantic config {args.get('semanticConfigurationName')})")
        elif kind == "agenticReasoning":
            effort = (entry.get("retrievalReasoningEffort") or {}).get("kind")
            kv("agentic reasoning",
               f"effort {effort}, {entry.get('reasoningTokens')} reasoning tokens")
        elif kind == "modelAnswerSynthesis":
            kv("answer synthesis",
               f"in {entry.get('inputTokens')} / out {entry.get('outputTokens')}")
    return subqueries


def print_references(references: list) -> None:
    head("references -- what you cite")
    for reference in (references or [])[:8]:
        source = (reference.get("sourceData") or {})
        title = source.get("title") or "?"
        kv(f"ref_id {reference.get('id')}",
           f"{title}   (from activity #{reference.get('activitySource')})")
    if references:
        print()
        print("  The ref_id is a handle for THIS response, not the document key.")
        print("  activitySource points back at the subquery that found it, which")
        print("  is how a citation links to the retrieval step that produced it.")


def grounding_text(payload: dict) -> str:
    """The merged grounding string -- one JSON-encoded blob of ranked chunks."""
    for message in payload.get("response") or []:
        for part in message.get("content") or []:
            if part.get("type") == "text":
                return part.get("text") or ""
    return ""


def ground_the_model(s: C.Settings, question: str, sources: str) -> str:
    """
    Hand the grounding to a model and demand citations.

    This is the half of the loop the knowledge base deliberately does NOT do
    for you in extractive mode. It is kept as the NO-AGENT baseline: retrieval
    already happened, unconditionally, and the model only writes prose. Beat 3
    runs the agent version of this and the difference is the teaching point.
    """
    url = f"{s.foundry_openai_endpoint}/openai/v1/chat/completions"
    body = {
        "model": s.chat_deployment,
        "messages": [
            {"role": "system", "content": GROUNDED_SYSTEM},
            {"role": "user", "content": f"SOURCES:\n{sources}\n\nQUESTION: {question}"},
        ],
    }
    payload, _ = m17_cache.remember(
        "chat", question[:40],
        lambda: request("POST", url, s.token(SCOPE_COGNITIVE), body)[1],
        url=url, body=body)
    return payload["choices"][0]["message"]["content"]


# ---------------------------------------------------------------------------
# The agent. Retrieval as a tool the MODEL decides to call.
# ---------------------------------------------------------------------------

# Tool calls are counted here so the demo can prove the model actually invoked
# retrieval rather than answering from what it already knows. A tool that is
# never called and a tool that returned nothing look identical in the answer.
TOOL_CALLS: list[dict] = []


def build_agent(settings: C.Settings, search: Search):
    """
    An Agent over FoundryChatClient, with the knowledge base as a function tool.

    THE DOCSTRING IS THE TOOL CONTRACT. The framework turns this function's
    signature and docstring into the JSON schema the model sees, which makes
    the prose below a functional part of the system, not a comment. Vague
    wording here is a retrieval bug: the model calls the tool at the wrong
    times, or not at all.
    """
    from agent_framework import Agent, tool
    from agent_framework.foundry import FoundryChatClient
    from azure.identity import AzureCliCredential

    retrieve_path = f"knowledgeBases/{C.KNOWLEDGE_BASE}/retrieve"

    # approval_mode gates a tool behind human sign-off: the run pauses and
    # surfaces an approval request before the function executes. Retrieval is
    # READ-ONLY, so 'never_require' is the correct setting -- it is stated
    # explicitly rather than defaulted, because the exam asks where the gate
    # belongs. Put 'always_require' on the tool that moves money, not the one
    # that reads policy.
    @tool(name="search_woodgrove_policy", approval_mode="never_require")
    def search_woodgrove_policy(question: str) -> str:
        """Search Woodgrove Bank's consumer banking policy corpus.

        Call this for ANY question about Woodgrove Bank fees, wire transfers,
        account terms, overdrafts, card disputes, or product addenda. Returns
        ranked policy excerpts. Returns no usable content when the corpus does
        not cover the topic, which is itself a valid and meaningful answer.

        Args:
            question: The user's question, in natural language.
        """
        payload, cached = search.cached(
            "retrieve", f"agent-tool-{question[:30]}", "POST", retrieve_path,
            {"messages": [{"role": "user",
                           "content": [{"type": "text", "text": question}]}],
             "includeActivity": True,
             "knowledgeSourceParams": [{
                 "knowledgeSourceName": C.KNOWLEDGE_SOURCE,
                 "kind": "searchIndex",
                 "includeReferences": True,
                 "includeReferenceSourceData": True}]},
            api_version=settings.preview_api_version)
        grounding = grounding_text(payload)
        TOOL_CALLS.append({
            "question": question,
            "chars": len(grounding),
            "subqueries": sum(1 for e in (payload.get("activity") or [])
                              if e.get("type") == "searchIndex"),
            "references": len(payload.get("references") or []),
            "cached": cached,
        })
        # An empty string would let the model treat this as a tool failure and
        # retry. Say plainly that the corpus has no answer, so "I don't know"
        # is the obvious next move rather than a guess.
        return grounding or "No Woodgrove Bank policy content matches that question."

    return Agent(
        client=FoundryChatClient(
            project_endpoint=settings.project_endpoint,
            model=settings.chat_deployment,
            credential=AzureCliCredential(),
        ),
        name="woodgrove-support",
        instructions=GROUNDED_SYSTEM,
        tools=[search_woodgrove_policy],
        # TOOL CHOICE. "auto" is the default; it is written out because the
        # value is the demo. "required" would force a call every turn and
        # "none" would disable calling while leaving the tool in the schema.
        # Beat 4 only works on "auto": the refusal is worth showing because
        # the MODEL chose to search and then declined. Force the call and you
        # have proven nothing about the model's judgment, only your own.
        default_options={"tool_choice": "auto"},
    )


def run_agent(agent, question: str) -> str:
    """One agent turn. The framework owns the tool loop, so this stays small."""
    result = asyncio.run(agent.run(question))
    return (result.text or "").strip()


def report_tool_calls(label: str) -> bool:
    """Show what the model chose to do. Returns True if it called the tool."""
    head(f"what the agent actually did -- {label}")
    if not TOOL_CALLS:
        warn("the model answered without calling the retrieval tool")
        return False
    for i, call in enumerate(TOOL_CALLS, 1):
        kv(f"tool call {i}", f"search_woodgrove_policy(\"{call['question'][:52]}\")")
        kv("", f"{call['chars']:,} chars, {call['subqueries']} subqueries, "
               f"{call['references']} references"
               f"{'  (replayed from cache)' if call['cached'] else ''}")
    ok(f"the model invoked the retrieval pipeline {len(TOOL_CALLS)} time(s)")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--minimal-only", action="store_true",
                        help="only run the low-effort contrast")
    m17_cache.add_cache_arguments(parser)
    args = parser.parse_args()
    m17_cache.apply_cache_arguments(args)

    settings = C.load_settings()
    search = Search(settings)
    preview = settings.preview_api_version

    banner("AI-103 L17 Beat 3b -- retrieval as a tool an agent can call",
           f"knowledge base {C.KNOWLEDGE_BASE}  api-version {preview}")

    # Source first, then base. The base references the source by name.
    head("creating the retrieval contract")
    for label, path, body in (
            ("knowledge source", f"knowledgeSources/{C.KNOWLEDGE_SOURCE}",
             knowledge_source_definition()),
            ("knowledge base", f"knowledgeBases/{C.KNOWLEDGE_BASE}",
             knowledge_base_definition(settings))):
        status, _ = search.call("PUT", path, body, api_version=preview)
        ok(f"{label:<18} {path.split('/')[-1]}  (HTTP {status})")

    retrieve_path = f"knowledgeBases/{C.KNOWLEDGE_BASE}/retrieve"

    # -----------------------------------------------------------------------
    # Planned retrieval. One sentence, three facts, three documents.
    # -----------------------------------------------------------------------
    if not args.minimal_only:
        banner("1. a compound question, decomposed")
        kv("question", COMPOUND)
        planned, _ = search.cached(
            "retrieve", "compound-planned", "POST", retrieve_path,
            {"messages": [{"role": "user",
                           "content": [{"type": "text", "text": COMPOUND}]}],
             "includeActivity": True,
             "knowledgeSourceParams": [{
                 "knowledgeSourceName": C.KNOWLEDGE_SOURCE,
                 "kind": "searchIndex",
                 "includeReferences": True,
                 "includeReferenceSourceData": True}]},
            api_version=preview)
        planned_subqueries = print_activity(planned.get("activity"))
        print_references(planned.get("references"))

    # -----------------------------------------------------------------------
    # The dial, turned all the way down.
    # -----------------------------------------------------------------------
    banner("2. the same question with no model in the retrieval path")
    minimal, _ = search.cached(
        "retrieve", "compound-minimal", "POST", retrieve_path,
        # NOTE THE INPUT SHAPE CHANGE. Minimal effort rejects `messages` with
        # "Messages input not supported when 'minimal' reasoning effort is
        # requested. Use intents input instead." Conversation history is
        # something a PLANNER reads; with no planner there is nothing to read
        # it, so the input degrades to a single stated intent.
        {"intents": [{"type": "semantic", "search": COMPOUND}],
         "includeActivity": True,
         "retrievalReasoningEffort": {"kind": "minimal"}},
        api_version=preview)
    minimal_subqueries = print_activity(minimal.get("activity"))

    if not args.minimal_only:
        head("the dial, in one comparison")
        kv("medium effort", f"{planned_subqueries} subqueries, "
                            f"{len(planned.get('references') or [])} references, "
                            f"planning tokens billed to the model")
        kv("minimal effort", f"{minimal_subqueries} subquery, "
                             f"{len(minimal.get('references') or [])} references, "
                             f"no model in the retrieval path")
        print()
        print("  Two bills, one feature: Azure AI Search charges retrieval")
        print("  tokens for subquery execution and semantic ranking, and the")
        print("  model provider separately charges input and output tokens for")
        print("  query planning. Budget only the search line and you will be")
        print("  surprised.")

    if args.minimal_only:
        print()
        kv("cache", m17_cache.summary())
        return 0

    # -----------------------------------------------------------------------
    # The agent's half of the job. The pipeline becomes a TOOL.
    # -----------------------------------------------------------------------
    banner("3. the retrieval pipeline as an agent tool",
           "Microsoft Agent Framework -- Agent over FoundryChatClient")
    print()
    print("  Everything above called retrieve directly: the search happened")
    print("  because this script said so. Now the knowledge base is a function")
    print("  tool on an agent, and whether retrieval runs at all is the MODEL's")
    print("  decision. Same REST body, same knowledge base -- different owner.")

    step("building the agent and registering the retrieval tool")
    agent = build_agent(settings, search)
    ok(f"tool registered   search_woodgrove_policy -> {C.KNOWLEDGE_BASE}")
    kv("tool_choice", "auto        (required = force a call, none = disable)")
    kv("approval_mode", "never_require  (always_require gates on a human)")

    kv("question", COMPOUND)
    TOOL_CALLS.clear()
    answer = run_agent(agent, COMPOUND)
    called = report_tool_calls("the answerable question")

    head("the agent's answer")
    for line in answer.splitlines():
        print(f"  {line}")

    cited = "[" in answer and "]" in answer
    print()
    if cited:
        ok("the answer carries citations back to reference ids")
    else:
        warn("no citations in the answer -- tighten the system prompt")

    # -----------------------------------------------------------------------
    # The negative case. This is the one people forget to test.
    # -----------------------------------------------------------------------
    banner("4. the question the corpus cannot answer")
    kv("question", OUT_OF_SCOPE)
    TOOL_CALLS.clear()
    refusal = run_agent(agent, OUT_OF_SCOPE)
    searched_anyway = report_tool_calls("the unanswerable question")

    head("the agent's answer")
    for line in refusal.splitlines():
        print(f"  {line}")
    print()
    print("  A knowledge source that returns zero good matches is a SUCCESS,")
    print("  not a failure. Vector retrieval alone would still have handed the")
    print("  model its nearest neighbors and let it improvise -- the refusal is")
    print("  the instruction plus semantic reranking doing their jobs.")
    if searched_anyway:
        print()
        print("  Note the agent still SEARCHED before declining. That is the")
        print("  correct order: it cannot know the corpus is silent on crypto")
        print("  custody until it looks. Declining without searching would be")
        print("  the same right answer for the wrong reason.")
    declined = "don't know" in refusal.lower() or "do not know" in refusal.lower()
    if declined:
        ok("the agent declined instead of inventing a policy")
    else:
        warn("the model answered anyway -- that is a grounding failure")

    # -----------------------------------------------------------------------
    # The portability argument.
    # -----------------------------------------------------------------------
    banner("5. the same knowledge base, as a portable tool")
    mcp_url = search.url(f"knowledgeBases/{C.KNOWLEDGE_BASE}/mcp",
                         api_version=preview)
    kv("MCP endpoint", mcp_url.split("?")[0])
    try:
        # MCP speaks JSON-RPC and answers as a server-sent-event stream, so the
        # Accept header has to admit text/event-stream or the server refuses.
        _, raw = request("POST", mcp_url, settings.token(C.SCOPE_SEARCH),
                         {"jsonrpc": "2.0", "id": 1, "method": "tools/list",
                          "params": {}},
                         extra_headers={"Accept": "application/json, text/event-stream"})
        blob = raw if isinstance(raw, str) else json.dumps(raw)
        payload = json.loads(blob.split("data:", 1)[1].strip()) if "data:" in blob \
            else json.loads(blob)
        tools = payload["result"]["tools"]
        for tool in tools:
            kv("tool exposed", tool.get("name"))
        ok(f"{len(tools)} tool. Any MCP-capable client can call this retrieval "
           f"pipeline.")
        print()
        print("  That is the objective in one line: the pipeline is a TOOL, not")
        print("  code welded into one application. One tuned knowledge base can")
        print("  serve a Foundry agent, a low-code agent, and a developer IDE")
        print("  without being rebuilt three times.")
        print()
        print("  Caveat worth saying out loud: the MCP result returns content as")
        print("  a JSON-encoded string with NO separate activity or references")
        print("  arrays. If the teaching point is the query plan, demo the")
        print("  retrieve action, not the MCP endpoint.")
    except (HttpError, KeyError, ValueError, IndexError) as exc:
        warn(f"MCP probe did not return a tool list: {exc}")

    print()
    kv("cache", m17_cache.summary())
    # `called` belongs in this gate: an answer that is correct and cited but
    # was never retrieved is the model reciting training data, which is the
    # exact failure this whole lesson exists to make visible.
    return 0 if (called and cited and declined) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Fail as exc:
        print(f"\n  [FAIL] {exc}")
        raise SystemExit(2)
    except HttpError as exc:
        print(f"\n  [FAIL] {exc.short(600)}")
        raise SystemExit(2)
    # Anything else -- expired az token, DNS, timeout, JSON decode -- must
    # land as the same one-line [FAIL] the panic table trains you to read.
    # A raw traceback mid-take is the loudest way to lose a recording.
    except Exception as exc:
        print(f"\n  [FAIL] {type(exc).__name__}: {exc}")
        if "Credential" in type(exc).__name__:
            print("  [FIX]  run: az login")
        raise SystemExit(2)
