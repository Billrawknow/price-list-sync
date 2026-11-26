# Progress notes

## Day 2: Core built (Thursday 26 November 2026, build-week Day 2 of 5)

**Core feature:** supplier price list in, a *checked* list of what changed since last week out.
Matching to the shop's products, markup pricing, email and the schedule are deliberately not
started (see PARKING_LOT.md).

**What works**
- **Reads all 3 suppliers' formats:**
  - Rift Valley: coded PDF table, 3 pages, about 114 rows.
  - Kapsoit: PDF with no codes, grouped by category, "Ksh 1,480.00".
  - Sunrise: Excel with title rows above the header.
- **AI only where it's needed:**
  - PDFs are read page by page by Claude into a fixed schema.
  - Excel is read directly by code: free, exact and instant.
- **The price check (plain code):** a PDF price is only used if one printed line holds both that product and that exact price.
- **Comparison against last week:** up, down, new, no longer listed, and unchanged.
- **Plain-text report**, with the biggest increases first and a "to check by hand" section.
- **Each list is read once** and cached by file fingerprint, so the AI cost isn't repeated.
- **21 tests pass.** The sample-data report matches the known changes exactly: Rift Valley 18 up, 3 down, 6 new, 3 gone; Y12 bar 1,130 to 1,175. Disabling the price check makes 4 tests fail.
- **A real CLI run on the Excel supplier** reported Emulsion 20L +250, Emulsion 4L +45 and Thinner −70, which are the known changes.

**Not proven yet**
- **Real AI accuracy on the PDFs.** `evaluate.py` scores it against the true prices, but it needs a run with the API key. The scoring itself is validated: a perfect reader gets 317/317.

**What changed (things found by testing as I built)**
1. **The sample generator shifted supplier codes when new products were added,** so CEM-016 meant a different product each week. Real suppliers keep codes stable, and code-based comparison depends on it. Fixed.
2. **The price check had two holes:**
   - a price of 20 "matched" the 20 in "PPR elbow 20mm";
   - "elbow 25mm" could be checked against the "elbow 20mm" line.
   Now prices must stand alone, and size words (20mm, 1/2, 4L) must match exactly. Both cases are tested.
3. **A cut-off AI answer would have made the products it missed look "no longer listed".** Now it stops with a clear message instead.
4. **A product that fails the check this week is no longer reported as "gone".** It's unknown, so it goes to "to check".
5. **A supplier printing the same code twice with two prices:** both rows are set aside, because neither can be trusted.

**First real run with the AI (evaluate.py):**

```
kapsoit-plumbing                 2026-11-16     30     24      6       6      0    80.0%
kapsoit-plumbing                 2026-11-23     30     24      6       6      0    80.0%
rift-valley-building-supplies    2026-11-16    111    111      0       0      0   100.0%
rift-valley-building-supplies    2026-11-23    114    114      0       0      0   100.0%
sunrise-paints-hardware          2026-11-16     16     16      0       0      0   100.0%
sunrise-paints-hardware          2026-11-23     16     16      0       0      0   100.0%
Overall: 305/317 correct = 96.2% | FAIL
```

**Diagnosis:** 0 set aside means every Kapsoit price passed the check and is really printed next to its product, so no wrong price was used. The "6 wrong + 6 missed" are the same 6 rows worded differently from the truth file. **But the cause is a real bug, not just a scoring issue.** Kapsoit prints no product codes, so products were recognised by Claude's description and unit, and the AI's wording can change from one run to the next. In the weekly comparison that would show a product as both "new" and "no longer listed".

**Fix:** a product without a code is now recognised by **the text printed before its price** on the PDF line the price check already finds. That's the same every week, whatever words the AI uses. The evaluator identifies true rows the same way, and now lists every row that doesn't line up (wrong price / not on list / missed / set aside), so a failure explains itself.

**Also:**
- **Saved results are versioned,** so lists cached in the old format are re-read once.
- **Tests: 24.** The new ones reword the AI's answer between weeks and assert the report still shows only the 4 real Kapsoit changes. With the old identity rule restored, they fail.

**Re-run after the fix (real AI, `evaluate.py --fresh`):**

```
kapsoit-plumbing                 2026-11-16     30     30      0       0      0   100.0%
kapsoit-plumbing                 2026-11-23     30     30      0       0      0   100.0%
rift-valley-building-supplies    2026-11-16    111    111      0       0      0   100.0%
rift-valley-building-supplies    2026-11-23    114    114      0       0      0   100.0%
sunrise-paints-hardware          2026-11-16     16     16      0       0      0   100.0%
sunrise-paints-hardware          2026-11-23     16     16      0       0      0   100.0%
Overall: 317/317 correct = 100.0%, 0 wrong prices used | AI cost $0.0078
PASS: meets the brief (>= 98% correct, no wrong price used)
```

**The changes report matches every known change:**
- Kapsoit: 3 up, 1 down, 0 new, 0 no longer listed.
- Rift Valley: 18 up, 3 down, 6 new, 3 no longer listed.
- Sunrise: 2 up, 1 down.

**Report polish from reading the real output:** the AI sometimes copies the unit into the description, which printed as "PPR pipe 20mm x 4m length (length)", and long labels were cut mid-word ("...10+ sheet (shee"). The unit is now shown once, and labels are shortened at a whole word with "…". There are 4 label tests (28 tests in total). One of them caught a further bug: a cut that landed exactly at a word's end dropped that word.

**Status: Day 2 milestone met** (the brief: "every row of one full week's price lists extracted and checked, at least 98% correct").

**Tomorrow (Day 3, per the brief):** match supplier items to the shop's price sheet (code first, then the matching table, then suggestions), apply markup rules, and flag below-margin items. Then compare against a manual comparison.

---

## Day 3: Completed and tested (Thursday 26 November 2026)

**Added, hardest first**
1. **Matching and pricing (`shop.py`):** each of the shop's 48 stocked items is matched to this week's supplier price, by supplier code, or for Kapsoit by the description printed in their PDF. The suggested selling price uses the category markup, rounded up to KES 10. Items selling below target are flagged first, biggest shortfall at the top. Unmatched items get a reason and a suggestion, never a guess:
   - "no longer on the supplier's list (was 6,695)"
   - "did you mean HWR-110 …?" for the code typo `HWR-11O`
   - "did you mean Kitchen sink single bowl?"
2. **Email (`deliver.py`):** an HTML report with a **plain-text version in the same email** (the fallback), plus `price_updates.xlsx` and `to_check.xlsx` attached, to **any number** of addresses. A refused address doesn't stop the others. There's a test mode (`send test email.bat`) that sends only to TEST_EMAIL_TO, marked [TEST].
3. **Settings check (`config.env`):** every mistake is named with its line, before anything runs. It catches typos like `@gmial.com` ("Did you mean @gmail.com?"), bad markups, times and days, a wrong price sheet path, and a missing key or App Password.
4. **Weekly schedule:** Monday 07:00 via Task Scheduler, works on battery, catches up if missed. Plus `logs/sync.log`, with **restart instructions in every error line**.
5. **Client files:** `setup.bat`, `run.bat`, `send test email.bat`, `remove_schedule.bat`, and `READ ME FIRST.txt` (numbered steps, no jargon).

**Results on the sample week:** 14 of 48 items changed cost, **13 now sell below target markup**, and 3 need checking. The top item is the 5000L tank: cost 41,500 to 43,900, sells at 51,880, suggested 54,880. The email reads well on a phone with no sideways scrolling.

**Tests:** 63 passing (28 core, 35 Day 3). Every user path is in TEST_PATHS.md. Breaking the plain-text fallback or the typo check makes tests fail.

**Bugs found and fixed today**
1. **Tests were writing into the real `logs/sync.log`.** That would have polluted the client's log. Fixed, and a test guards it.
2. **Wrong suggestions** ("fascia board" for a dropped marine board; the wrong tier for the HWR-11O typo).
3. **The email said "1,890 → 1,890"** for items that were already too cheap, and showed dates as 2026-11-23.

**What doesn't work yet or isn't proven**
- **The real Gmail send hasn't been tried yet.** Needs the user's App Password: run `send test email.bat`.
- **The observer session isn't done yet.** It needs a real person (OBSERVER_NOTES.md).
- **The walkthrough video isn't recorded yet** (WALKTHROUGH_SCRIPT.md).

**Tomorrow (Day 4/5):** observer session, top 3 fixes, video, delivery checklist, invoice.
