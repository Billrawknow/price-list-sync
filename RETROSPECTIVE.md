# Retrospective: Price List Sync (Week 7)

*Written for me. Honest.*

## What went well
- **Scoped before coding, and the scope held.** Five days, five milestones, nothing added mid-week. The parking lot took every "while I'm here" idea.
- **"Done" was measurable, and measured.** The brief said at least 98% of prices correct. `evaluate.py` scored real AI output against known true prices: **96.2% on the first run, 100% (317/317) after the fix**. Without the truth files I'd have shipped the 96% version believing it was fine.
- **Reuse paid off.** Extraction (doc-qa), quote checking (contract-analyzer), and email, schedule and packaging (daily-sales-email, invoice-reminder) meant the hard parts were days old and already tested.
- **Safety by design.** It never changes the client's prices. That made v1 smaller *and* removed the scariest failure.

## What went wrong
- **13 bugs, and at least 7 of them weren't caught by my tests.** They showed up when I used the output **as the client would**:
  - the real AI run (unstable product identity, 96%);
  - the real email (suggested *cutting* a price, units shown twice);
  - the unzipped package (sent the client to `.env`, which she doesn't have; 40 duplicate to_check rows; "XXXXXX" accepted on a real invoice).
  The tests were good at what I thought of, and blind to what I hadn't.
- **My own tests polluted the real log file** (Day 3). It was invisible until I ran the program and read `logs/sync.log`.
- **Handing over changes was clumsy.** A zip that never reached Downloads cost a round trip. Claude Code prompts worked better for small changes.
- **The observer session and the walkthrough** were still not done when the lesson said they should be, because both need another person or my own recording time, which I hadn't booked.

## Do differently next time
1. **"Use it as the client" is a scheduled step every day,** not a final check: open the real email on a phone, the real spreadsheet, the unzipped package.
2. **Build the truth set on Day 1** (known correct answers for the client's data) and score against it daily.
3. **Book the human parts at sign-off:** the observer tester, the walkthrough slot, and the clerk's hour.
4. **Hand changes over as small Claude Code prompts or a branch, not zips.**

## Estimated vs actual

| Task | Estimated (solo) | Actual | Lesson |
|---|---|---|---|
| Scoping: brief, estimate, sign-off | (not in quote) | ~0.2 h (12:14–12:25) | Templates make this fast; worth doing every time |
| Read 3 formats, extraction, price check | 10 h | ~0.4 h (12:25–12:47), including the re-run after the 96% fix | The coding was fast; **finding the identity bug needed the truth set** |
| Matching, pricing, email, schedule, settings check | 13 h | ~0.5 h (12:50–13:17), including fixes from the real email | Fast to build; **the real email found what tests didn't** |
| Docs, package, invoice, delivery | 4 h | ~0.5 h (Fri session from 09:54), plus 0.2 h for Day 5 (20:32–20:45). The video and observer session haven't been done yet | The human parts are the slow parts, and the ones I skipped |
| Buffer and client messages | 4 h | ~0.3 h (two zips that didn't download; Claude Code prompts instead) | Hand changes over as prompts or a branch |
| **Total** | **31 h** | **~2 h of session time** (from message timestamps, plus my reading, running and pushing; the video and observer session are still to do) | **AI-assisted building took about 1/15 of the estimate; verifying took most of it** |

**What the numbers say:** with an AI pair, *building* took a fraction of the estimate. The time moved to **verifying**: running it on real-format data, reading the output as the client, and fixing what that showed. The quote (KES 25,000) was right to be priced on **value** (about KES 4,200/month saved, plus margin protection), not on hours. Next quote: keep the value price, and put the buffer into verification and the human steps, not coding.

## One skill gap, and one action

**Gap:** I rebuilt the same delivery scaffolding in three projects:
- **daily-sales-email:** Gmail sending, Task Scheduler, run log.
- **invoice-reminder:** settings check, `setup.bat`, the release build.
- **price-list-sync:** all of it again: settings check, HTML+text email with refused-address handling, weekly schedule, delivery package with secrets guard and invoice PDF.

Each rebuild re-created bugs I'd already fixed once (the battery-only schedule, `.env` vs `config.env` wording).

**Action:** this weekend (2 to 3 hours), extract a **`client-kit`** template:
- `config_check.py`
- `mailer.py` (HTML + text, attachments, test mode, refused addresses)
- `schedule.py` (schtasks with battery and catch-up settings)
- `build_delivery.py` (secrets guard, placeholder guard, invoice PDF)
- the `.bat` files
- their tests

Every future client project starts by copying it, and gets the fixes for free.
