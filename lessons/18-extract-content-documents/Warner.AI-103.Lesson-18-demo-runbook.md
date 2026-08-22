# L18 RECORDING CARD -- Extract Content from Documents

**3 beats, 4 commands, 14-16 min** | `lessons/18-extract-content-documents/`

> **Verified live 2026-08-14** against `YOUR-FOUNDRY-RESOURCE` (eastus2),
> Content Understanding API **2025-11-01** (GA, not preview). Every `CHECK`
> below is a real string from a real run. All three beats green, twice.

## THE ONE THING THAT WILL RUIN THE TAKE

**Don't quote the confidence decimals out loud.** They move between runs.

| Field | Run A | Run B |
| --- | --- | --- |
| `addendum_id` | 0.784 | 0.784 |
| `product_category` | 0.779 | **0.856** |
| `waiver_summary` | 0.779 | **0.856** |
| `waiver_summary` spans | 12 | **7** |

Say **"high eighties"** or **"call it point seven, point eight"** and move on.
What's stable, and what the beat actually rests on, is the **relationship**:
`generate` always grounds to MORE spans than `extract`. That never inverted
across any run. Read the ORDER, not the decimals -- same rule as Lesson 17's
BM25 scores.

## TIMING REALITY

Scripts are fast, but this API is genuinely asynchronous. **Beat 1 makes five
analyze calls**, each a submit-then-poll, so it runs about **50 seconds** with
nothing on screen but status lines. That's not dead air, that's your best
teaching window. Talk over it.

| Beat | Script time | Talk time | Total |
| --- | --- | --- | --- |
| 1 Prebuilt ladder | ~50s | ~5 min | **5-6 min** |
| 2 Grounding | ~12s | ~4 min | **4 min** |
| 3 Custom analyzer | ~45s | ~5 min | **5-6 min** |

**Corpus: two files, and the contrast between them IS the lesson.**

| File | What it is | Why it's here |
| --- | --- | --- |
| `wg-addendum-scan.png` | A scan. **Pixels only, no text layer.** | The Premier Household wire-fee waiver exists nowhere else. |
| `wg-fee-schedule.pdf` | **Born-digital.** Real text layer, real table. | The control case that proves digitalParse isn't broken. |

Learners who did Lesson 17 will recognize that scan. That's deliberate -- L17
proved those pixels could be retrieved, and L18 shows you what actually did the
extracting.

## PRE-FLIGHT

- [ ] `az login` -> `you@contoso.com`
- [ ] **Token has 30+ min left.** Check before you roll:
      `az account get-access-token --resource https://cognitiveservices.azure.com --query expiresOn -o tsv`
- [ ] `uv run python m18_extract_demo.py --dry-run` -> both fixtures **[OK]**
- [ ] Edge tab 1: **Foundry portal** on the account Overview. Tab 2: the deck.
- [ ] VS Code on `m18_extract_demo.py` at `ANALYZER_BODY`
- [ ] Terminal font large, scrollback deep
- [ ] Remember: **don't read the decimals.**

---

## 1 · The prebuilt ladder (5-6 min)

`SHOW` `assets/corpus/wg-addendum-scan.png` full screen for two beats, then the terminal

[SAY] Welcome back. In the last lesson we built a retrieval pipeline, and there
was one file in that corpus I promised we'd come back to. This one. It's a scan
of a Woodgrove Bank product addendum, and I want you to notice what it isn't.
There's no text in this file. Not one character. This is a picture of a page,
and every letter you can read with your own eyes is just an arrangement of
pixels. So the question for this whole lesson is, how do we get from that to
something an agent can reason about?

[DO] `uv run python m18_extract_demo.py --only ladder`

[SAY] Now I'm running the exact same scanned page through three different
prebuilt analyzers, and I want you to watch the character counts. Because the
deck says prebuilt analyzers ladder from OCR up to tuned schemas, and I'd rather
show you that ladder than assert it.

`CHECK` **`prebuilt-digitalParse      0 markdown characters`**
`CHECK` **`prebuilt-read            852 markdown characters`**
`CHECK` **`prebuilt-layout          854 markdown characters`**
`CHECK` **`[WARN] prebuilt-digitalParse returned ZERO characters -- and reported Succeeded`**

[PAUSE] Hold on that zero. Let it sit for three full beats before you say a word.

[SAY] Zero characters. And look at the status on that call, because it came back
Succeeded. Nothing errored, nothing threw, the operation polled green, and it
extracted absolutely nothing. Now you might be thinking, hang on Tim, the
analyzer's broken. It isn't. Digital parse reads an existing text layer and it
never looks at pixels at all, so against a scan it did its job perfectly and
correctly found nothing there. That's the failure mode I want burned into your
memory, because a pipeline that only checks status is a pipeline that ships
empty documents to production and tells you everything's fine.

`SHOW` scroll to **What OCR recovered (prebuilt-read)**

[SAY] Read is the next rung up, and now we've got 852 characters that were
recovered from pixels. That's optical character recognition doing the work.
But watch what happens when I climb one rung higher.

`CHECK` **`read: sections 0`** and **`layout: sections 1`**

[SAY] Same characters, both of them, but a completely different understanding of
the page. Read hands you text. Layout hands you reading order, paragraph
boundaries, and a section tree, which is exactly the structure a chunker needs
downstream. And that's why the deck insists content extraction is a wider net
than OCR. Optical character recognition is one skill living inside content
extraction, and it isn't a synonym for the whole thing.

`SHOW` the born-digital PDF section

`CHECK` **`prebuilt-digitalParse    797 chars | HTML table: False`**
`CHECK` **`prebuilt-layout         1069 chars | HTML table: True`**

[SAY] And here's the control case. Same digital parse analyzer that gave us
nothing a minute ago, now against a born-digital PDF, and it returns the whole
document. One variable changed, whether the bytes carry a text layer or only
pixels, and the analyzer that looked broken looks brilliant. So picking a rung
on this ladder is a statement about your INPUT. It isn't a statement about
your ambition, and it isn't about paying for the fanciest option.

`SHOW` the HTML table block

[SAY] One more thing before we move on, and this one matters more than it looks.
Notice the tables come back as HTML, with a caption element and real header
cells. They don't come back as pipe-style markdown. That's a deliberate design
call, because pipe markdown physically can't express a merged cell or a
caption, and HTML can. When a fee table breaks across two pages, this is the
difference between one coherent table and two orphaned fragments that retrieve
terribly.

`IF IT BREAKS` A 401 means the token expired mid-beat. Re-run `az login` and
narrate it honestly; the beat is idempotent and re-runs clean.

---

## 2 · Two coordinate systems (4 min)

[DO] `uv run python m18_extract_demo.py --only ground`

`CHECK` **`mimeType in image/png`** and **`kind out document`** and **`unit pixel`**

[SAY] Look at that trio for a second. A PNG went into this call, and what came
back describes itself as a document, measured in pixels. Audio and video land on
this same markdown surface too. That right there is the whole grounding story
for retrieval-augmented generation: you write one chunker and one indexer, and
every modality you throw at it arrives in the shape they already understand.

`CHECK` **`span (into markdown)   offset 47, length 44`**
`CHECK` **`source (onto pixels)   page 1, 4-point polygon`**

[SAY] Now here's the part I love, and it's the thing the deck means when it says
grounding gives you two coordinates and not one. That single paragraph knows
where it lives twice over. The span is a character offset into the markdown,
and that's how a citation survives chunking. The source is a page number plus a
four-point polygon, and that's how you draw a highlight box over the original
scan for a human reviewer. You genuinely need both, because they answer
different questions.

[SAY] And notice it's four points, not two. A rectangle would be two corners and
we'd be done. But scanned paper goes through a scanner at an angle, so text sits
a couple degrees off level, and a rectangle simply can't describe that. Four
points can.

`CHECK` **`[OK] span sliced out of the markdown matches the paragraph exactly`**

[SAY] And that match isn't cosmetic, so don't skim past it. What we just did
was take the offset the service handed us, slice it straight out of the markdown
string in Python, and land on the identical text. That's the guarantee that lets
an agent cite a source honestly. The offset means the same thing to Azure that
it means to your code. The default encoding is Unicode code points, which is
exactly how Python 3 indexes a string, so those two agree for free. Pass string
encoding as UTF-16 and this line stops lining up on you.

[PAUSE] Clean seam here. Good spot to cut before the last beat.

---

## 3 · A custom analyzer, built and run (5-6 min)

`SHOW` VS Code on `ANALYZER_BODY` in `m18_extract_demo.py`

[SAY] So the prebuilts got us a long way, but eventually you need fields nobody
at Microsoft could have guessed you wanted. That's a custom analyzer, and I want
to walk the definition before I run it, because every line here is doing work.

`SHOW` `baseAnalyzerId`

[SAY] Start with the base analyzer. There are exactly four legal values here:
document, audio, video, and image. That's the whole list. And I want to flag
something that trips people up constantly, because prebuilt-invoice is a
document analyzer you can absolutely call directly, but you can't inherit from
it. You call a prebuilt, and you inherit from a base. Those are two different
verbs and the exam leans on that distinction.

`SHOW` `estimateFieldSourceAndConfidence`

[SAY] This one is the switch. Confidence and grounding are off by default, and I
mean genuinely off, not defaulted to something reasonable. Leave this line out
and every field still comes back, they just arrive naked with no confidence and
no source polygon, and the entire grounding story we just built evaporates
silently. Nothing warns you.

`SHOW` the three `method` values

[SAY] Now the three methods, and this is the heart of the lesson. Extract pulls
a literal that is physically printed on the page. Classify picks from a closed
list I define with an enum. And generate synthesizes something that isn't
written anywhere on that page at all. Same call, same document, three different
kinds of work.

[DO] `uv run python m18_extract_demo.py --only analyzer`

`CHECK` **`create returned HTTP 201`** then **`build: Succeeded`**

[SAY] And notice the build is a long-running operation. That 201 means accepted,
it doesn't mean finished. Here's the trap: when you poll that operation, the
poll itself comes back two hundred whether the build worked or not, and two
hundred only tells you the polling worked. It says nothing about the work.
Read the status field, not the HTTP code, or you'll ship a broken analyzer and
never see it go by.

`CHECK` `addendum_id` -> value **`WG-ADD-7742`**, **`spans 1`** (stable every run)
`CHECK` `waiver_summary` -> **`spans`** is 7 or more. **The number moves. Don't read it.**
`CHECK` **`[OK] generate is grounded to MORE of the page than extract -- as it should be`**

[SAY] There it is. Extract found the addendum ID in one place on that page and
it points at exactly one place. Generate wrote a sentence that exists nowhere on
the page, assembled out of several paragraphs scattered down the document, and
its grounding names every single one of them. Same document, same analyze call,
completely different accountability. When somebody asks you where a generated
summary came from, this is the answer, and it's specific.

`CHECK` **`[OK] branch_hours came back empty -- the analyzer declined to invent it`**

[SAY] And this last field is the one I care about most, which is why I put it in
there. I asked for branch lobby hours, and this addendum says nothing about
branch hours anywhere. It came back empty. Now that is exactly what we want to
see, and it happened because the field description explicitly told the model to
return an empty string when the document doesn't say. A field description is a
prompt, it isn't documentation. Ask for a fact that isn't there without giving
the model permission to decline, and you'll get a plausible, confident, and
completely wrong answer with a nice confidence score sitting next to it.

`CHECK` **`markdown characters 854 -> feeds retrieval`**
`CHECK` **`fields returned 4 -> feeds automation`**

[SAY] And we land right where the objective wants us. You never had to choose
between markdown and structure. One analyze call returned the prose surface that
a search index will chunk, and the typed object that a workflow will branch on.
Markdown feeds retrieval, fields feed automation, and you got both off a
photograph of a piece of paper.

`CHECK` **`[OK] deleted ai103L18AddendumV1`**

[SAY] Last thing, and it's a genuinely surprising one. That cleanup delete needs
the Content Understanding Owner role. Contributor can build an analyzer and
Contributor can run an analyzer, but Contributor can't remove one, which turns
a lot of well-intentioned cleanup scripts into a 403 nobody expected.

---

## RECAP (30 seconds, on camera)

[SAY] So three things to carry out of this lesson. Number one, content
extraction is a ladder, and the rung you pick is a statement about your input,
not your budget. Number two, grounding gives you two coordinates, a span into
the markdown and a polygon onto the page, and you need both to cite honestly.
And number three, one analyze call gives you markdown for retrieval and typed
fields for automation, so you're never actually choosing between them.

---

## POCKET CARD

| Thing | Value |
| --- | --- |
| API version | `2025-11-01` (**GA**, not preview) |
| Endpoint | `{foundry-account}.cognitiveservices.azure.com` |
| Token scope | `https://cognitiveservices.azure.com/.default` |
| Legal `baseAnalyzerId` | `prebuilt-document`, `prebuilt-audio`, `prebuilt-video`, `prebuilt-image` |
| Grounding switch | `estimateFieldSourceAndConfidence: true` (**off** by default) |
| Field methods | `extract` (literal) / `classify` (enum) / `generate` (synthesized) |
| Mandatory with `fieldSchema` | `models.completion` |
| Delete an analyzer | needs **Owner**, not Contributor |
| Source format | `D(page, x1,y1, x2,y2, x3,y3, x4,y4)`, `;` between regions |

## IF THE WHOLE THING FALLS OVER

Run the beats individually. Each one stands alone:

```powershell
uv run python m18_extract_demo.py --only ladder
uv run python m18_extract_demo.py --only ground
uv run python m18_extract_demo.py --only analyzer
```

**403 on Beat 3 teardown** -> you have Contributor, not Owner. Add `--keep`,
finish the take, and clean up afterwards.

**"needs a 'completion' model deployment"** -> the resource-level defaults are
missing. Check with:

```powershell
$t = az account get-access-token --resource https://cognitiveservices.azure.com --query accessToken -o tsv; curl -s -H "Authorization: Bearer $t" "$env:CU_ENDPOINT/contentunderstanding/defaults?api-version=2025-11-01"
```
