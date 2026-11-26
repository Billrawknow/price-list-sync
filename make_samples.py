"""
Builds the simulated client data: two weeks of price lists from Mlimani Hardware's 3 suppliers,
each in its own format, plus the TRUE rows behind each list (samples/truth/) so extraction
accuracy can be measured against the brief's 98% target.

    python make_samples.py

    price_lists/rift-valley-building-supplies/2026-11-16.pdf   coded table, ~4 pages
    price_lists/rift-valley-building-supplies/2026-11-23.pdf   same, with price changes
    price_lists/kapsoit-plumbing/2026-11-16.pdf                no codes, grouped by category, "Ksh 1,480.00"
    price_lists/kapsoit-plumbing/2026-11-23.pdf
    price_lists/sunrise-paints-hardware/2026-11-16.xlsx        Excel with title rows above the header
    price_lists/sunrise-paints-hardware/2026-11-23.xlsx

All companies, products and prices are made up.
"""

import csv
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

HERE = Path(__file__).resolve().parent
LISTS = HERE / "price_lists"
TRUTH = HERE / "samples" / "truth"
WEEK1, WEEK2 = "2026-11-16", "2026-11-23"

# ------------------------------------------------------------------ supplier 1: coded table (PDF)

RIFT = {
    "CEM": [("Cement 42.5N", "50kg bag", 780), ("Cement 32.5R", "50kg bag", 720), ("White cement", "25kg bag", 1650),
            ("Tile adhesive", "20kg bag", 980), ("Ready mix mortar", "40kg bag", 690)],
    "STL": [("Y8 deformed bar 12m", "length", 520), ("Y10 deformed bar 12m", "length", 790),
            ("Y12 deformed bar 12m", "length", 1130), ("Y16 deformed bar 12m", "length", 2010),
            ("Y20 deformed bar 12m", "length", 3150), ("R6 round bar 12m", "length", 310),
            ("BRC mesh A142 2.4x4.8m", "sheet", 4850), ("BRC mesh A98 2.4x4.8m", "sheet", 3600),
            ("Binding wire", "25kg roll", 4300), ("Hollow section 2x2 inch 6m", "length", 2650)],
    "ROF": [("Box profile sheet G30 3m", "sheet", 1120), ("Box profile sheet G28 3m", "sheet", 1380),
            ("Corrugated sheet G30 3m", "sheet", 980), ("Corrugated sheet G32 2m", "sheet", 590),
            ("Roofing ridge G30 2m", "piece", 650), ("Roofing nails", "1kg", 280), ("Valley gutter 2m", "piece", 760)],
    "TIM": [("Timber cypress 2x4", "per ft", 85), ("Timber cypress 2x3", "per ft", 62),
            ("Plywood 18mm 8x4", "sheet", 4700), ("Blockboard 18mm 8x4", "sheet", 5200),
            ("Marine board 18mm 8x4", "sheet", 6900), ("Fascia board 1x8", "per ft", 95)],
    "HWR": [("Wire nails 3 inch", "1kg", 210), ("Wire nails 4 inch", "1kg", 210), ("Hinges 4 inch", "pair", 240),
            ("Padlock 50mm", "piece", 650), ("Door lock 3-lever", "piece", 1450), ("Door lock 4-lever", "piece", 1950),
            ("Barrel bolt 6 inch", "piece", 180), ("Chain-link fence 1.2m x 20m", "roll", 4650),
            ("Barbed wire", "25kg roll", 4950)],
}
TIERS = [("", 1.0), (" - bulk 10+", 0.97), (" - bulk 50+", 0.94)]
# Week 2: what changed (known exactly, so the report can be checked)
RIFT_CHANGES = {"Cement 42.5N": 810, "Cement 32.5R": 745, "Y10 deformed bar 12m": 820, "Y12 deformed bar 12m": 1175,
                "Y16 deformed bar 12m": 2090, "Box profile sheet G30 3m": 1095, "Binding wire": 4450}
RIFT_GONE = {"Marine board 18mm 8x4"}
RIFT_NEW = {"CEM": [("Cement 42.5R rapid", "50kg bag", 860)], "HWR": [("Door lock 2-lever", "piece", 990)]}


def rift_rows(week):
    """Codes stay the same every week (as real suppliers' do); new products get new codes."""
    rows, n = [], 0
    for prefix, items in RIFT.items():
        for name, unit, price in items:
            for tier, factor in TIERS:
                n += 1
                if week == WEEK2 and name in RIFT_GONE:
                    continue
                base = RIFT_CHANGES.get(name, price) if week == WEEK2 else price
                rows.append({"code": f"{prefix}-{n:03d}", "description": name + tier, "unit": unit,
                             "price": round(base * factor / 5) * 5})
        if week == WEEK2:
            for k, (name, unit, price) in enumerate(RIFT_NEW.get(prefix, []), start=1):
                for t, (tier, factor) in enumerate(TIERS):
                    rows.append({"code": f"{prefix}-9{k}{t}", "description": name + tier, "unit": unit,
                                 "price": round(price * factor / 5) * 5})
    return rows


def rift_pdf(week, rows, out):
    ss = getSampleStyleSheet()
    title = ParagraphStyle("t", parent=ss["Title"], fontSize=16, alignment=0, spaceAfter=2)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9.5, leading=13)
    story = [Paragraph("RIFT VALLEY BUILDING SUPPLIES LTD", title),
             Paragraph(f"Industrial Area, Nakuru. Trade price list valid from {week}. Prices in KES per unit, "
                       "VAT inclusive. Subject to change without notice.", body), Spacer(1, 8)]
    table = Table([["Code", "Product", "Unit", "Price (KES)", "Stock"]] +
                  [[r["code"], r["description"], r["unit"], f"{r['price']:,}", "In stock" if i % 4 else "On order"]
                   for i, r in enumerate(rows)],
                  colWidths=[22 * mm, 75 * mm, 25 * mm, 25 * mm, 22 * mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#7A2E0E")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8.5), ("ALIGN", (3, 1), (3, -1), "RIGHT"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F6F1EC")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#DDD3C8"))]))
    story.append(table)
    footer = lambda c, d: (c.setFont("Helvetica", 7.5),  # noqa: E731
                           c.drawString(20 * mm, 10 * mm, f"Rift Valley Building Supplies | Price list {week} | Page {d.page}"))
    SimpleDocTemplate(str(out), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=15 * mm,
                      bottomMargin=18 * mm).build(story, onFirstPage=footer, onLaterPages=footer)


# ------------------------------------------------------------------ supplier 2: no codes, grouped, decimals (PDF)

KAPSOIT = {
    "PPR PIPES AND FITTINGS": [("PPR pipe 20mm x 4m", "length", 340), ("PPR pipe 25mm x 4m", "length", 510),
                               ("PPR pipe 32mm x 4m", "length", 790), ("PPR elbow 20mm", "piece", 25),
                               ("PPR elbow 25mm", "piece", 40), ("PPR tee 20mm", "piece", 30),
                               ("PPR tee 25mm", "piece", 45), ("PPR union 20mm", "piece", 180)],
    "PVC PIPES": [("PVC pipe 4 inch x 6m (class B)", "length", 1850), ("PVC pipe 2 inch x 6m", "length", 720),
                  ("PVC pipe 1 inch x 6m", "length", 420), ("PVC bend 4 inch", "piece", 260),
                  ("PVC solvent cement 250ml", "tin", 480)],
    "VALVES AND TAPS": [("Gate valve 1/2 inch brass", "piece", 690), ("Gate valve 3/4 inch brass", "piece", 980),
                        ("Gate valve 1 inch brass", "piece", 1480), ("Ball valve 1/2 inch", "piece", 450),
                        ("Pillar tap chrome", "piece", 950), ("Bib tap 1/2 inch", "piece", 520),
                        ("Float valve 1/2 inch", "piece", 780)],
    "TANKS": [("Water tank 500L", "piece", 6200), ("Water tank 1000L", "piece", 9800),
              ("Water tank 2300L", "piece", 19500), ("Water tank 5000L", "piece", 41500)],
    "SANITARY": [("Toilet set close-coupled white", "set", 8900), ("Wash hand basin with pedestal", "set", 4600),
                 ("Kitchen sink single bowl", "piece", 3950), ("Shower mixer", "piece", 3200),
                 ("Flexible connector 40cm", "piece", 220), ("Teflon tape", "roll", 30)],
}
KAPSOIT_CHANGES = {"Water tank 1000L": 10400, "Water tank 5000L": 43900, "PPR pipe 20mm x 4m": 355,
                   "Gate valve 1 inch brass": 1420}


def kapsoit_rows(week):
    rows = []
    for category, items in KAPSOIT.items():
        for name, unit, price in items:
            p = KAPSOIT_CHANGES.get(name, price) if week == WEEK2 else price
            rows.append({"code": "", "description": name, "unit": unit, "price": p, "category": category})
    return rows


def kapsoit_pdf(week, rows, out):
    ss = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=ss["Heading2"], fontSize=11, spaceBefore=10, spaceAfter=4,
                       textColor=colors.HexColor("#0B5394"))
    story = [Paragraph("Kapsoit Plumbing Distributors", ss["Title"]),
             Paragraph(f"Kericho Road, Kapsoit. Dealer price list for the week of {week}. "
                       "All prices in Kenya Shillings (Ksh), VAT inclusive.", ss["BodyText"])]
    for category in KAPSOIT:
        story.append(Paragraph(category, h))
        data = [["Description", "Unit", "Dealer price"]] + \
               [[r["description"], r["unit"], f"Ksh {r['price']:,.2f}"] for r in rows if r["category"] == category]
        t = Table(data, colWidths=[95 * mm, 30 * mm, 40 * mm])
        t.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 9), ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                               ("ALIGN", (2, 0), (2, -1), "RIGHT"), ("TEXTCOLOR", (0, 0), (-1, 0), colors.grey)]))
        story.append(t)
    story.append(Spacer(1, 12))
    story.append(Paragraph("Delivery free within Kericho town for orders above Ksh 20,000. Prices valid 7 days.",
                           ss["BodyText"]))
    SimpleDocTemplate(str(out), pagesize=A4).build(story)


# ------------------------------------------------------------------ supplier 3: Excel with title rows

SUNRISE = [("SP-101", "Emulsion paint white", "20L", 6400), ("SP-102", "Emulsion paint white", "4L", 1450),
           ("SP-103", "Emulsion paint magnolia", "20L", 6600), ("SP-110", "Gloss paint white", "4L", 2350),
           ("SP-111", "Gloss paint black", "4L", 2350), ("SP-112", "Gloss paint red oxide", "4L", 2200),
           ("SP-120", "Wood varnish clear", "4L", 2700), ("SP-130", "Thinner", "5L", 1250),
           ("SP-140", "Undercoat white", "4L", 1650), ("SH-201", "Paint brush 2 inch", "piece", 140),
           ("SH-202", "Paint brush 4 inch", "piece", 260), ("SH-210", "Roller set 9 inch", "set", 650),
           ("SH-220", "Masking tape 2 inch", "roll", 180), ("SH-230", "Sandpaper P120", "sheet", 35),
           ("SH-240", "Putty filler", "1kg", 420), ("SH-250", "Wall scraper", "piece", 280)]
SUNRISE_CHANGES = {"SP-101": 6650, "SP-102": 1495, "SP-130": 1180}


def sunrise_rows(week):
    return [{"code": c, "description": d, "unit": u,
             "price": SUNRISE_CHANGES.get(c, p) if week == WEEK2 else p} for c, d, u, p in SUNRISE]


def sunrise_xlsx(week, rows, out):
    book = Workbook()
    ws = book.active
    ws.title = "Price list"
    ws.append(["SUNRISE PAINTS & HARDWARE"])
    ws["A1"].font = Font(bold=True, size=14)
    ws.append([f"Trade prices from {week}"])
    ws.append([])
    ws.append(["Item Code", "Description", "Pack", "Price Ksh"])
    for r in rows:
        ws.append([r["code"], r["description"], r["unit"], r["price"]])
    ws.append([])
    ws.append(["Prices include VAT. E&OE."])
    book.save(out)


# ------------------------------------------------------------------ write everything

def write_truth(supplier, week, rows):
    folder = TRUTH / supplier
    folder.mkdir(parents=True, exist_ok=True)
    with open(folder / f"{week}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["code", "description", "unit", "price"])
        w.writeheader()
        w.writerows({k: r[k] for k in ("code", "description", "unit", "price")} for r in rows)


def main():
    builders = [("rift-valley-building-supplies", rift_rows, rift_pdf, ".pdf"),
                ("kapsoit-plumbing", kapsoit_rows, kapsoit_pdf, ".pdf"),
                ("sunrise-paints-hardware", sunrise_rows, sunrise_xlsx, ".xlsx")]
    for supplier, rows_for, build, ext in builders:
        (LISTS / supplier).mkdir(parents=True, exist_ok=True)
        for week in (WEEK1, WEEK2):
            rows = rows_for(week)
            build(week, rows, LISTS / supplier / f"{week}{ext}")
            write_truth(supplier, week, rows)
            print(f"{supplier:<32} {week}  {len(rows):>4} rows")


if __name__ == "__main__":
    main()
