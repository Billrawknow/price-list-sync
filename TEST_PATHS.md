# Every user path, tested (Day 3)

Every row is an automated test in `tests/test_week.py` (65 tests in total, all passing). The email is faked, so no messages are sent.

| Path | Test | Result |
|---|---|---|
| **Normal** | Run on the 23 Nov price lists against the shop's 48-item price sheet | **PASS.** 14 cost changes, 13 items below target markup, 3 to check. The email has an HTML version, a plain-text version and 2 spreadsheets |
| Normal | Numbers are right | **PASS.** Cement 42.5N bulk: cost 755 to 785, sells at 850, suggested 880 (785 × 1.12 = 879.2, rounded up to 10) |
| Normal | Supplier without codes (Kapsoit) | **PASS.** Tank 5000L matched by its printed description: 41,500 to 43,900, suggested 54,880 |
| Normal | Item already too cheap before any change | **PASS.** Door lock 4-lever flagged, email says "cost unchanged" |
| **More than 3 recipients** | 6 addresses in REPORT_TO | **PASS.** All 6 get it |
| **Test mode** | `send test email.bat` | **PASS.** Only TEST_EMAIL_TO, subject starts `[TEST]` |
| **Wrong email: typo** | `manager@gmial.com`, `grace.mlimani.co.ke` | **FIXED:** caught *before* running ("Did you mean @gmail.com?", "isn't a valid email address"), nothing sent |
| **Wrong email: address doesn't exist** | Gmail refuses one of 3 | **PASS.** The other 2 still get it, and the bad address is named on screen and in the log |
| Wrong email: all refused | The only address doesn't exist | **PASS.** "Gmail refused every address… check REPORT_TO" |
| **Wrong Gmail password** | Login refused | **PASS.** "Email login failed. Check… the 16-letter GMAIL_APP_PASSWORD" |
| **No internet** | Email can't connect | **PASS.** Logged with restart steps, and the files are still saved in reports/ |
| **Empty week** | No price lists in the folder | **PASS.** "No price lists found… save this week's supplier lists there" |
| **Supplier sent nothing new** | Run 3 weeks after the last list | **PASS.** "No new list for 21 days: ask Kapsoit Plumbing for this week's prices" |
| **Shop sheet problems** | Wrong path; a cost cell that says "ask Grace" | **PASS.** The setting is named; the bad row is listed in to_check and the other 47 are priced |
| **Product not found** | Dropped by supplier / code typo `HWR-11O` / different wording | **PASS.** "No longer on the supplier's list (was 6,695)" / "Did you mean HWR-110…" / "Did you mean Kitchen sink single bowl…". Never guessed |
| **Settings mistakes** | Time `7am`, day `Someday`, a normal password, `Cement=12`, no AI key | **PASS.** Each named with its config.env line |
| **No-email mode** | `--no-email` with no Gmail set | **PASS.** Files only |
| **Unexpected crash** | Forced error inside pricing | **PASS.** Calm message, full details in logs/sync.log only |
| **Schedule** | RUN_DAY=Monday, RUN_TIME=7:00 | **PASS.** Weekly task for MON 07:00, works on battery, catches up if missed |

## Bugs found and fixed today

1. **Tests were writing into the real `logs/sync.log`.** A support check on the client's machine would have read test noise. Tests now log to a temporary folder, and a test guards it.
2. **Bad suggestions for unmatched items.** Marine board suggested "fascia board"; it was actually dropped by the supplier. `HWR-11O` (letter O) suggested the wrong tier. Now dropped items are recognised from last week's list, and code typos (O/0, I/1) are checked first.
3. **The email showed "1,890 → 1,890"** for items that were already priced too low. It now says "unchanged 1,890". Supplier dates now read "23 Nov 2026", not "2026-11-23".

4. **From the first real email:** cost-down rows suggested cutting prices. They now keep the current price and note the lowest fair price. Percentages show one decimal, and the to_check suggestions say exactly what to change.

## Checked by breaking it

- Removing the plain-text part of the email makes the email test fail.
- Disabling the typo check makes the wrong-email test fail.
