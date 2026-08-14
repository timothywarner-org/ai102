#!/usr/bin/env python
"""
AI-103 Lesson 17 - build the Woodgrove Bank fixture corpus.

WHY A GENERATED CORPUS AND NOT A FOLDER OF PDFs
-----------------------------------------------
Every claim this lesson makes on camera is a claim about RETRIEVAL, and
retrieval is only provable if you know exactly what is in the haystack. A
borrowed sample corpus gives you plausible-looking results you cannot verify.
This corpus is built so that specific questions have exactly one findable
answer, and so that the *shape* of each question exercises a different part of
the pipeline:

  * WIRE_FEE_DOMESTIC lives in plain text        -> ordinary text extraction
  * ADDENDUM_CODE is a rare exact token          -> keyword recall (BM25) wins
  * "send funds abroad" shares no vocabulary
    with "international wire transfer"           -> vector recall wins
  * THE WAIVER FACT EXISTS ONLY AS PIXELS        -> proves the OCR chain end to end

That last one is the load-bearing fixture. `wg-addendum-scan.png` is an image.
There is no text layer, no embedded font, nothing for a document cracker to
extract. If a query for the waiver returns the right chunk, then image
normalization ran, OCR ran, Text Merge put the recognized characters back into
the document body, the split skill chunked the merged text, the embedding skill
vectorized the chunk, and the index projection wrote it as its own search
document. One green CHECK line proves six stages.

DETERMINISM
-----------
The page render is seeded, so the same machine produces a byte-identical PNG
every run and the retrieval cache stays warm across retakes. The generated
files are committed, so a fresh clone never needs Pillow at all -- this script
is a build tool, not a runtime dependency.

    uv run python assets/make_assets.py            # write anything missing
    uv run python assets/make_assets.py --force    # rebuild everything
"""
from __future__ import annotations

import argparse
import hashlib
import math
import pathlib
import random
import struct
import sys
import wave

CORPUS = pathlib.Path(__file__).parent / "corpus"

# ---------------------------------------------------------------------------
# Ground truth. Other scripts import these instead of hardcoding strings, so a
# fixture edit can never silently invalidate an assertion in a beat.
# ---------------------------------------------------------------------------

# A rare exact token. BM25 loves this; an embedding model has nothing to
# generalize from. This is the keyword half of the hybrid argument.
ADDENDUM_CODE = "WG-ADD-7742"

# The fact that exists ONLY inside the scanned image.
OCR_ONLY_FACT = "Premier Household"
OCR_ONLY_PROOF = "250,000"

# Concept-only phrasing. None of these words appear in the corpus; the corpus
# says "international wire transfer". This is the vector half of the argument.
CONCEPT_QUERY = "what does it cost to send funds abroad"

MEDIA_BLOB = "wg-call-recording.wav"
SCAN_BLOB = "wg-addendum-scan.png"

# ---------------------------------------------------------------------------
# The text corpus. Woodgrove Bank -- retail banking policy, the kind of content
# a grounding pipeline actually gets pointed at.
# ---------------------------------------------------------------------------

DOCS: dict[str, str] = {}

DOCS["wg-fee-schedule.md"] = """\
# Woodgrove Bank - Consumer Deposit Account Fee Schedule

This schedule applies to all consumer checking and savings accounts. Fees are
assessed at the time the service is performed and appear on the monthly
statement in the Fees and Charges section.

## Transfer fees

| Service | Fee |
| --- | --- |
| Outgoing domestic wire transfer | $30.00 per transfer |
| Outgoing international wire transfer | $45.00 per transfer |
| Incoming wire transfer, domestic or international | $15.00 per transfer |
| Same-day ACH transfer | $3.00 per transfer |
| Standard ACH transfer | No charge |

## Account maintenance

| Service | Fee |
| --- | --- |
| Monthly maintenance, Everyday Checking | $12.00 per month |
| Monthly maintenance, waived with qualifying direct deposit | No charge |
| Paper statement delivery | $2.00 per statement |
| Stop payment request | $25.00 per request |
| Cashier's check | $10.00 per check |

## Notes

Fees on this schedule are the standard published rates. Relationship pricing,
promotional waivers, and product addendums may reduce or eliminate a listed fee
for eligible customers. Where an addendum conflicts with this schedule, the
addendum controls. Nothing on this page should be read as the final price for a
customer whose account carries a relationship pricing designation.
"""

DOCS["wg-wire-transfers.md"] = """\
# Woodgrove Bank - Wire Transfer Policy

A wire transfer moves funds directly between financial institutions and settles
the same business day once it has been released. Unlike an ACH transfer, a wire
is final on receipt. It cannot be reversed by the sender.

## Cutoff times

Wire requests are processed in the order received. Requests received after the
cutoff are dated the next business day.

| Wire type | Cutoff, Eastern Time |
| --- | --- |
| Domestic wire, same business day | 4:00 PM |
| International wire, same business day | 2:00 PM |
| Wire requests on a bank holiday | Next business day |

## Correspondent bank charges

An international wire may pass through one or more correspondent institutions
before it reaches the beneficiary bank. Each correspondent may deduct its own
handling charge from the transferred amount. Woodgrove Bank does not set,
receive, or refund those charges, and cannot quote them in advance. The
beneficiary may therefore receive less than the amount sent.

## Recalls

A recall request asks the receiving institution to return funds voluntarily.
Woodgrove Bank will transmit a recall request on the customer's behalf, but the
receiving institution is under no obligation to honor it. Recall requests carry
no fee. Funds already credited to the beneficiary are generally unrecoverable
without a court order.

## Verification

Wires above $10,000 require callback verification to a phone number already on
file for the account. A phone number added or changed within the previous ten
calendar days cannot be used for callback verification.
"""

DOCS["wg-card-disputes.md"] = """\
# Woodgrove Bank - Card Dispute and Chargeback Handling

A dispute is a customer's claim that a posted card transaction is incorrect,
unauthorized, or not as described. A chargeback is the network process the bank
uses to pursue that claim against the merchant.

## Filing windows

| Dispute type | Window from statement date |
| --- | --- |
| Unauthorized transaction | 60 calendar days |
| Goods or services not received | 120 calendar days |
| Goods not as described | 120 calendar days |
| Duplicate posting | 60 calendar days |
| ATM withdrawal discrepancy | 60 calendar days |

## Provisional credit

For a disputed debit card transaction, Woodgrove Bank issues provisional credit
within ten business days of receiving the claim. Provisional credit is not a
resolution. If the investigation finds in the merchant's favor, the provisional
credit is reversed and the customer is notified at least five business days
before the reversal posts.

## What the customer must provide

The investigation cannot begin without the transaction date, the merchant name
as it appears on the statement, the disputed amount, and a description of what
the customer expected. For a not-as-described claim, the customer must also show
a good-faith attempt to resolve the matter with the merchant first.

## Wire transfers are not disputable

A completed wire transfer is not a card transaction and carries no chargeback
right. Customers who ask to dispute a wire should be routed to the recall
process in the wire transfer policy instead.
"""

DOCS["wg-overdraft.md"] = """\
# Woodgrove Bank - Overdraft Protection and Courtesy Pay

An overdraft occurs when a transaction posts against a balance that cannot cover
it. Woodgrove Bank offers two distinct programs, and customers regularly confuse
them.

## Overdraft protection transfer

The customer links a savings account or a line of credit to the checking
account. When a posting would overdraw the checking account, funds move
automatically from the linked account to cover it. The transfer fee is $10.00
per day, regardless of how many transfers occur that day. If the linked account
also lacks funds, the transaction falls through to courtesy pay.

## Courtesy pay

Courtesy pay is a discretionary decision by the bank to honor a transaction that
overdraws the account. It is not a line of credit and it is not guaranteed. The
fee is $35.00 per item, with a maximum of three items charged per business day.

## What is never charged an overdraft fee

Woodgrove Bank does not assess an overdraft fee on a transaction that overdraws
the account by less than $5.00, and does not assess an overdraft fee on an ATM
withdrawal or a one-time debit card purchase unless the customer has explicitly
opted in to that coverage.

## Restoring the account

An account that stays negative for 45 consecutive calendar days is closed and
charged off. The bank sends written notice at day 30.
"""

DOCS["wg-account-opening.md"] = """\
# Woodgrove Bank - Account Opening and Identity Verification

Every new consumer deposit account requires identity verification before the
account can be funded. This is a regulatory obligation, not a bank preference,
and there is no branch-level discretion to waive it.

## Required from every applicant

The applicant must provide a full legal name, a residential street address, a
date of birth, and a government-issued taxpayer identification number. A post
office box is not a residential address and cannot be used on its own.

## Acceptable identification

| Document | Accepted |
| --- | --- |
| Unexpired state driver's license | Yes |
| Unexpired passport | Yes |
| Unexpired military identification | Yes |
| Permanent resident card | Yes |
| Student identification | No |
| Expired document of any type | No |

## Funding the account

An account opened online is not active until the initial deposit clears. The
minimum opening deposit is $25.00 for Everyday Checking and $100.00 for a
savings account. An account with no funding activity within 30 days of opening
is automatically closed with no fee.

## Relationship pricing designation

A household that maintains a qualifying combined balance across its Woodgrove
Bank deposit and investment accounts may be assigned a relationship pricing
designation. The designation is evaluated monthly. Specific balance thresholds
and the fee treatment attached to each designation are published in the product
addendums, not in this document.
"""

# ---------------------------------------------------------------------------
# The scanned page. This text NEVER appears as characters anywhere in the
# corpus -- only as pixels in a PNG.
# ---------------------------------------------------------------------------

SCAN_LINES = [
    ("WOODGROVE BANK", "head"),
    ("PRODUCT ADDENDUM " + ADDENDUM_CODE, "head"),
    ("", "gap"),
    ("Wire Transfer Fee Waiver - Premier Household", "sub"),
    ("", "gap"),
    ("Woodgrove Bank waives the outgoing domestic wire", "body"),
    ("transfer fee in full for any account enrolled in the", "body"),
    ("Premier Household relationship pricing designation.", "body"),
    ("", "gap"),
    ("Eligibility requires a combined relationship balance", "body"),
    ("of $250,000 or more across deposit and investment", "body"),
    ("accounts, evaluated on the last business day of each", "body"),
    ("calendar month.", "body"),
    ("", "gap"),
    ("The waiver does NOT extend to outgoing international", "body"),
    ("wire transfers. Those remain billed at the published", "body"),
    ("rate and remain subject to correspondent bank charges", "body"),
    ("deducted in transit.", "body"),
    ("", "gap"),
    ("A household that falls below the qualifying balance", "body"),
    ("keeps the waiver through the end of the following", "body"),
    ("calendar month before standard pricing resumes.", "body"),
    ("", "gap"),
    ("This addendum controls where it conflicts with the", "body"),
    ("published consumer deposit account fee schedule.", "body"),
]


def _font(size: int):
    """
    First real TrueType face that exists wins. OCR on Pillow's built-in bitmap
    font is unreliable, so a missing TTF is a hard failure with a clear message
    rather than a mystery empty OCR result three stages downstream.
    """
    from PIL import ImageFont

    candidates = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if pathlib.Path(path).exists():
            return ImageFont.truetype(path, size)
    raise SystemExit(
        "No TrueType font found. OCR against Pillow's default bitmap font is\n"
        "not reliable enough to teach from. Install a font or run this on a\n"
        "machine that has one, then commit the resulting PNG."
    )


def render_scan(target: pathlib.Path) -> None:
    """
    Render the addendum as a page that has been photocopied, not typeset.

    The paper tint, the speckle, and the half-degree rotation are not
    decoration. A perfectly clean render of black text on pure white is
    effectively a screenshot, and OCR on a screenshot proves less than OCR on
    something that looks like it came off a flatbed. The skew stays small
    because the point of the beat is that the pipeline works, not that OCR can
    be defeated.
    """
    from PIL import Image, ImageDraw, ImageFilter

    rng = random.Random(17)                    # seeded: byte-identical rebuilds
    width, height = 1240, 1754                 # A4 at 150 dpi, under the 2000px
                                               # normalization ceiling
    page = Image.new("L", (width, height), 247)  # paper is never pure white
    draw = ImageDraw.Draw(page)

    fonts = {"head": _font(46), "sub": _font(34), "body": _font(30)}
    leading = {"head": 62, "sub": 52, "body": 46, "gap": 26}

    y = 190
    for text, kind in SCAN_LINES:
        if kind != "gap":
            draw.text((150, y), text, font=fonts[kind], fill=25)
        y += leading[kind]

    # Toner speckle. Sparse enough not to touch glyph interiors.
    for _ in range(5200):
        sx, sy = rng.randrange(width), rng.randrange(height)
        page.putpixel((sx, sy), rng.randrange(150, 215))

    # The scanner lid seam every real copy of a real document seems to have.
    draw.line([(0, 1620), (width, 1626)], fill=214, width=3)

    page = page.filter(ImageFilter.GaussianBlur(0.4))
    page = page.rotate(-0.5, resample=Image.BICUBIC, fillcolor=247)

    target.parent.mkdir(parents=True, exist_ok=True)
    page.save(target, format="PNG", optimize=True)


def render_media(target: pathlib.Path) -> None:
    """
    A real, playable, three-second WAV -- and completely unindexable.

    This file exists to be REJECTED. Learning objective one names audio and
    video, which invites the assumption that a blob indexer cracks them. It
    does not. A blob indexer extracts text from text-bearing formats; an audio
    file is an unsupported content type and the run stops on it unless you tell
    it not to. Having the file in the container makes that boundary something
    the room can watch happen instead of something I assert.
    """
    rate, seconds = 16000, 3.0
    frames = bytearray()
    for n in range(int(rate * seconds)):
        # 440 Hz, quiet, with a slow fade so it is obviously a real recording.
        envelope = 0.35 * (1.0 - n / (rate * seconds))
        sample = int(12000 * envelope * math.sin(2 * math.pi * 440 * n / rate))
        frames += struct.pack("<h", sample)

    target.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(target), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(bytes(frames))


def build(force: bool = False) -> list[tuple[str, int, str]]:
    """Write anything missing. Returns (name, bytes, sha256-prefix) per file."""
    CORPUS.mkdir(parents=True, exist_ok=True)
    written = []

    for name, text in DOCS.items():
        path = CORPUS / name
        if force or not path.exists():
            path.write_text(text, encoding="utf-8", newline="\n")

    scan = CORPUS / SCAN_BLOB
    if force or not scan.exists():
        render_scan(scan)

    media = CORPUS / MEDIA_BLOB
    if force or not media.exists():
        render_media(media)

    for path in sorted(CORPUS.iterdir()):
        blob = path.read_bytes()
        written.append((path.name, len(blob),
                        hashlib.sha256(blob).hexdigest()[:12]))
    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true",
                        help="rebuild every fixture even if it already exists")
    args = parser.parse_args()

    print("AI-103 L17 -- Woodgrove Bank fixture corpus")
    print(f"  {CORPUS}\n")
    for name, size, digest in build(force=args.force):
        kind = "SCANNED IMAGE" if name.endswith(".png") else (
            "AUDIO (unindexable by design)" if name.endswith(".wav") else "text")
        print(f"  {name:<26} {size:>8,} bytes  sha256:{digest}  {kind}")
    print(f"\n  the waiver fact exists ONLY inside {SCAN_BLOB}")
    print(f"  rare exact token for the keyword-recall beat: {ADDENDUM_CODE}")
    sys.exit(0)
