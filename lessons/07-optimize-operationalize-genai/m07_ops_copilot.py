#!/usr/bin/env python
"""
m07_ops_copilot.py -- AI-103 Lesson 7, the interactive version.

A REPL you OPERATE, not a script that runs on rails. You play a support-ops lead at
Contoso working a live ticket queue, and every generation lever the lesson teaches
is a control you actually turn while doing the work:

  * generation dials      -- temperature / top_p (standard models) OR reasoning_effort /
                             verbosity (reasoning models), plus max_output_tokens. The app
                             exposes whichever the CURRENT model supports and tells you why.
  * prompt patterns       -- a role/persona system prompt, few-shot triage, STRUCTURED OUTPUT
                             (a JSON schema the model must satisfy), and grounding in a KB.
  * reflection            -- draft a reply, have the model score it against criteria, and
                             regenerate using its own critique.
  * tokens + cost         -- a running meter: input/output tokens and an estimated dollar cost
                             per call and for the session.
  * model switching       -- flip between a reasoning model and a standard model on the same
                             task and watch which dials light up.

Auth is KEYLESS (AzureCliCredential -- your `az login` identity). Read-only: it calls the
model, mutates no Azure resource.

Run interactive:  uv run python m07_ops_copilot.py
Guided auto-tour:  uv run python m07_ops_copilot.py --auto        # non-interactive, for a quick look
Plan only:         uv run python m07_ops_copilot.py --dry-run

Type `help` inside the REPL for the command list.

Author: Tim Warner (TechTrainerTim.com) | Microsoft Press AI-103 video course
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass

# Model output carries smart punctuation; force UTF-8 so a Windows console never crashes on print.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")  # so piped/redirected input decodes cleanly too
except Exception:
    pass

from azure.identity import AzureCliCredential
from azure.ai.projects import AIProjectClient

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except ImportError:
    pass


# =============================================================================
# Model registry -- reasoning + (optional) standard, read from .env
# =============================================================================
# A "reasoning" model (gpt-5 / o-series) rejects temperature/top_p and steers with
# reasoning_effort. A "standard" model (gpt-4o, gpt-4.1, Phi-4, ...) takes temperature.
# The app adapts to whichever you point it at. Set MODEL_STANDARD_NAME to light up
# the temperature dial for real.
REASONING_MODEL = os.environ.get("MODEL_DEPLOYMENT_NAME", "gpt-5-mini")
STANDARD_MODEL = os.environ.get("MODEL_STANDARD_NAME", "")  # e.g. "phi-4" or "gpt-4o-mini"

# Illustrative pricing (USD per 1,000 tokens). These are teaching estimates, NOT a bill --
# check the Azure pricing page for live numbers. Override per model as you like.
PRICING = {
    "gpt-5-mini": {"in": 0.00025, "out": 0.002},
    "phi-4": {"in": 0.000125, "out": 0.0005},
    "_default": {"in": 0.0005, "out": 0.0015},
}

REASONING_HINTS = ("gpt-5", "o1", "o3", "o4", "reasoning")


def is_reasoning_model(name: str) -> bool:
    n = name.lower()
    # gpt-5-chat is NOT a reasoning model; everything else in the gpt-5 family is.
    if "gpt-5-chat" in n:
        return False
    return any(h in n for h in REASONING_HINTS)


# =============================================================================
# Generation settings -- the dials, as live state you edit with `set`
# =============================================================================
@dataclass
class GenSettings:
    temperature: float = 0.7          # standard models only
    top_p: float = 1.0                # standard models only
    reasoning_effort: str = "low"     # reasoning models only: minimal|low|medium|high
    verbosity: str = "medium"         # reasoning models: low|medium|high
    max_output_tokens: int = 800      # both; on reasoning models this budget also covers thinking
    persona: str = (
        "You are a calm, precise Contoso support engineer. Be concise, specific, "
        "and never promise timelines you can't verify."
    )

    def summary(self, model: str) -> str:
        reasoning = is_reasoning_model(model)
        lines = [f"  model            : {model}   ({'reasoning' if reasoning else 'standard'})"]
        if reasoning:
            lines += [
                f"  reasoning_effort : {self.reasoning_effort}   [active]",
                f"  verbosity        : {self.verbosity}   [active]",
                f"  temperature      : {self.temperature}   [ignored -- reasoning model]",
                f"  top_p            : {self.top_p}   [ignored -- reasoning model]",
            ]
        else:
            lines += [
                f"  temperature      : {self.temperature}   [active]",
                f"  top_p            : {self.top_p}   [active]",
                f"  reasoning_effort : {self.reasoning_effort}   [ignored -- standard model]",
                f"  verbosity        : {self.verbosity}   [ignored -- standard model]",
            ]
        lines.append(f"  max_output_tokens: {self.max_output_tokens}   [active]")
        lines.append(f"  persona          : {self.persona[:60]}...")
        return "\n".join(lines)


# =============================================================================
# The ticket queue + a tiny grounding KB (the "business")
# =============================================================================
TICKETS = [
    {
        "id": "CS-4471",
        "from": "dana@northwind.example",
        "subject": "Checkout API returning 503 for the last hour",
        "body": "Every call to /v2/checkout has returned 503 since about 14:00. Our storefront is "
                "down and we're losing sales. This is urgent -- please escalate.",
    },
    {
        "id": "CS-4472",
        "from": "sam@fabrikam.example",
        "subject": "How do I rotate my API keys?",
        "body": "We're doing a security review and I need to rotate our API keys. "
                "Where in the portal is that, and will active sessions drop?",
    },
    {
        "id": "CS-4473",
        "from": "billing@woodgrove.example",
        "subject": "Charged twice for the November invoice",
        "body": "We got billed two times for invoice #NOV-2231. Please refund the duplicate. "
                "Frankly this has happened before and it's frustrating.",
    },
]

KB = {
    "key-rotation": "API keys rotate under Portal > Settings > API Keys > Rotate. Rotation issues a "
                    "new key immediately; the old key keeps working for a 24-hour grace window, so "
                    "active sessions do NOT drop if you swap within 24 hours.",
    "refunds": "Duplicate-charge refunds are processed within 5-7 business days to the original "
               "payment method. Support can flag a duplicate; Finance issues the refund.",
    "status": "Platform status and active incidents are published at status.contoso.example.",
}


# =============================================================================
# The one place model calls happen -- builds the RIGHT kwargs for the model type
# =============================================================================
class Copilot:
    def __init__(self, oai, model: str, settings: GenSettings):
        self.oai = oai
        self.model = model
        self.settings = settings
        self.session_tokens = {"in": 0, "out": 0}
        self.session_cost = 0.0

    # -- core call -----------------------------------------------------------
    def _call(self, instructions: str, user_input: str, schema: dict | None = None,
              effort: str | None = None):
        """Send one Responses API call, adapting parameters to the model type."""
        s = self.settings
        kwargs = {"model": self.model, "instructions": instructions, "input": user_input,
                  "max_output_tokens": s.max_output_tokens}
        if is_reasoning_model(self.model):
            kwargs["reasoning"] = {"effort": effort or s.reasoning_effort}
        else:
            kwargs["temperature"] = s.temperature
            kwargs["top_p"] = s.top_p
        if schema is not None:
            kwargs["text"] = {"format": {"type": "json_schema", "name": "out",
                                         "schema": schema, "strict": True}}
        start = time.perf_counter()
        resp = self.oai.responses.create(**kwargs)
        secs = time.perf_counter() - start
        self._meter(resp)
        text = (resp.output_text or "").strip()
        status = getattr(resp, "status", "completed")
        return text, secs, status

    def _meter(self, resp) -> None:
        u = getattr(resp, "usage", None)
        tin = getattr(u, "input_tokens", 0) or 0
        tout = getattr(u, "output_tokens", 0) or 0
        self.session_tokens["in"] += tin
        self.session_tokens["out"] += tout
        rate = PRICING.get(self.model, PRICING["_default"])
        cost = tin / 1000 * rate["in"] + tout / 1000 * rate["out"]
        self.session_cost += cost
        self._last = {"in": tin, "out": tout, "cost": cost}

    def last_meter(self) -> str:
        m = getattr(self, "_last", {"in": 0, "out": 0, "cost": 0.0})
        return f"[tokens in={m['in']} out={m['out']} | ~${m['cost']:.5f} this call | " \
               f"session ~${self.session_cost:.5f}]"

    # -- live parameter probe: prove which dials this model actually honors ---
    def probe_dials(self) -> None:
        """Send real calls so the generation dials are tangible, not theoretical."""
        reasoning = is_reasoning_model(self.model)
        print(f"  model: {self.model}  ({'reasoning' if reasoning else 'standard'})")

        # 1) temperature: the dial everyone reaches for first. Watch what THIS model does.
        try:
            r = self.oai.responses.create(model=self.model, input="Say hi in one word.",
                                          temperature=0.9, max_output_tokens=50)
            self._meter(r)
            print(f"  temperature=0.9 -> ACCEPTED  (standard model: temperature IS your creativity dial)")
        except Exception as exc:
            msg = str(exc).split("message':")[-1][:80]
            print(f"  temperature=0.9 -> REJECTED  ...{msg}")
            print("     reasoning models don't take temperature/top_p -- their dial is reasoning_effort")

        # 2) the dial that DOES steer this model -- show two settings back to back.
        if reasoning:
            for eff in ("minimal", "high"):
                t = time.perf_counter()
                r = self.oai.responses.create(model=self.model, reasoning={"effort": eff},
                                              input="In one sentence, why cap token budgets in production?",
                                              max_output_tokens=2000)
                self._meter(r)
                print(f"  reasoning_effort={eff:<7} -> {r.output_text.strip()[:70]!r}  ({time.perf_counter()-t:.1f}s)")
        else:
            for temp in (0.0, 1.2):
                r = self.oai.responses.create(model=self.model, temperature=temp,
                                              input="Give a one-line tagline for a router.", max_output_tokens=60)
                self._meter(r)
                print(f"  temperature={temp} -> {r.output_text.strip()[:70]!r}")
        print(f"  max_output_tokens is the length ceiling on BOTH; on a reasoning model it also covers hidden thinking.")

    # -- business operations -------------------------------------------------
    def triage(self, ticket: dict):
        """Classify the ticket into structured JSON (deterministic work -> low effort/temp)."""
        schema = {
            "type": "object",
            "properties": {
                "category": {"type": "string", "enum": ["outage", "how-to", "billing", "other"]},
                "priority": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
                "sentiment": {"type": "string", "enum": ["angry", "neutral", "happy"]},
                "one_line_summary": {"type": "string"},
            },
            "required": ["category", "priority", "sentiment", "one_line_summary"],
            "additionalProperties": False,
        }
        instructions = (
            "You triage support tickets. Use the examples as the labeling standard.\n"
            "EXAMPLES:\n"
            "  'Everything is 500ing, we're down!' -> outage / urgent / angry\n"
            "  'Where do I find my invoice PDF?' -> how-to / low / neutral\n"
            "Return only the structured fields."
        )
        text, secs, _ = self._call(instructions, self._ticket_text(ticket), schema=schema,
                                    effort="minimal")
        return json.loads(text), secs

    def draft_reply(self, ticket: dict, kb_key: str | None):
        """Draft a customer reply: persona (role) + grounding in a KB snippet."""
        grounding = KB.get(kb_key or "", "")
        instructions = (
            f"{self.settings.persona}\n"
            "Write a reply to the customer. Ground every factual claim ONLY in the KB below; "
            "if the KB doesn't cover something, say you'll follow up rather than inventing it.\n"
            f"KB: {grounding or '(no KB article attached)'}"
        )
        return self._call(instructions, self._ticket_text(ticket))

    def critique(self, ticket: dict, reply: str):
        """Self-critique: score the draft against criteria, return JSON the loop branches on."""
        schema = {
            "type": "object",
            "properties": {
                "score": {"type": "integer", "minimum": 1, "maximum": 5},
                "grounded": {"type": "boolean"},
                "critique": {"type": "string"},
            },
            "required": ["score", "grounded", "critique"],
            "additionalProperties": False,
        }
        instructions = (
            "Score the REPLY from 1-5 for a support answer: accurate, grounded in the ticket, "
            "concise, and appropriately empathetic. grounded=false if it invents facts. "
            "Give a one-line critique."
        )
        text, secs, _ = self._call(instructions, f"TICKET:\n{self._ticket_text(ticket)}\n\nREPLY:\n{reply}",
                                    schema=schema, effort="medium")
        return json.loads(text), secs

    def improve(self, ticket: dict, reply: str, critique: str, kb_key: str | None):
        grounding = KB.get(kb_key or "", "")
        instructions = (
            f"{self.settings.persona}\n"
            f"Rewrite the reply to fix this critique: {critique}\n"
            f"Ground claims in the KB only. KB: {grounding or '(none)'}"
        )
        return self._call(instructions, f"TICKET:\n{self._ticket_text(ticket)}\n\nDRAFT:\n{reply}")

    @staticmethod
    def _ticket_text(t: dict) -> str:
        return f"[{t['id']}] From {t['from']}\nSubject: {t['subject']}\n\n{t['body']}"


# =============================================================================
# Presentation helpers
# =============================================================================
def rule(title: str = "") -> None:
    print("\n" + "=" * 78)
    if title:
        print(title)
        print("=" * 78)


def show_tickets(active_idx: int | None) -> None:
    print("\nTicket queue:")
    for i, t in enumerate(TICKETS):
        mark = ">" if i == active_idx else " "
        print(f" {mark} [{i}] {t['id']}  {t['subject']}  (from {t['from']})")


HELP = """
Commands (you drive -- nothing is on rails):
  tickets                 list the ticket queue
  pick <n>                make ticket n the active ticket
  dials                   live probe: which generation params THIS model honors (temp vs effort)
  triage                  classify the active ticket -> structured JSON (few-shot + schema)
  draft [kb]              draft a customer reply; optional KB key to ground it
                          (kb keys: key-rotation, refunds, status)
  critique                have the model score the last draft (1-5 + grounded + critique)
  improve                 regenerate the draft using that critique (the reflection loop)
  set <dial> <value>      temperature | top_p | effort | verbosity | maxtokens | persona
  show                    show current generation settings for the active model
  model <reasoning|standard>   switch model (standard lights up temperature for real)
  tokens                  session token + cost meter
  help                    this list
  quit                    exit
"""


# =============================================================================
# REPL
# =============================================================================
def connect() -> AIProjectClient:
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        sys.exit("ERROR: FOUNDRY_PROJECT_ENDPOINT not set. See .env.example, then `az login`.")
    return AIProjectClient(endpoint=endpoint, credential=AzureCliCredential())


def build_copilot(project: AIProjectClient, which: str, settings: GenSettings) -> Copilot:
    model = STANDARD_MODEL if which == "standard" else REASONING_MODEL
    if which == "standard" and not STANDARD_MODEL:
        print("  (no MODEL_STANDARD_NAME set -- staying on the reasoning model. "
              "Deploy a standard model and set it in .env to turn temperature for real.)")
        model = REASONING_MODEL
    return Copilot(project.get_openai_client(), model, settings)


def repl(project: AIProjectClient) -> None:
    settings = GenSettings()
    bot = build_copilot(project, "reasoning", settings)
    active = None
    last_draft = ""
    last_kb = None

    rule("CONTOSO SUPPORT OPS COPILOT")
    print("You're the ops lead. Work the queue. Type `help` for commands, `quit` to leave.")
    show_tickets(active)

    while True:
        try:
            # lstrip a stray BOM too, so piped/redirected input behaves like typed input.
            raw = input("\nops> ").lstrip("\ufeff").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not raw:
            continue
        cmd, *rest = raw.split(maxsplit=1)
        arg = rest[0] if rest else ""
        cmd = cmd.lower()

        if cmd in ("quit", "exit"):
            print(f"\nSession close. {bot.last_meter()}")
            return
        if cmd == "help":
            print(HELP)
        elif cmd == "tickets":
            show_tickets(active)
        elif cmd == "pick":
            if arg.isdigit() and 0 <= int(arg) < len(TICKETS):
                active = int(arg)
                last_draft = ""
                print(f"  active ticket -> {TICKETS[active]['id']}: {TICKETS[active]['subject']}")
            else:
                print("  usage: pick <n>  (see `tickets`)")
        elif cmd == "show":
            print(settings.summary(bot.model))
        elif cmd == "tokens":
            print(f"  session totals: in={bot.session_tokens['in']} out={bot.session_tokens['out']} "
                  f"| estimated ~${bot.session_cost:.5f}")
        elif cmd == "model":
            bot = build_copilot(project, "standard" if arg.lower() == "standard" else "reasoning", settings)
            print(f"  model -> {bot.model}  ({'reasoning' if is_reasoning_model(bot.model) else 'standard'})")
        elif cmd == "dials":
            rule("PARAMETER DIALS (live probe)")
            bot.probe_dials()
        elif cmd == "set":
            _apply_set(settings, arg)
        elif cmd in ("triage", "draft", "critique", "improve"):
            if active is None:
                print("  pick a ticket first: `pick 0`")
                continue
            last_draft, last_kb = _run_op(cmd, bot, TICKETS[active], settings, last_draft, last_kb, arg)
        else:
            print(f"  unknown command: {cmd!r}. Type `help`.")


def _apply_set(settings: GenSettings, arg: str) -> None:
    parts = arg.split(maxsplit=1)
    if len(parts) != 2:
        print("  usage: set <dial> <value>   (temperature|top_p|effort|verbosity|maxtokens|persona)")
        return
    dial, value = parts[0].lower(), parts[1]
    try:
        if dial == "temperature":
            settings.temperature = float(value)
        elif dial == "top_p":
            settings.top_p = float(value)
        elif dial == "effort":
            settings.reasoning_effort = value
        elif dial == "verbosity":
            settings.verbosity = value
        elif dial == "maxtokens":
            settings.max_output_tokens = int(value)
        elif dial == "persona":
            settings.persona = value
        else:
            print(f"  unknown dial {dial!r}")
            return
        print(f"  {dial} -> {value}")
    except ValueError:
        print(f"  couldn't set {dial} to {value!r}")


def _run_op(cmd, bot, ticket, settings, last_draft, last_kb, arg):
    if cmd == "triage":
        rule(f"TRIAGE  {ticket['id']}")
        data, secs = bot.triage(ticket)
        print(json.dumps(data, indent=2))
        print(f"  ({secs:.1f}s)  {bot.last_meter()}")
    elif cmd == "draft":
        kb = arg.strip() or None
        rule(f"DRAFT REPLY  {ticket['id']}" + (f"  (grounded: {kb})" if kb else "  (ungrounded)"))
        text, secs, status = bot.draft_reply(ticket, kb)
        print(text)
        print(f"  ({secs:.1f}s, status={status})  {bot.last_meter()}")
        last_draft, last_kb = text, kb
    elif cmd == "critique":
        if not last_draft:
            print("  nothing to critique -- run `draft` first.")
        else:
            rule("CRITIQUE (self-score)")
            data, secs = bot.critique(ticket, last_draft)
            print(f"  score={data['score']}/5  grounded={data['grounded']}")
            print(f"  critique: {data['critique']}")
            print(f"  ({secs:.1f}s)  {bot.last_meter()}")
    elif cmd == "improve":
        if not last_draft:
            print("  nothing to improve -- run `draft` first.")
        else:
            rule("IMPROVE (reflection loop)")
            data, _ = bot.critique(ticket, last_draft)
            print(f"  critique was: {data['critique']}")
            text, secs, _ = bot.improve(ticket, last_draft, data["critique"], last_kb)
            print("\n  improved draft:\n" + text)
            print(f"  ({secs:.1f}s)  {bot.last_meter()}")
            last_draft = text
    return last_draft, last_kb


# =============================================================================
# Non-interactive guided tour (for a quick look / verification)
# =============================================================================
def auto_tour(project: AIProjectClient) -> None:
    settings = GenSettings()
    bot = Copilot(project.get_openai_client(), REASONING_MODEL, settings)
    ticket = TICKETS[0]  # the outage
    rule("AUTO TOUR -- one ticket, end to end (interactive mode has the full controls)")
    print(f"Active ticket: [{ticket['id']}] {ticket['subject']}\n")

    print("0) Which dials does this model honor? (live probe)")
    bot.probe_dials()

    print("\n1) Triage (few-shot + structured JSON, minimal effort for determinism):")
    data, secs = bot.triage(ticket)
    print("   " + json.dumps(data) + f"\n   ({secs:.1f}s)  {bot.last_meter()}")

    print("\n2) Draft a grounded reply (persona + KB grounding):")
    text, secs, _ = bot.draft_reply(ticket, "status")
    print("   " + text.replace("\n", "\n   ") + f"\n   ({secs:.1f}s)  {bot.last_meter()}")

    print("\n3) Self-critique the draft (score + grounded + critique JSON):")
    crit, secs = bot.critique(ticket, text)
    print(f"   score={crit['score']}/5 grounded={crit['grounded']} :: {crit['critique']}"
          f"\n   ({secs:.1f}s)  {bot.last_meter()}")

    print("\n4) Improve using that critique (the reflection loop):")
    better, secs, _ = bot.improve(ticket, text, crit["critique"], "status")
    print("   " + better.replace("\n", "\n   ") + f"\n   ({secs:.1f}s)  {bot.last_meter()}")

    rule("AUTO TOUR DONE")
    print(f"Session estimate: in={bot.session_tokens['in']} out={bot.session_tokens['out']} "
          f"~${bot.session_cost:.5f}. Run without --auto to operate it yourself.")


# =============================================================================
def main() -> None:
    parser = argparse.ArgumentParser(description="AI-103 L7 -- interactive support-ops copilot.")
    parser.add_argument("--auto", action="store_true", help="Run a non-interactive guided tour.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan; call nothing.")
    args = parser.parse_args()

    if args.dry_run:
        rule("DRY RUN -- plan")
        print(f"  Project endpoint : {os.environ.get('FOUNDRY_PROJECT_ENDPOINT', '<unset>')}")
        print(f"  Reasoning model  : {REASONING_MODEL}")
        print(f"  Standard model   : {STANDARD_MODEL or '(none set -- temperature stays illustrative)'}")
        print( "  Scenario         : Contoso support-ops queue (triage/draft/critique/improve)")
        return

    project = connect()
    if args.auto:
        auto_tour(project)
    else:
        repl(project)


if __name__ == "__main__":
    main()
