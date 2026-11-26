# Backlog: what I'd do with one more day

| Item | Why | Priority |
|---|---|---|
| Watch-folder helper: drag a price list onto `add price list.bat`, which asks the supplier and date, then files and renames it | Saving with the date as the file name is the step people will get wrong | HIGH |
| A sentence in the email explaining "target markup" with one worked example | Owners say "margin" and mean different things | HIGH |
| Apply approved prices back into the price sheet with one click (writes a new copy, never overwrites) | Saves the copy-paste step; v1 deliberately leaves it manual | MEDIUM |
| Supplier names in config.env (`Sunrise Paints & Hardware`) for suppliers not yet in the price sheet | The name comes from the price sheet today, or the folder name if the supplier isn't in it | MEDIUM |
| SMS alert (Africa's Talking) if the Monday email bounces or fails | The owner may not check the log | NICE TO HAVE |
| Compare prices across suppliers: who's cheapest for Y12 this week | A natural upsell | NICE TO HAVE |
| Price-history chart per product in the email | Shows a trend, not just this week | NICE TO HAVE |
| OCR for scanned price lists | Out of scope; quoted at KES 5,000 | CHANGE REQUEST |
| Read price lists straight from the Gmail inbox | Out of scope; quoted at KES 3,500 | CHANGE REQUEST |

**Known limits right now**
- Very long PDF pages (more than about 150 rows) stop with a clear message instead of being split.
- Category names in the price sheet must match the MARKUPS names. An unknown category uses DEFAULT_MARKUP.
