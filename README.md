# Price List Sync: Week 7 client project

**Status: scoped, awaiting client sign-off.** The build runs from Monday 30 November to Friday 4 December 2026.

AI Masterclass 2, Week 7 (Client Project), Day 1: **Scoping.** No code yet, by design: this repo holds the scope, the estimate and the sign-off, written before a line of code. The client is simulated: Mlimani Hardware & Building Supplies is a fictional Kericho hardware shop, used across my earlier projects.

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

## Next (Days 2 to 5)

| Day | Milestone |
|---|---|
| Mon 30 Nov | Real data in, and Python reads all 3 suppliers' formats |
| Tue 1 Dec | Extraction and price check, at least 98% on one week |
| Wed 2 Dec | Matching, comparison and markup pricing; matches the clerk's manual comparison |
| Thu 3 Dec | Email, 7:00 am schedule, re-run 4 weeks, edge cases |
| Fri 4 Dec | Install, guide and handover; first automatic run Mon 7 Dec |
