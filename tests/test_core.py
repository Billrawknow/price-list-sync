"""
Core tests (Day 2). No API key needed: FakeClaude "reads" each page perfectly from the
known true rows, and individual tests inject the mistakes a real model can make.

    pytest -v
"""

import csv
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pricesync as ps  # noqa: E402

RIFT, KAPSOIT, SUNRISE = "rift-valley-building-supplies", "kapsoit-plumbing", "sunrise-paints-hardware"
W1, W2 = "2026-11-16", "2026-11-23"


def truth(supplier, week):
    with open(ROOT / "samples" / "truth" / supplier / f"{week}.csv", encoding="utf-8") as f:
        return [dict(r, price=float(r["price"])) for r in csv.DictReader(f)]


class FakeClaude:
    """Returns the true rows printed on each page. `mutate` lets a test corrupt the answer."""

    def __init__(self, rows, mutate=None, stop="end_turn"):
        self.rows, self.mutate, self.stop, self.calls = rows, mutate, stop, 0
        self.messages = NS(create=self.create)

    def create(self, **kwargs):
        self.calls += 1
        text = kwargs["messages"][0]["content"]
        found = [r for r in self.rows if ps.check_row(ps.Row(r["code"], r["description"], r["unit"], r["price"]), text)
                 and (r["code"] or r["description"] in text)]
        found = [dict(r) for r in {(r["code"], r["description"], r["unit"], r["price"]): r for r in found}.values()]
        if self.mutate:
            found = self.mutate(found)
        return NS(content=[NS(type="tool_use", name="record_rows", input={"rows": found})],
                  stop_reason=self.stop, usage=NS(input_tokens=1500, output_tokens=900))


@pytest.fixture(autouse=True)
def workspace(tmp_path, monkeypatch):
    """Each test gets its own copy of the price lists and empty extracted/ and reports/."""
    shutil.copytree(ROOT / "price_lists", tmp_path / "price_lists")
    monkeypatch.setattr(ps, "LISTS", tmp_path / "price_lists")
    monkeypatch.setattr(ps, "EXTRACTED", tmp_path / "extracted")
    monkeypatch.setattr(ps, "REPORTS", tmp_path / "reports")
    return tmp_path


def pdf(supplier, week, tmp):
    return tmp / "price_lists" / supplier / f"{week}.pdf"


# ------------------------------------------------------------------ the lesson's checks

def test_core_with_sample_data_matches_the_truth_exactly(workspace):
    """MUST PASS: every row of a real-format list read and checked, against the known true prices."""
    for supplier in (RIFT, KAPSOIT):
        expected = truth(supplier, W2)
        pl = ps.read_list(pdf(supplier, W2, workspace), client=FakeClaude(expected))
        got = {(r.code, r.description, r.price) for r in pl.rows}
        assert got == {(r["code"], r["description"], r["price"]) for r in expected}, supplier
        assert pl.rejected == []


def test_report_numbers_match_what_the_client_expects(workspace):
    """MUST PASS: the changes report equals the changes we know were made between the two weeks."""
    rows = truth(RIFT, W1) + truth(RIFT, W2)
    old = ps.read_list(pdf(RIFT, W1, workspace), client=FakeClaude(truth(RIFT, W1)))
    new = ps.read_list(pdf(RIFT, W2, workspace), client=FakeClaude(truth(RIFT, W2)))
    ch = ps.compare(old, new)
    assert (len(ch["up"]), len(ch["down"]), len(ch["new"]), len(ch["gone"])) == (18, 3, 6, 3)
    y12 = next(c for c in ch["up"] if c["row"].description == "Y12 deformed bar 12m")   # single-bar price
    assert (y12["old"], y12["new"], y12["diff"]) == (1130, 1175, 45)
    assert {r.description for r in ch["gone"]} == {"Marine board 18mm 8x4", "Marine board 18mm 8x4 - bulk 10+",
                                                     "Marine board 18mm 8x4 - bulk 50+"}
    assert ch["up"][0]["pct"] >= ch["up"][-1]["pct"]                           # biggest increase first
    assert rows                                                                # (truth files exist)


def test_empty_folder_is_handled(workspace):
    """CHECK: nothing to read gives a plain message, no crash."""
    shutil.rmtree(workspace / "price_lists")
    (workspace / "price_lists").mkdir()
    with pytest.raises(ps.SyncError, match="No supplier folders"):
        ps.run()


# ------------------------------------------------------------------ the price check catches AI mistakes

def test_a_misread_price_is_set_aside_not_reported():
    def wrong_y12(rows):
        for r in rows:
            if r["code"] == "STL-019":
                r["price"] = 1715.0                                              # digits swapped (1175 -> 1715)
        return rows
    pl = ps.read_list(ps.LISTS / RIFT / f"{W2}.pdf", client=FakeClaude(truth(RIFT, W2), wrong_y12))
    assert "STL-019" not in {r.code for r in pl.rows}
    assert any(r.code == "STL-019" and "not found next to this product" in r.note for r in pl.rejected)


def test_an_invented_product_is_set_aside():
    def invent(rows):
        return rows + [{"code": "CEM-777", "description": "Cement 52.5N premium", "unit": "50kg bag", "price": 950}]
    pl = ps.read_list(ps.LISTS / RIFT / f"{W2}.pdf", client=FakeClaude(truth(RIFT, W2), invent))
    assert "CEM-777" in {r.code for r in pl.rejected}
    assert "CEM-777" not in {r.code for r in pl.rows}


def test_prices_swapped_between_similar_sizes_are_caught():
    def swap(rows):                                     # called once per page: act only where both are
        a = next((r for r in rows if r["description"] == "PPR elbow 20mm"), None)
        b = next((r for r in rows if r["description"] == "PPR elbow 25mm"), None)
        if a and b:
            a["price"], b["price"] = b["price"], a["price"]
        return rows
    pl = ps.read_list(ps.LISTS / KAPSOIT / f"{W2}.pdf", client=FakeClaude(truth(KAPSOIT, W2), swap))
    assert {r.description for r in pl.rejected} == {"PPR elbow 20mm", "PPR elbow 25mm"}


@pytest.mark.parametrize("row, line, ok", [
    (("CEM-001", "Cement 42.5N", "50kg bag", 810), "CEM-001 Cement 42.5N 50kg bag 810 On order", True),
    (("CEM-001", "Cement 42.5N", "50kg bag", 42.5), "CEM-001 Cement 42.5N 50kg bag 810 On order", False),
    (("", "PPR elbow 20mm", "piece", 20), "PPR elbow 20mm piece Ksh 25.00", False),
    (("", "Water tank 1000L", "piece", 10400), "Water tank 1000L piece Ksh 10,400.00", True),
    (("", "Water tank 1000L", "piece", 10400), "Water tank 5000L piece Ksh 10,400.00", False),
    (("STL-019", "Y12", "length", 1130), "STL-019 Y12 deformed bar 12m length 11,130", False),
])
def test_check_row(row, line, ok):
    assert ps.check_row(ps.Row(*row), line) is ok


def test_a_product_that_failed_the_check_is_not_reported_as_gone(workspace):
    def drop_y12_price(rows):
        for r in rows:
            if r["code"] == "STL-019":
                r["price"] = 1.0
        return rows
    old = ps.read_list(pdf(RIFT, W1, workspace), client=FakeClaude(truth(RIFT, W1)))
    new = ps.read_list(pdf(RIFT, W2, workspace), client=FakeClaude(truth(RIFT, W2), drop_y12_price))
    ch = ps.compare(old, new)
    assert "STL-019" not in {r.code for r in ch["gone"]}                    # unknown, not discontinued
    assert "TO CHECK BY HAND" in ps.report([(RIFT, old, new, ch)])


def test_supplier_printing_one_code_twice_with_two_prices_is_set_aside(tmp_path):
    # Both lines really are in the PDF, so both pass the price check; neither can be trusted.
    from reportlab.pdfgen import canvas
    path = tmp_path / "2026-11-23.pdf"
    c = canvas.Canvas(str(path))
    for y, line in ((800, "CEM-001  Cement 42.5N  50kg bag  810"), (780, "CEM-001  Cement 42.5N  50kg bag  795"),
                    (760, "CEM-004  Cement 32.5R  50kg bag  745")):
        c.drawString(40, y, line)
    c.save()
    rows = [{"code": "CEM-001", "description": "Cement 42.5N", "unit": "50kg bag", "price": 810.0},
            {"code": "CEM-001", "description": "Cement 42.5N", "unit": "50kg bag", "price": 795.0},
            {"code": "CEM-004", "description": "Cement 32.5R", "unit": "50kg bag", "price": 745.0}]
    pl = ps.read_list(path, "test", client=FakeClaude(rows), cache=False)
    assert [r.code for r in pl.rows] == ["CEM-004"]
    assert [r.note for r in pl.rejected] == ["the same product appears with two different prices"] * 2


def test_cut_off_answer_stops_instead_of_dropping_products():
    with pytest.raises(ps.SyncError, match="too many rows"):
        ps.read_list(ps.LISTS / RIFT / f"{W2}.pdf", client=FakeClaude(truth(RIFT, W2), stop="max_tokens"))


# ------------------------------------------------------------------ Excel, files, cache

def test_excel_header_found_below_title_rows_and_footer_ignored():
    rows, rejected = ps.read_excel(ps.LISTS / SUNRISE / f"{W2}.xlsx")
    assert len(rows) == 16 and rejected == []
    assert (rows[0].code, rows[0].description, rows[0].unit, rows[0].price) == ("SP-101", "Emulsion paint white", "20L", 6650)


def test_excel_changes(workspace):
    old = ps.read_list(ps.LISTS / SUNRISE / f"{W1}.xlsx")
    new = ps.read_list(ps.LISTS / SUNRISE / f"{W2}.xlsx")
    ch = ps.compare(old, new)
    assert {c["row"].code: c["diff"] for c in ch["up"]} == {"SP-101": 250, "SP-102": 45}
    assert {c["row"].code: c["diff"] for c in ch["down"]} == {"SP-130": -70}


def test_excel_bad_price_cell_is_listed(tmp_path):
    from openpyxl import Workbook
    wb = Workbook()
    wb.active.append(["Description", "Price"])
    wb.active.append(["Good item", 100])
    wb.active.append(["Bad item", "call us"])
    path = tmp_path / "2026-11-23.xlsx"
    wb.save(path)
    rows, rejected = ps.read_excel(path)
    assert [r.description for r in rows] == ["Good item"]
    assert "call us" in rejected[0].note


def test_list_is_read_once_then_cached(workspace):
    client = FakeClaude(truth(KAPSOIT, W2))
    ps.read_list(pdf(KAPSOIT, W2, workspace), client=client)
    calls = client.calls
    again = ps.read_list(pdf(KAPSOIT, W2, workspace), client=client)
    assert client.calls == calls and again.cost_usd == 0                    # no second AI cost
    assert len(again.rows) == 30


def test_scanned_pdf_is_refused_before_any_ai_cost(tmp_path):
    from pypdf import PdfWriter
    path = tmp_path / "2026-11-23.pdf"
    w = PdfWriter()
    w.add_blank_page(width=595, height=842)
    w.write(path)
    client = FakeClaude([])
    with pytest.raises(ps.SyncError, match="scan or photo"):
        ps.read_list(path, "x", client=client, cache=False)
    assert client.calls == 0


def test_full_run_all_three_suppliers(workspace, monkeypatch):
    rows = {s: truth(s, W1) + truth(s, W2) for s in (RIFT, KAPSOIT)}

    real_read = ps.read_list
    monkeypatch.setattr(ps, "read_list", lambda path, supplier=None, client=None, cache=True:
                        real_read(path, supplier, FakeClaude(rows.get(Path(path).parent.name, [])), cache))
    text, out, cost = ps.run()
    assert out.exists() and out.name == f"changes_{W2}.txt"
    assert "Rift Valley Building Supplies: price list 2026-11-23 vs 2026-11-16" in text
    assert "18 up, 3 down, 6 new, 3 no longer listed" in text
    assert "Water tank 5000L (piece)" in text and "41,500 ->    43,900" in text
    assert "SP-130 Thinner (5L)" in text
    assert cost > 0


# ------------------------------------------------------------------ found in the first real run (26 Nov)

def reword(rows):
    """What Claude did on the real run: same products and prices, worded differently."""
    for r in rows:
        if " x " in r["description"]:                       # "PPR pipe 20mm x 4m" / "length"
            name, size = r["description"].split(" x ", 1)
            r["description"], r["unit"] = name, f"x {size} {r['unit']}"
        else:
            r["description"] = r["description"].upper()
    return rows


def test_suppliers_without_codes_keep_the_same_identity_however_the_ai_words_it(workspace):
    old = ps.read_list(pdf(KAPSOIT, W1, workspace), client=FakeClaude(truth(KAPSOIT, W1)))
    new = ps.read_list(pdf(KAPSOIT, W2, workspace), client=FakeClaude(truth(KAPSOIT, W2), reword))
    ch = ps.compare(old, new)
    assert (len(ch["new"]), len(ch["gone"])) == (0, 0)          # no fake "new" or "no longer listed"
    assert {c["row"].price for c in ch["up"]} == {355, 10400, 43900}
    assert [(c["old"], c["new"]) for c in ch["down"]] == [(1480, 1420)]


def test_identity_is_the_printed_text_before_the_price(workspace):
    pl = ps.read_list(pdf(KAPSOIT, W2, workspace), client=FakeClaude(truth(KAPSOIT, W2)))
    tank = next(r for r in pl.rows if r.description == "Water tank 1000L")
    assert tank.key == "printed:water tank 1000l piece"         # no price, no "Ksh"


def test_lists_saved_in_the_old_format_are_read_again(workspace):
    path = pdf(KAPSOIT, W2, workspace)
    ps.read_list(path, client=FakeClaude(truth(KAPSOIT, W2)))
    saved = ps.EXTRACTED / KAPSOIT / f"{W2}.json"
    data = json.loads(saved.read_text())
    data.pop("version")                                          # as saved by the Day 2 version
    saved.write_text(json.dumps(data))
    client = FakeClaude(truth(KAPSOIT, W2))
    ps.read_list(path, client=client)
    assert client.calls > 0


@pytest.mark.parametrize("row, width, text", [
    (("", "PPR pipe 20mm x 4m length", "length", 355), None, "PPR pipe 20mm x 4m (length)"),
    (("TIM-080", "Marine board 18mm 8x4 - bulk 10+ sheet", "sheet", 6695), None, "TIM-080 Marine board 18mm 8x4 - bulk 10+ (sheet)"),
    (("STL-022", "Y12 deformed bar 12m", "length", 1175), None, "STL-022 Y12 deformed bar 12m (length)"),
    (("TIM-080", "Marine board 18mm 8x4 - bulk 10+", "sheet", 6695), 30, "TIM-080 Marine board 18mm 8x4…"),
])
def test_labels_show_the_unit_once_and_cut_at_a_word(row, width, text):
    # Real run, 26 Nov: "PPR pipe 20mm x 4m length (length)" and "...bulk 10+ sheet (shee"
    assert ps.label(ps.Row(*row), width) == text

