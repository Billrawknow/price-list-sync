"""
Delivery: the two spreadsheets and the Monday email.

    price_updates_<date>.xlsx   every stocked item whose cost changed or that sells below target:
                                old cost, new cost, change, selling price now, suggested price
    to_check_<date>.xlsx        items not found (with a suggested match), rows set aside by the
                                price check, and problems in the shop's own price sheet
    email                       HTML report with a plain-text version (for mail apps that can't
                                show HTML), both spreadsheets attached, to every REPORT_TO address
"""

import html
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

import pricesync as ps

STATUS_TEXT = {"below_target": "Below target markup", "cost_up": "Cost up", "cost_down": "Cost down",
               "not_found": "Not found", "ok": "No change"}
RED, AMBER, GREEN, GREY = "B42318", "9A5B00", "1F7A4D", "667085"


class DeliveryError(Exception):
    """Email couldn't be sent. Safe to show; the files are still saved."""


# ------------------------------------------------------------------ spreadsheets

def _sheet(ws, header, rows, widths, money_cols=()):
    ws.append(header)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E79")
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    for row in rows:
        ws.append(row)
    for i, width in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = width
    for row in ws.iter_rows(min_row=2):
        for i in money_cols:
            row[i].number_format = "#,##0"
    ws.freeze_panes = "A2"


def write_updates(results, out):
    """The file the clerk uses to update the price sheet: one row per item that needs attention."""
    book = Workbook()
    ws = book.active
    ws.title = "Price updates"
    rows = []
    for p in results:
        if p.status in ("ok", "not_found"):
            continue
        # Cost down: never suggest cutting the price. Keep it, and say what the lowest fair price would be.
        suggested = p.item.selling if p.status == "cost_down" else p.target
        note = (f"Keep {ps.fmt(p.item.selling)}, or lower to {ps.fmt(p.target)} and still make "
                f"{round(p.markup * 100)}%" if p.status == "cost_down" else
                "Was already below target before this week" if p.status == "below_target" and p.change == 0 else "")
        rows.append([p.item.code, p.item.product, p.item.supplier, STATUS_TEXT[p.status], p.item.cost, p.new_cost,
                     p.change_pct / 100, p.item.selling, p.markup_now / 100, p.markup,
                     suggested, p.shortfall, note])
    _sheet(ws, ["Shop code", "Product", "Supplier", "What happened", "Old cost", "New cost", "Cost change",
                "Selling now", "Markup now", "Target markup", "Suggested selling price", "Short per unit", "Note"],
           rows, (10, 26, 28, 20, 10, 10, 10, 11, 10, 10, 13, 10, 44), money_cols=(4, 5, 7, 10, 11))
    for row in ws.iter_rows(min_row=2):
        for i in (6, 8, 9):                       # one decimal everywhere: 4.0%, not 4
            row[i].number_format = "0.0%"
    for row in ws.iter_rows(min_row=2):
        if row[3].value == STATUS_TEXT["below_target"]:
            for cell in row:
                cell.font = Font(color=RED, bold=cell.column in (2, 11))
    book.save(out)
    return len(rows)


def write_to_check(results, price_lists, sheet_problems, out):
    book = Workbook()
    ws = book.active
    ws.title = "To check"
    rows = [[p.item.code, p.item.product, p.item.supplier, p.item.supplier_item, "Not found this week", p.suggestion]
            for p in results if p.status == "not_found"]
    for supplier, pl in price_lists.items():
        rows += [["", ps.label(r), supplier, r.code or "", "Set aside by the price check", r.note] for r in pl.rejected]
    rows += [["", "", "Your price sheet", "", "Row needs fixing", problem] for problem in sheet_problems]
    _sheet(ws, ["Shop code", "Product", "Supplier", "Supplier item", "Why it's here", "What to do / suggestion"],
           rows, (10, 28, 28, 36, 26, 70))
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    book.save(out)
    return len(rows)


# ------------------------------------------------------------------ email

def subject(summary, week, test=False):
    flag = f"{summary['below_target']} below margin" if summary["below_target"] else "no items below margin"
    return f"{'[TEST] ' if test else ''}Price changes week of {week}: {summary['changed']} cost changes, {flag}"


def text_body(shop_name, week, results, summary, supplier_notes, to_check):
    lines = [f"{shop_name}: supplier price changes, week of {week}", "",
             f"{summary['changed']} of your items changed cost. {summary['below_target']} now sell below your "
             f"target markup. {to_check} item(s) to check.", ""]
    below = [p for p in results if p.status == "below_target"]
    if below:
        lines += ["REPRICE THESE FIRST (selling below target markup)"]
        lines += [f"  {p.item.product}: selling {ps.fmt(p.item.selling)}, suggest {ps.fmt(p.target)} "
                  f"(cost {cost_cell(p, '->')})" for p in below] + [""]
    down = [p for p in results if p.status == "cost_down"]
    if down:
        lines += ["COSTS DOWN (keep the extra margin, or pass it on)"]
        lines += [f"  {p.item.product}: cost {ps.fmt(p.item.cost)} -> {ps.fmt(p.new_cost)}" for p in down] + [""]
    lines += ["SUPPLIERS"] + [f"  {note}" for note in supplier_notes] + [""]
    lines += ["Attached: price_updates (paste into your price sheet) and to_check (items for your clerk).",
              "Nothing has been changed in your price sheet: you decide.", "", "Price List Sync, Rawknow Company Ltd"]
    return "\n".join(lines)


def html_body(shop_name, week, results, summary, supplier_notes, to_check):
    e = html.escape
    below = [p for p in results if p.status == "below_target"]
    down = [p for p in results if p.status == "cost_down"]
    cell = "padding:8px 10px;border-bottom:1px solid #EAECF0;font-size:14px;"
    num = cell + "text-align:right;white-space:nowrap;"

    def table(rows, head):
        th = "".join(f'<th style="{cell}text-align:{"right" if i else "left"};color:{GREY};font-size:12px;'
                     f'font-weight:600;">{e(h)}</th>' for i, h in enumerate(head))
        return (f'<table role="presentation" cellspacing="0" cellpadding="0" style="border-collapse:collapse;'
                f'width:100%;max-width:640px;"><tr>{th}</tr>{"".join(rows)}</table>')

    parts = ['<div style="font-family:Segoe UI,Arial,sans-serif;color:#101828;max-width:640px;">',
             f'<h2 style="margin:0 0 4px;font-size:20px;">{e(shop_name)}: price changes</h2>',
             f'<p style="margin:0 0 16px;color:{GREY};">Week of {e(week)}</p>',
             f'<p style="font-size:15px;"><b>{summary["changed"]}</b> of your items changed cost. '
             f'<b style="color:#{RED};">{summary["below_target"]}</b> now sell below your target markup. '
             f'<b>{to_check}</b> item(s) to check.</p>']
    if below:
        rows = [f'<tr><td style="{cell}">{e(p.item.product)}</td>'
                f'<td style="{num}">{cost_cell(p)}</td>'
                f'<td style="{num}color:#{RED};">{ps.fmt(p.item.selling)}</td>'
                f'<td style="{num}font-weight:700;">{ps.fmt(p.target)}</td></tr>' for p in below]
        parts += [f'<h3 style="font-size:16px;color:#{RED};margin:24px 0 8px;">Reprice these first</h3>',
                  table(rows, ["Product", "Cost (KES)", "Selling now", "Suggested"])]
    if down:
        rows = [f'<tr><td style="{cell}">{e(p.item.product)}</td>'
                f'<td style="{num}color:#{GREEN};">{ps.fmt(p.item.cost)} &rarr; {ps.fmt(p.new_cost)}</td></tr>'
                for p in down]
        parts += ['<h3 style="font-size:16px;margin:24px 0 8px;">Costs down</h3>',
                  table(rows, ["Product", "Cost (KES)"])]
    parts += ['<h3 style="font-size:16px;margin:24px 0 8px;">Suppliers</h3><ul style="padding-left:18px;">']
    parts += [f'<li style="margin-bottom:4px;">{e(n)}</li>' for n in supplier_notes] + ["</ul>"]
    parts += [f'<p style="color:{GREY};font-size:13px;">Attached: <b>price_updates</b> (paste into your price sheet) '
              f'and <b>to_check</b> (items for your clerk). Nothing has been changed in your price sheet: you decide.</p>',
              f'<p style="color:{GREY};font-size:12px;">Price List Sync &middot; Rawknow Company Ltd</p></div>']
    return "".join(parts)


def cost_cell(p, arrow="&rarr;"):
    """'1,095 -> 1,140', or 'unchanged 1,890' for an item that was already priced too low."""
    if p.new_cost == p.item.cost:
        return f"unchanged {ps.fmt(p.new_cost)}"
    return f"{ps.fmt(p.item.cost)} {arrow} {ps.fmt(p.new_cost)}"


def build_email(sender, recipients, subject_line, text, html_text, attachments):
    msg = EmailMessage()
    msg["Subject"] = subject_line
    msg["From"] = formataddr(("Price List Sync", sender))
    msg["To"] = ", ".join(recipients)
    msg.set_content(text)                         # plain text first: shown if HTML can't be
    msg.add_alternative(html_text, subtype="html")
    for path in attachments:
        msg.add_attachment(path.read_bytes(), maintype="application",
                           subtype="vnd.openxmlformats-officedocument.spreadsheetml.sheet", filename=path.name)
    return msg


def send(msg, sender, password, recipients, smtp=None):
    """Send to every address. Returns the list of refused addresses (others still get it)."""
    smtp = smtp or smtplib.SMTP_SSL
    try:
        with smtp("smtp.gmail.com", 465, context=ssl.create_default_context(), timeout=30) as server:
            server.login(sender, password.replace(" ", ""))
            refused = server.send_message(msg, to_addrs=recipients)
            return sorted(refused)
    except smtplib.SMTPAuthenticationError:
        raise DeliveryError("Email login failed. Check GMAIL_ADDRESS and the 16-letter GMAIL_APP_PASSWORD in config.env.")
    except smtplib.SMTPRecipientsRefused as err:
        raise DeliveryError(f"Gmail refused every address: {', '.join(sorted(err.recipients))}. "
                            "Check REPORT_TO in config.env for typos.")
    except (smtplib.SMTPException, OSError) as err:
        raise DeliveryError(f"The email couldn't be sent ({type(err).__name__}). No internet? "
                            "The report and spreadsheets are saved in the reports folder.")
