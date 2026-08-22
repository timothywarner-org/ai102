"""m12_provenance_scan.py -- harm categories and content provenance for media you did not make.

    uv run python m12_provenance_scan.py --folder img/
    uv run python m12_provenance_scan.py --dry-run          # read files locally, call nothing
    uv run python m12_provenance_scan.py --only harm        # skip the provenance half
    uv run python m12_provenance_scan.py --only provenance --file love_the_style_but_the_text.png
    uv run python m12_provenance_scan.py --local-c2pa       # parse manifests offline, no cloud

Beat 1 of Lesson 12. Every other beat in this lesson MAKES media. This one asks the
inverse question: somebody hands you a PNG, what can Azure actually tell you about it?

Two APIs answer two different questions, and conflating them is the exam trap:

  * Analyze Image (GA, api-version=2024-09-01) returns four harm categories --
    Hate, Sexual, Violence, SelfHarm -- at severity 0/2/4/6. That is ALL it does.
    It has no idea whether an image was AI-generated and never claims to.

  * Content Provenance Detection (PREVIEW, api-version=2026-07-01-preview) reads
    C2PA Content Credentials and Microsoft's invisible watermark. It answers "did a
    MICROSOFT AI system make this?" -- a much narrower question than "is this
    AI-generated?", and the gap between those two is the entire point of the demo.
    Microsoft's own docs say a NoProvenanceDetected result does NOT mean the content
    is not AI-generated.

The img/ fixture set is chosen to make that gap visible in one run:

    love_the_style_but_the_text.png   Microsoft-signed -> ProvenanceDetected
    chatgpt-gpt4o-signed.png          OpenAI-signed    -> NoProvenanceDetected
    the other 19                      no manifest      -> NoProvenanceDetected

The middle row is the lesson. That file's own bytes carry softwareAgent "GPT-4o" and
digitalSourceType trainedAlgorithmicMedia. It is unambiguously AI-generated, it says so
in a valid C2PA manifest, and the API still answers "no provenance detected" because
the issuer is not Microsoft. The third row teaches the other half: those files have no
manifest at ALL, not even EXIF, because a browser download or an editor save-as strips
the metadata container wholesale. C2PA metadata is fragile. The invisible watermark
(alg com.microsoft.invismark.1, in the Microsoft fixture's soft-binding assertion) is
the part that survives a re-encode.

Everything below runs against ONE AIServices Foundry account. A separate
--kind ContentSafety resource is NOT required; verified 2026-08-11.

Idempotent. Creates no Azure resources. Uploaded blobs are deleted on the way out
unless --keep-blobs, so it is safe to re-run as many times as a take requires.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import pathlib
import struct
import sys
import time
import urllib.error
import urllib.request

# VS Code's integrated terminal injects proxy vars on some setups; strip them so the
# HTTP layer doesn't fail with "getaddrinfo failed" against public Azure endpoints.
# This happens BEFORE the azure imports, which read the environment at import time.
for _pv in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
            "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_pv, None)

from azure.identity import AzureCliCredential  # noqa: E402

try:
    from dotenv import load_dotenv
    # override=True on purpose, matching the other L12 scripts. A stale value
    # exported in an earlier shell otherwise wins over .env and you spend twenty
    # minutes debugging a 404 against a resource name that isn't in your file.
    load_dotenv(override=True)
except ImportError:  # dotenv is convenience only; real env vars still work.
    pass

# --- Configuration -----------------------------------------------------------
# Config comes from .env, never hardcoded. An earlier cut of this course carried a
# real endpoint as a fallback, and when that account was deleted the "fallback"
# quietly pointed every reader at a resource that no longer exists.
CONTENT_SAFETY_ENDPOINT = os.environ.get("CONTENT_SAFETY_ENDPOINT")
STORAGE_ACCOUNT = os.environ.get("STORAGE_ACCOUNT_NAME")
CONTAINER = os.environ.get("PROVENANCE_CONTAINER", "provenance-input")

# Pinned as module constants because these churn independently. Provenance is preview
# and WILL move; Analyze Image is GA and should not.
PROVENANCE_API_VERSION = "2026-07-01-preview"
ANALYZE_API_VERSION = "2024-09-01"

# Two different token audiences. The Content Safety data plane wants the Cognitive
# Services audience -- note this DIFFERS from the other L12 scripts, which use
# ai.azure.com for the /openai/v1 surface. Same account, two data planes.
SCOPE_COGNITIVE = "https://cognitiveservices.azure.com/.default"
SCOPE_STORAGE = "https://storage.azure.com/.default"

# Analyze Image caps at 4 MB; provenance allows 100 MB. Several fixtures sit between
# those numbers, which is why the harm half downscales and the provenance half does not.
ANALYZE_MAX_BYTES = 4 * 1024 * 1024
PROVENANCE_MAX_BYTES = 100 * 1024 * 1024

# Measured on an AIServices S0 tier 2026-08-11: provenance rejects a second request
# inside ~9 s with a 429 naming that exact retry window. A naive loop over 21 files
# earns an immediate 429, so the script paces itself rather than making the learner
# discover the limit mid-take.
PROVENANCE_MIN_INTERVAL = 10.0
POLL_INTERVAL = 5.0
POLL_TIMEOUT = 120.0

# Provenance accepts JPEG/PNG/GIF/WebP. Analyze Image additionally allows BMP/TIFF.
# Intersecting them keeps one enumeration honest for both halves.
IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".webp")

CATEGORIES = ("Hate", "SelfHarm", "Sexual", "Violence")
SEVERITY_LABEL = {0: "safe", 2: "low", 4: "medium", 6: "high"}

HERE = pathlib.Path(__file__).resolve().parent
RULE = "=" * 72


# --- Local inspection: free, no Azure calls ----------------------------------

def has_c2pa_manifest(path: pathlib.Path) -> bool:
    """True when the file carries an embedded C2PA manifest.

    Walking the container's real structure rather than grepping for strings, because
    the JUMBF payload is partly binary and a substring scan produces both false
    positives and false negatives.

    C2PA rides in a different box per format: PNG puts it in a 'caBX' ancillary
    chunk, JPEG in an APP11 segment. Anything we can't parse is reported as "no
    manifest", which is the safe direction to be wrong in -- the cloud call is still
    authoritative.
    """
    try:
        with path.open("rb") as fh:
            head = fh.read(8)
            if head == b"\x89PNG\r\n\x1a\n":
                # PNG is a flat chunk list: 4-byte length, 4-byte type, payload, CRC.
                while True:
                    header = fh.read(8)
                    if len(header) < 8:
                        return False
                    length = struct.unpack(">I", header[:4])[0]
                    ctype = header[4:8]
                    if ctype == b"caBX":
                        return True
                    if ctype == b"IEND":
                        return False
                    fh.seek(length + 4, os.SEEK_CUR)  # payload + CRC
            if head[:2] == b"\xff\xd8":
                fh.seek(2)
                while True:
                    marker = fh.read(2)
                    if len(marker) < 2 or marker[0] != 0xFF:
                        return False
                    if marker[1] == 0xDA:  # start of scan; metadata is behind us
                        return False
                    size_bytes = fh.read(2)
                    if len(size_bytes) < 2:
                        return False
                    seg_len = struct.unpack(">H", size_bytes)[0]
                    if marker[1] == 0xEB:  # APP11 carries the JUMBF box
                        return True
                    fh.seek(seg_len - 2, os.SEEK_CUR)
    except OSError:
        return False
    return False


# The three fixtures that carry the whole beat, in the order the story builds:
# Microsoft-signed (detected) -> third-party AI (manifest present, NOT detected) ->
# stripped (nothing at all). Matched as prefixes so a rename of the awkward ChatGPT
# filename does not silently drop it from the demo.
DEMO_FIXTURES = (
    "love_the_style_but_the_text",
    "chatgpt-gpt4o-signed",
    "raven-skull",
)


def select_demo_fixtures(folder: pathlib.Path) -> list[pathlib.Path]:
    """Pick the three contrast files, keeping DEMO_FIXTURES order rather than
    alphabetical -- the beat reads as an argument, and the order is the argument."""
    picked: list[pathlib.Path] = []
    for prefix in DEMO_FIXTURES:
        for candidate in sorted(folder.iterdir()):
            if (candidate.is_file()
                    and candidate.suffix.lower() in IMAGE_SUFFIXES
                    and candidate.name.startswith(prefix)):
                picked.append(candidate)
                break
        else:
            print(f"  [warn] demo fixture not found: {prefix}*")
    return picked


def enumerate_images(folder: pathlib.Path, only_file: str | None) -> list[pathlib.Path]:
    """Return the files to scan, validated locally before a single request is spent."""
    if only_file:
        candidate = pathlib.Path(only_file)
        if not candidate.is_absolute():
            candidate = folder / only_file
        if not candidate.exists():
            sys.exit(f"ERROR: file not found: {candidate}")
        return [candidate]
    if not folder.exists():
        sys.exit(
            f"ERROR: folder not found: {folder}\n"
            "  -> the fixture set ships in the repo at lessons/12-image-video-generation/img/"
        )
    found = sorted(p for p in folder.iterdir()
                   if p.is_file() and p.suffix.lower() in IMAGE_SUFFIXES)
    if not found:
        sys.exit(f"ERROR: no images in {folder} (looked for {', '.join(IMAGE_SUFFIXES)})")
    return found


def downscale_for_analyze(path: pathlib.Path) -> tuple[bytes, str]:
    """Return bytes under the Analyze Image 4 MB cap, plus a note describing any change.

    Pillow is already a lesson dependency (m12_image_edit.py builds its mask with it).
    Resizing a COPY in memory keeps the original file untouched, which matters because
    a re-encode would destroy exactly the C2PA manifest the provenance half is reading.
    """
    raw = path.read_bytes()
    if len(raw) <= ANALYZE_MAX_BYTES:
        return raw, ""
    try:
        import io
        from PIL import Image
    except ImportError:
        return b"", "Pillow not installed; cannot downscale"

    with Image.open(path) as img:
        img = img.convert("RGB")
        original = f"{img.width}x{img.height}"
        # Halve until it fits. Cheap, predictable, and it converges fast: every step
        # cuts pixel count to a quarter.
        for _ in range(6):
            img = img.resize((max(img.width // 2, 1), max(img.height // 2, 1)))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85)
            data = buf.getvalue()
            if len(data) <= ANALYZE_MAX_BYTES:
                return data, (f"downscaled {original} -> {img.width}x{img.height} "
                              f"({len(raw):,} -> {len(data):,} bytes) for the 4 MB cap")
    return b"", "could not get under the 4 MB cap"


# --- HTTP helpers -------------------------------------------------------------

def request_json(url: str, token: str, *, method: str = "GET",
                 body: dict | None = None) -> tuple[int, dict]:
    """Issue one JSON request and return (status, parsed_body).

    urllib rather than requests, so the lesson adds no HTTP dependency for what is
    three calls. Error bodies are parsed and RETURNED rather than raised, because the
    Content Safety error messages are unusually good and the triage ladder below
    reads them.
    """
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            return exc.code, json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return exc.code, {"error": {"message": raw.decode("utf-8", "replace")[:400]}}


def upload_blob(account: str, container: str, name: str,
                payload: bytes, token: str) -> tuple[bool, str]:
    """PUT one block blob. Returns (ok, url_or_error)."""
    url = f"https://{account}.blob.core.windows.net/{container}/{name}"
    req = urllib.request.Request(url, data=payload, method="PUT")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("x-ms-version", "2021-08-06")
    req.add_header("x-ms-blob-type", "BlockBlob")
    req.add_header("Content-Type", "application/octet-stream")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return (resp.status in (200, 201)), url
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode('utf-8', 'replace')[:200]}"
    except OSError as exc:
        return False, str(exc)


def delete_blob(account: str, container: str, name: str, token: str) -> None:
    """Best-effort cleanup. A leaked blob costs fractions of a cent and must never
    sink a take, so failures here are deliberately silent."""
    url = f"https://{account}.blob.core.windows.net/{container}/{name}"
    req = urllib.request.Request(url, method="DELETE")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("x-ms-version", "2021-08-06")
    try:
        urllib.request.urlopen(req, timeout=30).close()
    except (urllib.error.HTTPError, OSError):
        pass


# --- The two APIs -------------------------------------------------------------

def analyze_harm(endpoint: str, token: str, payload: bytes) -> tuple[bool, dict | str]:
    """Analyze Image: four harm categories at severity 0/2/4/6. GA."""
    url = f"{endpoint}/contentsafety/image:analyze?api-version={ANALYZE_API_VERSION}"
    body = {
        "image": {"content": base64.b64encode(payload).decode()},
        "categories": list(CATEGORIES),
        # The image model supports only the trimmed four-level scale. Text supports 0-7.
        "outputType": "FourSeverityLevels",
    }
    status, parsed = request_json(url, token, method="POST", body=body)
    if status == 200:
        return True, parsed
    return False, parsed.get("error", {}).get("message", f"HTTP {status}")


def detect_provenance(endpoint: str, token: str, blob_url: str) -> tuple[bool, dict | str]:
    """Content Provenance Detection: submit, then poll. Preview.

    Async in a specific way worth reading carefully: the operation id comes back in
    the RESPONSE BODY as `id`, not in an Operation-Location header the way most
    long-running Azure operations work.
    """
    url = f"{endpoint}/contentsafety/provenance:detect?api-version={PROVENANCE_API_VERSION}"
    status, parsed = request_json(url, token, method="POST",
                                  body={"content": {"uri": blob_url}})
    if status not in (200, 202) or not parsed.get("id"):
        return False, parsed.get("error", {}).get("message", f"HTTP {status}")

    op_url = (f"{endpoint}/contentsafety/provenance/operations/{parsed['id']}"
              f"?api-version={PROVENANCE_API_VERSION}")
    deadline = time.monotonic() + POLL_TIMEOUT
    while time.monotonic() < deadline:
        time.sleep(POLL_INTERVAL)
        status, poll = request_json(op_url, token)
        state = poll.get("status", "")
        if state == "Succeeded":
            return True, poll.get("result", {})
        if state == "Failed":
            return False, poll.get("error", {}).get("message", "operation failed")
        if state not in ("NotStarted", "Running"):
            return False, f"unexpected status: {state or f'HTTP {status}'}"
    return False, f"still running after {POLL_TIMEOUT:.0f}s"


def read_local_manifest(path: pathlib.Path) -> tuple[bool, str]:
    """Parse the manifest with the c2pa library instead of calling the cloud.

    This answers a genuinely different question than the cloud API. The Detect API
    reports only whether MICROSOFT made the content; the local parser reports what the
    manifest actually SAYS, whoever signed it. That is why the ChatGPT fixture comes
    back empty from the cloud and fully populated here.
    """
    try:
        from c2pa import Reader
    except ImportError:
        return False, "c2pa not installed (uv add c2pa-python)"
    try:
        # Context-manager form releases the native handle deterministically. The
        # constructor takes the path positionally; older Reader.from_file() is gone.
        with Reader(str(path)) as reader:
            store = json.loads(reader.json())
    except Exception as exc:  # noqa: BLE001 - the library raises its own error types
        # "No manifest" is the EXPECTED result for most of the fixture set, not an
        # error, so say it in English. The library's own _C2paManifestNotFound class
        # name on screen mid-demo reads like the script broke.
        detail = str(exc)
        if "ManifestNotFound" in type(exc).__name__ or "no JUMBF data" in detail:
            return False, "no C2PA manifest embedded in this file"
        return False, f"could not read manifest: {detail[:120]}"

    active = store.get("active_manifest")
    manifests = store.get("manifests", {})
    manifest = manifests.get(active, {}) if active else {}
    generator = manifest.get("claim_generator_info") or []
    gen_name = generator[0].get("name", "?") if generator else manifest.get("claim_generator", "?")

    # Walk EVERY manifest in the store, not just the active one. A C2PA store is a
    # chain: the active manifest describes the most recent edit, and the ORIGIN --
    # the c2pa.created action naming the model that generated the pixels -- usually
    # sits in an earlier manifest referenced as an ingredient. Reading only the
    # active manifest on the ChatGPT fixture reports "c2pa.opened" and misses
    # GPT-4o entirely, which would undersell the very point of the beat.
    agents: list[str] = []
    sources: list[str] = []
    actions: list[str] = []
    watermark = False
    for entry in manifests.values():
        for assertion in entry.get("assertions", []):
            label = assertion.get("label", "")
            data = assertion.get("data", {})
            if not isinstance(data, dict):
                continue
            if label.startswith("c2pa.actions"):
                for action in data.get("actions", []):
                    name = action.get("action", "")
                    if name and name not in actions:
                        actions.append(name)
                    agent = action.get("softwareAgent")
                    if isinstance(agent, dict):
                        agent = agent.get("name")
                    if agent and agent not in agents:
                        agents.append(agent)
                    src = action.get("digitalSourceType", "")
                    if src and src.rsplit("/", 1)[-1] not in sources:
                        sources.append(src.rsplit("/", 1)[-1])
            if "soft-binding" in label:
                watermark = True

    bits = [f"generator={gen_name}"]
    if len(manifests) > 1:
        bits.append(f"chain of {len(manifests)} manifests")
    if agents:
        bits.append("agent=" + ", ".join(agents))
    if sources:
        bits.append("digitalSourceType=" + ", ".join(sources))
    if actions:
        bits.append("actions=" + ", ".join(actions))
    signer = (manifest.get("signature_info") or {}).get("issuer")
    if signer:
        bits.append(f"issuer={signer}")
    if watermark:
        bits.append("soft-binding present (invisible watermark)")
    return True, "; ".join(bits)


# --- Presentation -------------------------------------------------------------

def print_header(args: argparse.Namespace, files: list[pathlib.Path]) -> None:
    print(RULE)
    print("AI-103 L12 Beat 1 -- content safety + provenance")
    print(RULE)
    print(f"  endpoint  : {CONTENT_SAFETY_ENDPOINT or '(not set)'}")
    print(f"  storage   : {STORAGE_ACCOUNT or '(not set)'}/{CONTAINER}")
    print(f"  harm api  : {ANALYZE_API_VERSION} (GA)")
    print(f"  prov api  : {PROVENANCE_API_VERSION} (preview)")
    print(f"  folder    : {args.folder}")
    print(f"  files     : {len(files)}")
    print(f"  mode      : {args.only or 'harm + provenance'}"
          f"{' [demo fixtures]' if args.demo else ''}"
          f"{' [local c2pa]' if args.local_c2pa else ''}"
          f"{' [dry-run]' if args.dry_run else ''}")
    print()


def print_summary(rows: list[dict]) -> None:
    print()
    print(RULE)
    print("SUMMARY")
    print(RULE)
    name_w = min(max((len(r["name"]) for r in rows), default=20), 44)
    print(f"  {'file'.ljust(name_w)}  {'manifest':9s}  {'harm':16s}  provenance")
    print(f"  {'-' * name_w}  {'-' * 9}  {'-' * 16}  {'-' * 20}")
    for r in rows:
        name = r["name"] if len(r["name"]) <= name_w else r["name"][:name_w - 3] + "..."
        print(f"  {name.ljust(name_w)}  {r['manifest']:9s}  {r['harm']:16s}  {r['provenance']}")
    detected = sum(1 for r in rows if r["provenance"].startswith("ProvenanceDetected"))
    local = sum(1 for r in rows if r["manifest"] == "yes")
    print()
    print(f"  {len(rows)} scanned | {local} carry a C2PA manifest locally | "
          f"{detected} returned ProvenanceDetected")
    if local > detected:
        print()
        print("  [note] A file can carry a valid C2PA manifest and still come back")
        print("         NoProvenanceDetected: the API covers Microsoft-generated")
        print("         content only. Absence of provenance proves nothing.")


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Scan images for harm categories and content provenance.")
    ap.add_argument("--folder", default="img",
                    help="Folder of images to scan. Default: img")
    ap.add_argument("--file", default=None,
                    help="Scan a single file instead of the whole folder.")
    ap.add_argument("--only", choices=("harm", "provenance"), default=None,
                    help="Run just one half of the demo.")
    ap.add_argument("--demo", action="store_true",
                    help="Scan only the three fixtures that show the contrast (~40 s). "
                         "Use this on camera; the full folder takes about 7 minutes.")
    ap.add_argument("--local-c2pa", action="store_true",
                    help="Parse manifests locally with the c2pa library; skip the cloud API.")
    ap.add_argument("--keep-blobs", action="store_true",
                    help="Leave uploaded blobs in place instead of deleting them.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Enumerate and inspect locally; make no Azure calls.")
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    folder = pathlib.Path(args.folder)
    if not folder.is_absolute():
        folder = HERE / args.folder
    if args.demo and not args.file:
        files = select_demo_fixtures(folder)
        if not files:
            sys.exit(f"ERROR: none of the demo fixtures are in {folder}")
    else:
        files = enumerate_images(folder, args.file)

    print_header(args, files)

    want_harm = args.only in (None, "harm")
    want_prov = args.only in (None, "provenance")

    # --- Dry run: everything above is local, so stop before spending a request.
    if args.dry_run:
        for path in files:
            size = path.stat().st_size
            flags = []
            if has_c2pa_manifest(path):
                flags.append("C2PA manifest")
            if size > ANALYZE_MAX_BYTES:
                flags.append(f"over 4 MB, will downscale for harm scan")
            if size > PROVENANCE_MAX_BYTES:
                flags.append("over 100 MB, too large for provenance")
            note = ("  <- " + "; ".join(flags)) if flags else ""
            print(f"  [dry-run] {path.name:52s} {size:>10,} B{note}")
        print()
        print(f"  [dry-run] {len(files)} file(s) would be scanned. No Azure calls made.")
        return 0

    # --- Config checks happen AFTER the dry run, so --dry-run works on a bare clone.
    if not CONTENT_SAFETY_ENDPOINT and not args.local_c2pa:
        sys.exit(
            "ERROR: CONTENT_SAFETY_ENDPOINT is not set.\n"
            "  -> https://<account>.cognitiveservices.azure.com\n"
            "  See .env.example, then: cp .env.example .env\n"
            "  Or run with --local-c2pa to parse manifests offline."
        )
    if want_prov and not args.local_c2pa and not STORAGE_ACCOUNT:
        sys.exit(
            "ERROR: STORAGE_ACCOUNT_NAME is not set.\n"
            "  -> The provenance API reads a blob URI; it does not accept raw bytes.\n"
            "  See .env.example, or run with --local-c2pa."
        )

    cred = AzureCliCredential()
    cs_token = storage_token = ""
    try:
        if not args.local_c2pa:
            cs_token = cred.get_token(SCOPE_COGNITIVE).token
            if want_prov:
                storage_token = cred.get_token(SCOPE_STORAGE).token
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: could not acquire a token: {type(exc).__name__}: {str(exc)[:200]}")
        print("  -> run: az login")
        return 1

    rows: list[dict] = []
    last_prov_call = 0.0

    for index, path in enumerate(files, start=1):
        size = path.stat().st_size
        local_manifest = has_c2pa_manifest(path)
        row = {
            "name": path.name,
            "manifest": "yes" if local_manifest else "no",
            "harm": "-",
            "provenance": "-",
        }
        print(f"[{index}/{len(files)}] {path.name}  ({size:,} bytes)")
        print(f"  [local] C2PA manifest: {'present' if local_manifest else 'absent'}")

        # --- Harm categories -------------------------------------------------
        if want_harm and not args.local_c2pa:
            payload, note = downscale_for_analyze(path)
            if note:
                print(f"  [note]  {note}")
            if not payload:
                row["harm"] = "skipped"
                print("  [warn]  skipped harm scan (could not fit the 4 MB cap)")
            else:
                ok, result = analyze_harm(CONTENT_SAFETY_ENDPOINT, cs_token, payload)
                if ok:
                    analysis = {c["category"]: c["severity"]
                                for c in result.get("categoriesAnalysis", [])}
                    worst = max(analysis.values()) if analysis else 0
                    row["harm"] = f"max {worst} ({SEVERITY_LABEL.get(worst, '?')})"
                    detail = "  ".join(f"{c}={analysis.get(c, 0)}" for c in CATEGORIES)
                    print(f"  [harm]  {detail}")
                else:
                    row["harm"] = "error"
                    print(f"  [warn]  harm scan failed: {result}")

        # --- Provenance ------------------------------------------------------
        if want_prov:
            if args.local_c2pa:
                ok, detail = read_local_manifest(path)
                row["provenance"] = "local: manifest read" if ok else "local: none"
                # One fact per line. The joined string runs well past a terminal
                # width on the Microsoft fixture, and this beat is read off a screen.
                for piece in (detail.split("; ") if ok else [detail]):
                    print(f"  [c2pa]  {piece}")
            elif size > PROVENANCE_MAX_BYTES:
                row["provenance"] = "too large"
                print("  [warn]  over the 100 MB provenance limit; skipped")
            else:
                # Pace against the ~9 s server-side limit measured on S0.
                wait = PROVENANCE_MIN_INTERVAL - (time.monotonic() - last_prov_call)
                if last_prov_call and wait > 0:
                    print(f"  [pace]  waiting {wait:.0f}s (rate limit)")
                    time.sleep(wait)

                blob_name = f"scan-{index:02d}{path.suffix.lower()}"
                ok, blob_url = upload_blob(STORAGE_ACCOUNT, CONTAINER, blob_name,
                                           path.read_bytes(), storage_token)
                if not ok:
                    row["provenance"] = "upload failed"
                    print(f"  [warn]  upload failed: {blob_url}")
                    if "403" in str(blob_url):
                        print("  [note]  403 usually means RBAC has not propagated yet.")
                        print("          You need Storage Blob Data Contributor; wait 5 min.")
                else:
                    last_prov_call = time.monotonic()
                    ok, result = detect_provenance(CONTENT_SAFETY_ENDPOINT, cs_token, blob_url)
                    if ok:
                        outcome = result.get("outcome", "?")
                        row["provenance"] = outcome
                        print(f"  [prov]  {outcome}")
                        # NoProvenanceDetected omits `results` entirely, and the
                        # elements that do come back may omit modelName/timestamp.
                        # Every field is optional; never index blindly.
                        for entry in result.get("results", []):
                            parts = [f"type={entry.get('type', '?')}"]
                            for key in ("provider", "modelName", "timestamp"):
                                if entry.get(key):
                                    parts.append(f"{key}={entry[key]}")
                            print(f"          {'  '.join(parts)}")
                    else:
                        row["provenance"] = "error"
                        print(f"  [warn]  provenance failed: {result}")
                        if "429" in str(result):
                            print("  [note]  rate limited; raise PROVENANCE_MIN_INTERVAL.")
                        elif "not a valid Azure Blob" in str(result):
                            print("  [note]  the API accepts only real Azure Storage URLs.")
                        elif "Access denied" in str(result):
                            print("  [note]  the Content Safety managed identity needs")
                            print("          Storage Blob Data Reader on the storage account.")
                    if not args.keep_blobs:
                        delete_blob(STORAGE_ACCOUNT, CONTAINER, blob_name, storage_token)

        rows.append(row)
        print()

    print_summary(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
