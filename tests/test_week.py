"""
Day 3: matching, pricing, delivery and every user path (normal, empty, wrong email,
no internet, test mode, more than 3 recipients, settings mistakes, schedule).

    pytest -v
"""

import email
import logging
import os
import shutil
import smtplib
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace as NS

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import pricesync as ps  # noqa: E402
import shop  # noqa: E402
import sync  # noqa: E402
from test_core import FakeClaude, truth  # noqa: E402

TODAY = date(2026, 11, 30)          # the Monday after the 23 Nov lists
GOOD = {
    "SHOP_NAME": "Mlimani Hardware & Building Supplies", "SHOP_PRICE_SHEET": "shop/Mlimani price sheet.xlsx",
    "PRICE_LISTS_FOLDER": "price_lists",
    "MARKUPS": "Cement:12, Steel:15, Roofing:18, Timber:20, Hardware:30, Plumbing:25, Paint:25",
    "DEFAULT_MARKUP": "20", "ROUND_TO": "10", "REPORT_TO": "owner@mlimani.co.ke, m1@mlimani.co.ke, m2@mlimani.co.ke",
    "GMAIL_ADDRESS": "mlimani.reports@gmail.com", "GMAIL_APP_PASSWORD": "abcd efgh ijkl mnop",
    "RUN_DAY": "MON", "RUN_TIME": "07:00", "TEST_MODE": "no", "TEST_EMAIL_TO": "bildad@test.co.ke",
    "ANTHROPIC_API_KEY": "sk-ant-test",
}


class AllSuppliers:
    """FakeClaude that knows every supplier's true rows (both weeks)."""

    def __init__(self):
        rows = []
        for s in ("rift-valley-building-supplies", "kapsoit-plumbing"):
            rows += truth(s, "2026-11-16") + truth(s, "2026-11-23")
        self.inner = FakeClaude(rows)
        self.messages = self.inner.messages


class FakeSMTP:
    """Stands in for smtplib.SMTP_SSL. `refuse` = addresses Gmail rejects; `fail` = exception on connect."""
    sent = []

    def __init__(self, *args, refuse=(), fail=None, **kwargs):
        if fail:
            raise fail
        self.refuse = set(refuse)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        assert len(password) == 16 and " " not in password

    def send_message(self, msg, to_addrs):
        if set(to_addrs) <= self.refuse:
            raise smtplib.SMTPRecipientsRefused({a: (550, b"no such user") for a in to_addrs})
        FakeSMTP.sent.append((msg, to_addrs))
        return {a: (550, b"no such user") for a in to_addrs if a in self.refuse}


def smtp(**kw):
    return lambda *a, **k: FakeSMTP(*a, **{**k, **kw})


@pytest.fixture
def env(tmp_path, monkeypatch):
    """A clean copy of the project data and a config.env, as on the shop's computer."""
    shutil.copytree(ROOT / "price_lists", tmp_path / "price_lists")
    shutil.copytree(ROOT / "shop", tmp_path / "shop")
    monkeypatch.setattr(sync, "HERE", tmp_path)
    monkeypatch.setattr(sync, "CONFIG", tmp_path / "config.env")
    monkeypatch.setattr(sync, "REPORTS", tmp_path / "reports")
    monkeypatch.setattr(sync, "LOG_DIR", tmp_path / "logs")          # never write into the real log
    monkeypatch.setattr(ps, "EXTRACTED", tmp_path / "extracted")
    monkeypatch.setattr(ps, "LISTS", tmp_path / "price_lists")
    for key in GOOD:
        monkeypatch.delenv(key, raising=False)
    FakeSMTP.sent = []
    logger = logging.getLogger("pricesync")
    monkeypatch.setattr(logger, "handlers", [logging.NullHandler()])

    def write(**changes):
        values = {**GOOD, **changes}
        (tmp_path / "config.env").write_text("\n".join(f"{k}={v}" for k, v in values.items()), encoding="utf-8")
    write()
    return NS(dir=tmp_path, write=write)


def run(env, *args, smtp_kw=None, capsys=None):
    code = sync.main(list(args), today=TODAY, client=AllSuppliers(), smtp=smtp(**(smtp_kw or {})))
    return code


# ------------------------------------------------------------------ matching and pricing

def priced(env):
    lists, prev = {}, {}
    for s in ("rift-valley-building-supplies", "kapsoit-plumbing", "sunrise-paints-hardware"):
        a, b = ps.supplier_lists(ps.LISTS / s)
        fake = FakeClaude(truth(s, a.stem) + truth(s, b.stem))
        prev[s], lists[s] = ps.read_list(a, s, fake), ps.read_list(b, s, fake)
    items, problems = shop.read_sheet(env.dir / "shop" / "Mlimani price sheet.xlsx")
    markups, default = shop.parse_markups(GOOD["MARKUPS"], 20)
    return {p.item.product: p for p in shop.price_items(items, lists, markups, default, 10, prev)}, problems


def test_cost_increase_makes_selling_price_fall_below_target(env):
    p, _ = priced(env)
    cement = p["Cement 42.5N 50kg"]                # bulk 10+: 755 -> 785, sells at 850, markup 12%
    assert (cement.item.cost, cement.new_cost, cement.item.selling) == (755, 785, 850)
    assert cement.status == "below_target"
    assert cement.target == 880                    # 785 x 1.12 = 879.2, rounded up to 10
    assert cement.shortfall == 30
    assert round(cement.markup_now, 1) == 8.3


def test_items_already_below_target_are_flagged_even_without_a_cost_change(env):
    p, _ = priced(env)
    lock = p["Door lock 4-lever"]
    assert lock.new_cost == lock.item.cost and lock.status == "below_target"


def test_cost_decrease_and_no_change(env):
    p, _ = priced(env)
    assert p["Thinner 5L"].status == "cost_down" and p["Thinner 5L"].change == -70
    assert p["PPR elbow 20mm"].status == "ok"


def test_supplier_without_codes_matched_by_printed_description(env):
    p, _ = priced(env)
    tank = p["Tank 5000L"]
    assert (tank.new_cost, tank.target, tank.status) == (43900, 54880, "below_target")


@pytest.mark.parametrize("product, hint", [
    ("Marine board 18mm", "No longer on the supplier's list (was 6,695 on 16 Nov 2026). Ask the supplier, or "
                          "find another supplier and update Supplier Item."),
    ("Barbed wire 25kg", "Did you mean HWR-110 Barbed wire - bulk 10+ (25kg roll) (4,800)? If so, change "
                         "Supplier Item to HWR-110."),
    ("Kitchen sink single bowl", "Did you mean Kitchen sink single bowl (piece) (3,950)? If so, change Supplier "
                                 "Item to \"Kitchen sink single bowl\"."),
])
def test_not_found_items_get_a_reason_never_a_silent_guess(env, product, hint):
    p, _ = priced(env)
    assert p[product].status == "not_found"
    assert p[product].suggestion == hint
    assert p[product].new_cost == p[product].item.cost         # nothing assumed


def test_most_urgent_first(env):
    lists, _ = priced(env)
    ordered = sorted(lists.values(), key=lambda x: 0)          # dict keeps price_items order
    statuses = [x.status for x in ordered]
    assert statuses[0] == "below_target" and ordered[0].item.product == "Tank 5000L"   # biggest shortfall
    assert statuses.index("cost_down") > max(i for i, s in enumerate(statuses) if s == "below_target")


@pytest.mark.parametrize("text, message", [
    ("Cement 12", "should look like Category:percent"),
    ("Cement:twelve", "isn't a percentage"),
    ("Cement:1200", "looks wrong"),
])
def test_markup_mistakes(text, message):
    with pytest.raises(ValueError, match=message):
        shop.parse_markups(text, 20)


def test_round_up():
    assert (shop.round_up(879.2, 10), shop.round_up(880, 10), shop.round_up(41.0, 50)) == (880, 880, 50)


def test_price_sheet_with_a_bad_row_reports_it(env):
    from openpyxl import load_workbook
    path = env.dir / "shop" / "Mlimani price sheet.xlsx"
    wb = load_workbook(path)
    wb.active["F3"] = "ask Grace"                              # cost cell for item 2
    wb.save(path)
    items, problems = shop.read_sheet(path)
    assert len(items) == 47 and problems == ["Row 3 (Cement 32.5R 50kg): 'ask Grace' is not a price"]


# ------------------------------------------------------------------ user paths (the lesson's table)

def test_path_normal_run_emails_html_and_text_with_both_spreadsheets(env):
    assert run(env) == 0
    msg, to = FakeSMTP.sent[0]
    assert to == ["owner@mlimani.co.ke", "m1@mlimani.co.ke", "m2@mlimani.co.ke"]
    assert msg["Subject"] == "Price changes week of 30 November 2026: 14 cost changes, 13 below margin"
    parsed = email.message_from_bytes(msg.as_bytes())
    types = [part.get_content_type() for part in parsed.walk()]
    assert "text/plain" in types and "text/html" in types        # plain-text fallback is always there
    names = [part.get_filename() for part in parsed.walk() if part.get_filename()]
    assert names == ["price_updates_2026-11-30.xlsx", "to_check_2026-11-30.xlsx"]
    html = next(p for p in parsed.walk() if p.get_content_type() == "text/html").get_payload(decode=True).decode()
    assert "Tank 5000L" in html and "54,880" in html and "Mlimani Hardware &amp; Building Supplies" in html


def test_path_updates_spreadsheet_contents(env):
    run(env)
    from openpyxl import load_workbook
    rows = list(load_workbook(env.dir / "reports" / "price_updates_2026-11-30.xlsx").active.iter_rows(values_only=True))
    assert rows[0][1] == "Product" and rows[1][1] == "Tank 5000L"
    assert rows[1][3] == "Below target markup" and rows[1][10] == 54880
    check = list(load_workbook(env.dir / "reports" / "to_check_2026-11-30.xlsx").active.iter_rows(values_only=True))
    assert {r[1] for r in check[1:]} == {"Marine board 18mm", "Barbed wire 25kg", "Kitchen sink single bowl"}


def test_path_more_than_three_recipients(env):
    many = ", ".join(f"manager{i}@mlimani.co.ke" for i in range(1, 7))
    env.write(REPORT_TO=many)
    assert run(env) == 0
    assert len(FakeSMTP.sent[0][1]) == 6


def test_path_test_mode_sends_only_to_the_test_address(env):
    assert run(env, "--test") == 0
    msg, to = FakeSMTP.sent[0]
    assert to == ["bildad@test.co.ke"] and msg["Subject"].startswith("[TEST] ")


def test_path_wrong_email_typo_is_caught_before_running(env, capsys):
    env.write(REPORT_TO="owner@mlimani.co.ke, manager@gmial.com, grace.mlimani.co.ke")
    assert run(env) == 1
    out = capsys.readouterr().out
    assert "'manager@gmial.com' looks like a typo. Did you mean @gmail.com?" in out
    assert "'grace.mlimani.co.ke' isn't a valid email address" in out
    assert FakeSMTP.sent == []


def test_path_address_that_does_not_exist_others_still_get_it(env, capsys):
    assert run(env, smtp_kw={"refuse": {"m2@mlimani.co.ke"}}) == 0
    assert FakeSMTP.sent[0][1][:2] == ["owner@mlimani.co.ke", "m1@mlimani.co.ke"]
    assert "Gmail refused 'm2@mlimani.co.ke'" in capsys.readouterr().out


def test_path_every_address_refused(env, capsys):
    env.write(REPORT_TO="ghost@mlimani.co.ke")
    assert run(env, smtp_kw={"refuse": {"ghost@mlimani.co.ke"}}) == 1
    assert "Gmail refused every address" in capsys.readouterr().out


def test_path_no_internet_files_are_saved_and_it_says_how_to_restart(env, capsys):
    assert run(env, smtp_kw={"fail": OSError("getaddrinfo failed")}) == 1
    out = capsys.readouterr().out
    assert "No internet?" in out and "double-click run.bat" in out
    assert (env.dir / "reports" / "price_updates_2026-11-30.xlsx").exists()


def test_path_wrong_gmail_password(env, capsys):
    assert run(env, smtp_kw={"fail": smtplib.SMTPAuthenticationError(535, b"bad")}) == 1
    assert "Email login failed" in capsys.readouterr().out


def test_path_empty_week_no_price_lists(env, capsys):
    for folder in (env.dir / "price_lists").iterdir():
        shutil.rmtree(folder)
    assert run(env) == 1
    assert "No price lists found" in capsys.readouterr().out


def test_path_supplier_sent_nothing_new_is_pointed_out(env, capsys):
    sync.main([], today=date(2026, 12, 14), client=AllSuppliers(), smtp=smtp())
    text = FakeSMTP.sent[0][0].get_body(("plain",)).get_content()
    assert "No new list for 21 days: ask Kapsoit Plumbing for this week's prices" in text


def test_path_missing_price_sheet(env, capsys):
    env.write(SHOP_PRICE_SHEET="shop/wrong name.xlsx")
    assert run(env) == 1
    assert "SHOP_PRICE_SHEET: can't find" in capsys.readouterr().out


@pytest.mark.parametrize("change, message", [
    ({"RUN_TIME": "7am"}, "RUN_TIME '7am' should be a 24-hour time"),
    ({"RUN_DAY": "Someday"}, "RUN_DAY 'Someday' should be a day"),
    ({"GMAIL_APP_PASSWORD": "mypassword"}, "16-letter App Password"),
    ({"MARKUPS": "Cement=12"}, "MARKUPS: 'Cement=12' should look like Category:percent"),
    ({"ANTHROPIC_API_KEY": ""}, "ANTHROPIC_API_KEY is empty"),
])
def test_settings_mistakes_are_named(env, capsys, change, message):
    env.write(**change)
    assert run(env) == 1
    assert message in capsys.readouterr().out


def test_no_email_mode_needs_no_gmail(env):
    env.write(GMAIL_ADDRESS="", GMAIL_APP_PASSWORD="")
    assert run(env, "--no-email") == 0
    assert FakeSMTP.sent == [] and (env.dir / "reports" / "email_2026-11-30.html").exists()


def test_unexpected_error_is_calm_and_logged(env, capsys, monkeypatch):
    monkeypatch.setattr(shop, "price_items", lambda *a, **k: 1 / 0)
    assert run(env) == 1
    out = capsys.readouterr().out
    assert "Something unexpected went wrong" in out and "ZeroDivisionError" not in out


def test_weekly_schedule_uses_run_day_and_time(env):
    env.write(RUN_DAY="Monday", RUN_TIME="7:00")
    from dotenv import load_dotenv
    load_dotenv(env.dir / "config.env", override=True)
    calls = []
    sync.ON_WINDOWS = True
    try:
        sync.install_schedule(lambda cmd, **k: calls.append(cmd) or NS(returncode=0, stdout="", stderr=""))
    finally:
        sync.ON_WINDOWS = os.name == "nt"
    create = calls[0]
    assert create[create.index("/SC") + 1] == "WEEKLY" and create[create.index("/D") + 1] == "MON"
    assert create[create.index("/ST") + 1] == "07:00" and "--scheduled" in create[create.index("/TR") + 1]


def test_tests_never_touch_the_real_log(env):
    # Bug found on Day 3: test runs were appending to the project's real logs/sync.log.
    real_log = ROOT / "logs" / "sync.log"
    before = real_log.read_text(encoding="utf-8") if real_log.exists() else None
    run(env)
    after = real_log.read_text(encoding="utf-8") if real_log.exists() else None
    assert before == after
    assert (env.dir / "logs" / "sync.log").exists()


def test_email_says_unchanged_for_items_that_were_already_too_cheap_and_uses_short_dates(env):
    run(env)
    text = FakeSMTP.sent[0][0].get_body(("plain",)).get_content()
    assert "Door lock 4-lever: selling 2,350, suggest 2,460 (cost unchanged 1,890)" in text
    assert "Rift Valley Building Supplies: list of 23 Nov 2026: 18 up" in text


def test_cost_down_rows_never_suggest_cutting_the_price(env):
    # From the first real email (26 Nov): Thinner showed "Suggested 1,480" against selling 1,570.
    run(env)
    from openpyxl import load_workbook
    rows = {r[1]: r for r in load_workbook(env.dir / "reports" / "price_updates_2026-11-30.xlsx")
            .active.iter_rows(min_row=2, values_only=True)}
    thinner = rows["Thinner 5L"]
    assert thinner[3] == "Cost down" and thinner[10] == thinner[7] == 1570        # keep the price
    assert thinner[12] == "Keep 1,570, or lower to 1,480 and still make 25%"
    assert rows["Door lock 4-lever"][12] == "Was already below target before this week"


def test_percent_columns_always_show_one_decimal(env):
    run(env)
    from openpyxl import load_workbook
    ws = load_workbook(env.dir / "reports" / "price_updates_2026-11-30.xlsx").active
    cement = next(r for r in ws.iter_rows(min_row=2) if r[1].value == "Cement 42.5N 50kg")
    assert cement[6].number_format == "0.0%" and abs(cement[6].value - 0.0397) < 0.001
    assert cement[9].value == 0.12


def test_supplier_with_no_list_is_one_clear_note_not_a_flood_of_to_check_rows(env, capsys):
    # Found testing the delivery package (27 Nov): an empty supplier folder put 40 near-identical rows in to_check.
    for supplier in ("kapsoit-plumbing", "rift-valley-building-supplies"):
        shutil.rmtree(env.dir / "price_lists" / supplier)
    assert run(env) == 0
    text = FakeSMTP.sent[0][0].get_body(("plain",)).get_content()
    assert "Kapsoit Plumbing: NO PRICE LIST in the folder, so its 15 item(s) weren't checked this week." in text
    assert "Rift Valley Building Supplies: NO PRICE LIST in the folder, so its 25 item(s) weren't checked" in text
    from openpyxl import load_workbook
    check = list(load_workbook(env.dir / "reports" / "to_check_2026-11-30.xlsx").active.iter_rows(values_only=True))
    assert len(check) == 1                                     # header only: nothing to fix item by item


def test_messages_point_at_config_env_not_dot_env():
    # Found testing the delivery package: "Check ANTHROPIC_API_KEY in .env", but the client's file is config.env.
    for name in ("pricesync.py", "sync.py", "shop.py", "deliver.py"):
        source = (ROOT / name).read_text(encoding="utf-8")
        assert " in .env" not in source and "to .env" not in source, name

