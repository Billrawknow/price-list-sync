# Friday delivery checklist (tick every item before sending)

| # | Check | How | Done |
|---|---|---|---|
| 1 | All tests pass | `pytest -q`: 78 passed | ☐ |
| 2 | The package builds as **final**, not draft | `python build_delivery.py --whatsapp … --kra-pin … --payment …` (it refuses XXX or [placeholders]) | ☐ |
| 3 | The package runs on a clean computer | Unzip on the shop PC, `setup.bat`, `run.bat`; the log shows `OK` | ☐ |
| 4 | The correct report arrives in **all 3** managers' inboxes, on a computer and a phone | `send test email.bat` with TEST_EMAIL_TO = the 3 addresses, then TEST_MODE=no | ☐ |
| 5 | The numbers match the clerk's own comparison for last week | 15 minutes with the clerk | ☐ |
| 6 | The weekly task exists: Monday 07:00, battery allowed | `schtasks /Query /TN "Price List Sync" /V /FO LIST` | ☐ |
| 7 | The README is accurate and a non-technical person can follow it | Observer session done, top 3 fixes made (OBSERVER_NOTES.md) | ☐ |
| 8 | Walkthrough recorded, **under 3 minutes**, in the package | `docs/walkthrough.mp4`, then rebuild; the build no longer says "Missing: walkthrough" | ☐ |
| 9 | config.env on the shop PC has the real addresses, and **TEST_MODE=no** | Read every line | ☐ |
| 10 | Invoice sent **with** the delivery | `delivery/invoice.pdf`, KES 12,500 balance | ☐ |
| 11 | Mon 7 Dec 07:00: first automatic run checked | Ask Grace for the email, or check `logs/sync.log` | ☐ |
