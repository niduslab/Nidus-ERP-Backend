# backend/reports/exporters/csv_renderer.py

"""
CSV export renderer for transaction-level financial reports.

Only supports flat/transaction-level reports where data fits naturally
into rows and columns. Tree-structured reports (Trial Balance, Balance
Sheet, Income Statement, Cash Flow) are not exported as CSV because
nested classifications don't flatten well.

SUPPORTED REPORT TYPES:
    - general_ledger
    - account_transactions
    - journal_entries

FEATURES:
    - UTF-8 with BOM (ensures Excel opens with correct encoding)
    - Clean column headers
    - Dates as YYYY-MM-DD
    - Amounts as plain numbers (no formatting — let the consumer format)
"""

import csv
import io


def render_csv(report_type, report_data):
    """
    Main entry point. Dispatches to the appropriate report-specific renderer.
    Returns bytes (the .csv file content with UTF-8 BOM).
    """
    renderers = {
        'general_ledger': _render_general_ledger,
        'account_transactions': _render_account_transactions,
        'journal_entries': _render_journal_entries,
    }
    renderer = renderers.get(report_type)
    if not renderer:
        raise ValueError('No CSV renderer for report type: {}'.format(report_type))
    return renderer(report_data)


def _to_bytes(output):
    """Convert StringIO CSV output to bytes with UTF-8 BOM."""
    # BOM ensures Excel opens the file with correct UTF-8 encoding
    # without requiring the user to manually select it
    return ('\ufeff' + output.getvalue()).encode('utf-8')


# ══════════════════════════════════════════════════
# GENERAL LEDGER
# ══════════════════════════════════════════════════

def _render_general_ledger(data):
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row — separate Debit and Credit columns
    writer.writerow([
        'Account Code', 'Account Name', 'Date', 'Debit',
        'Credit', 'Running Balance',
        'Note', 'Journal Type', 'Source Module',
    ])

    for account in data.get('accounts', []):
        # Opening balance row
        writer.writerow([
            account['code'], account['name'], '',
            '', '', account.get('opening_balance'),
            'Opening Balance', '', '',
        ])

        # Transaction rows — split by entry_type into Debit/Credit cells
        for txn in account.get('transactions', []):
            dr_val = txn.get('debit', '')
            cr_val = txn.get('credit', '')
            writer.writerow([
                account['code'], account['name'], txn.get('date'),
                dr_val, cr_val,
                txn.get('running_balance'), txn.get('note'),
                txn.get('journal_type'), txn.get('source_module'),
            ])

        # Closing balance row
        writer.writerow([
            account['code'], account['name'], '',
            account.get('total_debit'), account.get('total_credit'),
            account.get('closing_balance'), 'Closing Balance', '', '',
        ])

    return _to_bytes(output)


# ══════════════════════════════════════════════════
# ACCOUNT TRANSACTIONS
# ══════════════════════════════════════════════════

def _render_account_transactions(data):
    output = io.StringIO()
    writer = csv.writer(output)

    acct = data.get('account', {})

    # Header row — separate Debit and Credit columns
    writer.writerow([
        'Date', 'Source Number', 'Source Description', 'Source Reference',
        'Debit', 'Credit', 'Currency',
        'Running Balance', 'Journal Type', 'Source Module',
    ])

    # Opening balance
    writer.writerow([
        '', '', 'Opening Balance', '',
        '', '', '',
        data.get('opening_balance'), '', '',
    ])

    # Transaction rows — split by entry_type
    for txn in data.get('transactions', []):
        dr_val = txn.get('debit', '')
        cr_val = txn.get('credit', '')
        writer.writerow([
            txn.get('date'), txn.get('source_number'),
            txn.get('source_description'), txn.get('source_reference'),
            dr_val, cr_val, txn.get('currency'),
            txn.get('running_balance'),
            txn.get('journal_type'), txn.get('source_module'),
        ])

    # Closing balance
    writer.writerow([
        '', '', 'Closing Balance', '',
        data.get('total_debit'), data.get('total_credit'), '',
        data.get('closing_balance'), '', '',
    ])

    return _to_bytes(output)


# ══════════════════════════════════════════════════
# JOURNAL ENTRIES
# ══════════════════════════════════════════════════

def _render_journal_entries(data):
    output = io.StringIO()
    writer = csv.writer(output)

    # Header row — separate Debit and Credit columns
    writer.writerow([
        'Entry Number', 'Date', 'Status', 'Journal Type',
        'Description', 'Reference', 'Currency', 'Exchange Rate',
        'Account Code', 'Account Name', 'Debit', 'Credit',
    ])

    for journal in data.get('journals', []):
        for line in journal.get('lines', []):
            dr_val = line.get('amount') if line.get('entry_type') == 'DEBIT' else ''
            cr_val = line.get('amount') if line.get('entry_type') == 'CREDIT' else ''
            writer.writerow([
                journal.get('entry_number'), journal.get('date'),
                journal.get('status'), journal.get('journal_type'),
                journal.get('description'), journal.get('reference'),
                journal.get('currency'), journal.get('exchange_rate'),
                line.get('account_code'), line.get('account_name'),
                dr_val, cr_val,
            ])

    return _to_bytes(output)
