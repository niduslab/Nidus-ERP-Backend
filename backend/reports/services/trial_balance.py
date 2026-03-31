# backend/reports/services/trial_balance.py

"""
Trial Balance report generation.

KEY FEATURES:
    1. INFINITE SUB-ACCOUNT DEPTH: Accounts nest under their parents
       to any depth. Each parent shows its own balance plus a subtotal
       that includes all descendants — exactly like Zoho Books.

       Example:
       Cash (L3 classification)
         ├─ Petty Cash .............. own: 50,000 | subtotal: 85,000
         │   ├─ Office Petty Cash .. 20,000
         │   └─ Branch Petty Cash .. own: 10,000 | subtotal: 15,000
         │       └─ Dhaka Branch ... 5,000
         └─ Bank .................. 200,000

    2. INACTIVE ACCOUNTS INCLUDED: Deactivated accounts may hold
       balances. is_active is in the response for frontend styling.

    3. THREE FILTER MODES:
       - 'all':               Every account in the CoA
       - 'with_transactions': Accounts with at least 1 ledger entry
       - 'non_zero':          Accounts with non-zero balance (default)

    4. COMPARISON MODE: Optional second date for side-by-side display.

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

ZERO = Decimal('0.00')


def generate_trial_balance(company, as_of_date, filter_mode=FILTER_NON_ZERO,
                           compare_date=None):
    """
    Generate a complete Trial Balance report.
    """
    # ── Step 1: Get raw balances ──
    balances = get_account_balances(company, as_of_date)
    compare_balances = get_account_balances(company, compare_date) if compare_date else None

    # ── Step 2: Get accounts with transactions (for filter mode) ──
    accounts_with_txn = None
    if filter_mode == FILTER_WITH_TRANSACTIONS:
        accounts_with_txn = get_accounts_with_transactions(company, as_of_date)
        if compare_date:
            accounts_with_txn |= get_accounts_with_transactions(company, compare_date)

    # ── Step 3: Load ALL accounts (active + inactive) ──
    # CRITICAL: Do NOT filter by is_active.
    all_accounts = list(
        Account.objects
        .filter(company=company)
        .select_related('classification', 'parent_account')
        .order_by('internal_path')
    )

    classifications = list(
        AccountClassification.objects
        .filter(company=company)
        .order_by('internal_path')
    )

    class_map = {c.internal_path: c for c in classifications}

    # ── Step 4: Build parent-child lookups ──
    children_by_parent = {}  # {parent_account_id: [child accounts]}
    root_accounts_by_l3 = {}  # {l3_classification_id: [root accounts]}

    for account in all_accounts:
        if account.parent_account_id:
            children_by_parent.setdefault(account.parent_account_id, []).append(account)
        else:
            root_accounts_by_l3.setdefault(account.classification_id, []).append(account)

    # ── Step 5: Determine included accounts ──
    included_ids = _get_included_account_ids(
        all_accounts, balances, compare_balances,
        accounts_with_txn, filter_mode, children_by_parent,
    )

    # ── Step 6: Build nested tree ──
    has_compare = compare_balances is not None
    tree = _build_classification_tree(
        root_accounts_by_l3, children_by_parent, class_map,
        balances, compare_balances, included_ids,
    )

    # ── Step 7: Grand totals (from ALL accounts, not filtered) ──
    grand_total_debit = ZERO
    grand_total_credit = ZERO
    compare_grand_debit = ZERO
    compare_grand_credit = ZERO

    for account in all_accounts:
        bal = balances.get(account.id)
        if bal:
            if bal['net'] > 0:
                grand_total_debit += bal['net']
            elif bal['net'] < 0:
                grand_total_credit += abs(bal['net'])

        if has_compare:
            comp = compare_balances.get(account.id)
            if comp:
                if comp['net'] > 0:
                    compare_grand_debit += comp['net']
                elif comp['net'] < 0:
                    compare_grand_credit += abs(comp['net'])

    # ── Step 8: Build flat list ──
    flat_list = _build_flat_list(
        all_accounts, balances, compare_balances,
        included_ids, children_by_parent,
    )

    return {
        'report_title': 'Trial Balance',
        'company_name': company.name,
        'base_currency': company.base_currency,
        'as_of_date': str(as_of_date),
        'compare_date': str(compare_date) if compare_date else None,
        'filter_mode': filter_mode,
        'account_count': len([a for a in all_accounts if a.id in included_ids]),
        'groups': tree,
        'flat_accounts': flat_list,
        'grand_total_debit': str(grand_total_debit),
        'grand_total_credit': str(grand_total_credit),
        'compare_grand_total_debit': str(compare_grand_debit) if has_compare else None,
        'compare_grand_total_credit': str(compare_grand_credit) if has_compare else None,
        'is_balanced': grand_total_debit == grand_total_credit,
    }


# ══════════════════════════════════════════════════
# FILTER: DETERMINE WHICH ACCOUNTS TO SHOW
# ══════════════════════════════════════════════════

def _get_included_account_ids(all_accounts, balances, compare_balances,
                               accounts_with_txn, filter_mode, children_by_parent):
    """
    Determine which accounts pass the filter.

    IMPORTANT: If a child passes, its entire parent chain is included
    so the tree structure remains coherent. A parent with zero balance
    still appears if its grandchild has a non-zero balance.
    """
    if filter_mode == FILTER_ALL:
        return {a.id for a in all_accounts}

    # First pass: accounts that directly pass the filter
    directly_included = set()
    for account in all_accounts:
        if filter_mode == FILTER_NON_ZERO:
            bal = balances.get(account.id)
            comp = compare_balances.get(account.id) if compare_balances else None
            if (bal and bal['net'] != ZERO) or (comp and comp['net'] != ZERO):
                directly_included.add(account.id)
        elif filter_mode == FILTER_WITH_TRANSACTIONS:
            if account.id in accounts_with_txn:
                directly_included.add(account.id)

    # Second pass: include parent chain for every directly included account
    account_map = {a.id: a for a in all_accounts}
    included = set(directly_included)

    for account_id in directly_included:
        current = account_map.get(account_id)
        while current and current.parent_account_id:
            included.add(current.parent_account_id)
            current = account_map.get(current.parent_account_id)

    return included


# ══════════════════════════════════════════════════
# CLASSIFICATION TREE BUILDER (L1 > L2 > L3)
# ══════════════════════════════════════════════════

def _build_classification_tree(root_accounts_by_l3, children_by_parent,
                                class_map, balances, compare_balances,
                                included_ids):
    """
    Build the top-level classification tree (L1 > L2 > L3), then
    attach the account tree under each L3.

    All subtotals are computed as Decimals during construction,
    then converted to strings at the very end via _stringify_tree().
    """
    has_compare = compare_balances is not None

    # Find which L3 classifications have included accounts
    needed_l3_ids = set()
    for l3_id, root_accts in root_accounts_by_l3.items():
        for acct in root_accts:
            if acct.id in included_ids or _has_included_descendant(
                acct.id, included_ids, children_by_parent
            ):
                needed_l3_ids.add(l3_id)
                break

    # Map L3 IDs to paths
    l3_paths = {}
    for path, cls in class_map.items():
        if cls.id in needed_l3_ids:
            l3_paths[cls.id] = path

    needed_l3_path_set = set(l3_paths.values())
    needed_l2 = {'.'.join(p.split('.')[:2]) for p in needed_l3_path_set}
    needed_l1 = {p.split('.')[0] for p in needed_l3_path_set}

    tree = []

    for l1_path in sorted(needed_l1):
        l1_cls = class_map.get(l1_path)
        if not l1_cls:
            continue
        l1 = {'name': l1_cls.name, 'classification_path': l1_path,
               'subtotal_debit': ZERO, 'subtotal_credit': ZERO, 'children': []}
        if has_compare:
            l1['compare_subtotal_debit'] = ZERO
            l1['compare_subtotal_credit'] = ZERO

        for l2_path in sorted(p for p in needed_l2 if p.startswith(l1_path + '.')):
            l2_cls = class_map.get(l2_path)
            if not l2_cls:
                continue
            l2 = {'name': l2_cls.name, 'classification_path': l2_path,
                   'subtotal_debit': ZERO, 'subtotal_credit': ZERO, 'children': []}
            if has_compare:
                l2['compare_subtotal_debit'] = ZERO
                l2['compare_subtotal_credit'] = ZERO

            for l3_path in sorted(p for p in needed_l3_path_set if p.startswith(l2_path + '.')):
                l3_cls = class_map.get(l3_path)
                if not l3_cls:
                    continue
                l3 = {'name': l3_cls.name, 'classification_path': l3_path,
                       'subtotal_debit': ZERO, 'subtotal_credit': ZERO, 'accounts': []}
                if has_compare:
                    l3['compare_subtotal_debit'] = ZERO
                    l3['compare_subtotal_credit'] = ZERO

                # Build account trees under this L3
                for root_acct in root_accounts_by_l3.get(l3_cls.id, []):
                    acct_node = _build_account_node(
                        root_acct, children_by_parent, balances,
                        compare_balances, included_ids,
                    )
                    if acct_node is None:
                        continue
                    l3['accounts'].append(acct_node)
                    # Roll up to L3 subtotal (use the account's subtotal which
                    # already includes all descendants)
                    l3['subtotal_debit'] += acct_node['subtotal_debit']
                    l3['subtotal_credit'] += acct_node['subtotal_credit']
                    if has_compare:
                        l3['compare_subtotal_debit'] += acct_node['compare_subtotal_debit']
                        l3['compare_subtotal_credit'] += acct_node['compare_subtotal_credit']

                if not l3['accounts']:
                    continue

                l2['subtotal_debit'] += l3['subtotal_debit']
                l2['subtotal_credit'] += l3['subtotal_credit']
                if has_compare:
                    l2['compare_subtotal_debit'] += l3['compare_subtotal_debit']
                    l2['compare_subtotal_credit'] += l3['compare_subtotal_credit']

                l2['children'].append(l3)

            if not l2['children']:
                continue

            l1['subtotal_debit'] += l2['subtotal_debit']
            l1['subtotal_credit'] += l2['subtotal_credit']
            if has_compare:
                l1['compare_subtotal_debit'] += l2['compare_subtotal_debit']
                l1['compare_subtotal_credit'] += l2['compare_subtotal_credit']

            l1['children'].append(l2)

        if not l1['children']:
            continue

        tree.append(l1)

    # ── Final pass: convert all Decimal values to strings ──
    _stringify_tree(tree, has_compare)

    return tree


def _stringify_tree(nodes, has_compare):
    """
    Recursively convert all Decimal subtotals in the tree to strings.
    Called once after the entire tree is built.
    """
    for node in nodes:
        # Classification nodes
        if 'subtotal_debit' in node and isinstance(node['subtotal_debit'], Decimal):
            node['subtotal_debit'] = str(node['subtotal_debit'])
            node['subtotal_credit'] = str(node['subtotal_credit'])
            if has_compare and 'compare_subtotal_debit' in node:
                node['compare_subtotal_debit'] = str(node['compare_subtotal_debit'])
                node['compare_subtotal_credit'] = str(node['compare_subtotal_credit'])

        # Recurse into children (classification) or accounts
        if 'children' in node:
            _stringify_tree(node['children'], has_compare)
        if 'accounts' in node:
            _stringify_accounts(node['accounts'], has_compare)


def _stringify_accounts(accounts, has_compare):
    """Recursively convert Decimal values in account nodes to strings."""
    for acct in accounts:
        if isinstance(acct.get('subtotal_debit'), Decimal):
            acct['subtotal_debit'] = str(acct['subtotal_debit'])
            acct['subtotal_credit'] = str(acct['subtotal_credit'])
        if has_compare:
            if isinstance(acct.get('compare_subtotal_debit'), Decimal):
                acct['compare_subtotal_debit'] = str(acct['compare_subtotal_debit'])
                acct['compare_subtotal_credit'] = str(acct['compare_subtotal_credit'])
        # Recurse into children accounts
        if acct.get('children'):
            _stringify_accounts(acct['children'], has_compare)


# ══════════════════════════════════════════════════
# ACCOUNT NODE BUILDER (INFINITE DEPTH)
# ══════════════════════════════════════════════════

def _build_account_node(account, children_by_parent, balances,
                         compare_balances, included_ids):
    """
    Recursively build an account node with nested children.

    Returns dict with:
        - own_debit_balance / own_credit_balance: this account only
        - subtotal_debit / subtotal_credit: own + all descendants (Decimal)
        - children: list of child nodes (recursive)

    Returns None if this account and all descendants are excluded.
    """
    # Skip if neither this account nor any descendant is included
    self_included = account.id in included_ids
    has_child = _has_included_descendant(account.id, included_ids, children_by_parent)
    if not self_included and not has_child:
        return None

    has_compare = compare_balances is not None

    # ── Own balance ──
    bal = balances.get(account.id)
    net = bal['net'] if bal else ZERO
    own_debit = net if net > 0 else None
    own_credit = abs(net) if net < 0 else None

    is_unusual = (
        (account.normal_balance == 'DEBIT' and net < 0) or
        (account.normal_balance == 'CREDIT' and net > 0)
    )

    node = {
        'account_id': str(account.id),
        'code': account.code,
        'name': account.name,
        'normal_balance': account.normal_balance,
        'currency': account.currency,
        'is_active': account.is_active,
        'is_sub_account': account.is_sub_account,
        'is_unusual_balance': is_unusual,
        'own_debit_balance': str(own_debit) if own_debit else None,
        'own_credit_balance': str(own_credit) if own_credit else None,
        # Subtotals as Decimals (converted to strings by _stringify later)
        'subtotal_debit': own_debit or ZERO,
        'subtotal_credit': own_credit or ZERO,
        'children': [],
    }

    # ── Comparison own balance ──
    if has_compare:
        comp = compare_balances.get(account.id)
        comp_net = comp['net'] if comp else ZERO
        comp_debit = comp_net if comp_net > 0 else None
        comp_credit = abs(comp_net) if comp_net < 0 else None

        node['compare_own_debit_balance'] = str(comp_debit) if comp_debit else None
        node['compare_own_credit_balance'] = str(comp_credit) if comp_credit else None
        node['compare_subtotal_debit'] = comp_debit or ZERO
        node['compare_subtotal_credit'] = comp_credit or ZERO

        change = net - comp_net
        node['change_amount'] = str(change)
        node['change_percentage'] = (
            str(((net - comp_net) / abs(comp_net) * 100).quantize(Decimal('0.01')))
            if comp_net != ZERO else None
        )
    else:
        node['compare_own_debit_balance'] = None
        node['compare_own_credit_balance'] = None
        node['compare_subtotal_debit'] = ZERO
        node['compare_subtotal_credit'] = ZERO
        node['change_amount'] = None
        node['change_percentage'] = None

    # ── Recursively build children ──
    for child in children_by_parent.get(account.id, []):
        child_node = _build_account_node(
            child, children_by_parent, balances,
            compare_balances, included_ids,
        )
        if child_node is None:
            continue
        node['children'].append(child_node)
        # Roll up child subtotals (still Decimals at this point)
        node['subtotal_debit'] += child_node['subtotal_debit']
        node['subtotal_credit'] += child_node['subtotal_credit']
        if has_compare:
            node['compare_subtotal_debit'] += child_node['compare_subtotal_debit']
            node['compare_subtotal_credit'] += child_node['compare_subtotal_credit']

    return node


def _has_included_descendant(account_id, included_ids, children_by_parent):
    """Check if any descendant of this account is in the included set."""
    for child in children_by_parent.get(account_id, []):
        if child.id in included_ids:
            return True
        if _has_included_descendant(child.id, included_ids, children_by_parent):
            return True
    return False


# ══════════════════════════════════════════════════
# FLAT LIST BUILDER
# ══════════════════════════════════════════════════

def _build_flat_list(all_accounts, balances, compare_balances,
                      included_ids, children_by_parent):
    """
    Build a flat list for ?layout=flat.

    Each row includes depth, parent_account_id, and has_children
    so the frontend can reconstruct the tree if needed.
    """
    has_compare = compare_balances is not None
    flat = []

    for account in all_accounts:
        if account.id not in included_ids:
            continue

        bal = balances.get(account.id)
        net = bal['net'] if bal else ZERO
        own_debit = net if net > 0 else None
        own_credit = abs(net) if net < 0 else None

        is_unusual = (
            (account.normal_balance == 'DEBIT' and net < 0) or
            (account.normal_balance == 'CREDIT' and net > 0)
        )

        # Depth: L4=0, L5=1, L6=2, ...
        depth = max(0, len(account.internal_path.split('.')) - 4)

        row = {
            'account_id': str(account.id),
            'code': account.code,
            'name': account.name,
            'normal_balance': account.normal_balance,
            'currency': account.currency,
            'is_active': account.is_active,
            'is_sub_account': account.is_sub_account,
            'is_unusual_balance': is_unusual,
            'depth': depth,
            'parent_account_id': str(account.parent_account_id) if account.parent_account_id else None,
            'has_children': account.id in children_by_parent,
            'classification_path': account.classification.internal_path,
            'classification_name': account.classification.name,
            'debit_balance': str(own_debit) if own_debit else None,
            'credit_balance': str(own_credit) if own_credit else None,
        }

        if has_compare:
            comp = compare_balances.get(account.id)
            comp_net = comp['net'] if comp else ZERO
            row['compare_debit_balance'] = str(comp_net) if comp_net > 0 else None
            row['compare_credit_balance'] = str(abs(comp_net)) if comp_net < 0 else None
            change = net - comp_net
            row['change_amount'] = str(change)
            row['change_percentage'] = (
                str(((net - comp_net) / abs(comp_net) * 100).quantize(Decimal('0.01')))
                if comp_net != ZERO else None
            )
        else:
            row['compare_debit_balance'] = None
            row['compare_credit_balance'] = None
            row['change_amount'] = None
            row['change_percentage'] = None

        flat.append(row)

    return flat