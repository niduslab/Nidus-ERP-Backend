# backend/reports/exporters/styles.py

"""
Shared style constants and helper functions for all export renderers.

Centralises colours, fonts, and formatting so all export formats
(Excel, PDF, DOCX) have a consistent visual identity.
"""

from decimal import Decimal


# ══════════════════════════════════════════════════
# BRAND COLOURS (Nidus ERP)
# ══════════════════════════════════════════════════

# Primary palette — dark navy-blue header, light body
COLOUR_PRIMARY = '1A5276'       # Dark navy — headers, titles
COLOUR_PRIMARY_LIGHT = '2E86C1' # Medium blue — accents, links
COLOUR_HEADER_BG = '1A5276'     # Table header background
COLOUR_HEADER_FG = 'FFFFFF'     # Table header text (white)
COLOUR_ROW_ALT = 'F2F7FB'       # Alternating row background (light blue-grey)
COLOUR_ROW_WHITE = 'FFFFFF'     # Normal row background
COLOUR_SUBTOTAL_BG = 'E8EDF2'   # Subtotal row background (slightly darker)
COLOUR_TOTAL_BG = 'D4DDE6'      # Grand total row background
COLOUR_SECTION_BG = 'E8F0FE'    # Section header background (light blue)
COLOUR_BORDER = 'CCCCCC'        # Table border colour (light grey)
COLOUR_TEXT = '333333'           # Body text colour
COLOUR_TEXT_LIGHT = '777777'     # Secondary text (dates, notes)
COLOUR_POSITIVE = '1B5E20'      # Positive values / profit (dark green)
COLOUR_NEGATIVE = 'B71C1C'      # Negative values / loss (dark red)

# Classification layer colours (for PDF/DOCX tree reports)
# Each layer gets a distinct colour so users can visually scan
# the hierarchy without needing indentation alone.
COLOUR_L1 = '1A237E'            # Deep indigo — L1 elements (Asset, Liability, etc.)
COLOUR_L2 = '00695C'            # Strong blue  — L2 categories (Current Asset, etc.)
COLOUR_L3 = '1565C0'            # Dark teal    — L3 groups (Cash, Bank, Inventory, etc.)
COLOUR_TOTAL = '1A237E'         # Deep indigo  — Total/summary rows


# ══════════════════════════════════════════════════
# FONT SETTINGS
# ══════════════════════════════════════════════════

# Excel and DOCX use OS font names (Arial is universally available)
FONT_NAME = 'Arial'
# Reportlab (PDF) uses PostScript font names — Arial doesn't exist there.
# Helvetica is reportlab's built-in equivalent of Arial.
FONT_NAME_PDF = 'Helvetica'

FONT_SIZE_TITLE = 14
FONT_SIZE_SUBTITLE = 11
FONT_SIZE_HEADER = 10
FONT_SIZE_BODY = 10
FONT_SIZE_SMALL = 9


# ══════════════════════════════════════════════════
# EXCEL-SPECIFIC CONSTANTS (openpyxl)
# ══════════════════════════════════════════════════

# Number formats
EXCEL_NUMBER_FORMAT = '#,##0.00'
EXCEL_DATE_FORMAT = 'YYYY-MM-DD'
EXCEL_PERCENTAGE_FORMAT = '#,##0.00"%"'


# ══════════════════════════════════════════════════
# SHARED HELPERS
# ══════════════════════════════════════════════════

def fmt_amount(value, show_sign=False):
    """
    Format an amount string for display.
    Converts Decimal/string to a clean number string.
    Returns '—' for None/zero when appropriate.
    """
    if value is None:
        return '—'
    if isinstance(value, str):
        try:
            value = Decimal(value)
        except Exception:
            return str(value)
    if isinstance(value, Decimal) and value == 0:
        return '0.00'
    if show_sign and isinstance(value, Decimal) and value > 0:
        return '+{:,.2f}'.format(value)
    if isinstance(value, (Decimal, float, int)):
        return '{:,.2f}'.format(value)
    return str(value)


def to_decimal(value):
    """Safely convert a string/number to Decimal."""
    if value is None:
        return Decimal('0.00')
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal('0.00')


def pl_account_amount(acct):
    """
    Return the single display amount for a P&L account.
    Prefers the pre-computed 'amount' field, falls back to own_balance fields.
    """
    # Pre-computed amount (set by _stringify_section in income_statement.py)
    amt = acct.get('amount')
    if amt is not None:
        return to_decimal(amt)
    # Fallback to raw balance fields
    own_dr = acct.get('own_debit_balance')
    own_cr = acct.get('own_credit_balance')
    if own_dr is not None:
        return to_decimal(own_dr)
    if own_cr is not None:
        return to_decimal(own_cr)
    return None


def pl_l3_amount(l3):
    """
    Return the single net display amount for a P&L L3 classification.
    Prefers the pre-computed 'amount' field, falls back to subtotal fields.
    """
    amt = l3.get('amount')
    if amt is not None:
        return to_decimal(amt)
    dr = to_decimal(l3.get('subtotal_debit'))
    cr = to_decimal(l3.get('subtotal_credit'))
    return abs(dr - cr)


def build_header_info(report_data):
    """
    Extract common header fields from any report data dict.
    Returns a dict with standardised keys for all renderers.
    """
    return {
        'report_title': report_data.get('report_title', 'Report'),
        'company_name': report_data.get('company_name', ''),
        'base_currency': report_data.get('base_currency', ''),
        'from_date': report_data.get('from_date', ''),
        'to_date': report_data.get('to_date', ''),
        'as_of_date': report_data.get('as_of_date', ''),
        'filter_mode': report_data.get('filter_mode', ''),
        'generated_at': report_data.get('generated_at', ''),
        'method': report_data.get('method', ''),
    }