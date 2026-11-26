# Estimate: how the price was worked out (internal, not sent to the client)

Price is checked two ways: **cost to build** (hours × rate) and **value to the client** (what it saves). The quote must clear the first and sit well under the second.

## 1. Hours

| Task | Day | Hours | Reuses |
|---|---|---|---|
| Check sample data, read 3 formats, project setup | Mon | 4 | doc-qa extraction |
| Extraction prompt and schema, the price check, tests | Tue | 6 | contract-analyzer (forced tool output, quote check) |
| Product matching (codes, then table, then suggestions), cost comparison, markup pricing | Wed | 5 | |
| Matching session with the clerk | Wed | 1 | |
| Email report (HTML and Excel), config.env, schedule, error handling | Thu | 5 | daily-sales-email, invoice-reminder |
| Re-run 4 weeks, edge cases, fresh-machine test | Thu | 2 | |
| Install, guide, handover | Fri | 4 | invoice-reminder release build |
| Client messages, sign-off, buffer for surprises (about 15%) | all | 4 | |
| **Total** | | **31 h** | |

**Cost floor:** 31 h × KES 750/h = **KES 23,250**. The quote of KES 25,000 covers it.

Without the earlier projects to reuse, this would be about 45 hours (KES 33,750). Reuse is what makes a 5-day timeline and this price realistic.

## 2. Value to the client

| Saving | Per month |
|---|---|
| Clerk time: about 3.5 h × 4 Mondays = 14 h at KES 300/h | KES 4,200 |
| Margin protection: one missed cement increase (KES 30 × 50 bags × 3 days) | about KES 4,500 each time |
| Fewer typing errors and disputes | not counted |

**Payback:** about 6 months on time alone, much sooner if it catches even one late price rise. KES 25,000 is under 6 months of savings, which is easy to justify to a small business owner.

## 3. Running cost (paid from the support fee)

About 900 rows a week means about 30,000 input tokens and 15,000 output tokens a week on Claude Haiku 5.5, so about $0.01 a week. Even allowing for retries and re-runs, that's **under KES 100/month**, against a support fee of KES 2,500/month.

## 4. Assumptions behind the estimate

- **All 3 suppliers send text-based PDFs or Excel files.** A scanned supplier adds about 6 hours (OCR plus extra checking), quoted at KES 5,000.
- **No more than 1,000 supplier rows a week.**
- **The clerk is available as booked.** Each lost session moves a milestone by half a day.
