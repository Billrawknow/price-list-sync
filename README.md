# Price List Sync: Week 7 client project

**Status: Day 2 done. Core built, tested, and verified on real AI output: 317/317 prices correct (100%), 0 wrong prices, $0.0078.** See [PROGRESS.md](PROGRESS.md).

AI Masterclass 2, Week 7 (Client Project). The client is simulated: Mlimani Hardware & Building Supplies is a fictional Kericho hardware shop, used across my earlier projects.
- **Day 1:** scoping (brief, estimate, sign-off).
- **Day 2:** the core feature.

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

`evaluate.py` scored Kapsoit (the supplier with no product codes) at 80%: the prices were right, but 6 products were worded differently by the AI. In the weekly comparison that would have shown products as both "new" and "no longer listed". Products without codes are now recognised by **the text printed before the price in the PDF**, which is stable every week, not by the AI's wording. Details are in [PROGRESS.md](PROGRESS.md).

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
