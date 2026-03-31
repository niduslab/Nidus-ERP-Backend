# backend/reports/services/balance_sheet.py

"""
Balance Sheet (Statement of Financial Position) report generation.

THE ACCOUNTING EQUATION:
    Assets = Liabilities + Equity + (Income − Expense)

    The last term — net income — is what makes the Balance Sheet
    different from a filtered Trial Balance. Income and Expense
    accounts don't appear directly, but their net effect must be
    included in the Equity section for the equation to balance.

RETAINED EARNINGS AUTO-CALCULATION:
    The system supports BOTH auto-calculation and manual closing journals.
    This works because:

    If user HAS done a year-end closing journal:
        → Income/Expense accounts are zeroed (DR Revenue / CR Retained Earnings)
        → Retained Earnings account holds the real value
        → Auto-calculated Net Income = 0 (correct — already closed)

    If user has NOT done a closing journal:
        → Income/Expense accounts still hold balances
        → Retained Earnings account = 0
        → Auto-calculated Net Income = Income − Expense (correct)

    Either way, Total Equity = actual equity accounts + auto Net Income
    and the equation balances.

    The auto-calculation is split into two lines for clarity:
        1. "Retained Earnings (Prior Years)" — Income−Expense before
           fiscal year start. Shows 0 if already closed manually.
        2. "Current Year Net Income" — Income−Expense from fiscal year
           start to the as_of_date.

RESPONSE STRUCTURE:
    Three sections (assets, liabilities, equity), each with:
    - Classification tree (L2 > L3 > accounts with infinite nesting)
    - Section total
    Plus equity has auto-calculated earnings lines.
    Plus a verification line: is_balanced = (assets == liabilities + equity)

CALLED FROM:
    reports/views.py → BalanceSheetView
"""

from datetime import date
from decimal import Decimal

from chartofaccounts.models import Account, AccountClassification
from companies.models import Company

from .balance_engine import get_account_balances, get_accounts_with_transactions
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

# ── L1 classification paths from seed.py ──
L1_ASSET = '1'
L1_LIABILITY = '2'
L1_EQUITY = '3'
L1_INCOME = '4'
L1_EXPENSE = '5'
BS_L1_PATHS = {L1_ASSET, L1_LIABILITY, L1_EQUITY}


def generate_balance_sheet(company, as_of_date, filter_mode=FILTER_NON_ZERO,
                           compare_date=None):
    """
    Generate a complete Balance Sheet report.

    Args:
        company: Company instance
        as_of_date: datetime.date — the reporting date
        filter_mode: str — 'all', 'with_transactions', or 'non_zero'
        compare_date: datetime.date or None — optional comparison date

    Returns:
        dict: Complete Balance Sheet data ready for API response
    """
    has_compare = compare_date is not None

    # ── Step 1: Get raw balances from balance engine ──
    balances = get_account_balances(company, as_of_date)
    compare_balances = get_account_balances(company, compare_date) if has_compare else None

    # ── Step 2: Get accounts with transactions (for filter mode) ──
    accounts_with_txn = None
    if filter_mode == FILTER_WITH_TRANSACTIONS:
        accounts_with_txn = get_accounts_with_transactions(company, as_of_date)
        if has_compare:
            accounts_with_txn |= get_accounts_with_transactions(company, compare_date)

    # ── Step 3: Load ALL accounts (active + inactive) ──
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

    # ── Step 4: Separate accounts by L1 type ──
    # Balance Sheet only directly shows Asset, Liability, Equity.
    # Income/Expense are used to compute Net Income.
    bs_accounts = []     # Accounts that appear in the report (L1: 1,2,3)
    income_accounts = []  # For net income calculation (L1: 4)
    expense_accounts = [] # For net income calculation (L1: 5)

    for account in all_accounts:
        l1_path = account.classification.internal_path.split('.')[0]
        if l1_path in BS_L1_PATHS:
            bs_accounts.append(account)
        elif l1_path == L1_INCOME:
            income_accounts.append(account)
        elif l1_path == L1_EXPENSE:
            expense_accounts.append(account)

    # ── Step 5: Build parent-child lookups (BS accounts only) ──
    children_by_parent = {}
    root_accounts_by_l3 = {}

    for account in bs_accounts:
        if account.parent_account_id:
            children_by_parent.setdefault(account.parent_account_id, []).append(account)
        else:
            root_accounts_by_l3.setdefault(account.classification_id, []).append(account)

    # ── Step 6: Determine included accounts ──
    included_ids = _get_included_account_ids(
        bs_accounts, balances, compare_balances,
        accounts_with_txn, filter_mode, children_by_parent,
    )

    # ── Step 7: Build the three sections ──
    assets_section = _build_section(
        L1_ASSET, root_accounts_by_l3, children_by_parent,
        class_map, balances, compare_balances, included_ids,
    )

    liabilities_section = _build_section(
        L1_LIABILITY, root_accounts_by_l3, children_by_parent,
        class_map, balances, compare_balances, included_ids,
    )

    equity_section = _build_section(
        L1_EQUITY, root_accounts_by_l3, children_by_parent,
        class_map, balances, compare_balances, included_ids,
    )

    # ── Step 8: Calculate Net Income (auto-retained earnings) ──
    fiscal_year_start = _get_fiscal_year_start(company, as_of_date)

    # Current year earnings: Income - Expense from fiscal year start to as_of_date
    current_year_earnings = _calculate_net_income(
        income_accounts, expense_accounts, balances,
        company, fiscal_year_start, as_of_date,
    )

    # Prior year retained: Income - Expense before fiscal year start
    prior_retained = _calculate_prior_retained(
        income_accounts, expense_accounts,
        company, fiscal_year_start,
    )

    # Comparison period calculations
    compare_current_year_earnings = None
    compare_prior_retained = None
    if has_compare:
        compare_fy_start = _get_fiscal_year_start(company, compare_date)
        compare_current_year_earnings = _calculate_net_income(
            income_accounts, expense_accounts, compare_balances,
            company, compare_fy_start, compare_date,
        )
        compare_prior_retained = _calculate_prior_retained(
            income_accounts, expense_accounts,
            company, compare_fy_start,
        )

    # ── Step 9: Calculate section totals ──
    #
    # _sum_section_total() returns raw (debit − credit) net:
    #   Assets:      positive when debit-heavy  (normal)
    #   Liabilities: negative when credit-heavy (normal)
    #   Equity:      negative when credit-heavy (normal)
    #
    # On a Balance Sheet, all sections display as positive in their
    # normal balance direction. So we NEGATE credit-normal sections.
    #
    # Example with your data:
    #   raw asset net     = +2,252,000  →  total_assets      = +2,252,000
    #   raw liability net = −2,410,000  →  total_liabilities  = +2,410,000
    #   raw equity net    =          0  →  total_equity_accts = 0
    #   retained earnings              = −158,000 (net loss)
    #   total_equity = 0 + (−158,000)  = −158,000
    #   total_L+E = 2,410,000 + (−158,000) = 2,252,000
    #   is_balanced: 2,252,000 == 2,252,000  ✓
    #
    total_assets = _sum_section_total(assets_section)

    # Negate: credit-normal sections return negative raw net
    total_liabilities = -_sum_section_total(liabilities_section)
    total_equity_accounts = -_sum_section_total(equity_section)

    total_equity = total_equity_accounts + current_year_earnings + prior_retained
    total_liabilities_and_equity = total_liabilities + total_equity

    # Comparison totals
    compare_total_assets = None
    compare_total_liabilities_and_equity = None
    if has_compare:
        compare_total_assets = _sum_section_total(assets_section, compare=True)
        compare_total_liabilities = -_sum_section_total(liabilities_section, compare=True)
        compare_total_equity_accounts = -_sum_section_total(equity_section, compare=True)
        compare_total_equity = (
            compare_total_equity_accounts +
            compare_current_year_earnings +
            compare_prior_retained
        )
        compare_total_liabilities_and_equity = compare_total_liabilities + compare_total_equity

    # ── Step 10: Stringify all sections ──
    _stringify_section(assets_section, has_compare)
    _stringify_section(liabilities_section, has_compare)
    _stringify_section(equity_section, has_compare)

    # Count included accounts
    account_count = len([a for a in bs_accounts if a.id in included_ids])

    return {
        'report_title': 'Balance Sheet',
        'company_name': company.name,
        'base_currency': company.base_currency,
        'as_of_date': str(as_of_date),
        'compare_date': str(compare_date) if has_compare else None,
        'filter_mode': filter_mode,
        'account_count': account_count,

        # ── Three sections ──
        'assets': assets_section,
        'liabilities': liabilities_section,
        'equity': equity_section,

        # ── Auto-calculated earnings (added to equity) ──
        'retained_earnings_auto': {
            'current_year_earnings': str(current_year_earnings),
            'prior_year_retained': str(prior_retained),
            'fiscal_year_start': str(fiscal_year_start),
            'compare_current_year_earnings': str(compare_current_year_earnings) if has_compare else None,
            'compare_prior_year_retained': str(compare_prior_retained) if has_compare else None,
            'note': (
                'Auto-calculated from Income minus Expense accounts. '
                'If you have posted year-end closing journals, these '
                'values will reflect only unclosed periods.'
            ),
        },

        # ── Totals ──
        'total_assets': str(total_assets),
        'total_liabilities': str(total_liabilities),
        'total_equity_accounts': str(total_equity_accounts),
        'total_equity': str(total_equity),
        'total_liabilities_and_equity': str(total_liabilities_and_equity),

        # ── Comparison totals ──
        'compare_total_assets': str(compare_total_assets) if has_compare else None,
        'compare_total_liabilities_and_equity': str(compare_total_liabilities_and_equity) if has_compare else None,

        # ── Equation check ──
        'is_balanced': total_assets == total_liabilities_and_equity,

        # ── Change (if comparison) ──
        'change_total_assets': str(total_assets - compare_total_assets) if has_compare else None,
        'change_total_le': str(
            total_liabilities_and_equity - compare_total_liabilities_and_equity
        ) if has_compare else None,
    }


# ══════════════════════════════════════════════════
# SECTION BUILDER
# ══════════════════════════════════════════════════

def _build_section(l1_path, root_accounts_by_l3, children_by_parent,
                    class_map, balances, compare_balances, included_ids):
    """
    Build one section (Assets, Liabilities, or Equity) as a tree.

    Returns list of L2 classification nodes, each containing L3 children,
    each containing account nodes with infinite sub-nesting.
    """
    has_compare = compare_balances is not None

    # Find all L3 classifications under this L1 that have included accounts
    needed_l3_ids = set()
    for l3_id, root_accts in root_accounts_by_l3.items():
        for acct in root_accts:
            # Check if this L3's classification path starts with the right L1
            cls_path = acct.classification.internal_path
            if not cls_path.startswith(l1_path + '.'):
                continue
            if acct.id in included_ids or _has_included_descendant(
                acct.id, included_ids, children_by_parent
            ):
                needed_l3_ids.add(l3_id)
                break

    # Get L3 paths
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

        for l3_path in sorted(p for p in needed_l3_path_set if p.startswith(l2_path + '.')):
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


def _stringify_section(section, has_compare):
    """Convert all Decimal values in a section tree to strings."""
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

            _stringify_accounts(l3_node.get('accounts', []), has_compare)


def _sum_section_total(section, compare=False):
    """
    Calculate the net total for a section.

    For Assets: net positive = debit balance (normal)
    For Liabilities/Equity: net positive = credit balance (normal)

    We return the net as: total_debit - total_credit.
    The caller handles sign interpretation.
    """
    total_debit = ZERO
    total_credit = ZERO

    for l2_node in section:
        d = l2_node.get('subtotal_debit', ZERO)
        c = l2_node.get('subtotal_credit', ZERO)

        # Handle both Decimal and string (depends on when called)
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

    # Return net: positive means debit balance, negative means credit balance
    return total_debit - total_credit


# ══════════════════════════════════════════════════
# RETAINED EARNINGS AUTO-CALCULATION
# ══════════════════════════════════════════════════

def _get_fiscal_year_start(company, as_of_date):
    """
    Calculate the start date of the fiscal year that contains as_of_date.

    Example: fiscal_year_start_month=7 (July), as_of_date=2026-03-31
        → Fiscal year: 2025-07-01 to 2026-06-30
        → Returns: 2025-07-01

    Example: fiscal_year_start_month=1 (January), as_of_date=2026-03-31
        → Fiscal year: 2026-01-01 to 2026-12-31
        → Returns: 2026-01-01
    """
    fy_month = company.fiscal_year_start_month or 1
    year = as_of_date.year

    # If the fiscal year start month is after the current month,
    # the fiscal year started in the previous calendar year.
    if fy_month > as_of_date.month:
        year -= 1
    elif fy_month == as_of_date.month and as_of_date.day < 1:
        year -= 1

    return date(year, fy_month, 1)


def _calculate_net_income(income_accounts, expense_accounts, balances,
                           company, from_date, to_date):
    """
    Calculate Net Income = Total Income − Total Expense
    for transactions between from_date and to_date.

    Since balances from balance_engine are cumulative (from the
    beginning of time to as_of_date), we need to subtract the
    balances as of (from_date - 1) to get just the period.

    For Income accounts: net credit balance = revenue earned
    For Expense accounts: net debit balance = expenses incurred
    Net Income = revenue - expenses
    """
    from datetime import timedelta

    # Balances already calculated for to_date (passed in as `balances`)
    # We need balances as of (from_date - 1) to subtract
    before_date = from_date - timedelta(days=1)
    before_balances = get_account_balances(company, before_date)

    total_income = ZERO
    total_expense = ZERO

    # Income: credit-normal accounts. Net credit = positive income.
    for acct in income_accounts:
        bal_to = balances.get(acct.id)
        bal_before = before_balances.get(acct.id)
        net_to = bal_to['net'] if bal_to else ZERO
        net_before = bal_before['net'] if bal_before else ZERO
        # Period net = cumulative at end - cumulative at start
        period_net = net_to - net_before
        # Income accounts have credit-normal: negative net = income earned
        total_income += abs(period_net) if period_net < 0 else -period_net

    # Expense: debit-normal accounts. Net debit = positive expense.
    for acct in expense_accounts:
        bal_to = balances.get(acct.id)
        bal_before = before_balances.get(acct.id)
        net_to = bal_to['net'] if bal_to else ZERO
        net_before = bal_before['net'] if bal_before else ZERO
        period_net = net_to - net_before
        # Expense accounts have debit-normal: positive net = expense incurred
        total_expense += period_net if period_net > 0 else -abs(period_net)

    return total_income - total_expense


def _calculate_prior_retained(income_accounts, expense_accounts,
                               company, fiscal_year_start):
    """
    Calculate cumulative Net Income from the beginning of time
    up to (but not including) the fiscal year start.

    This represents prior years' undistributed profits.
    If the user has done manual closing journals, Income/Expense
    accounts for those years will be zero, so this returns zero
    for the closed periods — avoiding double-counting.
    """
    from datetime import timedelta

    if fiscal_year_start <= date(2000, 1, 1):
        # Edge case: fiscal year start is effectively "the beginning"
        return ZERO

    before_fy = fiscal_year_start - timedelta(days=1)
    before_balances = get_account_balances(company, before_fy)

    total_income = ZERO
    total_expense = ZERO

    for acct in income_accounts:
        bal = before_balances.get(acct.id)
        if bal:
            # Income: credit-normal → negative net = income earned
            if bal['net'] < 0:
                total_income += abs(bal['net'])
            else:
                total_income -= bal['net']

    for acct in expense_accounts:
        bal = before_balances.get(acct.id)
        if bal:
            # Expense: debit-normal → positive net = expense incurred
            if bal['net'] > 0:
                total_expense += bal['net']
            else:
                total_expense -= abs(bal['net'])

    return total_income - total_expense