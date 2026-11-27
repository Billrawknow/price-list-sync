# Price List Sync: Week 7 client project

**Status: Day 4 done. Delivery package built and tested: 78 tests. The delivered folder runs on its own.**

Every Monday at 7:00 am, Price List Sync reads a hardware shop's supplier price lists (PDF and Excel). It checks every price against the original document, matches each item to the shop's own price sheet, and emails the owner and managers what to reprice, with the suggested selling price at the shop's markup. A person approves every change.

AI Masterclass 2, Week 7 (Client Project). The client is simulated: Mlimani Hardware & Building Supplies is a fictional Kericho shop.
- **Day 1:** scoping (brief, estimate, sign-off).
- **Day 2:** the core, verified on real AI output at 317/317 prices correct.
- **Day 3:** completing and testing.
- **Day 4:** documentation and the delivery package.

**For the client:** [client/README.md](client/README.md), with numbered steps, double-clicks only, and the 5 handover questions answered.

## Day 4: the delivery package

```bash
python build_delivery.py --whatsapp "07.. ... ..." --kra-pin P05........ --payment "M-Pesa ... | Bank ..."
python build_delivery.py --draft            # placeholders allowed, everything marked DRAFT
```

```
delivery/
  Price List Sync/              what the client copies to Documents
    sync.py, pricesync.py, shop.py, deliver.py
    setup.bat, run.bat, send test email.bat, remove_schedule.bat
    config.env.example          they fill in their own copy in setup
    README.md                   client guide (Notepad-friendly)
    requirements.txt            4 packages only (no test tools)
    price_lists/  shop/         their supplier lists and price sheet
    logs/  reports/             empty: filled when it runs
  walkthrough.mp4               under 3 minutes (docs/walkthrough.mp4, once recorded)
  invoice.pdf                   balance KES 12,500
  Price List Sync - delivery.zip
```

**Guards built into the build:**
- **No secrets ever ship.** `config.env`, `.env` and `delivery.env` anywhere in the package make the build refuse.
- **No developer files ship:** tests, sample truth files, the evaluator and caches stay out.
- **Placeholders block a final build.** Your WhatsApp number, KRA PIN and payment details go in at build time (never into the public repo), and "XXX" or "[...]" left in any of them means no final build.
- **The client README has no typed commands** (a test fails if `pip`, `python`, `.py`, "Command Prompt" and similar appear in it). It has numbered setup steps and answers the 5 handover questions.
- **The delivered zip runs on its own** when unzipped somewhere new (tested).

| Day 4 file | What it is |
|---|---|
| `client/README.md` | The client's guide |
| `build_delivery.py` | Builds the package, the invoice PDF and the zip |
| `DELIVERY_MESSAGE.md` | The delivery email and a short WhatsApp version |
| `WALKTHROUGH_SCRIPT.md` | Under-3-minute video script, timed |
| `HANDOVER_QA.md` | The 5 handover questions and answers |
| `DELIVERY_CHECKLIST.md` | 11 checks before sending |
| `tests/test_delivery.py` | 11 tests for the package |

## Run it (developer)

```bash
pip install -r requirements.txt
pytest -q                                   # 78 tests, no API key or email needed
cp config.env.example config.env            # add ANTHROPIC_API_KEY, Gmail App Password, REPORT_TO
python sync.py --check                      # settings check
python sync.py --no-email                   # makes reports/: price_updates, to_check, changes, email preview
python sync.py --test                       # emails TEST_EMAIL_TO only, subject [TEST]
python sync.py                              # the real thing (what the Monday schedule runs)
python sync.py --install-schedule           # Monday 07:00, Windows Task Scheduler
```

## Day 3: the complete tool

```
price_lists/<supplier>/<date>.pdf|.xlsx        shop/Mlimani price sheet.xlsx        config.env
        |                                              |                                |
   pricesync.py  read + check every price        shop.py  match each stocked item      sync.py  settings check,
   (Day 2 core, 317/317)                         to this week's supplier price,        weekly job, log, schedule
        |                                        price it at the category markup             |
        +------------------------------------------+------------------------------------------+
                                                   |
                                     deliver.py  price_updates.xlsx + to_check.xlsx
                                     + email: HTML with a plain-text version, to any number of addresses
```

**On the sample week:** 14 of the shop's 48 items changed cost, **13 now sell below target markup**, and 3 need checking:
- one dropped by the supplier;
- one code typo in the shop's sheet (`HWR-11O`, letter O for zero), with the fix suggested;
- one worded differently from the supplier's list.

The top item: **5000L tank, cost 41,500 to 43,900, sells at 51,880, suggested 54,880.**

| Day 3 file | What it is |
|---|---|
| `sync.py` | The program the client runs: settings check, weekly job, log, schedule, test mode |
| `shop.py` | Reads the price sheet, matches items, prices them, suggests fixes |
| `deliver.py` | The two spreadsheets and the email (HTML + plain text) |
| `config.env.example` | Every setting, with plain notes on each line |
| `setup.bat`, `run.bat`, `send test email.bat`, `remove_schedule.bat` | Double-click files |
| `client/README.md` | Client guide (shipped as README.md in the package) |
| `TEST_PATHS.md` | Every user path and its result |
| `OBSERVER_NOTES.md` | Template for watching someone use it without help |
| `BACKLOG.md` | What I'd fix with one more day |
| `HANDOVER_QA.md` | 5 likely client questions, answered |
| `DELIVERY_CHECKLIST.md`, `INVOICE.md`, `WALKTHROUGH_SCRIPT.md` | For Friday |
| `tests/test_week.py` | 35 tests: matching, pricing, email, and every user path |

---

## Day 2: the core

**One feature, working:** a supplier price list goes in, and a *checked* list of what changed since last week comes out.

```
price_lists/<supplier>/<date>.pdf|.xlsx
  [1] read     PDF: Claude, page by page, into a fixed schema · Excel: read by code (no AI, free)
  [2] check    plain code: a PDF price is used only if one printed line holds that product AND that exact price
               (a price of 20 can't "match" the 20 in "20mm", and elbow 25mm can't borrow elbow 20mm's line)
  [3] compare  vs the previous list from the same supplier: up / down / new / no longer listed
  [4] report   reports/changes_<date>.txt: biggest increases first, failed rows under "to check by hand"
```

### Run it

```bash
pip install -r requirements.txt
python make_samples.py                      # (optional) rebuild the simulated client data
pytest -v                                   # 28 tests, no API key needed
python pricesync.py --supplier sunrise-paints-hardware   # Excel supplier: no API key needed

cp .env.example .env                        # add ANTHROPIC_API_KEY for the PDF suppliers
python evaluate.py                          # accuracy vs the true prices: must be at least 98%, 0 wrong prices
python pricesync.py                         # all 3 suppliers: the changes report
```

### First real run: a bug found and fixed

`evaluate.py` scored Kapsoit (the supplier with no product codes) at 80%: the prices were right, but 6 products were worded differently by the AI. In the weekly comparison that would have shown products as both "new" and "no longer listed". Products without codes are now recognised by **the text printed before the price in the PDF**, which is stable every week, not by the AI's wording. **Re-run: 317/317 correct (100%).** Details are in [PROGRESS.md](PROGRESS.md).

### Client data (simulated)

There are two weeks of price lists from 3 suppliers, each in its own format:
- **Rift Valley Building Supplies:** a coded PDF table, about 114 rows.
- **Kapsoit Plumbing:** a PDF with no codes, grouped by category, prices like "Ksh 1,480.00".
- **Sunrise Paints & Hardware:** Excel, with title rows above the header.

`samples/truth/` holds the exact true rows, so accuracy is **measured**, not eyeballed. The known week-2 changes for Rift Valley are 18 up, 3 down, 6 new and 3 discontinued, and the tests check the report finds exactly these.

### Day 2 files

| File | What it is |
|---|---|
| `pricesync.py` | The core: read, check, compare, report, with each list cached so it's read once |
| `evaluate.py` | Scores real AI extraction against `samples/truth/` (the brief's 98% criterion) |
| `make_samples.py` | Builds the simulated price lists and their truth files |
| `tests/test_core.py` | 28 tests: the lesson's checks, plus misread prices, invented products, swapped sizes, cut-off answers, duplicates, scans, caching, and AI rewording (found in the first real run) |
| `PROGRESS.md` | End-of-day progress note |
| `PARKING_LOT.md` | What I'm *not* building this week |
| `CLIENT_UPDATE.md` | Mid-week update message to the client |

---

## Day 1: scoping

The brief, estimate and sign-off were written before a line of code.

## The project in one paragraph

A hardware shop's clerk spends 3 to 4 hours every Monday retyping 3 suppliers' PDF price lists into the shop's price sheet, and late updates mean selling below margin. **Price List Sync** reads the price lists, extracts every price with Claude, **checks each price against the original document in plain code**, matches items to the shop's products, and emails the owner a "what changed and what to reprice" report plus an update spreadsheet, every Monday at 7:00 am. A person approves every price change.

**Price:** KES 25,000 build + KES 2,500/month support · **Timeline:** 5 days · **Payback:** about 6 months on time saved, sooner with margin protection

## Files

| File | For | What it is |
|---|---|---|
| [PROJECT_BRIEF.md](PROJECT_BRIEF.md) | Client | The brief: problem in numbers, solution, in and out of scope, deliverables, **acceptance criteria**, daily milestones, risks, price, and what the client must provide |
| [SIGN_OFF_EMAIL.md](SIGN_OFF_EMAIL.md) | Client | The email asking for "Confirmed", the first payment and the sample data before Monday |
| [ESTIMATE.md](ESTIMATE.md) | Me | How the price was worked out: 31 hours × KES 750 (cost floor) against KES 4,200+/month saved (value), plus API running cost |
| [CHANGE_REQUESTS.md](CHANGE_REQUESTS.md) | Both | The log that keeps scope creep out of the 5-day build, with pre-quoted add-ons |

## Scoping decisions worth noting

- **"Done" is measurable.** There are 6 acceptance criteria. For example: at least 98% of rows extracted correctly on 4 real weeks of price lists, **zero prices that aren't in the source**, and the clerk can run it alone.
- **The biggest risk is tested first.** Unreadable or scanned price lists are checked on Day 1 with real samples requested before Monday, not discovered on Thursday.
- **Safety by design.** The tool never changes prices by itself, which also keeps v1 small.
- **Out of scope is written down and pre-quoted:** OCR, reading email or WhatsApp, and writing to the POS. Saying "not in this version, here's the price" is easier with a list.
- **The estimate is built on reuse.** Extraction comes from `doc-qa`, the quote check and structured output from `contract-analyzer`, and email and scheduling from `daily-sales-email` and `invoice-reminder`. Without them it would be about 45 hours and wouldn't fit 5 days.

## Plan (Days 2 to 5)

| Day | Milestone |
|---|---|
| Mon 30 Nov | Real data in, and Python reads all 3 suppliers' formats |
| Tue 1 Dec | Extraction and price check, at least 98% on one week |
| Wed 2 Dec | Matching, comparison and markup pricing; matches the clerk's manual comparison |
| Thu 3 Dec | Email, 7:00 am schedule, re-run 4 weeks, edge cases |
| Fri 4 Dec | Install, guide and handover; first automatic run Mon 7 Dec |
