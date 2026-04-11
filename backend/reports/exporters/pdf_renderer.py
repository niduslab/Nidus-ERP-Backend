# backend/reports/exporters/pdf_renderer.py

"""
PDF export renderer for all financial reports.

Uses reportlab. Each report type has its own render function.
All share the same header/footer, table styling, and page layout.

FEATURES:
    - Company letterhead header on every page
    - Page numbers ("Page 1 of 5") in footer
    - Professional tables with coloured headers and borders
    - Section headers with colour bands
    - Portrait for summary reports, landscape for detail reports
    - Summary totals box at the bottom
"""

import io
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak,
)

from .styles import (
    COLOUR_PRIMARY, COLOUR_HEADER_BG, COLOUR_ROW_ALT,
    COLOUR_TOTAL_BG, COLOUR_SECTION_BG,
    COLOUR_L1, COLOUR_L2, COLOUR_L3, COLOUR_TOTAL, COLOUR_TEXT,
    FONT_NAME_PDF, build_header_info, to_decimal,
)


# ══════════════════════════════════════════════════
# COLOUR CONVERSIONS (hex string → reportlab Color)
# ══════════════════════════════════════════════════

def _hex(colour_str):
    """Convert a hex colour string to a reportlab Color."""
    r = int(colour_str[0:2], 16) / 255
    g = int(colour_str[2:4], 16) / 255
    b = int(colour_str[4:6], 16) / 255
    return colors.Color(r, g, b)


CLR_PRIMARY = _hex(COLOUR_PRIMARY)
CLR_HEADER = _hex(COLOUR_HEADER_BG)
CLR_ALT = _hex(COLOUR_ROW_ALT)
CLR_TOTAL = _hex(COLOUR_TOTAL_BG)
CLR_SECTION = _hex(COLOUR_SECTION_BG)
CLR_WHITE = colors.white
CLR_BLACK = colors.black
CLR_GREY = colors.Color(0.5, 0.5, 0.5)
CLR_BORDER = colors.Color(0.8, 0.8, 0.8)

# Classification layer text colours
CLR_L1_TEXT = _hex(COLOUR_L1)       # Deep indigo for L1 elements
CLR_L2_TEXT = _hex(COLOUR_L2)       # Strong blue for L2 categories
CLR_L3_TEXT = _hex(COLOUR_L3)       # Dark teal for L3 groups
CLR_TOTAL_TEXT = _hex(COLOUR_TOTAL) # Deep indigo for totals
CLR_ACCT_TEXT = _hex(COLOUR_TEXT)   # Near-black for accounts

# Mapping: row style level → (text colour, bold font name)
ROW_STYLE_MAP = {
    'L1':    (CLR_L1_TEXT, FONT_NAME_PDF + '-Bold'),
    'L2':    (CLR_L2_TEXT, FONT_NAME_PDF + '-Bold'),
    'L3':    (CLR_L3_TEXT, FONT_NAME_PDF + '-Bold'),
    'TOTAL': (CLR_TOTAL_TEXT, FONT_NAME_PDF + '-Bold'),
}


# ══════════════════════════════════════════════════
# PARAGRAPH STYLES
# ══════════════════════════════════════════════════

_styles = getSampleStyleSheet()

STYLE_TITLE = ParagraphStyle(
    'NidusTitle', parent=_styles['Heading1'],
    fontName=FONT_NAME_PDF, fontSize=14, textColor=CLR_PRIMARY,
    spaceAfter=2 * mm,
)
STYLE_SUBTITLE = ParagraphStyle(
    'NidusSubtitle', parent=_styles['Normal'],
    fontName=FONT_NAME_PDF, fontSize=9, textColor=CLR_GREY,
    spaceAfter=1 * mm,
)
STYLE_BODY = ParagraphStyle(
    'NidusBody', parent=_styles['Normal'],
    fontName=FONT_NAME_PDF, fontSize=8, textColor=CLR_BLACK,
)
STYLE_BOLD = ParagraphStyle(
    'NidusBold', parent=_styles['Normal'],
    fontName=FONT_NAME_PDF, fontSize=8, textColor=CLR_BLACK,
)


# ══════════════════════════════════════════════════
# SHARED PDF HELPERS
# ══════════════════════════════════════════════════

def _build_header_elements(info):
    """Build the report header as a list of Platypus flowables."""
    elements = []
    elements.append(Paragraph(info['company_name'], STYLE_TITLE))
    elements.append(Paragraph(info['report_title'], STYLE_BOLD))

    if info.get('as_of_date'):
        elements.append(Paragraph('As of {}'.format(info['as_of_date']), STYLE_SUBTITLE))
    elif info.get('from_date') and info.get('to_date'):
        elements.append(Paragraph('Period: {} to {}'.format(
            info['from_date'], info['to_date']), STYLE_SUBTITLE))

    parts = []
    if info.get('base_currency'):
        parts.append('Currency: {}'.format(info['base_currency']))
    if info.get('method'):
        parts.append('Method: {}'.format(info['method']))
    if parts:
        elements.append(Paragraph(' | '.join(parts), STYLE_SUBTITLE))

    elements.append(Spacer(1, 5 * mm))
    return elements


def _make_table(data_rows, col_widths=None, has_header=True, row_styles=None):
    """
    Create a styled Table from a list of rows.
    First row is treated as header if has_header=True.
    row_styles: optional dict {row_index: 'L1'|'L2'|'L3'|'TOTAL'} for
                bold + coloured classification/total rows.
    """
    row_styles = row_styles or {}
    table = Table(data_rows, colWidths=col_widths, repeatRows=1 if has_header else 0)

    style_commands = [
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME_PDF),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, CLR_BORDER),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]

    if has_header:
        style_commands.extend([
            ('BACKGROUND', (0, 0), (-1, 0), CLR_HEADER),
            ('TEXTCOLOR', (0, 0), (-1, 0), CLR_WHITE),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ])

    # Alternating row colours (starting from row 1)
    for i in range(1, len(data_rows)):
        if i % 2 == 0:
            style_commands.append(('BACKGROUND', (0, i), (-1, i), CLR_ALT))

    # Apply classification/total row styling (bold + colour)
    for i, level in row_styles.items():
        if level in ROW_STYLE_MAP:
            text_colour, font_name = ROW_STYLE_MAP[level]
            style_commands.append(('FONTNAME', (0, i), (-1, i), font_name))
            style_commands.append(('TEXTCOLOR', (0, i), (-1, i), text_colour))

    table.setStyle(TableStyle(style_commands))
    return table


def _add_page_numbers(canvas, doc):
    """Add page numbers to every page footer."""
    canvas.saveState()
    canvas.setFont(FONT_NAME_PDF, 7)
    canvas.setFillColor(CLR_GREY)
    page_text = 'Page {} — Nidus ERP'.format(doc.page)
    canvas.drawCentredString(doc.pagesize[0] / 2, 12 * mm, page_text)
    canvas.restoreState()


def _build_pdf(elements, is_landscape=False):
    """Build the PDF from flowable elements and return bytes."""
    buf = io.BytesIO()
    pagesize = landscape(A4) if is_landscape else A4
    doc = SimpleDocTemplate(
        buf, pagesize=pagesize,
        leftMargin=15 * mm, rightMargin=15 * mm,
        topMargin=15 * mm, bottomMargin=20 * mm,
    )
    doc.build(elements, onFirstPage=_add_page_numbers, onLaterPages=_add_page_numbers)
    buf.seek(0)
    return buf.getvalue()


def _fmt(value):
    """Format a value for PDF display."""
    if value is None:
        return ''
    try:
        d = Decimal(str(value))
        return '{:,.2f}'.format(d)
    except Exception:
        return str(value)


# ══════════════════════════════════════════════════
# MAIN DISPATCH
# ══════════════════════════════════════════════════

def render_pdf(report_type, report_data):
    """Main entry point. Returns bytes (the .pdf file content)."""
    renderers = {
        'trial_balance': _render_trial_balance,
        'balance_sheet': _render_balance_sheet,
        'income_statement': _render_income_statement,
        'general_ledger': _render_general_ledger,
        'account_transactions': _render_account_transactions,
        'cash_flow': _render_cash_flow,
        'journal_entries': _render_journal_entries,
    }
    renderer = renderers.get(report_type)
    if not renderer:
        raise ValueError('No PDF renderer for report type: {}'.format(report_type))
    return renderer(report_data)


# ══════════════════════════════════════════════════
# TRIAL BALANCE
# ══════════════════════════════════════════════════

def _render_trial_balance(data):
    info = build_header_info(data)
    elements = _build_header_elements(info)

    rows = [['Classification / Account', 'Code', 'Debit', 'Credit']]
    row_styles = {}

    for group in data.get('groups', []):
        row_styles[len(rows)] = 'L1'
        rows.append([group['name'], '', '', ''])
        for l2 in group.get('children', []):
            row_styles[len(rows)] = 'L2'
            rows.append(['  ' + l2['name'], '', '', ''])
            for l3 in l2.get('children', []):
                row_styles[len(rows)] = 'L3'
                rows.append(['    ' + l3['name'], '', _fmt(l3.get('subtotal_debit')), _fmt(l3.get('subtotal_credit'))])
                for acct in l3.get('accounts', []):
                    _append_account_rows_recursive(rows, acct, depth=3)

    row_styles[len(rows)] = 'TOTAL'
    rows.append(['TOTAL', '', _fmt(data.get('grand_total_debit')), _fmt(data.get('grand_total_credit'))])

    table = _make_table(rows, col_widths=[220, 60, 80, 80], row_styles=row_styles)
    elements.append(table)

    balanced = 'YES' if data.get('is_balanced') else 'NO'
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph('Balanced: {}'.format(balanced), STYLE_BOLD))

    return _build_pdf(elements)


def _append_account_rows_recursive(rows, acct, depth=3):
    """
    Recursively append account rows to the rows list.
    Shows own balance only (not subtotals) to prevent double-counting.
    Skips zero-balance intermediary accounts but still recurses into children.
    """
    own_dr = acct.get('own_debit_balance')
    own_cr = acct.get('own_credit_balance')
    has_own_balance = (own_dr is not None) or (own_cr is not None)

    if has_own_balance:
        indent = '  ' * depth
        rows.append([
            indent + acct.get('name', ''),
            acct.get('code', ''),
            _fmt(own_dr),
            _fmt(own_cr),
        ])

    for child in acct.get('children', []):
        _append_account_rows_recursive(rows, child, depth + 1)


def _append_section_rows(rows, section, row_styles=None):
    """
    Append L2 > L3 > account rows for a BS/IS section.
    If row_styles dict is provided, L2 and L3 row indices are added with their level.
    """
    for l2 in section:
        if row_styles is not None:
            row_styles[len(rows)] = 'L2'
        rows.append(['  ' + l2['name'], '', '', ''])
        for l3 in l2.get('children', []):
            if row_styles is not None:
                row_styles[len(rows)] = 'L3'
            rows.append(['    ' + l3['name'], '', _fmt(l3.get('subtotal_debit')), _fmt(l3.get('subtotal_credit'))])
            for acct in l3.get('accounts', []):
                _append_account_rows_recursive(rows, acct, depth=3)


# ══════════════════════════════════════════════════
# BALANCE SHEET
# ══════════════════════════════════════════════════

def _render_balance_sheet(data):
    info = build_header_info(data)
    elements = _build_header_elements(info)

    col_widths = [220, 60, 80, 80]
    table_headers = ['Account', 'Code', 'Debit', 'Credit']

    # ── ASSETS section ──
    elements.append(Paragraph('ASSETS', STYLE_BOLD))
    elements.append(Spacer(1, 2 * mm))
    rows = [table_headers]
    row_styles = {}
    _append_section_rows(rows, data.get('assets', []), row_styles=row_styles)
    row_styles[len(rows)] = 'TOTAL'
    rows.append(['Total Assets', '', _fmt(data.get('total_assets')), ''])
    elements.append(_make_table(rows, col_widths=col_widths, row_styles=row_styles))
    elements.append(Spacer(1, 6 * mm))

    # ── LIABILITIES section ──
    elements.append(Paragraph('LIABILITIES', STYLE_BOLD))
    elements.append(Spacer(1, 2 * mm))
    rows = [table_headers]
    row_styles = {}
    _append_section_rows(rows, data.get('liabilities', []), row_styles=row_styles)
    row_styles[len(rows)] = 'TOTAL'
    rows.append(['Total Liabilities', '', _fmt(data.get('total_liabilities')), ''])
    elements.append(_make_table(rows, col_widths=col_widths, row_styles=row_styles))
    elements.append(Spacer(1, 6 * mm))

    # ── EQUITY section ──
    elements.append(Paragraph('EQUITY', STYLE_BOLD))
    elements.append(Spacer(1, 2 * mm))
    rows = [table_headers]
    row_styles = {}
    _append_section_rows(rows, data.get('equity', []), row_styles=row_styles)
    # Retained earnings auto
    re_auto = data.get('retained_earnings_auto', {})
    if re_auto:
        rows.append(['  Current Year Net Income (auto)', '', _fmt(re_auto.get('current_year_earnings')), ''])
        rows.append(['  Prior Year Retained (auto)', '', _fmt(re_auto.get('prior_year_retained')), ''])
    row_styles[len(rows)] = 'TOTAL'
    rows.append(['Total Equity', '', _fmt(data.get('total_equity')), ''])
    elements.append(_make_table(rows, col_widths=col_widths, row_styles=row_styles))
    elements.append(Spacer(1, 8 * mm))

    # ── Summary totals ──
    summary_rows = [
        ['', 'Amount'],
        ['Total Assets', _fmt(data.get('total_assets'))],
        ['Total Liabilities & Equity', _fmt(data.get('total_liabilities_and_equity'))],
    ]
    elements.append(_make_table(summary_rows, col_widths=[280, 100],
                    row_styles={1: 'TOTAL', 2: 'TOTAL'}))

    balanced = 'YES' if data.get('is_balanced') else 'NO'
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph('Balanced: {}'.format(balanced), STYLE_BOLD))

    return _build_pdf(elements)


# ══════════════════════════════════════════════════
# INCOME STATEMENT
# ══════════════════════════════════════════════════

def _render_income_statement(data):
    info = build_header_info(data)
    elements = _build_header_elements(info)

    rows = [['Account', 'Code', 'Debit', 'Credit']]
    row_styles = {}

    row_styles[len(rows)] = 'L1'
    rows.append(['REVENUE', '', '', ''])
    _append_section_rows(rows, data.get('revenue', []), row_styles=row_styles)

    row_styles[len(rows)] = 'TOTAL'
    rows.append(['Total Revenue', '', _fmt(data.get('total_revenue')), ''])
    rows.append(['', '', '', ''])

    row_styles[len(rows)] = 'L1'
    rows.append(['EXPENSES', '', '', ''])
    _append_section_rows(rows, data.get('expenses', []), row_styles=row_styles)

    row_styles[len(rows)] = 'TOTAL'
    rows.append(['Total Expenses', '', _fmt(data.get('total_expenses')), ''])
    row_styles[len(rows)] = 'TOTAL'
    rows.append(['NET INCOME', '', _fmt(data.get('net_income')), ''])

    table = _make_table(rows, col_widths=[220, 60, 80, 80], row_styles=row_styles)
    elements.append(table)

    return _build_pdf(elements)


# ══════════════════════════════════════════════════
# GENERAL LEDGER
# ══════════════════════════════════════════════════

def _render_general_ledger(data):
    info = build_header_info(data)
    elements = _build_header_elements(info)

    for account in data.get('accounts', []):
        # Account header
        elements.append(Paragraph(
            '{} — {} (Opening: {})'.format(
                account['code'], account['name'], _fmt(account.get('opening_balance'))
            ), STYLE_BOLD,
        ))
        elements.append(Spacer(1, 2 * mm))

        rows = [['Date', 'Dr/Cr', 'Amount', 'Running Balance', 'Note', 'Type']]
        for txn in account.get('transactions', []):
            rows.append([
                txn.get('date', ''), txn.get('entry_type', ''),
                _fmt(txn.get('base_amount')), _fmt(txn.get('running_balance')),
                str(txn.get('note', ''))[:40], txn.get('journal_type', ''),
            ])
        rows.append(['Closing', '', _fmt(account.get('total_debit')),
                      _fmt(account.get('closing_balance')), '', ''])

        table = _make_table(rows, col_widths=[55, 35, 65, 70, 130, 55])
        elements.append(table)
        elements.append(Spacer(1, 5 * mm))

    # Grand totals
    elements.append(Paragraph(
        'Grand Total — Debit: {} | Credit: {}'.format(
            _fmt(data.get('grand_total_debit')), _fmt(data.get('grand_total_credit'))
        ), STYLE_BOLD,
    ))

    return _build_pdf(elements, is_landscape=True)


# ══════════════════════════════════════════════════
# ACCOUNT TRANSACTIONS
# ══════════════════════════════════════════════════

def _render_account_transactions(data):
    info = build_header_info(data)
    elements = _build_header_elements(info)

    acct = data.get('account', {})
    elements.append(Paragraph(
        'Account: {} — {} ({})'.format(
            acct.get('code', ''), acct.get('name', ''), acct.get('normal_balance', '')
        ), STYLE_BOLD,
    ))
    elements.append(Paragraph(
        'Opening Balance: {}'.format(_fmt(data.get('opening_balance'))), STYLE_SUBTITLE,
    ))
    elements.append(Spacer(1, 3 * mm))

    rows = [['Date', 'Source #', 'Description', 'Dr/Cr', 'Amount', 'Running Bal.']]
    for txn in data.get('transactions', []):
        rows.append([
            txn.get('date', ''), txn.get('source_number', ''),
            str(txn.get('source_description', ''))[:35],
            txn.get('entry_type', ''), _fmt(txn.get('base_amount')),
            _fmt(txn.get('running_balance')),
        ])

    rows.append(['', '', 'CLOSING BALANCE', '', '', _fmt(data.get('closing_balance'))])

    table = _make_table(rows, col_widths=[55, 55, 150, 35, 65, 70])
    elements.append(table)

    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        'Total Debit: {} | Total Credit: {}'.format(
            _fmt(data.get('total_debit')), _fmt(data.get('total_credit'))
        ), STYLE_BOLD,
    ))

    return _build_pdf(elements, is_landscape=True)


# ══════════════════════════════════════════════════
# CASH FLOW STATEMENT
# ══════════════════════════════════════════════════

def _render_cash_flow(data):
    info = build_header_info(data)
    elements = _build_header_elements(info)

    rows = [['Item', 'Amount']]

    # Operating
    oa = data.get('operating_activities', {})
    rows.append(['OPERATING ACTIVITIES', ''])
    rows.append(['  Net Income', _fmt(oa.get('net_income'))])
    adj = oa.get('adjustments', {})
    rows.append(['  Depreciation & Amortisation (add-back)', _fmt(adj.get('depreciation_and_amortization'))])
    rows.append(['  Working Capital Changes:', ''])
    for item in oa.get('working_capital_changes', []):
        rows.append(['    {} ({})'.format(item['name'], item['code']), _fmt(item.get('cash_effect'))])
    rows.append(['  Net Cash from Operating', _fmt(oa.get('net_cash_from_operating'))])
    rows.append(['', ''])

    # Investing
    ia = data.get('investing_activities', {})
    rows.append(['INVESTING ACTIVITIES', ''])
    for item in ia.get('items', []):
        rows.append(['  {} ({})'.format(item['name'], item['code']), _fmt(item.get('cash_effect'))])
    rows.append(['  Net Cash from Investing', _fmt(ia.get('net_cash_from_investing'))])
    rows.append(['', ''])

    # Financing
    fa = data.get('financing_activities', {})
    rows.append(['FINANCING ACTIVITIES', ''])
    for item in fa.get('items', []):
        rows.append(['  {} ({})'.format(item['name'], item['code']), _fmt(item.get('cash_effect'))])
    rows.append(['  Net Cash from Financing', _fmt(fa.get('net_cash_from_financing'))])
    rows.append(['', ''])

    # Reconciliation
    cr = data.get('cash_reconciliation', {})
    rows.append(['CASH RECONCILIATION', ''])
    rows.append(['  Opening Cash Balance', _fmt(cr.get('opening_cash_balance'))])
    rows.append(['  Net Change in Cash', _fmt(cr.get('net_change_in_cash'))])
    rows.append(['  Closing Cash Balance', _fmt(cr.get('closing_cash_balance'))])

    table = _make_table(rows, col_widths=[320, 100])
    elements.append(table)

    balanced = 'YES' if cr.get('is_balanced') else 'NO'
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph('Balanced: {}'.format(balanced), STYLE_BOLD))

    return _build_pdf(elements)


# ══════════════════════════════════════════════════
# JOURNAL ENTRIES
# ══════════════════════════════════════════════════

def _render_journal_entries(data):
    info = build_header_info(data)
    elements = _build_header_elements(info)

    rows = [['Entry #', 'Date', 'Status', 'Account', 'Dr/Cr', 'Amount', 'Description']]

    for journal in data.get('journals', []):
        for line in journal.get('lines', []):
            rows.append([
                journal.get('entry_number', ''), journal.get('date', ''),
                journal.get('status', ''),
                '{} — {}'.format(line.get('account_code', ''), line.get('account_name', '')),
                line.get('entry_type', ''), _fmt(line.get('amount')),
                str(journal.get('description', ''))[:30],
            ])

    table = _make_table(rows, col_widths=[50, 50, 40, 150, 35, 55, 110])
    elements.append(table)

    return _build_pdf(elements, is_landscape=True)