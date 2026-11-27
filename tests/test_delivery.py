"""
Day 4: the delivery package. What the client receives, and that it works on its own.

    pytest -v
"""

import re
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import build_delivery as bd  # noqa: E402

FINAL = ["--whatsapp", "0711 000 999", "--kra-pin", "P051234567Z",
         "--payment", "M-Pesa Paybill 123456, Acc RCL-2026-0412 | KCB Kericho, A/C 1234567890"]


@pytest.fixture
def out(tmp_path, monkeypatch):
    monkeypatch.setattr(bd, "OUT", tmp_path / "delivery")
    monkeypatch.delenv("SUPPORT_WHATSAPP", raising=False)
    monkeypatch.delenv("KRA_PIN", raising=False)
    monkeypatch.delenv("PAYMENT_DETAILS", raising=False)
    monkeypatch.setattr(bd, "load_dotenv", lambda *a, **k: None)      # ignore any real delivery.env
    return tmp_path / "delivery"


def test_final_delivery_refuses_to_build_with_placeholders(out, capsys):
    assert bd.main([]) == 1
    assert "Missing for a final delivery: --whatsapp" in capsys.readouterr().out
    assert not out.exists()


@pytest.mark.parametrize("args", [
    ["--whatsapp", "07XX XXX XXX", "--kra-pin", "P051234567Z", "--payment", "Paybill 123456"],
    ["--whatsapp", "0711 000 999", "--kra-pin", "P05XXXXXXXX", "--payment", "Paybill 123456"],
    ["--whatsapp", "0711 000 999", "--kra-pin", "P051234567Z", "--payment", "Bank: [bank, branch, account]"],
])
def test_template_text_counts_as_missing(out, capsys, args):
    # Found rendering the invoice (27 Nov): "XXXXXX" and "[bank, branch, account]" were accepted as real details.
    assert bd.main(args) == 1
    assert "Missing for a final delivery" in capsys.readouterr().out


def test_draft_is_clearly_marked(out):
    assert bd.main(["--draft"]) == 0
    assert (out / "Price List Sync - delivery (DRAFT).zip").exists()
    from pypdf import PdfReader
    assert "DRAFT" in PdfReader(out / "invoice.pdf").pages[0].extract_text()


def test_package_contains_only_what_the_client_needs(out):
    bd.main(FINAL)
    app = out / "Price List Sync"
    assert sorted(p.name for p in app.iterdir()) == sorted(
        ["README.md", "config.env.example", "deliver.py", "logs", "price_lists", "pricesync.py", "remove_schedule.bat",
         "reports", "requirements.txt", "run.bat", "send test email.bat", "setup.bat", "shop", "shop.py", "sync.py"])
    assert list((app / "logs").iterdir()) == [] and list((app / "reports").iterdir()) == []
    assert (app / "requirements.txt").read_text().split() == ["anthropic>=0.40", "pypdf>=5.0", "openpyxl>=3.1",
                                                              "python-dotenv>=1.0"]


def test_secrets_never_ship_even_when_they_exist_in_the_project(out, tmp_path, monkeypatch):
    project = tmp_path / "project"
    for item in ROOT.iterdir():
        if item.name not in (".git", "delivery", "__pycache__", ".pytest_cache"):
            target = project / item.name
            (subprocess.run(["cp", "-r", str(item), str(target)]) if item.is_dir() else
             target.parent.mkdir(parents=True, exist_ok=True) or target.write_bytes(item.read_bytes()))
    (project / "config.env").write_text("GMAIL_APP_PASSWORD=realsecret123456")
    (project / "delivery.env").write_text("KRA_PIN=P000")
    (project / "shop" / "config.env").write_text("oops")
    monkeypatch.setattr(bd, "HERE", project)
    assert bd.main(FINAL) == 1                                   # the stray shop/config.env is refused
    (project / "shop" / "config.env").unlink()
    assert bd.main(FINAL) == 0
    with zipfile.ZipFile(next(out.glob("*.zip"))) as z:
        names = z.namelist()
        assert not any(n.endswith(("config.env", "delivery.env", ".env")) for n in names)
        assert not any("realsecret" in z.read(n).decode("utf-8", "ignore") for n in names if not n.endswith("/"))
        assert "Price List Sync/logs/" in names and "Price List Sync/reports/" in names   # empty folders kept


def test_readme_is_filled_in_and_has_no_developer_commands(out):
    bd.main(FINAL)
    readme = (out / "Price List Sync" / "README.md").read_text(encoding="utf-8")
    assert "{SUPPORT_WHATSAPP}" not in readme and readme.count("0711 000 999") == 2
    assert b"\r\n" in (out / "Price List Sync" / "README.md").read_bytes()   # opens cleanly in Notepad
    for jargon in ("pip ", "python ", "Command Prompt", "terminal", ".py", "API", "SMTP", "cmd"):
        assert jargon not in readme, jargon                      # double-clicks only
    steps = re.findall(r"^(\d)\. ", readme.split("EVERY WEEK")[0].split("SET IT UP")[1], re.M)
    assert steps == ["1", "2", "3", "4"]                         # numbered setup, four steps


def test_readme_answers_the_five_handover_questions(out):
    bd.main(FINAL)
    readme = (out / "Price List Sync" / "README.md").read_text(encoding="utf-8")
    for question in ("What if it stops working?", "Can I add more people to the email?",
                     "Will it still work if I change my price sheet?", "What does it cost to run?",
                     "What if I change computers?"):
        assert question in readme


def test_invoice_amounts_and_details(out):
    bd.main(FINAL)
    from pypdf import PdfReader
    text = PdfReader(out / "invoice.pdf").pages[0].extract_text()
    for expected in ("INVOICE", "RCL-2026-0412", "4 December 2026", "Mlimani Hardware & Building Supplies",
                     "25,000.00", "-12,500.00", "Balance due", "12,500.00", "P051234567Z", "Paybill 123456",
                     "KCB Kericho"):
        assert expected in text, expected
    assert "DRAFT" not in text and "[to fill in]" not in text


def test_delivered_folder_runs_on_its_own(out, tmp_path):
    """Unzip it somewhere new (as on the client's PC) and run the settings check and the Excel supplier."""
    bd.main(FINAL)
    client_pc = tmp_path / "client_pc"
    with zipfile.ZipFile(next(out.glob("*.zip"))) as z:
        z.extractall(client_pc)
    app = client_pc / "Price List Sync"
    config = (app / "config.env.example").read_text().replace("ANTHROPIC_API_KEY=", "ANTHROPIC_API_KEY=sk-ant-x")
    (app / "config.env").write_text(config)
    for supplier in ("kapsoit-plumbing", "rift-valley-building-supplies"):     # PDFs would need the real AI
        subprocess.run(["rm", "-r", str(app / "price_lists" / supplier)], check=True)
    result = subprocess.run([sys.executable, "sync.py", "--no-email"], cwd=app, capture_output=True, text=True,
                            timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Sunrise Paints & Hardware: list of 23 Nov 2026: 2 up, 1 down" in result.stdout
    assert any((app / "reports").glob("price_updates_*.xlsx"))
    assert "OK - manual" in (app / "logs" / "sync.log").read_text()
