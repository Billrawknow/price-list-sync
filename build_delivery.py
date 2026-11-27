"""
Builds the delivery package the client receives.

    python build_delivery.py --whatsapp "07XX XXX XXX" --kra-pin P05XXXXXXXX \
        --payment "M-Pesa Paybill 123456, Acc RCL-2026-0412 | KCB Kericho, A/C 1234567890"
    python build_delivery.py --draft          # placeholders allowed, everything marked DRAFT

Your phone number, KRA PIN and payment details are filled in here, at build time, so they
never sit in the public repository. Values can also come from delivery.env (git-ignored):
SUPPORT_WHATSAPP=..., KRA_PIN=..., PAYMENT_DETAILS=...

Output:
    delivery/
      Price List Sync/          the folder the client copies to Documents
      invoice.pdf
      walkthrough.mp4           copied from docs/walkthrough.mp4 once you've recorded it
      Price List Sync - delivery.zip   everything above, to send
"""

import argparse
import os
import re
import shutil
import sys
import zipfile
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
OUT = HERE / "delivery"
APP = "Price List Sync"

APP_FILES = ["sync.py", "pricesync.py", "shop.py", "deliver.py", "config.env.example",
             "setup.bat", "run.bat", "send test email.bat", "remove_schedule.bat"]
CLIENT_DATA = ["price_lists", "shop"]                  # the client's own lists and price sheet
CLIENT_REQUIREMENTS = ["anthropic", "pypdf", "openpyxl", "python-dotenv"]
NEVER_SHIP = {"config.env", ".env", "delivery.env", "tests", "samples", "extracted", "reports", "logs",
              "evaluate.py", "make_samples.py", "build_delivery.py", "__pycache__", ".git"}

INVOICE = {
    "number": "RCL-2026-0412", "date": date(2026, 12, 4),
    "client": ["Mlimani Hardware & Building Supplies", "Temple Road, Kericho", "Attn: Grace Chepkoech"],
    "lines": [("Price List Sync: build, installation and handover, as per the project brief of "
               "26 November 2026", 25000)],
    "paid": [("Deposit received 30 November 2026", 12500)],
}
PLACEHOLDER = "[to fill in]"


class BuildError(Exception):
    pass


def settings(args):
    load_dotenv(HERE / "delivery.env")
    values = {"whatsapp": args.whatsapp or os.getenv("SUPPORT_WHATSAPP", ""),
              "kra_pin": args.kra_pin or os.getenv("KRA_PIN", ""),
              "payment": args.payment or os.getenv("PAYMENT_DETAILS", "")}
    # Empty, or still template text like "07XX XXX XXX" or "[bank, branch, account]", counts as missing.
    missing = [k for k, v in values.items() if not v.strip() or re.search(r"XXX|\[.*?\]", v, re.I)]
    if missing and not args.draft:
        names = {"whatsapp": "--whatsapp (support number)", "kra_pin": "--kra-pin", "payment": "--payment"}
        raise BuildError("Missing for a final delivery: " + ", ".join(names[m] for m in missing) +
                         ". Add them, or use --draft to build a marked draft.")
    return {k: (PLACEHOLDER if k in missing else v.strip()) for k, v in values.items()}, bool(missing)


# ------------------------------------------------------------------ the client folder

def build_app_folder(dest, values):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for name in APP_FILES:
        shutil.copy2(HERE / name, dest / name)
    for folder in CLIENT_DATA:
        shutil.copytree(HERE / folder, dest / folder, ignore=shutil.ignore_patterns("~$*", "*.tmp"))
    for empty in ("logs", "reports"):
        (dest / empty).mkdir()
    readme = (HERE / "client" / "README.md").read_text(encoding="utf-8")
    readme = readme.replace("{SUPPORT_WHATSAPP}", values["whatsapp"])
    (dest / "README.md").write_text(readme.replace("\n", "\r\n"), encoding="utf-8", newline="")   # Notepad-friendly
    wanted = [line for line in (HERE / "requirements.txt").read_text().splitlines()
              if line.split(">=")[0].split("#")[0].strip() in CLIENT_REQUIREMENTS]
    (dest / "requirements.txt").write_text("\n".join(wanted) + "\n")
    secrets = {"config.env", ".env", "delivery.env"}
    leaked = sorted({p.name for p in dest.rglob("*") if p.name in secrets} |
                    {p.name for p in dest.iterdir() if p.name in NEVER_SHIP - {"logs", "reports"}} |
                    {p.name for folder in ("logs", "reports") for p in (dest / folder).iterdir()})
    if leaked:
        raise BuildError(f"Refusing to ship private or developer files: {leaked}")
    return dest


# ------------------------------------------------------------------ invoice.pdf

def build_invoice(out, values, draft):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    inv = INVOICE
    total = sum(a for _, a in inv["lines"])
    paid = sum(a for _, a in inv["paid"])
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=10, leading=14)
    small = ParagraphStyle("s", parent=body, fontSize=8.5, textColor=colors.HexColor("#555555"))
    navy = colors.HexColor("#1F4E79")

    head = Table([[Paragraph("<b><font size=16>Rawknow Company Ltd</font></b><br/>Kericho, Kenya<br/>"
                             f"bildadronoh@gmail.com &nbsp;|&nbsp; WhatsApp {values['whatsapp']}<br/>"
                             f"KRA PIN: {values['kra_pin']}", body),
                   Paragraph(f"<para alignment='right'><font size=22 color='#1F4E79'><b>INVOICE</b></font><br/>"
                             f"No. {inv['number']}<br/>Date: {inv['date'].day} {inv['date']:%B %Y}<br/>"
                             "Due: on receipt</para>", body)]], colWidths=[100 * mm, 70 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    rows = [["Description", "Amount (KES)"]] + [[Paragraph(d, body), f"{a:,.2f}"] for d, a in inv["lines"]]
    rows += [["Total", f"{total:,.2f}"]] + [[f"Less: {d}", f"-{a:,.2f}"] for d, a in inv["paid"]]
    rows += [["Balance due", f"{total - paid:,.2f}"]]
    table = Table(rows, colWidths=[130 * mm, 40 * mm])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), navy), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"), ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, colors.HexColor("#DDDDDD")),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"), ("FONTSIZE", (0, -1), (-1, -1), 11.5),
        ("LINEABOVE", (0, -1), (-1, -1), 1.2, navy), ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))

    story = [head, Spacer(1, 10 * mm), Paragraph("<b>Bill to</b><br/>" + "<br/>".join(inv["client"]), body),
             Spacer(1, 8 * mm), table, Spacer(1, 8 * mm),
             Paragraph(f"<b>How to pay</b><br/>{values['payment'].replace('|', '<br/>')}<br/>"
                       f"Please use <b>{inv['number']}</b> as the reference.", body), Spacer(1, 6 * mm),
             Paragraph("Optional monthly support (KES 2,500/month) starts only if confirmed in writing. "
                       "If Rawknow Company Ltd is VAT-registered, this invoice is issued through KRA eTIMS.", small),
             Spacer(1, 4 * mm), Paragraph("Thank you for your business.", body)]

    def mark(canvas, doc):
        if draft:
            canvas.saveState()
            canvas.setFont("Helvetica-Bold", 90)
            canvas.setFillColor(colors.Color(0.85, 0.1, 0.1, alpha=0.12))
            canvas.translate(105 * mm, 140 * mm)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "DRAFT")
            canvas.restoreState()

    SimpleDocTemplate(str(out), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=18 * mm,
                      title=f"Invoice {inv['number']}", author="Rawknow Company Ltd").build(
        story, onFirstPage=mark, onLaterPages=mark)
    return total - paid


# ------------------------------------------------------------------ zip

def build(args):
    values, draft = settings(args)
    if OUT.exists():
        shutil.rmtree(OUT)
    app = build_app_folder(OUT / APP, values)
    balance = build_invoice(OUT / "invoice.pdf", values, draft)
    video = HERE / "docs" / "walkthrough.mp4"
    if video.exists():
        shutil.copy2(video, OUT / "walkthrough.mp4")
    zip_path = OUT / f"{APP} - delivery{' (DRAFT)' if draft else ''}.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(OUT.rglob("*")):
            if path == zip_path:
                continue
            arc = path.relative_to(OUT).as_posix()
            if path.is_dir():
                if not any(path.iterdir()):
                    z.writestr(arc + "/", "")          # keep the empty logs/ and reports/ folders
            else:
                z.write(path, arc)
    return {"app": app, "zip": zip_path, "balance": balance, "draft": draft, "video": video.exists()}


def main(argv=None):
    p = argparse.ArgumentParser(description="Build the client delivery package.")
    p.add_argument("--whatsapp", default="", help="support WhatsApp number for the README and invoice")
    p.add_argument("--kra-pin", default="", help="Rawknow's KRA PIN for the invoice")
    p.add_argument("--payment", default="", help="payment details; use | between lines")
    p.add_argument("--draft", action="store_true", help="allow placeholders; mark everything DRAFT")
    args = p.parse_args(argv)
    try:
        result = build(args)
    except BuildError as err:
        print(f"Not built: {err}")
        return 1
    where = OUT.relative_to(HERE) if OUT.is_relative_to(HERE) else OUT
    print(f"\nBuilt {'a DRAFT ' if result['draft'] else ''}delivery package in {where}/")
    for path in sorted(OUT.iterdir()):
        size = sum(f.stat().st_size for f in path.rglob('*')) if path.is_dir() else path.stat().st_size
        print(f"  {path.name:<40} {size / 1024:>8,.0f} KB")
    print(f"\nInvoice balance: KES {result['balance']:,.2f}")
    if not result["video"]:
        print("Missing: docs/walkthrough.mp4. Record it (under 3 minutes, WALKTHROUGH_SCRIPT.md) and build again.")
    if result["draft"]:
        print("DRAFT: fill in --whatsapp, --kra-pin and --payment before sending.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
