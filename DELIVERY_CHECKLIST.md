# Friday delivery checklist (tick every item before sending)

| # | Check | How | Done |
|---|---|---|---|
| 1 | Runs without errors on a clean test run | Fresh folder on the client's PC, then `setup.bat`, then `run.bat`. The log shows `OK` | ☐ |
| 2 | The correct report arrives in **all 3** managers' inboxes, on a computer **and** a phone | `send test email.bat` with TEST_EMAIL_TO = the 3 addresses, then switch TEST_MODE=no | ☐ |
| 3 | The numbers match the clerk's own comparison for last week | Sit with the clerk for 15 minutes | ☐ |
| 4 | The weekly task exists: Monday 07:00, battery allowed | `schtasks /Query /TN "Price List Sync" /V /FO LIST` | ☐ |
| 5 | READ ME FIRST is accurate and a non-technical person can follow it | The observer session (OBSERVER_NOTES.md) is done and the top 3 fixes made | ☐ |
| 6 | Walkthrough video recorded and uploaded (Loom or Win+G, 3 to 5 minutes) | Script: WALKTHROUGH_SCRIPT.md | ☐ |
| 7 | config.env has the client's real addresses, and **TEST_MODE=no** | Open it and read every line | ☐ |
| 8 | No test data left in their folders | `price_lists/` has only real lists; `reports/` and `logs/` are empty | ☐ |
| 9 | Invoice ready and sent **with** the delivery | INVOICE.md: KES 12,500 balance | ☐ |
| 10 | Mon 7 Dec 07:00: first automatic run checked | Read logs/sync.log remotely or ask for the email | ☐ |
