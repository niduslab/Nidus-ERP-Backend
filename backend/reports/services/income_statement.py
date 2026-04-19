# backend/reports/services/income_statement.py

"""
Income Statement (Profit & Loss) — Zoho Books style layout.

LAYOUT:
    Operating Income → Total Operating Income
    Cost of Goods Sold → Total COGS
    GROSS PROFIT = Op Income − COGS
    Operating Expenses → Total Operating Expenses
    OPERATING PROFIT = Gross Profit − Op Expenses
    Non-Operating Income → Total Non-Op Income
    Non-Operating Expenses → Total Non-Op Expenses
    NET PROFIT/LOSS

L2 CLASSIFICATION PATHS (from seed.py):
    4.40  Operating Income
    4.41  Non-Operating Income
    5.50  Cost of Sales (COGS)
    5.51  Operating Expense
    5.52  Non-Operating Expense
"""

from datetime import date
from decimal import Decimal

from chartofaccounts.models import Account, AccountClassification
from companies.models import Company

from .balance_engine import (
    get_period_balances,
    get_accounts_with_transactions_in_period,
)
from .trial_balance import (
    _build_account_node,
    _has_included_descendant,
    _get_included_account_ids,
    _stringify_accounts,
    FILTER_ALL,
    FILTER_WITH_TRANSACTIONS,
    FILTER_NON_ZERO,
    VALID_FILTER_MODES,
)

ZERO = Decimal('0.00')

# ── L1 classification paths ──
L1_INCOME = '4'
L1_EXPENSE = '5'
PL_L1_PATHS = {L1_INCOME, L1_EXPENSE}

# ── L2 classification paths for Zoho-style P&L sections ──
L2_OPERATING_INCOME = '4.40'
L2_NON_OPERATING_INCOME = '4.41'
L2_COST_OF_SALES = '5.50'
L2_OPERATING_EXPENSE = '5.51'
L2_NON_OPERATING_EXPENSE = '5.52'


def generate_income_statement(company, from_date, to_date,
                               filter_mode=FILTER_NON_ZERO,
                               compare_from_date=None, compare_to_date=None):
    """
    Generate a Zoho Books-style Income Statement (P&L) report.

    Returns dict with 5 sections plus intermediary totals
    (gross_profit, operating_profit) and net_income.
    """
    has_compare = compare_from_date is not None and compare_to_date is not None

    # ── Step 1: Get period balances ──
    balances = get_period_balances(company, from_date, to_date)
    compare_balances = (
        get_period_balances(company, compare_from_date, compare_to_date)
        if has_compare else None
    )

    # ── Step 2: Get accounts with transactions (for filter mode) ──
    accounts_with_txn = None
    if filter_mode == FILTER_WITH_TRANSACTIONS:
        accounts_with_txn = get_accounts_with_transactions_in_period(
            company, from_date, to_date,
        )
        if has_compare:
            accounts_with_txn |= get_accounts_with_transactions_in_period(
                company, compare_from_date, compare_to_date,
            )

    # ── Step 3: Load ALL accounts ──
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

    # ── Step 4: Separate P&L accounts by L1 type ──
    pl_accounts = []
    for account in all_accounts:
        l1_path = account.classification.internal_path.split('.')[0]
        if l1_path in PL_L1_PATHS:
            pl_accounts.append(account)

    # ── Step 5: Build parent-child lookups ──
    children_by_parent = {}
    root_accounts_by_l3 = {}
    for account in pl_accounts:
        if account.parent_account_id:
            children_by_parent.setdefault(
                account.parent_account_id, []
            ).append(account)
        else:
            root_accounts_by_l3.setdefault(
                account.classification_id, []
            ).append(account)

    # ── Step 6: Determine included accounts ──
    included_ids = _get_included_account_ids(
        pl_accounts, balances, compare_balances,
        accounts_with_txn, filter_mode, children_by_parent,
    )

    # ── Step 7: Build full L1 sections ──
    revenue_l2_nodes = _build_section(
        L1_INCOME, root_accounts_by_l3, children_by_parent,
        class_map, balances, compare_balances, included_ids,
    )
    expenses_l2_nodes = _build_section(
        L1_EXPENSE, root_accounts_by_l3, children_by_parent,
        class_map, balances, compare_balances, included_ids,
    )

    # ── Step 8: Split L2 nodes into 5 Zoho-style sections ──
    operating_income = [
        n for n in revenue_l2_nodes
        if n['classification_path'].startswith(L2_OPERATING_INCOME)
    ]
    non_operating_income = [
        n for n in revenue_l2_nodes
        if n['classification_path'].startswith(L2_NON_OPERATING_INCOME)
    ]
    cost_of_goods_sold = [
        n for n in expenses_l2_nodes
        if n['classification_path'].startswith(L2_COST_OF_SALES)
    ]
    operating_expenses = [
        n for n in expenses_l2_nodes
        if n['classification_path'].startswith(L2_OPERATING_EXPENSE)
    ]
    non_operating_expenses = [
        n for n in expenses_l2_nodes
        if n['classification_path'].startswith(L2_NON_OPERATING_EXPENSE)
    ]

    # ── Step 9: Calculate Zoho-style totals ──
    # Revenue = NEGATED (credit-normal → positive display)
    # Expenses = AS-IS (debit-normal → already positive)
    total_operating_income = -_sum_section_total(operating_income)
    total_cogs = _sum_section_total(cost_of_goods_sold)
    gross_profit = total_operating_income - total_cogs

    total_operating_expenses = _sum_section_total(operating_expenses)
    operating_profit = gross_profit - total_operating_expenses

    total_non_operating_income = -_sum_section_total(non_operating_income)
    total_non_operating_expenses = _sum_section_total(non_operating_expenses)

    net_income = (
        operating_profit
        + total_non_operating_income
        - total_non_operating_expenses
    )

    # Legacy totals
    total_revenue = total_operating_income + total_non_operating_income
    total_expenses = total_cogs + total_operating_expenses + total_non_operating_expenses

    # ── Step 10: Comparison totals ──
    compare_data = {}
    if has_compare:
        c_op_inc = -_sum_section_total(operating_income, compare=True)
        c_cogs = _sum_section_total(cost_of_goods_sold, compare=True)
        c_gross = c_op_inc - c_cogs
        c_op_exp = _sum_section_total(operating_expenses, compare=True)
        c_op_profit = c_gross - c_op_exp
        c_noi = -_sum_section_total(non_operating_income, compare=True)
        c_noe = _sum_section_total(non_operating_expenses, compare=True)
        c_net = c_op_profit + c_noi - c_noe

        compare_data = {
            'compare_from_date': str(compare_from_date),
            'compare_to_date': str(compare_to_date),
            'compare_total_operating_income': str(c_op_inc),
            'compare_total_cogs': str(c_cogs),
            'compare_gross_profit': str(c_gross),
            'compare_total_operating_expenses': str(c_op_exp),
            'compare_operating_profit': str(c_op_profit),
            'compare_total_non_operating_income': str(c_noi),
            'compare_total_non_operating_expenses': str(c_noe),
            'compare_net_income': str(c_net),
            'compare_total_revenue': str(c_op_inc + c_noi),
            'compare_total_expenses': str(c_cogs + c_op_exp + c_noe),
            'change_net_income': str(net_income - c_net),
            'change_net_income_pct': (
                str(_pct_change(net_income, c_net))
                if _pct_change(net_income, c_net) is not None else None
            ),
        }

    # ── Step 11: Stringify all sections and add signed 'amount' field ──
    # Revenue sections are credit-normal: own_credit → +, own_debit → −
    # Expense sections are debit-normal:  own_debit → +, own_credit → −
    _stringify_section(operating_income, has_compare, debit_positive=False)
    _stringify_section(non_operating_income, has_compare, debit_positive=False)
    _stringify_section(cost_of_goods_sold, has_compare, debit_positive=True)
    _stringify_section(operating_expenses, has_compare, debit_positive=True)
    _stringify_section(non_operating_expenses, has_compare, debit_positive=True)

    # ── Step 12: Strip Dr/Cr fields — P&L uses single 'amount' only ──
    # The 'amount' field was set during stringify. Now remove the raw
    # debit/credit pairs so the JSON response is clean Zoho-style.
    for section in [operating_income, non_operating_income,
                    cost_of_goods_sold, operating_expenses, non_operating_expenses]:
        _strip_dr_cr_from_section(section)

    account_count = len([a for a in pl_accounts if a.id in included_ids])

    result = {
        'report_title': 'Income Statement',
        'company_name': company.name,
        'base_currency': company.base_currency,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'filter_mode': filter_mode,
        'account_count': account_count,

        # ── Five Zoho-style sections ──
        'operating_income': operating_income,
        'cost_of_goods_sold': cost_of_goods_sold,
        'operating_expenses': operating_expenses,
        'non_operating_income': non_operating_income,
        'non_operating_expenses': non_operating_expenses,

        # ── Intermediary totals ──
        'total_operating_income': str(total_operating_income),
        'total_cogs': str(total_cogs),
        'gross_profit': str(gross_profit),
        'total_operating_expenses': str(total_operating_expenses),
        'operating_profit': str(operating_profit),
        'total_non_operating_income': str(total_non_operating_income),
        'total_non_operating_expenses': str(total_non_operating_expenses),
        'net_income': str(net_income),

        # ── Legacy totals ──
        'total_revenue': str(total_revenue),
        'total_expenses': str(total_expenses),

        # ── Profitability indicator ──
        'is_net_profit': net_income >= ZERO,
    }
    result.update(compare_data)
    return result


# ══════════════════════════════════════════════════
# SECTION BUILDER (unchanged)
# ══════════════════════════════════════════════════

def _build_section(l1_path, root_accounts_by_l3, children_by_parent,
                    class_map, balances, compare_balances, included_ids):
    """
    Build one section (Revenue or Expenses) as a classification tree.
    Returns list of L2 nodes → L3 children → account nodes (infinite depth).
    """
    has_compare = compare_balances is not None
    needed_l3_ids = set()
    for l3_id, root_accts in root_accounts_by_l3.items():
        for acct in root_accts:
            cls_path = acct.classification.internal_path
            if not cls_path.startswith(l1_path + '.'):
                continue
            if acct.id in included_ids or _has_included_descendant(
                acct.id, included_ids, children_by_parent
            ):
                needed_l3_ids.add(l3_id)
                break

    l3_paths = {}
    for path, cls in class_map.items():
        if cls.id in needed_l3_ids and path.startswith(l1_path + '.'):
            l3_paths[cls.id] = path

    needed_l3_path_set = set(l3_paths.values())
    needed_l2 = {'.'.join(p.split('.')[:2]) for p in needed_l3_path_set}

    section = []
    for l2_path in sorted(needed_l2):
        l2_cls = class_map.get(l2_path)
        if not l2_cls:
            continue
        l2_node = {
            'name': l2_cls.name,
            'classification_path': l2_path,
            'subtotal_debit': ZERO,
            'subtotal_credit': ZERO,
            'children': [],
        }
        if has_compare:
            l2_node['compare_subtotal_debit'] = ZERO
            l2_node['compare_subtotal_credit'] = ZERO

        for l3_path in sorted(
            p for p in needed_l3_path_set if p.startswith(l2_path + '.')
        ):
            l3_cls = class_map.get(l3_path)
            if not l3_cls:
                continue
            l3_node = {
                'name': l3_cls.name,
                'classification_path': l3_path,
                'subtotal_debit': ZERO,
                'subtotal_credit': ZERO,
                'accounts': [],
            }
            if has_compare:
                l3_node['compare_subtotal_debit'] = ZERO
                l3_node['compare_subtotal_credit'] = ZERO

            for root_acct in root_accounts_by_l3.get(l3_cls.id, []):
                acct_node = _build_account_node(
                    root_acct, children_by_parent, balances,
                    compare_balances, included_ids,
                )
                if acct_node is None:
                    continue
                l3_node['accounts'].append(acct_node)
                l3_node['subtotal_debit'] += acct_node['subtotal_debit']
                l3_node['subtotal_credit'] += acct_node['subtotal_credit']
                if has_compare:
                    l3_node['compare_subtotal_debit'] += acct_node['compare_subtotal_debit']
                    l3_node['compare_subtotal_credit'] += acct_node['compare_subtotal_credit']

            if not l3_node['accounts']:
                continue
            l2_node['subtotal_debit'] += l3_node['subtotal_debit']
            l2_node['subtotal_credit'] += l3_node['subtotal_credit']
            if has_compare:
                l2_node['compare_subtotal_debit'] += l3_node['compare_subtotal_debit']
                l2_node['compare_subtotal_credit'] += l3_node['compare_subtotal_credit']
            l2_node['children'].append(l3_node)

        if not l2_node['children']:
            continue
        section.append(l2_node)

    return section


def _sum_section_total(section, compare=False):
    """Calculate raw net total (debit − credit) for a section."""
    total_debit = ZERO
    total_credit = ZERO
    for l2_node in section:
        d = l2_node.get('subtotal_debit', ZERO)
        c = l2_node.get('subtotal_credit', ZERO)
        if isinstance(d, str): d = Decimal(d)
        if isinstance(c, str): c = Decimal(c)
        if compare:
            cd = l2_node.get('compare_subtotal_debit', ZERO)
            cc = l2_node.get('compare_subtotal_credit', ZERO)
            if isinstance(cd, str): cd = Decimal(cd)
            if isinstance(cc, str): cc = Decimal(cc)
            total_debit += cd
            total_credit += cc
        else:
            total_debit += d
            total_credit += c
    return total_debit - total_credit


def _stringify_section(section, has_compare, debit_positive=True):
    """
    Convert Decimals to strings and add a signed 'amount' field.

    Sign convention (ensures accounts add up to L3 totals):
        debit_positive=True  (EXPENSE sections):
            L2/L3 amount = dr − cr;  account: own_debit→ +, own_credit→ −
        debit_positive=False (REVENUE sections):
            L2/L3 amount = cr − dr;  account: own_credit→ +, own_debit→ −
    """
    for l2_node in section:
        dr = l2_node['subtotal_debit'] if isinstance(l2_node['subtotal_debit'], Decimal) else Decimal(str(l2_node['subtotal_debit']))
        cr = l2_node['subtotal_credit'] if isinstance(l2_node['subtotal_credit'], Decimal) else Decimal(str(l2_node['subtotal_credit']))
        l2_node['amount'] = str(dr - cr) if debit_positive else str(cr - dr)

        l2_node['subtotal_debit'] = str(l2_node['subtotal_debit'])
        l2_node['subtotal_credit'] = str(l2_node['subtotal_credit'])
        if has_compare and 'compare_subtotal_debit' in l2_node:
            l2_node['compare_subtotal_debit'] = str(l2_node['compare_subtotal_debit'])
            l2_node['compare_subtotal_credit'] = str(l2_node['compare_subtotal_credit'])

        for l3_node in l2_node.get('children', []):
            l3_dr = l3_node.get('subtotal_debit', ZERO)
            l3_cr = l3_node.get('subtotal_credit', ZERO)
            if isinstance(l3_dr, str): l3_dr = Decimal(l3_dr)
            if isinstance(l3_cr, str): l3_cr = Decimal(l3_cr)
            l3_node['amount'] = str(l3_dr - l3_cr) if debit_positive else str(l3_cr - l3_dr)

            if isinstance(l3_node.get('subtotal_debit'), Decimal):
                l3_node['subtotal_debit'] = str(l3_node['subtotal_debit'])
                l3_node['subtotal_credit'] = str(l3_node['subtotal_credit'])
            if has_compare and isinstance(l3_node.get('compare_subtotal_debit'), Decimal):
                l3_node['compare_subtotal_debit'] = str(l3_node['compare_subtotal_debit'])
                l3_node['compare_subtotal_credit'] = str(l3_node['compare_subtotal_credit'])

            _add_amount_to_accounts(l3_node.get('accounts', []), debit_positive)
            _stringify_accounts(l3_node.get('accounts', []), has_compare)


def _add_amount_to_accounts(accounts, debit_positive=True):
    """
    Recursively add a signed 'amount' field to each account node.

    debit_positive=True  (EXPENSE): own_debit → +, own_credit → −
    debit_positive=False (REVENUE): own_credit → +, own_debit → −
    """
    for acct in accounts:
        own_dr = acct.get('own_debit_balance')
        own_cr = acct.get('own_credit_balance')
        if debit_positive:
            if own_dr is not None:
                acct['amount'] = str(own_dr)
            elif own_cr is not None:
                acct['amount'] = str(-Decimal(str(own_cr)))
            else:
                acct['amount'] = None
        else:
            if own_cr is not None:
                acct['amount'] = str(own_cr)
            elif own_dr is not None:
                acct['amount'] = str(-Decimal(str(own_dr)))
            else:
                acct['amount'] = None
        _add_amount_to_accounts(acct.get('children', []), debit_positive)


def _pct_change(current, previous):
    """Percentage change: ((current − previous) / |previous|) × 100."""
    if previous == ZERO:
        return None
    return ((current - previous) / abs(previous) * 100).quantize(Decimal('0.01'))


# ══════════════════════════════════════════════════
# DR/CR FIELD STRIPPER (Zoho-style clean JSON)
# ══════════════════════════════════════════════════

# Fields to remove from P&L nodes — the 'amount' field replaces these
_DR_CR_FIELDS = {
    'subtotal_debit', 'subtotal_credit',
    'own_debit_balance', 'own_credit_balance',
    'compare_subtotal_debit', 'compare_subtotal_credit',
    'compare_own_debit_balance', 'compare_own_credit_balance',
}


def _strip_dr_cr_from_section(section):
    """
    Remove all debit/credit field pairs from a P&L section tree.
    Called after 'amount' is set on every node, so the data is not lost.
    This gives the frontend a clean Zoho-style JSON with only 'amount'.
    """
    for l2_node in section:
        for field in _DR_CR_FIELDS:
            l2_node.pop(field, None)
        for l3_node in l2_node.get('children', []):
            for field in _DR_CR_FIELDS:
                l3_node.pop(field, None)
            _strip_dr_cr_from_accounts(l3_node.get('accounts', []))


def _strip_dr_cr_from_accounts(accounts):
    """Recursively strip debit/credit fields from account nodes."""
    for acct in accounts:
        for field in _DR_CR_FIELDS:
            acct.pop(field, None)
        _strip_dr_cr_from_accounts(acct.get('children', []))