# Handover: the five questions, and my answers

These are also in the client's README ("Questions you might have"), worded for her.

| Question | Answer |
|---|---|
| **What if it stops working?** | Open `logs\sync.log`: the last line says what went wrong and what to do. Fix it, then double-click `run.bat`. If you're stuck, WhatsApp me a photo of those lines. |
| **Can I add more people to the email list?** | Yes. Add their address to `REPORT_TO` in `config.env`, separated by commas. There's no limit. |
| **Will it work if I change my price sheet?** | Yes, as long as these column names stay: Product, Category, Supplier, Supplier Item, Cost, Selling Price. Adding rows or columns is fine; tell me before renaming one. A new category needs a markup in `MARKUPS`. |
| **What does it cost to run?** | The AI reading the PDFs costs about KES 1 a week, covered by the KES 2,500/month support. Gmail is free. Without support, you'd need your own AI key, which I can set up. |
| **What if I change laptops?** | Copy the whole folder, install Python, then double-click `setup.bat`; your settings come along. Run `remove_schedule.bat` on the old laptop so the email isn't sent twice. |

**Two more she's likely to ask**
- *"What if it gets a price wrong?"* Every PDF price is checked against the supplier's document first, and it never changes your sheet. On the sample lists it was 317 out of 317 correct.
- *"A supplier changed their price list layout?"* It reads lists the way a person does, so small changes are fine. Anything it can't match shows up in "to check"; it never guesses. Fixing a new layout is covered by support.
