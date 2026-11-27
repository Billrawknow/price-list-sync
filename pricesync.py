"""
Price List Sync: core (Week 7, Day 2).

Supplier price list in, a checked list of what changed since last time out.

    [1] read     PDF: Claude extracts every product row, page by page (forced JSON schema)
                 Excel: read directly by code, no AI needed
    [2] check    plain code confirms each PDF price is printed on a line with that product.
                 Rows that fail are set aside for a person, never used.
    [3] compare  this list against the previous one from the same supplier:
                 price up / down / new product / no longer listed
    [4] report   plain-text changes report, biggest increases first

    python pricesync.py                         # every supplier in price_lists/: newest list vs the one before
    python pricesync.py --supplier kapsoit-plumbing
    python pricesync.py --file price_lists/kapsoit-plumbing/2026-11-23.pdf    # read one list, show rows

Folder layout: price_lists/<supplier-name>/<YYYY-MM-DD>.pdf|.xlsx (date the list is valid from).
Each list is read once; the checked rows are saved in extracted/ and reused (no repeat AI cost).

Not in today's core (see PARKING_LOT.md): matching to the shop's products, markup pricing,
email, schedule.
"""

import argparse
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
LISTS = HERE / "price_lists"
EXTRACTED = HERE / "extracted"
REPORTS = HERE / "reports"

MODEL = os.getenv("CLAUDE_MODEL", "claude-haiku-5-5").strip()
EXTRA_ARGS = {"thinking": {"type": "disabled"}} if "haiku" in MODEL else {}
PRICE_PER_MTOK = {"input": 0.10, "output": 0.50}
API_TIMEOUT, MAX_ATTEMPTS = 60, 3
CACHE_VERSION = 2          # bump when the saved row format changes; older saved lists are re-read once

log = logging.getLogger("pricesync")
log.addHandler(logging.NullHandler())


class SyncError(Exception):
    """A problem a person can fix (unreadable file, scanned PDF, no API key...). Safe to show."""


@dataclass
class Row:
    code: str
    description: str
    unit: str
    price: float
    page: int = 0
    status: str = "verified"          # verified | unverified
    note: str = ""
    source: str = ""                  # PDF only: the printed text before the price on the matched line

    @property
    def key(self):
        """How a product is recognised from week to week.
        1. The supplier's code, if it has one.
        2. For PDFs without codes: the text PRINTED before the price on its line. It's the same every
           week, unlike the AI's wording (a real run named 6 Kapsoit rows differently from the truth).
        3. Otherwise (Excel without codes): description + unit from the cells."""
        if self.code:
            return self.code.upper().strip()
        if self.source:
            return "printed:" + self.source
        return f"{norm(self.description)}|{norm(self.unit)}"


@dataclass
class PriceList:
    supplier: str
    date: str
    file: str
    sha256: str
    rows: list = field(default_factory=list)          # verified rows only
    rejected: list = field(default_factory=list)      # failed the check: for a person to look at
    cost_usd: float = 0.0


def norm(text):
    return re.sub(r"[^a-z0-9.]+", " ", str(text).lower()).strip()


def money(value):
    """'Ksh 1,480.00' / '1,130' / 780 -> 1480.0 / 1130.0 / 780.0"""
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"(?i)ksh|kes|/=|,|\s", "", str(value))
    try:
        return float(cleaned)
    except ValueError:
        raise ValueError(f"'{value}' is not a price")


# ------------------------------------------------------------------ [1] read: Excel (no AI)

EXCEL_HEADERS = {
    "code": ["item code", "code", "product code", "item no", "sku"],
    "description": ["description", "product", "item", "item description", "product name"],
    "unit": ["pack", "unit", "uom", "size", "pack size"],
    "price": ["price ksh", "price (kes)", "price", "price kes", "unit price", "dealer price", "trade price"],
}


def read_excel(path):
    from openpyxl import load_workbook
    try:
        book = load_workbook(path, read_only=True, data_only=True)
    except Exception as err:
        raise SyncError(f"{path.name} couldn't be opened as Excel ({type(err).__name__}).")
    sheet = book.worksheets[0]
    grid = [list(r) for r in sheet.iter_rows(values_only=True)]
    book.close()
    # Suppliers put titles and dates above the table: find the header row in the first 15 rows.
    for h, header in enumerate(grid[:15]):
        names = [norm(c) for c in header]
        cols = {k: next((names.index(a) for a in aliases if a in names), None) for k, aliases in EXCEL_HEADERS.items()}
        if cols["description"] is not None and cols["price"] is not None:
            break
    else:
        raise SyncError(f"{path.name}: couldn't find a header row with Description and Price columns.")

    rows, rejected = [], []
    for n, line in enumerate(grid[h + 1:], start=h + 2):
        get = lambda k: line[cols[k]] if cols[k] is not None and cols[k] < len(line) else None  # noqa: E731
        desc = str(get("description") or "").strip()
        if not desc and get("price") in (None, ""):
            continue                                       # blank line or footer
        try:
            price = money(get("price"))
            if not desc:
                raise ValueError("no description")
            rows.append(Row(str(get("code") or "").strip(), desc, str(get("unit") or "").strip(), price, page=n))
        except (ValueError, TypeError) as err:
            if desc or get("code"):
                rejected.append(Row(str(get("code") or ""), desc, str(get("unit") or ""), 0, n, "unverified",
                                    f"row {n}: {err}"))
    return rows, rejected


# ------------------------------------------------------------------ [1] read: PDF (Claude, page by page)

ROWS_TOOL = {
    "name": "record_rows",
    "description": "Record every product row on this page of a supplier price list.",
    "input_schema": {"type": "object", "properties": {"rows": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "code": {"type": "string", "description": "Supplier's product code, or empty if the list has none"},
            "description": {"type": "string", "description": "Product description exactly as printed"},
            "unit": {"type": "string", "description": "Unit or pack as printed (e.g. 50kg bag, length, 4L), or empty"},
            "price": {"type": "number", "description": "The price as printed, as a number (1,480.00 -> 1480)"},
        },
        "required": ["code", "description", "unit", "price"]}}}, "required": ["rows"]},
}
ROWS_SYSTEM = """You copy product rows from Kenyan supplier price lists into structured data.
Copy every product row on the page, in order, exactly as printed: no rounding, no VAT maths, no
guessing. Skip headings, column titles, notes and totals. If a product has several prices
(e.g. retail and trade), use the main/dealer/trade price column."""


def pdf_pages(path):
    from pypdf import PdfReader
    try:
        reader = PdfReader(path)
        if reader.is_encrypted and not reader.decrypt(""):
            raise SyncError(f"{path.name} is password-protected.")
        pages = []
        for n, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text(extraction_mode="layout") or ""
            except Exception:
                text = page.extract_text() or ""
            pages.append((n, re.sub(r"[ \t]+", " ", text).strip()))
    except SyncError:
        raise
    except Exception as err:
        raise SyncError(f"{path.name} couldn't be read as a PDF ({type(err).__name__}).")
    if not any(t for _, t in pages):
        raise SyncError(f"{path.name} has no text: it's a scan or photo. Ask the supplier for the original "
                        "PDF or Excel (OCR is a separate change request).")
    return pages


class Claude:
    def __init__(self, client=None):
        self.client, self.input_tokens, self.output_tokens = client, 0, 0

    @property
    def cost(self):
        return (self.input_tokens * PRICE_PER_MTOK["input"] + self.output_tokens * PRICE_PER_MTOK["output"]) / 1e6

    def rows_on_page(self, supplier, page_no, text):
        import anthropic
        if self.client is None:
            key = os.getenv("ANTHROPIC_API_KEY", "").strip()
            if not key:
                raise SyncError("ANTHROPIC_API_KEY is missing. Add your key to config.env.")
            self.client = anthropic.Anthropic(api_key=key, timeout=API_TIMEOUT, max_retries=0)
        temporary = tuple(getattr(anthropic, n) for n in ("RateLimitError", "APIConnectionError",
                                                           "InternalServerError", "OverloadedError")
                          if hasattr(anthropic, n))
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self.client.messages.create(
                    model=MODEL, max_tokens=8000, system=ROWS_SYSTEM, tools=[ROWS_TOOL],
                    tool_choice={"type": "tool", "name": "record_rows"},
                    messages=[{"role": "user", "content": f"Supplier: {supplier}\nPage {page_no}:\n\n{text}"}],
                    **EXTRA_ARGS)
                break
            except anthropic.AuthenticationError:
                raise SyncError("The API key was rejected. Check ANTHROPIC_API_KEY in config.env.")
            except temporary as err:
                if attempt == MAX_ATTEMPTS:
                    raise SyncError(f"The AI service didn't respond after {MAX_ATTEMPTS} tries ({type(err).__name__}).")
                wait = 2 ** attempt + random.uniform(0, 1)
                log.warning(f"{supplier} p.{page_no}: {type(err).__name__}, retrying in {wait:.1f}s")
                time.sleep(wait)
            except anthropic.APIStatusError as err:
                raise SyncError(f"The AI service returned an error ({err.status_code}).")
        self.input_tokens += response.usage.input_tokens
        self.output_tokens += response.usage.output_tokens
        if response.stop_reason == "max_tokens":
            # A cut-off list must never look complete: the missing rows would read as "no longer listed".
            raise SyncError(f"{supplier} page {page_no} has too many rows for one request. "
                            "Split the page handling before trusting this list.")
        for block in response.content:
            if getattr(block, "type", "") == "tool_use":
                return block.input.get("rows", [])
        return []


# ------------------------------------------------------------------ [2] check (no AI)

def price_forms(price):
    """How a price can be printed: 1130 -> {'1,130', '1130', '1,130.00', '1130.00'}"""
    forms = {f"{price:,.2f}", f"{price:.2f}"}
    if price == int(price):
        forms |= {f"{int(price):,}", f"{int(price)}"}
    return forms


def check_row(row, page_text):
    """Verified only if one printed line holds both this product and this exact price."""
    return find_line(row, page_text) is not None


def find_line(row, page_text):
    """The printed text before the price, on the line that holds this product and this exact price; else None."""
    words = [w for w in norm(row.description).split() if len(w) > 1]
    for line in page_text.splitlines():
        low = line.lower()
        if row.code:
            if not re.search(rf"(?<![\w-]){re.escape(row.code.lower())}(?![\w-])", low):
                continue
        else:
            line_words = set(norm(line).split())
            sizes = [w for w in words if re.search(r"\d", w)]   # 20mm vs 25mm, 1/2 vs 3/4: must match exactly
            if not words or not all(w in line_words for w in sizes) \
                    or sum(w in line_words for w in words) < max(1, round(len(words) * 0.8)):
                continue
        # The price must stand alone: 20 must not "match" the 20 in "20mm" or in "1,205".
        for form in price_forms(row.price):
            hit = re.search(rf"(?<![\w,.]){re.escape(form)}(?![\w,]|\.\d)", line)
            if hit:
                before = re.sub(r"\b(ksh|kes|kshs)\b", " ", line[:hit.start()].lower())
                return norm(before)
    return None


def read_pdf(path, supplier, claude):
    rows, rejected = [], []
    for page_no, text in pdf_pages(path):
        if not text:
            continue
        for raw in claude.rows_on_page(supplier, page_no, text):
            try:
                row = Row(str(raw.get("code") or "").strip(), str(raw.get("description") or "").strip(),
                          str(raw.get("unit") or "").strip(), money(raw.get("price")), page_no)
            except (ValueError, TypeError) as err:
                rejected.append(Row(str(raw.get("code") or ""), str(raw.get("description") or ""), "", 0, page_no,
                                    "unverified", f"unreadable price: {err}"))
                continue
            source = find_line(row, text) if row.description else None
            if source is not None:
                row.source = source
                rows.append(row)
            else:
                row.status, row.note = "unverified", f"price {row.price:,.2f} not found next to this product on page {page_no}"
                rejected.append(row)
    return rows, rejected


# ------------------------------------------------------------------ read one list (cached)

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_list(path, supplier=None, client=None, cache=True):
    path = Path(path)
    supplier = supplier or path.parent.name
    date = path.stem
    digest = sha256(path)
    cached = EXTRACTED / supplier / f"{date}.json"
    if cache and cached.exists():
        data = json.loads(cached.read_text(encoding="utf-8"))
        if data.get("sha256") == digest and data.get("version") == CACHE_VERSION:   # same file: no AI cost
            return PriceList(supplier, date, data["file"], digest, [Row(**r) for r in data["rows"]],
                             [Row(**r) for r in data["rejected"]], 0.0)

    claude = Claude(client)
    if path.suffix.lower() == ".pdf":
        rows, rejected = read_pdf(path, supplier, claude)
    elif path.suffix.lower() in (".xlsx", ".xlsm"):
        rows, rejected = read_excel(path)
    else:
        raise SyncError(f"{path.name}: use PDF or Excel (.xlsx) price lists.")
    if not rows:
        raise SyncError(f"No prices could be read from {path.name}.")

    # Two rows claiming the same product with different prices can't both be right: set both aside.
    seen = {}
    for r in rows:
        seen.setdefault(r.key, []).append(r)
    clashes = {k for k, rs in seen.items() if len({r.price for r in rs}) > 1}
    for r in [r for r in rows if r.key in clashes]:
        r.status, r.note = "unverified", "the same product appears with two different prices"
        rejected.append(r)
    rows = [r for r in rows if r.key not in clashes]
    rows = list({r.key: r for r in rows}.values())       # exact duplicates (repeated header rows) once

    result = PriceList(supplier, date, path.name, digest, rows, rejected, round(claude.cost, 5))
    if cache:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps({"version": CACHE_VERSION, "file": path.name, "sha256": digest,
                                      "rows": [asdict(r) for r in rows],
                                      "rejected": [asdict(r) for r in rejected]}, indent=1), encoding="utf-8")
    log.info(f"{supplier} {date}: {len(rows)} rows checked, {len(rejected)} set aside, ${claude.cost:.4f}")
    return result


# ------------------------------------------------------------------ [3] compare

def compare(old, new):
    """Return a dict of lists: up, down, new, gone (each sorted most important first)."""
    before = {r.key: r for r in old.rows}
    after = {r.key: r for r in new.rows}
    up, down = [], []
    for key, r in after.items():
        if key in before and r.price != before[key].price:
            change = {"row": r, "old": before[key].price, "new": r.price, "diff": r.price - before[key].price,
                      "pct": (r.price - before[key].price) / before[key].price * 100 if before[key].price else 0}
            (up if change["diff"] > 0 else down).append(change)
    up.sort(key=lambda c: -c["pct"])
    down.sort(key=lambda c: c["pct"])
    # A product that failed this week's check isn't "gone": it's unknown, and listed under "to check".
    unsure = {r.key for r in new.rejected}
    return {"up": up, "down": down,
            "new": sorted((r for k, r in after.items() if k not in before), key=lambda r: r.description),
            "gone": sorted((r for k, r in before.items() if k not in after and k not in unsure),
                           key=lambda r: r.description),
            "unchanged": sum(1 for k, r in after.items() if k in before and r.price == before[k].price)}


# ------------------------------------------------------------------ [4] report

def fmt(price):
    return f"{price:,.0f}" if price == int(price) else f"{price:,.2f}"


def label(row, width=None):
    """'STL-022 Y12 deformed bar 12m (length)'. The unit is shown once even if the AI also put it in
    the description, and long labels are shortened at a word, with an ellipsis."""
    desc = row.description.strip()
    unit = row.unit.strip()
    if unit and norm(desc).endswith(norm(unit)):
        desc = desc[: len(desc) - len(unit)].rstrip(" ,-")
    text = f"{row.code + ' ' if row.code else ''}{desc}{' (' + unit + ')' if unit else ''}"
    if width and len(text) > width:
        cut = text[: width - 1]
        if text[width - 1] != " ":                  # mid-word: back up to the last whole word
            cut = cut.rsplit(" ", 1)[0]
        text = cut.rstrip(" -,") + "…"
    return text


def report(pairs):
    """pairs: [(supplier, old PriceList or None, new PriceList, changes or None)] -> report text"""
    lines = []
    for supplier, old, new, ch in pairs:
        name = supplier.replace("-", " ").title()
        lines += [f"{name}: price list {new.date}" + (f" vs {old.date}" if old else " (first list, nothing to compare)"),
                  "=" * 78]
        summary = f"{len(new.rows)} prices read and checked"
        if new.rejected:
            summary += f", {len(new.rejected)} set aside to check"
        if ch:
            summary += (f" | {len(ch['up'])} up, {len(ch['down'])} down, {len(ch['new'])} new, "
                        f"{len(ch['gone'])} no longer listed, {ch['unchanged']} unchanged")
        lines.append(summary)
        if ch:
            for title, items in (("PRICE INCREASES", ch["up"]), ("PRICE DECREASES", ch["down"])):
                if items:
                    lines += ["", title]
                    lines += [f"  {label(c['row'], 52):<52} {fmt(c['old']):>9} -> {fmt(c['new']):>9}  "
                              f"{c['diff']:+,.0f} ({c['pct']:+.1f}%)" for c in items]
            if ch["new"]:
                lines += ["", "NEW ON THE LIST"] + [f"  {label(r, 52):<52} {fmt(r.price):>9}" for r in ch["new"]]
            if ch["gone"]:
                lines += ["", "NO LONGER LISTED"] + [f"  {label(r, 52):<52} was {fmt(r.price)}" for r in ch["gone"]]
        if new.rejected:
            lines += ["", "TO CHECK BY HAND (not used above)"]
            lines += [f"  {label(r, 52):<52} {r.note}" for r in new.rejected]
        lines += ["", ""]
    return "\n".join(lines).rstrip() + "\n"


# ------------------------------------------------------------------ run

def supplier_lists(folder):
    files = sorted(p for p in folder.iterdir() if p.suffix.lower() in (".pdf", ".xlsx", ".xlsm")
                   and re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem))
    return files[-2:]                                       # previous and latest


def run(suppliers=None, client=None):
    folders = sorted(p for p in LISTS.iterdir() if p.is_dir()) if LISTS.exists() else []
    if suppliers:
        folders = [f for f in folders if f.name in suppliers]
    if not folders:
        raise SyncError(f"No supplier folders found in {LISTS.name}/.")
    pairs, cost = [], 0.0
    for folder in folders:
        files = supplier_lists(folder)
        if not files:
            continue
        new = read_list(files[-1], folder.name, client)
        old = read_list(files[-2], folder.name, client) if len(files) > 1 else None
        cost += new.cost_usd + (old.cost_usd if old else 0)
        pairs.append((folder.name, old, new, compare(old, new) if old else None))
    text = report(pairs)
    REPORTS.mkdir(exist_ok=True)
    latest = max(p[2].date for p in pairs)
    out = REPORTS / f"changes_{latest}.txt"
    out.write_text(text, encoding="utf-8")
    return text, out, cost


def main():
    p = argparse.ArgumentParser(description="Read supplier price lists and report what changed.")
    p.add_argument("--supplier", action="append", help="only this supplier folder (repeatable)")
    p.add_argument("--file", type=Path, help="read one price list and print its rows")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    for noisy in ("httpx", "httpx2", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        if args.file:
            pl = read_list(args.file)
            for r in pl.rows:
                print(f"  p.{r.page:<3} {label(r, 60):<60} {fmt(r.price):>10}")
            for r in pl.rejected:
                print(f"  CHECK {label(r, 60):<60} {r.note}")
            print(f"\n{len(pl.rows)} checked, {len(pl.rejected)} set aside, ${pl.cost_usd:.4f}")
            return
        text, out, cost = run(args.supplier)
        print(text)
        note = " (all lists were already read, so no AI cost)" if cost == 0 else ""
        print(f"Saved {out.relative_to(HERE)} | AI cost this run: ${cost:.4f}{note}")
    except SyncError as err:
        sys.exit(f"Problem: {err}")


if __name__ == "__main__":
    main()
