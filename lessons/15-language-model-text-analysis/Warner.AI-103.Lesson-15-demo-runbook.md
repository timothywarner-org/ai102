# L15 CHEATSHEET -- Catalog vs Schema, Characters vs Tokens

`lessons/15-language-model-text-analysis/` | **3 beats, 6 commands** | ~14 min

**Verified green 2026-08-12** against `aif-ai103-l11-gcn5uizgywfac`. Every `CHECK` below is a real observed string. Beat 1 is portal-only and not script-verified.

**Legend:** `SHOW` on screen | `SAY` riff it | `CHECK` proof | `FIX` if it blows up

---

## PRE-FLIGHT (off camera)

```powershell
pwsh -File validate.ps1
```

Rebuilds `.venv` if needed, runs all 12 steps, primes the cache. **Never activate a venv** -- `uv run` handles it.

- [ ] Ends with `Done. Cache is primed`
- [ ] `az account show` -> `tim@techtrainertim.com`
- [ ] Windows: Edge on Foundry portal | VS Code on lesson folder

Warm runs are ~2s, cold ~15-19s. Take one should be warm.

---

## 1 · Beat 1 -- The catalog, in the portal (4 min)

**No code.** Foundry portal -> **Discover** -> search `Azure` -> **Azure-Language-Text-PII redaction** -> **Open in Playground**

> Slow Discover? **Build** -> **Models** -> **AI services** tab.

`DO` paste `assets/ticket-support.txt`, select **Detect**

`CHECK` entities highlighted with **Type**, **Confidence**, **Offset**, **Length**

### Talk track -- the catalog

- **Check the catalog before you write a prompt.** Prebuilt gives you what a prompt can't: same answer twice, confidence score, a version you can name.
- **Configure pane, three settings, whole lesson.** *Model version* is the compliance control -- leave it on latest and a service refresh changes a classification you already reported. *Value to exclude* is for legitimate identifiers that keep tripping the detector. *Policy type* is mask/entity-mask/none.
- **Finding an entity and acting on it are two decisions.** That dropdown is where it gets concrete.
- **The setup for Beat 2:** now find me the customer's *tone*. Not here. Sentiment gives positive/negative/neutral/mixed. Nothing scores urgency or frustration. That's the edge of the catalog, not a portal gap.

`FIX` Playground won't load -> **Cognitive Services User** on the account plus a project. Owner is control plane, doesn't count.

---

## 2 · Beat 2 -- The schema starts where the catalog stops (5 min)

`SHOW` `m15_extract.py` **L96-137** (`CONTRACT_SCHEMA`)

```powershell
uv run python m15_extract.py
```

`CHECK` `EntityRecognition modelVersion=2026-05-01` then `KeyPhraseExtraction modelVersion=2022-10-01`
`CHECK` contract -> `retention_years 7`, `breach_notice_hours 72`, `confidence high`
`CHECK` **ticket -> all four contract fields `null`**

### Talk track -- the schema

- **Retention years. Breach notice hours. Liability cap.** No prebuilt taxonomy has these categories. They're specific to this contract.
- **Two modelVersions off one account**, independently versioned. Read them out loud -- that's your audit record.
- **The best moment on screen is the support ticket.** Same schema, wrong document, everything `null`. It did not invent a retention period from an angry email. That's the nullable types plus the prompt doing their job.

`SHOW` **L128** `"strict": True` and **L131** `additionalProperties: False`

```powershell
uv run python m15_extract.py --loose
```

`CHECK` header reads `strict=False`
`CHECK` drift: strict gave `['Dana Whitfield (Customer)']`, loose gives `['Dana Whitfield <dana.whitfield@northwindlogistics.example>']`

### Talk track -- strict vs loose

- **These two settings turn a model into a component.** Drop either and you're parsing prose with a regex.
- **A schema constrains shape, never truth.** Required fields are an invitation to invent one, which is why unknowns are nullable.
- **The drift is unglamorous on purpose.** Loose didn't crash, it quietly stopped following the field description. Worse than a crash -- nothing downstream notices.

`FIX` `403` on Path A is the data-plane role. `--skip-prebuilt` gets you to Path B.

---

## 3 · Beat 3 -- Two meters, two units (5 min)

`SHOW` `assets/release-note.txt` -- product name is **Dispatch**

```powershell
uv run python m15_translate.py --no-dictionary
```

`CHECK` `DETECT language=en score=1.0 cost: none`
`CHECK` `Source is 90 characters`
`CHECK` **`preserved: NO` on both** -> `Le dispatch...` (fr), `Die Leitstelle...` (de)
`CHECK` MODEL section reads `preserved: YES` on both
`CHECK` `180 characters` vs `57 prompt + ~351 completion tokens`

```powershell
uv run python m15_translate.py
```

`CHECK` **`preserved: YES` on both** -> `Dispatch montre...`, `Dispatch zeigt...`
`CHECK` still `180 characters` billed

`SHOW` `protect()` **L104-116**

### Talk track -- two meters

- **Why the boring name:** *Dispatch* collides with an ordinary noun. Invented CamelCase brands read as proper nouns and sail through untouched, making the dictionary look pointless. I probed 40 of them live and not one was localized. **The names that break are the ones that mean something.**
- **Detect is free.** You can check whether translation is needed at all and pay nothing.
- **Dictionary is free too.** Same 180 characters both runs. It changed the answer, not the bill.
- **Three documented constraints:** case-sensitive, needs explicit `from` (autodetect is out), compound nouns only.
- **Don't claim it scales.** Microsoft points at Custom Translator past a small term list.
- **The model preserved the name because I asked in plain English, and paid tokens** to do what markup did for free. That's the trade in one line.
- **Characters vs tokens don't convert.** Nobody eyeballs which is cheaper. Measure on your own content.

---

## 4 · Close (30 s)

1. **Check the catalog first.** Repeatable and versioned in a way a prompt isn't.
2. **The schema starts where the catalog stops.** Strict + `additionalProperties: false` makes a model a component.
3. **Characters and tokens don't convert.** Measure both before you pick.

"I hope you found this lesson helpful. I'll see you next time."

---

## PANIC TABLE

| Symptom | Real cause | Fix |
| --- | --- | --- |
| `403` on `:analyze-text` | data-plane role | **Cognitive Services User** on the account |
| `401` on Translator | missing headers | check `TRANSLATOR_REGION` + `TRANSLATOR_RESOURCE_ID` |
| Playground tile missing | no project selected | pick one upper-left |
| Path B empty fields | reasoning token budget | `gpt-5-mini` needs `max_completion_tokens` headroom |
| Name localized *with* markup | `from` omitted | dictionary requires explicit source language |
| Name preserved *without* dictionary | fixture drifted to CamelCase | must be **Dispatch**; re-run `make_assets.py` |
| Every `uv` command fails, "not a valid Python environment" | `.venv` built on another OS | `pwsh -File validate.ps1`; never hand-activate |
| Wording differs between takes | models aren't deterministic | that's the cache; don't `--clean` mid-take |
| Output differs from this card | service drift since 2026-08-12 | trust the screen |

## DO NOT

- Record before `validate.ps1`. It proves the env and primes the cache.
- Pass `--clean` mid-take. Pre-flight only.
- Rename the product. **Dispatch** is chosen because it breaks.
- Activate or deactivate a venv on camera.
- Claim the dynamic dictionary scales.
- Put real PII in `assets/`. Fixtures use `.example` domains on purpose.

## FILE MAP

| File | Beat | Owns |
| --- | --- | --- |
| *(portal)* | 1 | PII playground: version, exclusions, mask policy |
| `m15_extract.py` | 2 | `:analyze-text` vs `json_schema` + strict |
| `m15_translate.py` | 3 | detect / translate / dictionary, chars vs tokens |
| `m15_cache.py` | all | content-addressed replay |
| `assets/make_assets.py` | pre-flight | regenerates fixtures deterministically |
| `offline_harness.py` | pre-flight | 13 request-shape assertions, no network |

## OBJECTIVE COVERAGE

| LO | Where |
| --- | --- |
| 1 extract entities, topics, summaries, structured JSON | Beat 2, both paths |
| 2 sentiment, tone, safety, sensitive content | Beat 1, plus the tone gap opening Beat 2 |
| 3 translate via Translator or LLM flows | Beat 3 |
| 4 customize outputs for domain tasks | Beat 2 schema, Beat 3 dictionary, Beat 1 version pin |
