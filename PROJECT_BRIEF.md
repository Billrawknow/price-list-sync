# Project Brief: Price List Sync

**Prepared for:** Mlimani Hardware & Building Supplies, Temple Road, Kericho *(simulated client for AI Masterclass 2, Week 7)*
**Prepared by:** Bildad Ronoh, Rawknow Company Ltd · bildadronoh@gmail.com
**Date:** Thursday 26 November 2026 · **Version:** 1.0, awaiting client sign-off

---

## At a glance

| | |
|---|---|
| **Client** | Mlimani Hardware & Building Supplies, Kericho: about 400 stock lines, 3 regular suppliers, 1 accounts clerk |
| **Problem** | Every Monday the clerk spends **3 to 4 hours** retyping supplier price lists into the shop's price sheet. When a supplier's price rises and the update is missed or delayed, the shop **sells below its margin** until someone notices |
| **Solution** | A Python tool that reads the suppliers' PDF and Excel price lists, extracts every price with AI, **checks each price against the original document**, matches items to the shop's product list, and emails the owner a report of what changed and what to reprice, plus a file to update the price sheet. It runs automatically every Monday at 7:00 am |
| **Deliverables** | Working tool on the shop computer, settings file, product-matching table, 1-page user guide, 30-minute handover session |
| **Timeline** | 5 days: Monday 30 November to Friday 4 December 2026. First automatic run: Monday 7 December |
| **Price** | **KES 25,000** one-time build + **KES 2,500/month** support (optional) |

---

## 1. The problem, in numbers

- **3 suppliers** send price lists by email every week or two: building materials (cement, steel, roofing), plumbing, and paint and hardware. Together that's about **900 lines**, of which the shop stocks about **400**.
- **3 to 4 hours every Monday:** the clerk opens each PDF, finds the items the shop stocks, compares them with last week's prices, and types the changes into `Mlimani price sheet.xlsx`. That's about **14 hours a month**.
- **Margin leaks:** a missed or late update means selling at the old price. One example: if cement rises KES 30 a bag and the shop sells 50 bags a day, a 3-day delay costs **KES 4,500** on that one item.
- **Typing errors:** a wrong digit (1,130 typed as 1,310, or as 113) has caused at least one customer dispute this year.

## 2. The solution

Every Monday at 7:00 am, without anyone touching it:

1. **Collect:** read every price list saved this week in the `Price lists` folder (PDF or Excel).
2. **Extract:** Claude reads each list and returns every product row as structured data: supplier code, description, unit and price.
3. **Check:** plain code (not AI) confirms that **every extracted price appears in the original document** next to that product. Rows that fail are listed for a person to look at, and are never used.
4. **Match:** each supplier item is matched to the shop's own product, first by supplier code, then by an agreed matching table built with the clerk in week 1. New or unclear items are listed with a suggested match for the clerk to confirm. Nothing is guessed silently.
5. **Compare and price:** new cost against last week's cost. The suggested selling price comes from the shop's markup rules per category (for example cement +12%, paint +25%). **Items now selling below their target margin are flagged first.**
6. **Deliver:**
   - **Email** to the owner and 2 managers: "Price changes this week", with increases at the top and below-margin items highlighted.
   - **`price_updates_YYYY-MM-DD.xlsx`:** the changed items with old cost, new cost, % change and suggested new selling price, ready to paste into the price sheet.
   - **`to_check.xlsx`:** rows that failed the check, new products, and unmatched items.

**Nothing changes the shop's price sheet automatically.** The owner or clerk reviews the report and applies the update. That's a deliberate safety choice for version 1.

## 3. Scope

**Included**
- Reading text-based PDF and Excel (.xlsx) price lists from the 3 current suppliers, in their current formats.
- AI extraction, the price check, product matching, cost comparison and suggested selling prices from agreed markup rules.
- The email report, the update spreadsheet, the check list, and a log of every run.
- A Monday 7:00 am schedule on the shop's Windows computer, plus a `run now` button (`run.bat`).
- A settings file (`config.env`) for email addresses, markups, folder and time, so no code needs editing.

**Not included** (each can be quoted separately as a change request)
- Photos or scanned price lists (needs OCR): quoted on request.
- Reading price lists straight from email or WhatsApp; v1 uses a folder.
- Writing prices directly into the POS or price sheet; v1 produces a file to paste or import.
- Suppliers beyond the 3 named, or a supplier changing to a completely new layout after handover. Small layout changes are covered by monthly support.
- Purchase orders, stock levels or reorder suggestions.

## 4. Deliverables

| # | Deliverable | Format |
|---|---|---|
| 1 | Price List Sync tool, installed and scheduled on the shop computer | Windows folder: program, `run.bat`, `setup.bat` |
| 2 | Settings file with emails, markups by category, folder and time | `config.env`, editable in Notepad |
| 3 | Product-matching table (supplier item to shop item), built with the clerk | `product_map.xlsx` |
| 4 | 1-page user guide: the Monday routine, and what to do when something is flagged | `READ ME FIRST.txt` and PDF |
| 5 | 30-minute handover session with the owner and the clerk | In person or video call |
| 6 | Source code with tests | Private GitHub repository, shared with the client |

## 5. When it's done (acceptance criteria)

The project is complete when all six are true, checked together at handover:

1. **Accuracy:** on the last 4 weeks of real price lists, **at least 98% of rows** are extracted with the correct price, and **no price that isn't in the source document** appears in any report.
2. **Matching:** all of the shop's ~400 stocked items that appear in the price lists are either matched or listed in `to_check.xlsx`. None are dropped silently.
3. **Comparison:** for one past week, the "changes" report matches the clerk's own manual comparison.
4. **Delivery:** the email arrives correctly formatted for all 3 recipients, on a computer and on a phone.
5. **Schedule:** the tool runs by itself at 7:00 am and logs the result, including on battery and catching up after the computer was off.
6. **Handover:** the clerk can run it, read the report, confirm a new product match and fix a setting **without help**.

## 6. Timeline: daily milestones

| Day | Milestone | Done when |
|---|---|---|
| **Mon 30 Nov** | Setup and real data | I have the last 4 weeks of price lists from all 3 suppliers, the shop's product list and the markup rules, **and Python reads all of them** |
| **Tue 1 Dec** | Extraction and price check | Every row of one full week's price lists is extracted and checked, with at least 98% correct against a hand count |
| **Wed 2 Dec** | Matching, comparison and pricing | The changes report for last week matches the clerk's manual comparison, and the matching table is reviewed with the clerk (1 hour) |
| **Thu 3 Dec** | Email, schedule and testing | The report reaches all 3 inboxes. The 7:00 am schedule works. All 4 weeks are re-run. Bad inputs (empty folder, scan, locked file, no internet) give clear messages |
| **Fri 4 Dec** | Handover and documentation | Installed on the shop computer, guide delivered, handover done, and the clerk runs it alone. **Mon 7 Dec 7:00 am:** first automatic run, which I check remotely |

## 7. Risks and how they're managed

| Risk | Likelihood | How it's managed |
|---|---|---|
| **1. Price list formats.** A supplier sends a scanned PDF or photo, or each list is laid out differently, so extraction is unreliable | Medium | **I ask for 4 weeks of real price lists before Monday** and check them on Day 1, before writing any code. A scanned supplier is raised immediately and quoted as OCR, not discovered on Thursday. The price check catches misreads, and failed rows are listed and never used |
| **2. Product matching.** Supplier names differ from the shop's ("Y12 deformed bar 12m" vs "Y12 Bar") and some items are new | High | A matching table is built with the clerk on Wednesday (1 hour, booked now). Unclear items always go to `to_check.xlsx` with a suggested match: **no silent guessing** |
| **3. Scope creep.** Requests mid-week such as "can it also update the POS", "read WhatsApp" or "do stock levels" | High | This brief is the agreed scope, signed off before Monday. New requests go in the change-request log with a price and date and are **done after handover**, never squeezed into the 5 days |

**Also watched:**
- **Client availability.** I need the clerk for 1 hour on Wednesday and 30 minutes on Friday; these are booked at sign-off.
- **The shop computer.** Python and the Gmail App Password are set up and tested on Thursday, on the actual machine, not only on mine.
- **A wrong price reaching a customer.** The tool never changes prices by itself; a person always approves.

## 8. Price

| Item | Price |
|---|---|
| Build, install and handover (deliverables 1 to 6) | **KES 25,000** one-time |
| Optional monthly support: monitoring the Monday runs, fixes, small supplier layout changes, AI costs (about KES 100/month) | **KES 2,500/month**, cancel any time |

**Payment:** KES 12,500 (50%) on sign-off, before work starts, and **KES 12,500 on handover**, once the acceptance criteria are met.

**Why this price:** about 14 clerk hours a month saved (about KES 4,200 at KES 300/hour), plus protected margin. One avoided late price update on cement (KES 4,500 in the example above) pays for close to two months of support. The build pays for itself in about 6 months on time saved alone, and sooner each time it catches a late price rise.

## 9. What I need from the client

**Before Monday 30 November:**
- The last 4 weeks of price lists from each of the 3 suppliers, exactly as received.
- `Mlimani price sheet.xlsx` (the current product list with costs and selling prices).
- The markup rules by category (or a 15-minute call to agree them).

**During the week:**
- The clerk for 1 hour on Wednesday and 30 minutes on Friday.
- Access to the shop computer on Friday.
- A Gmail account for sending the report.

## 10. Changes after sign-off

Any change to sections 3 to 6 is written in the change-request log with what's asked, the price and the date, and needs a "yes" by email before work starts. Changes are scheduled after handover unless they replace something of equal size.

---

*Sign-off: the client confirms this brief by replying "Confirmed" to the sign-off email.*
