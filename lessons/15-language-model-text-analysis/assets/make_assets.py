#!/usr/bin/env python
"""
Regenerate Lesson 15's text fixtures deterministically.

Three files, each chosen to make one teaching point land:

  ticket-support.txt   A support email carrying a name, an email address, a
                       phone number, an account number, mixed sentiment across
                       sentences, and an urgent TONE that no Azure Language
                       feature scores. That last part is the point.

  contract-clause.txt  A compliance-flavored paragraph with dates, parties, and
                       obligations -- the domain-extraction case where a fixed
                       entity taxonomy stops being enough and you need a schema
                       of your own.

  release-note.txt     Short marketing copy with a product name that must NOT be
                       translated. That is the glossary / dynamic dictionary
                       case in Beat 3.

                       The product is called "Dispatch" ON PURPOSE. Invented
                       CamelCase names (ShipSense Pro, FleetPulse, WarehouseIQ)
                       are no longer a useful demo: current Translator reads the
                       capitalization as a proper-noun signal and passes them
                       through untouched, so the dictionary appears to do
                       nothing. Forty such candidates were probed live and not
                       one was localized. A product name that COLLIDES with an
                       ordinary noun is the case that still fails, and it is the
                       more honest lesson anyway -- plain Translator returns
                       "Le dispatch" and "Die Leitstelle", and the dynamic
                       dictionary is what pins the brand.

No randomness anywhere, so re-running this never changes what is on screen.
"""
import pathlib

HERE = pathlib.Path(__file__).parent

FILES = {
"ticket-support.txt": """From: Dana Whitfield <dana.whitfield@northwindlogistics.example>
Phone: (615) 555-0142
Account: NW-4471-88231

I have been a customer for six years and your team has always been excellent.
Today is a different story. The shipment tracking portal has been down since
this morning and my warehouse crew is standing around doing nothing.

I need someone to call me back within the hour. This is costing us money every
minute and I am running out of patience.

The billing team was helpful last quarter, so I know you can do better than this.
""",

"contract-clause.txt": """MASTER SERVICES AGREEMENT - CLAUSE 7.3, DATA HANDLING

Contoso Freight Services ("Provider") shall retain all shipment manifests
transmitted by Northwind Logistics ("Customer") for a period of not less than
seven years from the date of carriage. Provider shall notify Customer in writing
within seventy-two hours of becoming aware of any unauthorized disclosure of
Customer data. Provider's aggregate liability under this clause shall not exceed
the total fees paid by Customer in the twelve months preceding the incident.
Customer may audit Provider's compliance with this clause once per contract year
upon thirty days written notice.
""",

# Kept deliberately short and plain. A longer, more marketing-flavored body
# gives Translator enough surrounding context to infer "Dispatch" is a product
# and preserve it unaided in German, which kills the contrast. Verified live:
# plain returns 0 of 2 occurrences in BOTH fr and de, dictionary returns 2 of 2.
"release-note.txt": """Dispatch shows your team where every pallet is.
Dispatch replaces the morning spreadsheet.
""",
}


def main() -> int:
    for name, body in FILES.items():
        (HERE / name).write_text(body, encoding="utf-8")
        print(f"  wrote {name}  ({len(body)} chars)")
    print(f"\n{len(FILES)} fixtures regenerated deterministically.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
