#!/usr/bin/env python
"""
Build the one fixture Lesson 18 cannot borrow from Lesson 17.

WHY THIS FILE EXISTS
--------------------
Beat 1 walks the prebuilt ladder - digitalParse, read, layout - over the SAME
page, and the payoff is that `prebuilt-digitalParse` returns ZERO characters
from a scan while reporting `Succeeded`. That is a real trap and it teaches
itself. But a trap alone is only half the lesson: without a file where
digitalParse WORKS, a learner concludes the analyzer is broken rather than
learning that it is a deliberate, cheaper, pixels-free code path.

So this renders a genuine born-digital PDF with a real text layer. Same
Woodgrove Bank fee schedule content the L17 corpus carries as markdown, laid
out as a page. Run digitalParse over both files and the contrast is exact:

    wg-addendum-scan.png   -> 0 characters, status Succeeded  (no text layer)
    wg-fee-schedule.pdf    -> full text,    status Succeeded  (text layer)

One variable changed - whether the bytes contain text or only pixels.

This is a BUILD-TIME script, not a runtime dependency of any beat. The PDF it
produces is committed, so a fresh clone never needs to run this.

    uv run python assets/make_assets.py
"""
from __future__ import annotations

import pathlib

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

HERE = pathlib.Path(__file__).parent
CORPUS = HERE / "corpus"
OUT = CORPUS / "wg-fee-schedule.pdf"

TITLE = "WOODGROVE BANK RETAIL FEE SCHEDULE"
SUBTITLE = "Effective for all consumer deposit accounts"

# A real table, because Beat 2 needs one. Content Understanding emits tables as
# HTML rather than pipe-markdown specifically so merged cells and row spans
# survive, and you cannot show that with prose.
ROWS = [
    ("Service", "Standard", "Premier Household"),
    ("Outgoing domestic wire", "$30.00", "Waived"),
    ("Outgoing international wire", "$45.00", "$45.00"),
    ("Overdraft item", "$35.00", "$10.00"),
    ("Stop payment request", "$30.00", "$15.00"),
    ("Paper statement, monthly", "$3.00", "Waived"),
]

BODY = [
    "Fees listed apply per occurrence unless stated otherwise. The Premier",
    "Household column applies only to accounts carrying the Premier Household",
    "relationship pricing designation described in addendum WG-ADD-7742.",
    "",
    "Waivers are evaluated on the last business day of each calendar month.",
    "An account that falls below the qualifying combined relationship balance",
    "keeps its waivers through the end of the following statement cycle.",
]


def build() -> None:
    CORPUS.mkdir(parents=True, exist_ok=True)
    pdf = canvas.Canvas(str(OUT), pagesize=LETTER)
    width, height = LETTER
    y = height - 1.0 * inch

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(1.0 * inch, y, TITLE)
    y -= 0.28 * inch
    pdf.setFont("Helvetica", 11)
    pdf.drawString(1.0 * inch, y, SUBTITLE)
    y -= 0.5 * inch

    # The table. Drawn as ruled text rather than an image, so the text layer is
    # real and the layout analyzer has genuine cell geometry to reconstruct.
    col_x = (1.0 * inch, 3.6 * inch, 5.3 * inch)
    pdf.setFont("Helvetica-Bold", 10)
    for x, cell in zip(col_x, ROWS[0]):
        pdf.drawString(x, y, cell)
    y -= 0.08 * inch
    pdf.line(1.0 * inch, y, width - 1.0 * inch, y)
    y -= 0.22 * inch

    pdf.setFont("Helvetica", 10)
    for row in ROWS[1:]:
        for x, cell in zip(col_x, row):
            pdf.drawString(x, y, cell)
        y -= 0.26 * inch

    y -= 0.25 * inch
    pdf.line(1.0 * inch, y, width - 1.0 * inch, y)
    y -= 0.35 * inch

    pdf.setFont("Helvetica", 10)
    for line in BODY:
        pdf.drawString(1.0 * inch, y, line)
        y -= 0.20 * inch

    pdf.setFont("Helvetica-Oblique", 8)
    pdf.drawString(1.0 * inch, 0.75 * inch,
                   "Woodgrove Bank is a fictitious company used for training.")
    pdf.showPage()
    pdf.save()
    print(f"wrote {OUT}  ({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    build()
