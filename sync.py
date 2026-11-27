"""
Price List Sync: the weekly job (what run.bat and the Monday schedule run).

    python sync.py                    # read new price lists, price the shop's items, email the report
    python sync.py --test             # same, but email only TEST_EMAIL_TO, subject marked [TEST]
    python sync.py --no-email         # make the files only (reports/), send nothing
    python sync.py --check            # check config.env and stop
    python sync.py --install-schedule # run every RUN_DAY at RUN_TIME (Windows Task Scheduler)
    python sync.py --remove-schedule

Settings: config.env (copy config.env.example). Log: logs/sync.log.
"""

import argparse
import logging
import os
import re
import subprocess
import sys
from datetime import date, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv

import deliver
import pricesync as ps
import shop

HERE = Path(__file__).resolve().parent
CONFIG = HERE / "config.env"
REPORTS = HERE / "reports"
LOG_DIR = HERE / "logs"
TASK_NAME = "Price List Sync"
ON_WINDOWS = os.name == "nt"
DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
EMAIL_RE = re.compile(r"^[^@\s,;]+@[^@\s,;]+\.[a-z]{2,}$", re.I)
DOMAIN_TYPOS = {"gmial.com": "gmail.com", "gmai.com": "gmail.com", "gamil.com": "gmail.com", "gmail.co": "gmail.com",
                "gmail.con": "gmail.com", "gmal.com": "gmail.com", "yaho.com": "yahoo.com", "yahoo.con": "yahoo.com",
                "outlok.com": "outlook.com", "hotmial.com": "hotmail.com"}
RESTART = "Fix the problem, then double-click run.bat to run it again (or wait for next week's automatic run)."

log = logging.getLogger("pricesync")


def setting(name, default=""):
    return os.getenv(name, default).strip().strip('"').strip("'")


def path_setting(name, default):
    p = Path(setting(name, default)).expanduser()
    return p if p.is_absolute() else HERE / p


def emails(name):
    return [a.strip() for a in re.split(r"[,;]", setting(name)) if a.strip()]


def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)
    handler = RotatingFileHandler(LOG_DIR / "sync.log", maxBytes=500_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    log.addHandler(handler)
    log.setLevel(logging.INFO)
    for noisy in ("httpx", "httpx2", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


# ------------------------------------------------------------------ settings check

def check_config(send_email=True, test=False):
    """Every mistake in config.env, in plain words, naming the line to fix."""
    problems = []
    if not CONFIG.exists():
        return [f"config.env is missing. Copy config.env.example to config.env and fill it in ({HERE})."]
    sheet = path_setting("SHOP_PRICE_SHEET", "shop/price sheet.xlsx")
    if not sheet.exists():
        problems.append(f"SHOP_PRICE_SHEET: can't find '{sheet}'. Check the name and folder.")
    lists = path_setting("PRICE_LISTS_FOLDER", "price_lists")
    if not lists.is_dir():
        problems.append(f"PRICE_LISTS_FOLDER: can't find the folder '{lists}'.")
    try:
        shop.parse_markups(setting("MARKUPS"), setting("DEFAULT_MARKUP", "20"))
    except ValueError as err:
        problems.append(f"MARKUPS: {err}.")
    if not re.fullmatch(r"\d{1,4}", setting("ROUND_TO", "10")):
        problems.append("ROUND_TO should be a whole number of shillings, e.g. 10 or 50.")
    if setting("RUN_DAY", "MON").upper()[:3] not in DAYS:
        problems.append(f"RUN_DAY '{setting('RUN_DAY')}' should be a day like MON or Monday.")
    if not re.fullmatch(r"([01]?\d|2[0-3]):[0-5]\d", setting("RUN_TIME", "07:00")):
        problems.append(f"RUN_TIME '{setting('RUN_TIME')}' should be a 24-hour time like 07:00.")
    if any(f.suffix.lower() == ".pdf" for f in lists.glob("*/*")) and not setting("ANTHROPIC_API_KEY"):
        problems.append("ANTHROPIC_API_KEY is empty. It's needed to read PDF price lists.")
    if send_email:
        key = "TEST_EMAIL_TO" if test else "REPORT_TO"
        addresses = emails(key)
        if not addresses:
            problems.append(f"{key} is empty. Put at least one email address (several: separate with commas).")
        for a in addresses:
            domain = a.split("@")[-1].lower()
            if not EMAIL_RE.match(a):
                problems.append(f"{key}: '{a}' isn't a valid email address.")
            elif domain in DOMAIN_TYPOS:
                problems.append(f"{key}: '{a}' looks like a typo. Did you mean @{DOMAIN_TYPOS[domain]}?")
        if not EMAIL_RE.match(setting("GMAIL_ADDRESS")):
            problems.append("GMAIL_ADDRESS needs the Gmail address the report is sent from.")
        if len(setting("GMAIL_APP_PASSWORD").replace(" ", "")) != 16:
            problems.append("GMAIL_APP_PASSWORD should be the 16-letter App Password from your Google account.")
    return problems


# ------------------------------------------------------------------ the weekly job

def supplier_note(name, old, new, ch, today):
    age = (today - date.fromisoformat(new.date)).days
    listed = date.fromisoformat(new.date)
    note = f"{name}: list of {listed.day} {listed:%b %Y}"
    if ch:
        note += (f": {len(ch['up'])} up, {len(ch['down'])} down, {len(ch['new'])} new, "
                 f"{len(ch['gone'])} dropped")
    else:
        note += " (first list, nothing to compare yet)"
    if new.rejected:
        note += f", {len(new.rejected)} rows set aside to check"
    if age > 7:
        note += f". No new list for {age} days: ask {name} for this week's prices"
    return note


def run_week(today=None, send_email=True, test=False, client=None, smtp=None):
    """Returns a dict describing what happened. Raises ps.SyncError / deliver.DeliveryError."""
    today = today or date.today()
    ps.LISTS = path_setting("PRICE_LISTS_FOLDER", "price_lists")
    items, sheet_problems = shop.read_sheet(path_setting("SHOP_PRICE_SHEET", "shop/price sheet.xlsx"))
    display = {shop.supplier_folder(i.supplier, {f.name: 0 for f in ps.LISTS.iterdir() if f.is_dir()}): i.supplier
               for i in items}

    latest, previous, pairs, notes, cost = {}, {}, [], [], 0.0
    folders = sorted(f for f in ps.LISTS.iterdir() if f.is_dir()) if ps.LISTS.exists() else []
    for folder in folders:
        files = ps.supplier_lists(folder)
        if not files:
            notes.append(f"{display.get(folder.name, folder.name)}: no price list in the folder yet")
            continue
        new = ps.read_list(files[-1], folder.name, client)
        old = ps.read_list(files[-2], folder.name, client) if len(files) > 1 else None
        cost += new.cost_usd + (old.cost_usd if old else 0)
        latest[folder.name] = new
        if old:
            previous[folder.name] = old
        ch = ps.compare(old, new) if old else None
        pairs.append((folder.name, old, new, ch))
        notes.append(supplier_note(display.get(folder.name, folder.name.replace("-", " ").title()), old, new, ch, today))
    if not latest:
        raise ps.SyncError(f"No price lists found in {ps.LISTS}. Save this week's supplier lists there "
                           "(one folder per supplier, files named like 2026-11-30.pdf).")

    markups, default = shop.parse_markups(setting("MARKUPS"), setting("DEFAULT_MARKUP", "20"))
    results = shop.price_items(items, latest, markups, default, int(setting("ROUND_TO", "10")), previous)
    summary = shop.summary(results)
    unlisted = {}
    for p in results:
        if p.status == "no_list":
            unlisted[p.item.supplier] = unlisted.get(p.item.supplier, 0) + 1
    notes += [f"{name}: NO PRICE LIST in the folder, so its {n} item(s) weren't checked this week. "
              f"Save their list in price_lists and double-click run.bat." for name, n in sorted(unlisted.items())]

    REPORTS.mkdir(exist_ok=True)
    stamp = today.isoformat()
    updates = REPORTS / f"price_updates_{stamp}.xlsx"
    to_check_file = REPORTS / f"to_check_{stamp}.xlsx"
    n_updates = deliver.write_updates(results, updates)
    n_check = deliver.write_to_check(results, latest, sheet_problems, to_check_file)
    (REPORTS / f"changes_{stamp}.txt").write_text(ps.report(pairs), encoding="utf-8")

    shop_name = setting("SHOP_NAME", "Your shop")
    week = f"{today.day} {today:%B %Y}"
    text = deliver.text_body(shop_name, week, results, summary, notes, n_check)
    html_text = deliver.html_body(shop_name, week, results, summary, notes, n_check)
    (REPORTS / f"email_{stamp}.html").write_text(html_text, encoding="utf-8")   # preview without sending

    outcome = {"summary": summary, "updates": n_updates, "to_check": n_check, "cost": cost, "notes": notes,
               "files": [updates, to_check_file], "emailed": [], "refused": []}
    if send_email:
        recipients = emails("TEST_EMAIL_TO") if test else emails("REPORT_TO")
        msg = deliver.build_email(setting("GMAIL_ADDRESS"), recipients, deliver.subject(summary, week, test),
                                  text, html_text, [updates, to_check_file])
        refused = deliver.send(msg, setting("GMAIL_ADDRESS"), setting("GMAIL_APP_PASSWORD"), recipients, smtp)
        outcome["emailed"] = [r for r in recipients if r not in refused]
        outcome["refused"] = refused
    return outcome


# ------------------------------------------------------------------ schedule (Windows)

def install_schedule(run=subprocess.run):
    day = setting("RUN_DAY", "MON").upper()[:3]
    at = setting("RUN_TIME", "07:00").zfill(5)
    command = f'"{sys.executable}" "{Path(__file__).resolve()}" --scheduled'
    if not ON_WINDOWS:
        print(f"Task Scheduler is Windows-only. With cron:  {at[3:]} {at[:2]} * * {DAYS.index(day) + 1} {command}")
        return True
    result = run(["schtasks", "/Create", "/TN", TASK_NAME, "/TR", command, "/SC", "WEEKLY", "/D", day,
                  "/ST", at, "/F"], capture_output=True, text=True)
    if result.returncode != 0:
        print("Windows wouldn't create the weekly task. Right-click setup.bat and choose 'Run as administrator'.")
        log.error(f"schtasks failed: {(result.stderr or result.stdout).strip()}")
        return False
    run(["powershell", "-NoProfile", "-Command", "$s = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries "
         f"-DontStopIfGoingOnBatteries -StartWhenAvailable; Set-ScheduledTask -TaskName '{TASK_NAME}' -Settings $s"],
        capture_output=True, text=True)
    log.info(f"Weekly task installed: {day} {at}")
    print(f"Done. Price List Sync will run every {day} at {at}, even on battery; a missed run happens when the "
          "computer is next on.")
    return True


def remove_schedule(run=subprocess.run):
    if not ON_WINDOWS:
        print("Remove the line from 'crontab -e'.")
        return True
    result = run(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"], capture_output=True, text=True)
    print("The weekly run is off. Run setup.bat to turn it back on." if result.returncode == 0
          else "There was no weekly run to remove.")
    return True


# ------------------------------------------------------------------ command line

def main(argv=None, today=None, client=None, smtp=None):
    p = argparse.ArgumentParser(description="Weekly supplier price check for the shop.")
    p.add_argument("--test", action="store_true", help="email TEST_EMAIL_TO only, subject marked [TEST]")
    p.add_argument("--no-email", action="store_true", help="make the files only")
    p.add_argument("--check", action="store_true", help="check config.env and stop")
    p.add_argument("--install-schedule", action="store_true")
    p.add_argument("--remove-schedule", action="store_true")
    p.add_argument("--scheduled", action="store_true", help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    load_dotenv(CONFIG, override=True)
    if not log.handlers or all(isinstance(h, logging.NullHandler) for h in log.handlers):
        setup_logging()
    trigger = "scheduled" if args.scheduled else "test" if args.test else "manual"
    test = args.test or setting("TEST_MODE", "no").lower() in ("yes", "true", "1")

    if args.remove_schedule:
        return 0 if remove_schedule() else 1
    problems = check_config(send_email=not args.no_email, test=test)
    if problems:
        print("\nPlease fix these in config.env, then try again:\n")
        for n, problem in enumerate(problems, 1):
            print(f"  {n}. {problem}")
        print()
        log.error(f"FAILED - {trigger} | config.env needs fixing: " + " / ".join(problems))
        return 1
    if args.check:
        print(f"\nSettings OK: {setting('SHOP_NAME')} | report to {len(emails('REPORT_TO'))} address(es) | "
              f"every {setting('RUN_DAY', 'MON')} at {setting('RUN_TIME', '07:00')}\n")
        return 0
    if args.install_schedule:
        return 0 if install_schedule() else 1

    started = datetime.now()
    try:
        out = run_week(today, send_email=not args.no_email, test=test, client=client, smtp=smtp)
    except ps.SyncError as err:
        print(f"\nPROBLEM: {err}\n{RESTART}")
        log.error(f"FAILED - {trigger} | {err} | {RESTART}")
        return 1
    except deliver.DeliveryError as err:
        print(f"\nPROBLEM: {err}\nThe report files are in {REPORTS}. {RESTART}")
        log.error(f"FAILED - {trigger} | email not sent: {err} | files saved in reports/ | {RESTART}")
        return 1
    except Exception as err:
        print("\nSomething unexpected went wrong. Nothing was changed. Please send logs\\sync.log to support.")
        log.exception(f"FAILED - {trigger} | unexpected {type(err).__name__}: {err}")
        return 1

    s = out["summary"]
    print("\n" + "\n".join(out["notes"]))
    print(f"\n{s['changed']} items changed cost | {s['below_target']} below target markup | "
          f"{out['to_check']} to check | AI ${out['cost']:.4f}")
    if out["emailed"]:
        print(f"Emailed to: {', '.join(out['emailed'])}")
    for bad in out["refused"]:
        print(f"WARNING: Gmail refused '{bad}'. Check that address in config.env (the others got the email).")
    log.info(f"OK - {trigger} | {s['changed']} cost changes, {s['below_target']} below target, {out['to_check']} to "
             f"check | emailed {len(out['emailed'])}{' (TEST)' if test else ''} | refused {len(out['refused'])} | "
             f"AI ${out['cost']:.4f} | {(datetime.now() - started).seconds}s")
    for bad in out["refused"]:
        log.warning(f"refused address: {bad}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
