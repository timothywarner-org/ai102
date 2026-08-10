"""provision_knowledge.py -- seed the file_search knowledge store for L10/L11.

Converts the surviving m365_docs.json corpus into one Markdown file per document,
uploads them to the Foundry project, and builds a vector store that the
file_search tool attaches to. Idempotent enough to re-run: it creates a fresh
vector store each time and prints the id, so you can point agents at the new one.
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time

from azure.identity import AzureCliCredential
from openai import OpenAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is convenience only; real env vars still work.
    pass

# Config comes from .env, never hardcoded. An earlier cut of this script carried a
# real endpoint as a fallback, and when that account was deleted the "fallback"
# quietly pointed every reader at a resource that no longer exists. Failing loudly
# with a pointer to .env.example is far kinder than a confusing auth error.
PROJECT_ENDPOINT = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
if not PROJECT_ENDPOINT:
    sys.exit(
        "ERROR: FOUNDRY_PROJECT_ENDPOINT is not set.\n"
        "  -> https://<account>.services.ai.azure.com/api/projects/<project>\n"
        "  See .env.example, then: cp .env.example .env"
    )
# Paths are relative to THIS file, so the script runs from any working directory
# and on any machine, rather than depending on one absolute C:\github checkout.
_LESSONS = pathlib.Path(__file__).resolve().parent.parent
DOCS_JSON = _LESSONS / "08-build-generative-apps-foundry" / "m365_docs.json"
OUT_DIR = pathlib.Path(__file__).resolve().parent / "knowledge"

for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)

cred = AzureCliCredential()

# NOTE: use the PLAIN OpenAI client, not AzureOpenAI. The /openai/v1 path rejects
# an api-version query parameter, and AzureOpenAI always appends one. The Foundry
# project endpoint wants a plain bearer token with the ai.azure.com audience.
client = OpenAI(
    base_url=f"{PROJECT_ENDPOINT}/openai/v1",
    api_key=cred.get_token("https://ai.azure.com/.default").token,
    max_retries=4,
    timeout=120.0,
)

# --- 1. Explode the JSON corpus into one Markdown file per doc -----------------
data = json.loads(DOCS_JSON.read_text(encoding="utf-8"))
docs = data["docs"]
OUT_DIR.mkdir(parents=True, exist_ok=True)

paths = []
for d in docs:
    p = OUT_DIR / f"{d['id']}-{d['title'][:50].replace(' ', '-').replace('/', '-')}.md"
    p.write_text(
        f"# {d['title']}\n\n"
        f"**Category:** {d.get('category','')}  \n"
        f"**Source:** {d.get('source','')}\n\n"
        f"{d['content']}\n",
        encoding="utf-8",
    )
    paths.append(p)

print(f"[knowledge] wrote {len(paths)} markdown files to {OUT_DIR}")

# --- 2. Upload each file ------------------------------------------------------
file_ids = []
for p in paths:
    with p.open("rb") as fh:
        f = client.files.create(file=fh, purpose="assistants")
    file_ids.append(f.id)
    print(f"  uploaded {p.name} -> {f.id}")

# --- 3. Vector store ----------------------------------------------------------
vs = client.vector_stores.create(name="m365-knowledge", file_ids=file_ids)
print(f"[knowledge] vector store {vs.id}")

for _ in range(30):
    cur = client.vector_stores.retrieve(vs.id)
    counts = getattr(cur, "file_counts", None)
    print(f"  status={cur.status} counts={counts}")
    if cur.status == "completed":
        break
    time.sleep(3)

print(f"\nVECTOR_STORE_ID={vs.id}")
