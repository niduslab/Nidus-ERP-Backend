# backend/reports/services/trial_balance.py

"""
Trial Balance report generation.

Takes raw account balances from balance_engine and transforms them into
a structured, grouped report ready for API response.

GROUPING STRATEGY:
    Layer 1 (Asset, Liability, Equity, Income, Expense)
      └─ Layer 2 (Current Asset, Non-Current Asset, ...)
           └─ Layer 3 (Cash, Bank, Inventory, ...)
                └─ Accounts (Petty Cash, Bank, ...)

    Each layer includes a subtotal. The grand total at the bottom
    proves that total debits = total credits.

FILTER MODES:
    - 'all':               Every active account in the CoA
    - 'with_transactions': Only accounts that have at least 1 ledger entry
    - 'non_zero':          Only accounts with non-zero balance (default)

COMPARISON MODE:
    When compare_date is provided, the report includes two columns:
    primary date balances and comparison date balances, plus the
    change (amount and percentage) between them.

CALLED FROM:
    reports/views.py → TrialBalanceView
"""

from decimal import Decimal

from chartofaccounts.models import Account, AccountClassification

from .balance_engine import get_account_balances, get_accounts_with_transactions


# ── Valid filter modes ──
FILTER_ALL = 'all'
FILTER_WITH_TRANSACTIONS = 'with_transactions'
FILTER_NON_ZERO = 'non_zero'
VALID_FILTER_MODES = {FILTER_ALL, FILTER_WITH_TRANSACTIONS, FILTER_NON_ZERO}


def generate_trial_balance(company, as_of_date, filter_mode=FILTER_NON_ZERO,
                           compare_date=None):
    """
    Generate a complete Trial Balance report.

    Args:
        company: Company instance
        as_of_date: datetime.date — primary report date
        filter_mode: str — 'all', 'with_transactions', or 'non_zero'
        compare_date: datetime.date or None — optional comparison date

    Returns:
        dict: Complete report data ready for API response
    """
    # ── Step 1: Get raw balances from the balance engine ──
    balances = get_account_balances(company, as_of_date)

    compare_balances = None
    if compare_date:
        compare_balances = get_account_balances(company, compare_date)

    # ── Step 2: Get accounts with transactions (for filter mode) ──
    accounts_with_txn = None
    if filter_mode == FILTER_WITH_TRANSACTIONS:
        accounts_with_txn = get_accounts_with_transactions(company, as_of_date)
        if compare_date:
            # Union: include accounts with transactions in either period
            accounts_with_txn |= get_accounts_with_transactions(
                company, compare_date,
            )

    # ── Step 3: Load all active accounts + classifications ──
    # Two queries total: one for accounts, one for classifications
    accounts = (
        Account.objects
        .filter(company=company, is_active=True)
        .select_related('classification')
        .order_by('internal_path')
    )

    classifications = (
        AccountClassification.objects
        .filter(company=company)
        .order_by('internal_path')
    )

    # ── Step 4: Build classification lookup ──
    # {internal_path: classification object}
    class_map = {c.internal_path: c for c in classifications}

    # ── Step 5: Filter accounts based on filter_mode ──
    filtered_accounts = []
    for account in accounts:
        account_id = account.id
        bal = balances.get(account_id)
        comp_bal = compare_balances.get(account_id) if compare_balances else None

        if filter_mode == FILTER_NON_ZERO:
            # Show only if primary OR comparison balance is non-zero
            has_primary = bal and bal['net'] != Decimal('0.00')
            has_compare = comp_bal and comp_bal['net'] != Decimal('0.00')
            if not has_primary and not has_compare:
                continue

        elif filter_mode == FILTER_WITH_TRANSACTIONS:
            # Show only if the account has at least one transaction
            if account_id not in accounts_with_txn:
                continue

        # filter_mode == FILTER_ALL → include everything

        filtered_accounts.append(account)

    # ── Step 6: Build the nested tree structure ──
    tree = _build_nested_tree(
        filtered_accounts, class_map, balances, compare_balances,
    )

    # ── Step 7: Calculate grand totals ──
    grand_total_debit = Decimal('0.00')
    grand_total_credit = Decimal('0.00')
    compare_grand_total_debit = Decimal('0.00')
    compare_grand_total_credit = Decimal('0.00')

    for account in filtered_accounts:
        bal = balances.get(account.id)
        if bal:
            if bal['net'] > 0:
                grand_total_debit += bal['net']
            elif bal['net'] < 0:
                grand_total_credit += abs(bal['net'])

        if compare_balances:
            comp_bal = compare_balances.get(account.id)
            if comp_bal:
                if comp_bal['net'] > 0:
                    compare_grand_total_debit += comp_bal['net']
                elif comp_bal['net'] < 0:
                    compare_grand_total_credit += abs(comp_bal['net'])

    # ── Step 8: Build flat list (for ?format=flat) ──
    flat_list = _build_flat_list(
        filtered_accounts, balances, compare_balances,
    )

    return {
        'report_title': 'Trial Balance',
        'company_name': company.name,
        'base_currency': company.base_currency,
        'as_of_date': str(as_of_date),
        'compare_date': str(compare_date) if compare_date else None,
        'filter_mode': filter_mode,
        'account_count': len(filtered_accounts),
        'groups': tree,
        'flat_accounts': flat_list,
        'grand_total_debit': str(grand_total_debit),
        'grand_total_credit': str(grand_total_credit),
        'compare_grand_total_debit': str(compare_grand_total_debit) if compare_balances else None,
        'compare_grand_total_credit': str(compare_grand_total_credit) if compare_balances else None,
        'is_balanced': grand_total_debit == grand_total_credit,
    }


def _build_nested_tree(accounts, class_map, balances, compare_balances):
    """
    Build a nested tree grouped by Layer 1 > Layer 2 > Layer 3 > Accounts.

    Returns a list of Layer 1 groups, each containing Layer 2 children,
    each containing Layer 3 children, each containing account rows.
    """
    # ── Organize accounts by their Layer 3 classification path ──
    # {l3_path: [list of accounts]}
    accounts_by_l3 = {}
    for account in accounts:
        l3_path = account.classification.internal_path
        if l3_path not in accounts_by_l3:
            accounts_by_l3[l3_path] = []
        accounts_by_l3[l3_path].append(account)

    # ── Identify which L1, L2, L3 paths are needed ──
    # Only include classification nodes that have at least one account
    needed_l3_paths = set(accounts_by_l3.keys())

    # Derive L2 and L1 paths from L3 paths
    # e.g., L3 path "1.10.1010" → L2 "1.10" → L1 "1"
    needed_l2_paths = set()
    needed_l1_paths = set()
    for l3_path in needed_l3_paths:
        parts = l3_path.split('.')
        needed_l1_paths.add(parts[0])
        needed_l2_paths.add(f"{parts[0]}.{parts[1]}")

    # ── Build tree ──
    tree = []

    # Sort L1 paths for consistent ordering (1, 2, 3, 4, 5)
    for l1_path in sorted(needed_l1_paths):
        l1_class = class_map.get(l1_path)
        if not l1_class:
            continue

        l1_node = {
            'name': l1_class.name,
            'classification_path': l1_path,
            'subtotal_debit': Decimal('0.00'),
            'subtotal_credit': Decimal('0.00'),
            'compare_subtotal_debit': Decimal('0.00') if compare_balances else None,
            'compare_subtotal_credit': Decimal('0.00') if compare_balances else None,
            'children': [],
        }

        # L2 children under this L1
        for l2_path in sorted(p for p in needed_l2_paths if p.startswith(l1_path + '.')):
            l2_class = class_map.get(l2_path)
            if not l2_class:
                continue

            l2_node = {
                'name': l2_class.name,
                'classification_path': l2_path,
                'subtotal_debit': Decimal('0.00'),
                'subtotal_credit': Decimal('0.00'),
                'compare_subtotal_debit': Decimal('0.00') if compare_balances else None,
                'compare_subtotal_credit': Decimal('0.00') if compare_balances else None,
                'children': [],
            }

            # L3 children under this L2
            for l3_path in sorted(p for p in needed_l3_paths if p.startswith(l2_path + '.')):
                l3_class = class_map.get(l3_path)
                if not l3_class:
                    continue

                l3_node = {
                    'name': l3_class.name,
                    'classification_path': l3_path,
                    'subtotal_debit': Decimal('0.00'),
                    'subtotal_credit': Decimal('0.00'),
                    'compare_subtotal_debit': Decimal('0.00') if compare_balances else None,
                    'compare_subtotal_credit': Decimal('0.00') if compare_balances else None,
                    'accounts': [],
                }

                # Accounts under this L3
                for account in accounts_by_l3.get(l3_path, []):
                    acct_data = _format_account_row(
                        account, balances, compare_balances,
                    )
                    l3_node['accounts'].append(acct_data)

                    # Accumulate subtotals upward (L3 → L2 → L1)
                    _accumulate_subtotals(l3_node, acct_data)

                # Propagate L3 subtotals up to L2
                _propagate_subtotals(l2_node, l3_node)

                l3_node['subtotal_debit'] = str(l3_node['subtotal_debit'])
                l3_node['subtotal_credit'] = str(l3_node['subtotal_credit'])
                if compare_balances:
                    l3_node['compare_subtotal_debit'] = str(l3_node['compare_subtotal_debit'])
                    l3_node['compare_subtotal_credit'] = str(l3_node['compare_subtotal_credit'])

                l2_node['children'].append(l3_node)

            l2_node['subtotal_debit'] = str(l2_node['subtotal_debit'])
            l2_node['subtotal_credit'] = str(l2_node['subtotal_credit'])
            if compare_balances:
                l2_node['compare_subtotal_debit'] = str(l2_node['compare_subtotal_debit'])
                l2_node['compare_subtotal_credit'] = str(l2_node['compare_subtotal_credit'])

            l1_node['children'].append(l2_node)

            # Propagate L2 subtotals up to L1
            _propagate_subtotals(l1_node, l2_node, from_str=True)

        l1_node['subtotal_debit'] = str(l1_node['subtotal_debit'])
        l1_node['subtotal_credit'] = str(l1_node['subtotal_credit'])
        if compare_balances:
            l1_node['compare_subtotal_debit'] = str(l1_node['compare_subtotal_debit'])
            l1_node['compare_subtotal_credit'] = str(l1_node['compare_subtotal_credit'])

        tree.append(l1_node)

    return tree


def _format_account_row(account, balances, compare_balances):
    """
    Format a single account's data for the report.

    Returns dict with account info, balance columns, and comparison data.
    """
    bal = balances.get(account.id)
    net = bal['net'] if bal else Decimal('0.00')

    # Determine debit/credit column placement
    debit_balance = net if net > 0 else None
    credit_balance = abs(net) if net < 0 else None

    # Flag unusual balances (balance is opposite of normal_balance)
    is_unusual = False
    if account.normal_balance == 'DEBIT' and net < 0:
        is_unusual = True
    elif account.normal_balance == 'CREDIT' and net > 0:
        is_unusual = True

    row = {
        'account_id': str(account.id),
        'code': account.code,
        'name': account.name,
        'normal_balance': account.normal_balance,
        'currency': account.currency,
        'is_sub_account': account.is_sub_account,
        'debit_balance': str(debit_balance) if debit_balance else None,
        'credit_balance': str(credit_balance) if credit_balance else None,
        'is_unusual_balance': is_unusual,
    }

    # ── Comparison columns ──
    if compare_balances is not None:
        comp_bal = compare_balances.get(account.id)
        comp_net = comp_bal['net'] if comp_bal else Decimal('0.00')

        comp_debit = comp_net if comp_net > 0 else None
        comp_credit = abs(comp_net) if comp_net < 0 else None

        row['compare_debit_balance'] = str(comp_debit) if comp_debit else None
        row['compare_credit_balance'] = str(comp_credit) if comp_credit else None

        # Change calculation
        change = net - comp_net
        row['change_amount'] = str(change)
        if comp_net != 0:
            change_pct = ((net - comp_net) / abs(comp_net) * 100).quantize(
                Decimal('0.01'),
            )
            row['change_percentage'] = str(change_pct)
        else:
            row['change_percentage'] = None
    else:
        row['compare_debit_balance'] = None
        row['compare_credit_balance'] = None
        row['change_amount'] = None
        row['change_percentage'] = None

    return row


def _accumulate_subtotals(node, acct_data):
    """Add an account's balance to the node's running subtotal."""
    if acct_data['debit_balance']:
        node['subtotal_debit'] += Decimal(acct_data['debit_balance'])
    if acct_data['credit_balance']:
        node['subtotal_credit'] += Decimal(acct_data['credit_balance'])

    if node.get('compare_subtotal_debit') is not None:
        if acct_data.get('compare_debit_balance'):
            node['compare_subtotal_debit'] += Decimal(acct_data['compare_debit_balance'])
        if acct_data.get('compare_credit_balance'):
            node['compare_subtotal_credit'] += Decimal(acct_data['compare_credit_balance'])


def _propagate_subtotals(parent, child, from_str=False):
    """Propagate a child node's subtotals up to its parent."""
    if from_str:
        parent['subtotal_debit'] += Decimal(child['subtotal_debit'])
        parent['subtotal_credit'] += Decimal(child['subtotal_credit'])
        if parent.get('compare_subtotal_debit') is not None and child.get('compare_subtotal_debit'):
            parent['compare_subtotal_debit'] += Decimal(child['compare_subtotal_debit'])
            parent['compare_subtotal_credit'] += Decimal(child['compare_subtotal_credit'])
    else:
        parent['subtotal_debit'] += child['subtotal_debit']
        parent['subtotal_credit'] += child['subtotal_credit']
        if parent.get('compare_subtotal_debit') is not None and child.get('compare_subtotal_debit') is not None:
            parent['compare_subtotal_debit'] += child['compare_subtotal_debit']
            parent['compare_subtotal_credit'] += child['compare_subtotal_credit']


def _build_flat_list(accounts, balances, compare_balances):
    """
    Build a flat list of accounts (no grouping) for ?format=flat.
    Each row includes the account's L1/L2/L3 classification names
    so the frontend can group if needed.
    """
    flat = []
    for account in accounts:
        row = _format_account_row(account, balances, compare_balances)

        # Add classification context for frontend grouping
        classification_path = account.classification.internal_path
        parts = classification_path.split('.')

        row['classification_l1'] = parts[0] if len(parts) > 0 else None
        row['classification_l2'] = '.'.join(parts[:2]) if len(parts) > 1 else None
        row['classification_l3'] = classification_path
        row['classification_name'] = account.classification.name

        flat.append(row)

    return flat