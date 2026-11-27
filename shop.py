"""
The shop side: read the shop's price sheet, match each stocked item to this week's supplier
price, and work out what to charge. Plain code, no AI: free, exact and repeatable.

Price sheet columns (header names are flexible, see SHEET_HEADERS):
    Shop Code | Product | Category | Supplier | Supplier Item | Cost | Selling Price

"Supplier Item" is the matching table: the supplier's code (Rift Valley, Sunrise) or, for a
supplier without codes (Kapsoit), the description exactly as the supplier prints it.
"""

import difflib
import math
import re
from dataclasses import dataclass

import pricesync as ps

SHEET_HEADERS = {
    "code": ["shop code", "code", "item code", "sku"],
    "product": ["product", "description", "item", "product name"],
    "category": ["category", "group", "department"],
    "supplier": ["supplier", "supplier name", "vendor"],
    "supplier_item": ["supplier item", "supplier code", "supplier ref", "supplier product"],
    "cost": ["cost", "cost (kes)", "buying price", "cost price"],
    "selling": ["selling price", "selling price (kes)", "price", "selling", "retail price"],
}
REQUIRED = ["product", "supplier", "supplier_item", "cost", "selling"]


@dataclass
class ShopItem:
    row: int
    code: str
    product: str
    category: str
    supplier: str
    supplier_item: str
    cost: float
    selling: float


@dataclass
class Priced:
    item: ShopItem
    supplier_row: object          # pricesync.Row, or None if not matched
    new_cost: float = 0.0
    markup: float = 0.0           # target markup on cost, e.g. 0.12
    target: float = 0.0           # selling price that gives the target markup on the NEW cost
    status: str = ""              # below_target | cost_up | cost_down | ok | not_found | no_list
    suggestion: str = ""          # for not_found: the closest supplier item

    @property
    def change(self):
        return self.new_cost - self.item.cost

    @property
    def change_pct(self):
        return self.change / self.item.cost * 100 if self.item.cost else 0.0

    @property
    def markup_now(self):
        """Markup the CURRENT selling price gives on the NEW cost."""
        return (self.item.selling - self.new_cost) / self.new_cost * 100 if self.new_cost else 0.0

    @property
    def shortfall(self):
        """KES per unit the shop loses against its target, at today's selling price."""
        return max(0.0, self.target - self.item.selling)


# ------------------------------------------------------------------ reading the sheet

def read_sheet(path):
    """Return (items, problems). Problems are rows a person must fix; they are never guessed."""
    from openpyxl import load_workbook
    try:
        book = load_workbook(path, read_only=True, data_only=True)
    except FileNotFoundError:
        raise ps.SyncError(f"Can't find the shop price sheet ({path}). Check SHOP_PRICE_SHEET in config.env.")
    except PermissionError:
        raise ps.SyncError(f"{path.name} is open in Excel. Close it and run again.")
    except Exception as err:
        raise ps.SyncError(f"{path.name} couldn't be opened as Excel ({type(err).__name__}).")
    grid = [list(r) for r in book.worksheets[0].iter_rows(values_only=True)]
    book.close()
    for h, header in enumerate(grid[:10]):
        names = [ps.norm(c) for c in header]
        cols = {k: next((names.index(ps.norm(a)) for a in aliases if ps.norm(a) in names), None)
                for k, aliases in SHEET_HEADERS.items()}
        if all(cols[k] is not None for k in REQUIRED):
            break
    else:
        wanted = ", ".join(SHEET_HEADERS[k][0].title() for k in REQUIRED)
        raise ps.SyncError(f"{path.name}: couldn't find the header row. It needs these columns: {wanted}.")

    items, problems = [], []
    for n, line in enumerate(grid[h + 1:], start=h + 2):
        get = lambda k: line[cols[k]] if cols[k] is not None and cols[k] < len(line) else None  # noqa: E731
        product = str(get("product") or "").strip()
        if not product:
            continue
        try:
            items.append(ShopItem(n, str(get("code") or "").strip(), product, str(get("category") or "").strip(),
                                  str(get("supplier") or "").strip(), str(get("supplier_item") or "").strip(),
                                  ps.money(get("cost")), ps.money(get("selling"))))
        except (ValueError, TypeError) as err:
            problems.append(f"Row {n} ({product}): {err}")
    if not items:
        raise ps.SyncError(f"{path.name} has no products in it.")
    return items, problems


# ------------------------------------------------------------------ markups

def parse_markups(text, default):
    """'Cement:12, Steel:15' -> {'cement': 0.12, 'steel': 0.15}. Raises ValueError with a plain message."""
    rules = {}
    for part in [p for p in re.split(r"[,;]", text or "") if p.strip()]:
        if ":" not in part:
            raise ValueError(f"'{part.strip()}' should look like Category:percent, e.g. Cement:12")
        name, pct = part.split(":", 1)
        try:
            value = float(pct.strip().rstrip("%"))
        except ValueError:
            raise ValueError(f"'{pct.strip()}' isn't a percentage (in '{part.strip()}')")
        if not 0 <= value <= 300:
            raise ValueError(f"{value}% for {name.strip()} looks wrong (use 0 to 300)")
        rules[ps.norm(name)] = value / 100
    return rules, float(default) / 100


def round_up(value, step):
    return math.ceil(value / step - 1e-9) * step if step else round(value, 2)


# ------------------------------------------------------------------ matching and pricing

def supplier_folder(name, price_lists):
    """'Sunrise Paints & Hardware' -> the 'sunrise-paints-hardware' list."""
    wanted = ps.norm(name).replace(" ", "")
    return next((slug for slug in price_lists if ps.norm(slug).replace(" ", "") == wanted), None)


def find_supplier_row(item, price_list):
    """By supplier code; for suppliers without codes, by the description as printed in their list."""
    ref = item.supplier_item.strip()
    if not ref:
        return None
    by_code = next((r for r in price_list.rows if r.code and r.code.upper() == ref.upper()), None)
    if by_code:
        return by_code
    wanted = ps.norm(ref)
    return next((r for r in price_list.rows if not r.code and
                 (ps.norm(r.description) == wanted or (r.source and r.source.startswith(wanted)))), None)


def suggest(item, price_list, previous=None):
    """Why it wasn't found and the closest supplier item, for a person to confirm. Never applied automatically."""
    if previous is not None:
        was = find_supplier_row(item, previous)
        if was is not None:          # it was on last week's list: the supplier dropped it
            from datetime import date
            seen = date.fromisoformat(previous.date)
            return (f"No longer on the supplier's list (was {ps.fmt(was.price)} on {seen.day} {seen:%b %Y}). "
                    "Ask the supplier, or find another supplier and update Supplier Item.")
    ref = item.supplier_item.strip().upper()
    codes = {r.code.upper(): r for r in price_list.rows if r.code}
    if codes and re.fullmatch(r"[A-Z]{1,5}-?[0-9A-Z]{2,6}", ref):
        # Typos in codes: letter O for zero, I/l for one, then the closest code.
        fixed = ref.replace("O", "0").replace("I", "1").replace("L", "1")
        guess = fixed if fixed in codes else next(iter(difflib.get_close_matches(fixed, list(codes), n=1, cutoff=0.8)), None)
        if guess:
            r = codes[guess]
            return f"Did you mean {ps.label(r)} ({ps.fmt(r.price)})? If so, change Supplier Item to {r.code}."
    candidates = {ps.label(r): r for r in price_list.rows}
    by_name = difflib.get_close_matches(f"{item.supplier_item} {item.product}", list(candidates), n=1, cutoff=0.45)
    if by_name:
        r = candidates[by_name[0]]
        return (f"Did you mean {ps.label(r)} ({ps.fmt(r.price)})? If so, change Supplier Item to "
                f"\"{r.code or r.description}\".")
    return "Not found on the supplier's list. Check Supplier Item in your price sheet."


def price_items(items, price_lists, markups, default_markup, round_to=10, previous=None):
    """price_lists: {supplier folder: latest PriceList}; previous: {supplier folder: the list before}.
    Returns [Priced], most urgent first."""
    previous = previous or {}
    results = []
    for item in items:
        slug = supplier_folder(item.supplier, price_lists)
        markup = markups.get(ps.norm(item.category), default_markup)
        row = find_supplier_row(item, price_lists[slug]) if slug else None
        if slug is None:
            # No list from this supplier at all: one note in the email, not a line per item in to_check.
            results.append(Priced(item, None, item.cost, markup, round_up(item.cost * (1 + markup), round_to),
                                  "no_list"))
            continue
        if row is None:
            results.append(Priced(item, None, item.cost, markup, round_up(item.cost * (1 + markup), round_to),
                                  "not_found", suggest(item, price_lists[slug], previous.get(slug))))
            continue
        target = round_up(row.price * (1 + markup), round_to)
        status = ("below_target" if item.selling < target else
                  "cost_up" if row.price > item.cost else
                  "cost_down" if row.price < item.cost else "ok")
        results.append(Priced(item, row, row.price, markup, target, status))
    order = {"below_target": 0, "cost_up": 1, "cost_down": 2, "not_found": 3, "ok": 4, "no_list": 5}
    results.sort(key=lambda p: (order[p.status], -p.shortfall, -abs(p.change_pct)))
    return results


def summary(results):
    count = {s: sum(1 for p in results if p.status == s) for s in
             ("below_target", "cost_up", "cost_down", "not_found", "ok", "no_list")}
    count["changed"] = sum(1 for p in results if p.supplier_row and p.new_cost != p.item.cost)
    return count
