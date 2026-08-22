"""
Offline harness: exercise every code path in the L15 scripts with canned,
Azure-shaped responses. Proves the request shapes, the cache, the rendering,
and the schema logic BEFORE anyone burns a take on a live call.

This does NOT prove Azure accepts the requests. It proves the code is correct
given responses shaped the way Microsoft documents them.
"""
import io, json, os, sys, types, urllib.request, contextlib, pathlib

os.environ.update({
    "FOUNDRY_ACCOUNT_ENDPOINT": "https://fake.openai.azure.com",
    "CHAT_MODEL": "gpt-5-mini",
    "LANGUAGE_ENDPOINT": "https://fake.cognitiveservices.azure.com",
    "TRANSLATOR_REGION": "eastus2",
    "TRANSLATOR_RESOURCE_ID": "/subscriptions/x/resourceGroups/y/providers/Microsoft.CognitiveServices/accounts/z",
})
# Import the scripts from THIS folder. A hardcoded absolute path (the old
# "/tmp/l15") silently imports nothing on Windows and everything still appears
# to pass, which is worse than failing.
sys.path.insert(0, str(pathlib.Path(__file__).parent))

CAPTURED = []          # every request the scripts attempt

# ---- fake urllib -----------------------------------------------------------
class FakeResp:
    def __init__(self, payload): self._b = json.dumps(payload).encode()
    def read(self): return self._b
    def __enter__(self): return self
    def __exit__(self, *a): return False

def fake_urlopen(req, timeout=None):
    url = req.full_url
    body = json.loads(req.data.decode()) if req.data else None
    CAPTURED.append({"url": url, "headers": dict(req.headers), "body": body})
    if "/language/:analyze-text" in url:
        kind = body["kind"]
        doc = {"id": "1"}
        if kind == "EntityRecognition":
            doc["entities"] = [
                {"text": "Dana Whitfield", "category": "Person", "confidenceScore": 0.99},
                {"text": "Northwind Logistics", "category": "Organization", "confidenceScore": 0.87},
            ]
        else:
            doc["keyPhrases"] = ["shipment tracking portal", "warehouse crew"]
        return FakeResp({"kind": kind, "results": {
            "documents": [doc], "errors": [], "modelVersion": "2024-11-01"}})
    if "/detect" in url:
        return FakeResp([{"language": "en", "score": 1.0}])
    if "/translate" in url:
        has_dict = "mstrans:dictionary" in json.dumps(body)
        outs = []
        for lang in req.full_url.split("to=")[1].split("&")[0].split("%2C"):
            # Mirrors the real service: without the dictionary the brand collides
            # with the ordinary noun and gets localized; with it, the brand survives.
            term = "Dispatch" if has_dict else {"fr": "Le dispatch"}.get(lang, "Die Leitstelle")
            outs.append({"to": lang, "text": f"[{lang}] {term} montre où se trouve chaque palette."})
        return FakeResp([{"translations": outs}])
    raise AssertionError(f"unexpected URL: {url}")

urllib.request.urlopen = fake_urlopen

# ---- fake OpenAI + credential ---------------------------------------------
import azure.identity
class FakeCred:
    def get_token(self, *a, **k): return types.SimpleNamespace(token="FAKE")
azure.identity.AzureCliCredential = lambda *a, **k: FakeCred()
azure.identity.get_bearer_token_provider = lambda *a, **k: (lambda: "FAKE")

import openai
class FakeCompletions:
    def create(self, model=None, response_format=None, messages=None, **kw):
        CAPTURED.append({"url": "chat.completions", "response_format": response_format,
                         "prompt": messages[0]["content"][:80]})
        if response_format:                      # extraction path
            content = json.dumps({
                "parties": ["Contoso Freight Services (Provider)",
                            "Northwind Logistics (Customer)"],
                "retention_years": 7, "breach_notice_hours": 72,
                "liability_cap": "fees paid in the preceding twelve months",
                "audit_rights": "once per contract year, thirty days notice",
                "confidence": "high"})
        else:                                     # translation path
            # A model told to preserve the term does so; that is the contrast
            # against plain Translator, which localizes it.
            content = "Dispatch montre à votre équipe où se trouve chaque palette."
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))],
            usage=types.SimpleNamespace(prompt_tokens=118, completion_tokens=47))
class FakeOpenAI:
    def __init__(self, **kw): self.chat = types.SimpleNamespace(completions=FakeCompletions())
openai.OpenAI = FakeOpenAI

# ---- run both scripts ------------------------------------------------------
import m15_cache
m15_cache.clean()

def run(mod_name, argv):
    sys.argv = [mod_name] + argv
    for m in list(sys.modules):
        if m.startswith("m15_") and m != "m15_cache": del sys.modules[m]
    mod = __import__(mod_name)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        try: mod.main()
        except SystemExit: pass
    return buf.getvalue()

print("#" * 74); print("# m15_extract.py  (cold)"); print("#" * 74)
print(run("m15_extract", []))
print("#" * 74); print("# m15_extract.py  (warm -- must be byte-identical minus [cached] tags)")
print("#" * 74)
warm = run("m15_extract", [])
print(warm)
print("#" * 74); print("# m15_translate.py  --no-dictionary  (cold)"); print("#" * 74)
print(run("m15_translate", ["--no-dictionary"]))
print("#" * 74); print("# m15_translate.py  (with dictionary)"); print("#" * 74)
print(run("m15_translate", []))

# ---- assertions on what was actually sent ---------------------------------
print("#" * 74); print("# REQUEST-SHAPE ASSERTIONS"); print("#" * 74)
lang = [c for c in CAPTURED if "analyze-text" in str(c.get("url"))]
tr   = [c for c in CAPTURED if "/translate" in str(c.get("url"))]
det  = [c for c in CAPTURED if "/detect" in str(c.get("url"))]
chat = [c for c in CAPTURED if c.get("url") == "chat.completions"]

def check(label, cond, detail=""):
    print(f"  {'PASS' if cond else 'FAIL'}  {label}  {detail}")
    return cond

ok = True
ok &= check("Language uses api-version=2024-11-01", all("api-version=2024-11-01" in c["url"] for c in lang))
ok &= check("Language sends modelVersion parameter",
            all(c["body"]["parameters"].get("modelVersion") for c in lang),
            f"({lang[0]['body']['parameters']['modelVersion']})" if lang else "")
ok &= check("Language sends Bearer, not a key", all(h.startswith("Bearer ") for h in
            [c["headers"].get("Authorization","") for c in lang]))
ok &= check("Translator sends all three Entra headers",
            all(all(k in c["headers"] for k in
                ("Authorization","Ocp-apim-subscription-region","Ocp-apim-resourceid"))
                for c in tr))
ok &= check("Detect is called before translate", bool(det) and CAPTURED.index(det[0]) < CAPTURED.index(tr[0]))
ok &= check("Dictionary run wraps the term in mstrans markup",
            any("mstrans:dictionary" in json.dumps(c["body"]) for c in tr))
ok &= check("Dictionary run sends explicit from=", any("from=" in c["url"] for c in tr))
ok &= check("--no-dictionary run omits from=", any("from=" not in c["url"] for c in tr))
ok &= check("Schema sent with strict=True",
            any(c.get("response_format",{}).get("json_schema",{}).get("strict") is True for c in chat))
ok &= check("Schema sets additionalProperties=False",
            any(c.get("response_format",{}).get("json_schema",{}).get("schema",{})
                .get("additionalProperties") is False for c in chat))
ok &= check("Warm run reports cached", "[cached]" in warm)

# The teaching contrast itself, asserted. Beat 3 is worthless if both runs report
# the term preserved -- which is exactly what happened when the fixture used an
# invented CamelCase brand that Translator never localized in the first place.
nodict_out = run("m15_translate", ["--no-dictionary", "--clean"])
dict_out = run("m15_translate", ["--clean"])
ok &= check("--no-dictionary run LOSES the term (contrast exists)",
            "preserved: NO" in nodict_out)
ok &= check("dictionary run PRESERVES the term",
            "preserved: NO" not in dict_out.split("MODEL")[0])
print(f"\n  {'ALL ASSERTIONS PASS' if ok else 'FAILURES ABOVE'}   ({len(CAPTURED)} requests captured)")
