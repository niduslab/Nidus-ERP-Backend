"""
Income Statement (Profit & Loss) report generation.

THE ACCOUNTING MODEL:
    Net Income = Total Revenue − Total Expenses

    Revenue accounts (L1 = 4) are credit-normal:
        - Raw net from balance_engine = (debit − credit)
        - For a healthy revenue account, this is NEGATIVE (more credits)
        - We NEGATE to display revenue as a positive number

    Expense accounts (L1 = 5) are debit-normal:
        - Raw net from balance_engine = (debit − credit)
        - For a normal expense account, this is POSITIVE (more debits)
        - We display as-is (positive = expense incurred)

    Net Income = Total Revenue (negated credit net) − Total Expenses (raw debit net)

PERIOD vs POINT-IN-TIME:
    Unlike the Balance Sheet (point-in-time: "as of" a date), the
    Income Statement is PERIOD-BASED: it shows activity between two dates.

    We use get_period_balances(company, from_date, to_date) from the
    balance engine, which runs a single SQL query with date range filter.
    This is more efficient than the subtraction approach used in the
    Balance Sheet's retained earnings calculation.

DEFAULT DATE LOGIC:
    If no from_date is given, we default to the company's fiscal year
    start date. This matches standard accounting practice — the P&L
    shows "Year-to-Date" (YTD) by default.

COMPARISON SUPPORT:
    The optional compare period (compare_from_date, compare_to_date)
    enables period-over-period analysis. Typical use cases:
    - This month vs. last month
    - This quarter vs. same quarter last year
    - YTD this year vs. YTD last year

RESPONSE STRUCTURE:
    Two sections (revenue, expenses), each with:
    - Classification tree (L2 > L3 > accounts with infinite nesting)
    - Section total (displayed as positive)
    Plus summary totals: total_revenue, total_expenses, net_income
    Plus comparison columns and change amounts when compare period is given

REUSES FROM trial_balance.py:
    _build_account_node, _has_included_descendant,
    _get_included_account_ids, _stringify_accounts,
    FILTER_ALL, FILTER_WITH_TRANSACTIONS, FILTER_NON_ZERO, VALID_FILTER_MODES

CALLED FROM:
    reports/views.py → IncomeStatementView
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

# ── L1 classification paths (from seed.py) ──
L1_INCOME = '4'
L1_EXPENSE = '5'
PL_L1_PATHS = {L1_INCOME, L1_EXPENSE}


def generate_income_statement(company, from_date, to_date,
                               filter_mode=FILTER_NON_ZERO,
                               compare_from_date=None, compare_to_date=None):
    """
    Generate a complete Income Statement (P&L) report.

    Args:
        company: Company instance
        from_date: datetime.date — start of reporting period (inclusive)
        to_date: datetime.date — end of reporting period (inclusive)
        filter_mode: str — 'all', 'with_transactions', or 'non_zero'
        compare_from_date: datetime.date or None — start of comparison period
        compare_to_date: datetime.date or None — end of comparison period

    Returns:
        dict: Complete Income Statement data ready for API response
    """
    has_compare = compare_from_date is not None and compare_to_date is not None

    # ── Step 1: Get period balances from balance engine ──
    # Unlike Balance Sheet which uses cumulative get_account_balances(),
    # we use get_period_balances() which filters to [from_date, to_date].
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
            # Union: include accounts active in either period
            accounts_with_txn |= get_accounts_with_transactions_in_period(
                company, compare_from_date, compare_to_date,
            )

    # ── Step 3: Load ALL accounts (active + inactive) ──
    # CRITICAL: Do NOT filter by is_active — inactive accounts may
    # have had activity during the period before deactivation.
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
    # Income Statement only shows Income (L1=4) and Expense (L1=5).
    # Balance Sheet accounts (L1=1,2,3) are excluded entirely.
    income_accounts = []   # L1 = 4 (Revenue / Income)
    expense_accounts = []  # L1 = 5 (Expense)
    pl_accounts = []       # Combined for filter/tree building

    for account in all_accounts:
        l1_path = account.classification.internal_path.split('.')[0]
        if l1_path == L1_INCOME:
            income_accounts.append(account)
            pl_accounts.append(account)
        elif l1_path == L1_EXPENSE:
            expense_accounts.append(account)
            pl_accounts.append(account)

    # ── Step 5: Build parent-child lookups (P&L accounts only) ──
    children_by_parent = {}       # {parent_account_id: [child accounts]}
    root_accounts_by_l3 = {}      # {l3_classification_id: [root accounts]}

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

    # ── Step 7: Build the two sections ──
    revenue_section = _build_section(
        L1_INCOME, root_accounts_by_l3, children_by_parent,
        class_map, balances, compare_balances, included_ids,
    )

    expenses_section = _build_section(
        L1_EXPENSE, root_accounts_by_l3, children_by_parent,
        class_map, balances, compare_balances, included_ids,
    )

    # ── Step 8: Calculate totals ──
    #
    # _sum_section_total() returns raw (debit − credit):
    #   Revenue:  typically negative (credit-normal) → negate for display
    #   Expenses: typically positive (debit-normal)  → use as-is
    #
    # Example:
    #   Revenue raw net  = −500,000  → total_revenue  = 500,000
    #   Expense raw net  = +350,000  → total_expenses = 350,000
    #   Net Income = 500,000 − 350,000 = 150,000 (profit)
    #
    total_revenue = -_sum_section_total(revenue_section)
    total_expenses = _sum_section_total(expenses_section)
    net_income = total_revenue - total_expenses

    # ── Step 9: Comparison totals ──
    compare_total_revenue = None
    compare_total_expenses = None
    compare_net_income = None
    change_revenue = None
    change_expenses = None
    change_net_income = None
    change_revenue_pct = None
    change_expenses_pct = None
    change_net_income_pct = None

    if has_compare:
        compare_total_revenue = -_sum_section_total(
            revenue_section, compare=True
        )
        compare_total_expenses = _sum_section_total(
            expenses_section, compare=True
        )
        compare_net_income = compare_total_revenue - compare_total_expenses

        # Absolute changes
        change_revenue = total_revenue - compare_total_revenue
        change_expenses = total_expenses - compare_total_expenses
        change_net_income = net_income - compare_net_income

        # Percentage changes (None if compare base is zero)
        change_revenue_pct = _pct_change(total_revenue, compare_total_revenue)
        change_expenses_pct = _pct_change(total_expenses, compare_total_expenses)
        change_net_income_pct = _pct_change(net_income, compare_net_income)

    # ── Step 10: Stringify all sections ──
    _stringify_section(revenue_section, has_compare)
    _stringify_section(expenses_section, has_compare)

    # Count included accounts
    account_count = len([a for a in pl_accounts if a.id in included_ids])

    return {
        'report_title': 'Income Statement',
        'company_name': company.name,
        'base_currency': company.base_currency,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'compare_from_date': str(compare_from_date) if has_compare else None,
        'compare_to_date': str(compare_to_date) if has_compare else None,
        'filter_mode': filter_mode,
        'account_count': account_count,

        # ── Two sections ──
        'revenue': revenue_section,
        'expenses': expenses_section,

        # ── Summary totals ──
        'total_revenue': str(total_revenue),
        'total_expenses': str(total_expenses),
        'net_income': str(net_income),

        # ── Comparison totals ──
        'compare_total_revenue': str(compare_total_revenue) if has_compare else None,
        'compare_total_expenses': str(compare_total_expenses) if has_compare else None,
        'compare_net_income': str(compare_net_income) if has_compare else None,

        # ── Changes ──
        'change_revenue': str(change_revenue) if has_compare else None,
        'change_expenses': str(change_expenses) if has_compare else None,
        'change_net_income': str(change_net_income) if has_compare else None,
        'change_revenue_pct': str(change_revenue_pct) if change_revenue_pct is not None else None,
        'change_expenses_pct': str(change_expenses_pct) if change_expenses_pct is not None else None,
        'change_net_income_pct': str(change_net_income_pct) if change_net_income_pct is not None else None,

        # ── Profitability indicator ──
        'is_net_profit': net_income >= ZERO,
    }


# ══════════════════════════════════════════════════
# SECTION BUILDER
# ══════════════════════════════════════════════════

def _build_section(l1_path, root_accounts_by_l3, children_by_parent,
                    class_map, balances, compare_balances, included_ids):
    """
    Build one section (Revenue or Expenses) as a classification tree.

    Identical structure to balance_sheet._build_section():
        L2 classification > L3 classification > account nodes (infinite depth)

    Returns list of L2 nodes, each containing L3 children, each
    containing account nodes with recursive sub-account nesting.
    """
    has_compare = compare_balances is not None

    # Find L3 classifications under this L1 that have included accounts
    needed_l3_ids = set()
    for l3_id, root_accts in root_accounts_by_l3.items():
        for acct in root_accts:
            cls_path = acct.classification.internal_path
            # Ensure this L3 belongs to the correct L1 section
            if not cls_path.startswith(l1_path + '.'):
                continue
            if acct.id in included_ids or _has_included_descendant(
                acct.id, included_ids, children_by_parent
            ):
                needed_l3_ids.add(l3_id)
                break  # One qualifying account is enough for this L3

    # Map L3 IDs to their internal paths
    l3_paths = {}
    for path, cls in class_map.items():
        if cls.id in needed_l3_ids and path.startswith(l1_path + '.'):
            l3_paths[cls.id] = path

    needed_l3_path_set = set(l3_paths.values())
    # Derive which L2 groups are needed (take the first 2 segments of L3 paths)
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

        # Iterate L3 classifications under this L2
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

            # Build account trees under this L3
            for root_acct in root_accounts_by_l3.get(l3_cls.id, []):
                acct_node = _build_account_node(
                    root_acct, children_by_parent, balances,
                    compare_balances, included_ids,
                )
                if acct_node is None:
                    continue
                l3_node['accounts'].append(acct_node)
                # Roll up child subtotals into L3
                l3_node['subtotal_debit'] += acct_node['subtotal_debit']
                l3_node['subtotal_credit'] += acct_node['subtotal_credit']
                if has_compare:
                    l3_node['compare_subtotal_debit'] += acct_node['compare_subtotal_debit']
                    l3_node['compare_subtotal_credit'] += acct_node['compare_subtotal_credit']

            if not l3_node['accounts']:
                continue

            # Roll up L3 subtotals into L2
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


# ══════════════════════════════════════════════════
# SECTION TOTAL CALCULATOR
# ══════════════════════════════════════════════════

def _sum_section_total(section, compare=False):
    """
    Calculate the raw net total (debit − credit) for a section.

    Returns the same (debit − credit) convention as the balance engine:
        Revenue section:  raw net is typically NEGATIVE (credit-heavy)
        Expense section:  raw net is typically POSITIVE (debit-heavy)

    The caller handles sign interpretation:
        total_revenue  = -_sum_section_total(revenue_section)
        total_expenses =  _sum_section_total(expenses_section)
    """
    total_debit = ZERO
    total_credit = ZERO

    for l2_node in section:
        d = l2_node.get('subtotal_debit', ZERO)
        c = l2_node.get('subtotal_credit', ZERO)

        # Handle both Decimal and string (depends on call timing)
        if isinstance(d, str):
            d = Decimal(d)
        if isinstance(c, str):
            c = Decimal(c)

        if compare:
            cd = l2_node.get('compare_subtotal_debit', ZERO)
            cc = l2_node.get('compare_subtotal_credit', ZERO)
            if isinstance(cd, str):
                cd = Decimal(cd)
            if isinstance(cc, str):
                cc = Decimal(cc)
            total_debit += cd
            total_credit += cc
        else:
            total_debit += d
            total_credit += c

    return total_debit - total_credit


# ══════════════════════════════════════════════════
# STRINGIFY HELPERS
# ══════════════════════════════════════════════════

def _stringify_section(section, has_compare):
    """
    Convert all Decimal values in a section tree to strings.

    Mirrors balance_sheet._stringify_section() exactly — single
    stringify pass at the end to avoid repeated Decimal→str conversion.
    """
    for l2_node in section:
        l2_node['subtotal_debit'] = str(l2_node['subtotal_debit'])
        l2_node['subtotal_credit'] = str(l2_node['subtotal_credit'])
        if has_compare and 'compare_subtotal_debit' in l2_node:
            l2_node['compare_subtotal_debit'] = str(l2_node['compare_subtotal_debit'])
            l2_node['compare_subtotal_credit'] = str(l2_node['compare_subtotal_credit'])

        for l3_node in l2_node.get('children', []):
            if isinstance(l3_node.get('subtotal_debit'), Decimal):
                l3_node['subtotal_debit'] = str(l3_node['subtotal_debit'])
                l3_node['subtotal_credit'] = str(l3_node['subtotal_credit'])
            if has_compare and isinstance(l3_node.get('compare_subtotal_debit'), Decimal):
                l3_node['compare_subtotal_debit'] = str(l3_node['compare_subtotal_debit'])
                l3_node['compare_subtotal_credit'] = str(l3_node['compare_subtotal_credit'])

            # Reuse the shared recursive account stringifier
            _stringify_accounts(l3_node.get('accounts', []), has_compare)


# ══════════════════════════════════════════════════
# PERCENTAGE CHANGE HELPER
# ══════════════════════════════════════════════════

def _pct_change(current, previous):
    """
    Calculate percentage change: ((current − previous) / |previous|) × 100.

    Returns Decimal rounded to 2 places, or None if previous is zero
    (division by zero → undefined percentage change).
    """
    if previous == ZERO:
        return None
    return ((current - previous) / abs(previous) * 100).quantize(Decimal('0.01'))