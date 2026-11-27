PRICE LIST SYNC
===============

For Mlimani Hardware & Building Supplies
Set up by Rawknow Company Ltd


WHAT IT DOES
------------

Every Monday at 7:00 am, Price List Sync:

1. reads the price lists your suppliers sent (PDF or Excel),
2. checks every price against the supplier's own document,
3. compares them with your price sheet, and
4. emails you and your managers a short report:
   - which of your items now cost more or less,
   - which items now SELL BELOW YOUR MARKUP, and the price to charge,
   - two spreadsheets: "price_updates" and "to_check".

It never changes your price sheet. You decide every price.


WHAT YOU NEED
-------------

- A Windows 10 or Windows 11 computer that is usually on during the week
- Internet
- Python 3.10 or newer (setup tells you if it's missing, and where to get it)
- A Gmail account to send the report, with an "App Password" (step 2 below)


SET IT UP (once, about 15 minutes)
----------------------------------

1. Copy the "Price List Sync" folder into Documents.

2. Get a Gmail App Password for the Gmail account that will send the report:
   - Go to myaccount.google.com and open Security.
   - Turn on 2-Step Verification if it isn't on.
   - Search for "App passwords", create one called "Price List Sync".
   - Google shows 16 letters. Keep them for the next step.

3. Double-click  setup.bat
   Notepad opens your settings. Fill in these lines:
     REPORT_TO           who gets the email. Separate several with commas.
     GMAIL_ADDRESS       the Gmail account from step 2
     GMAIL_APP_PASSWORD  the 16 letters from step 2
     TEST_EMAIL_TO       your own email, for test emails
   Save (Ctrl+S) and close Notepad.
   If something is wrong, setup says which line to fix and opens Notepad again.

4. Double-click  send test email.bat
   A copy marked [TEST] goes to TEST_EMAIL_TO only.
   Open it on your phone and check it arrived.

Done. From now on it runs by itself every Monday at 7:00 am.


EVERY WEEK
----------

1. When a supplier sends a price list, save it in that supplier's folder
   inside "price_lists", named with the date on the list:

       price_lists\kapsoit-plumbing\2026-11-30.pdf
       price_lists\rift-valley-building-supplies\2026-11-30.pdf
       price_lists\sunrise-paints-hardware\2026-11-30.xlsx

   PDF or Excel only. Photos and scans can't be read.

2. On Monday morning, open the email. Start with "Reprice these first".

3. Open the attached "price_updates" file. For each line, put the new cost
   and, if you agree, the suggested selling price into your price sheet.

4. Open "to_check". It lists items that couldn't be matched, with the
   likely fix, e.g. "Did you mean HWR-110? If so, change Supplier Item
   to HWR-110."


WHAT THE EMAIL MEANS
--------------------

Below target markup   At today's selling price you earn less than your
                      markup for that category. "Suggested" is the price
                      that gives you your full markup, rounded up to KES 10.
Costs down            The supplier lowered their price. Keep your price
                      (more profit) or lower it: your choice.
To check              Items it could not match. It never guesses.


IF IT STOPS OR SOMETHING LOOKS WRONG
------------------------------------

To run it again at any time:  double-click  run.bat

1. Open the "logs" folder and open sync.log in Notepad.
   The last line says what happened. Every problem line says what to do.
2. Fix what it says, then double-click run.bat.
3. Still stuck? WhatsApp Bildad at {SUPPORT_WHATSAPP} and send a photo
   of the last few lines of sync.log.

Common messages:

"Please fix these in config.env"
   Right-click config.env, Open with, Notepad. Fix the lines listed, save,
   then double-click run.bat.

"looks like a typo. Did you mean @gmail.com?"
   An address in REPORT_TO is mistyped. Correct it in config.env.

"Email login failed"
   GMAIL_APP_PASSWORD must be the 16-letter App Password, not your normal
   Gmail password.

"No internet?"
   The report and spreadsheets are still saved in the "reports" folder.
   When you're back online, double-click run.bat to send the email.

"No new list for 14 days: ask (supplier) for this week's prices"
   That supplier hasn't sent a list. Ask them, save it, double-click run.bat.

To stop the Monday run:      double-click  remove_schedule.bat
To start it again:           double-click  setup.bat


QUESTIONS YOU MIGHT HAVE
------------------------

What if it stops working?
   Open logs\sync.log: the last line says what went wrong and what to do.
   Then double-click run.bat. If you're stuck, WhatsApp me a photo of it.

Can I add more people to the email?
   Yes. Open config.env in Notepad and add their address to REPORT_TO,
   separated by a comma. Save. That's all: no limit on how many.

Will it still work if I change my price sheet?
   Yes, if these column names stay: Product, Category, Supplier,
   Supplier Item, Cost, Selling Price. Adding rows or new columns is fine.
   Tell me before you rename or delete any of those columns.
   A new category needs its markup added to MARKUPS in config.env.

What does it cost to run?
   The AI that reads the PDF price lists costs about KES 1 a week, paid from
   the monthly support fee. Gmail is free. If you don't take support, you
   need your own AI key (I can set it up).

What if I change computers?
   Copy the whole "Price List Sync" folder to the new computer, install
   Python, and double-click setup.bat. Your settings come with the folder.
   Then double-click remove_schedule.bat on the OLD computer, so the email
   isn't sent twice. I can do this with you.


SUPPORT
-------

Bildad Ronoh, Rawknow Company Ltd
WhatsApp: {SUPPORT_WHATSAPP}
Email: bildadronoh@gmail.com
