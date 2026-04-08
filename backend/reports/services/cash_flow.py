# backend/reports/services/cash_flow.py

"""
Cash Flow Statement (Indirect Method) report generation.

THE INDIRECT METHOD:
    Starts from Net Income, then works backward to figure out how much
    ACTUAL CASH moved during the period. The three sections are:

    1. OPERATING ACTIVITIES:
       Net Income (from P&L)
       + Non-cash adjustments (Depreciation — reduced net income but
         didn't actually use cash)
       + Working capital changes (increases/decreases in AR, AP, Inventory,
         etc. that affect cash differently than P&L recognition)
       = Net Cash from Operating Activities

    2. INVESTING ACTIVITIES:
       Changes in long-term asset accounts (PPE, Investments, Intangibles).
       Asset purchase = cash outflow. Asset sale = cash inflow.
       = Net Cash from Investing Activities

    3. FINANCING ACTIVITIES:
       Changes in debt and equity accounts (Loans, Owner Capital, Drawings).
       Loan taken = cash inflow. Loan repaid = cash outflow.
       = Net Cash from Financing Activities

    CASH RECONCILIATION:
       Opening Cash Balance (CASH-category accounts at period start)
       + Net Change in Cash (Operating + Investing + Financing)
       = Closing Cash Balance
       Verification: Closing should match actual cash account balances

WHY CASH IS A SEPARATE CATEGORY:
    Cash and Bank accounts are the SUBJECT of the Cash Flow Statement,
    not an activity. OPERATING/INVESTING/FINANCING explain WHERE cash
    came from and went. The CASH category identifies WHICH accounts
    hold the actual cash — needed for opening/closing balance lines.

THE UNIVERSAL FORMULA:
    For any non-cash BS account, its cash flow effect is:
        cash_effect = -(closing_net - opening_net)

    This works universally because:
      - Asset increases (positive raw change) → cash was USED → negative
      - Asset decreases (negative raw change) → cash was FREED → positive
      - Liability increases (more negative raw) → cash was GAINED → positive
      - Liability decreases (less negative raw) → cash was USED → negative

    The formula naturally handles both debit-normal and credit-normal accounts.

SPECIAL HANDLING:
    1. NON-CASH ADD-BACK: Calculated from the balance CHANGES of
       contra-asset accounts (Accumulated Depreciation L3 1.11.1120 and
       Accumulated Amortisation L3 1.11.1125). These charges reduced
       Net Income but didn't use cash. By using the contra-asset changes
       instead of the expense accounts, we guarantee the add-back exactly
       equals what we exclude from Investing — no double-counting possible.

    2. CONTRA-ASSET EXCLUSION: Both Accumulated Depreciation and Accumulated
       Amortisation are excluded from the Investing section. Their cash
       effect is already captured by the non-cash add-back in Operating.

    3. RETAINED EARNINGS EXCLUSION: Changes to the Retained Earnings account
       (system_code RETAINED_EARNINGS) are excluded from Financing because
       Net Income already captures the economic effect. Manual closing journals
       would otherwise double-count income as a financing activity.

QUERY COUNT: 4 SQL queries total (+ 2 more per comparison period)
    1. get_account_balances(company, from_date - 1)    → opening balances
    2. get_account_balances(company, to_date)           → closing balances
    3. get_period_balances(company, from_date, to_date) → period P&L activity
    4. Account + Classification query with select_related

CALLED FROM:
    reports/views.py → CashFlowView
"""

from datetime import timedelta
from decimal import Decimal

from chartofaccounts.models import Account, AccountClassification, SystemAccountMapping

from .balance_engine import get_account_balances, get_period_balances


ZERO = Decimal('0.00')

# ── L1 classification paths (from seed.py) ──
L1_INCOME = '4'
L1_EXPENSE = '5'
PL_L1_PATHS = {L1_INCOME, L1_EXPENSE}
BS_L1_PATHS = {'1', '2', '3'}

# ── Special L3 paths for non-cash adjustments ──
# Both are contra-asset accounts excluded from Investing.
# Their balance changes are used as the non-cash add-back in Operating.
ACCUM_DEP_L3_PATH = '1.11.1120'    # Accumulated Depreciation
ACCUM_AMORT_L3_PATH = '1.11.1125'  # Accumulated Amortisation
# Set of both paths for easy lookup
CONTRA_ASSET_L3_PATHS = {ACCUM_DEP_L3_PATH, ACCUM_AMORT_L3_PATH}


def generate_cash_flow(company, from_date, to_date,
                        compare_from_date=None, compare_to_date=None):
    """
    Generate a complete Cash Flow Statement (Indirect Method).

    Args:
        company: Company instance
        from_date: datetime.date — start of reporting period (inclusive)
        to_date: datetime.date — end of reporting period (inclusive)
        compare_from_date: datetime.date or None — comparison period start
        compare_to_date: datetime.date or None — comparison period end

    Returns:
        dict: Complete Cash Flow Statement data ready for API response
    """
    has_compare = compare_from_date is not None and compare_to_date is not None

    # ── Step 1: Fetch all balances ──
    # Opening = cumulative balances up to (from_date - 1)
    # Closing = cumulative balances up to to_date
    # Period = activity within [from_date, to_date] for P&L
    opening_date = from_date - timedelta(days=1)
    opening_balances = get_account_balances(company, opening_date)
    closing_balances = get_account_balances(company, to_date)
    period_balances = get_period_balances(company, from_date, to_date)

    # Comparison period balances
    compare_opening_balances = None
    compare_closing_balances = None
    compare_period_balances = None
    if has_compare:
        compare_opening_date = compare_from_date - timedelta(days=1)
        compare_opening_balances = get_account_balances(company, compare_opening_date)
        compare_closing_balances = get_account_balances(company, compare_to_date)
        compare_period_balances = get_period_balances(
            company, compare_from_date, compare_to_date,
        )

    # ── Step 2: Load all accounts with classification info ──
    all_accounts = list(
        Account.objects
        .filter(company=company)
        .select_related('classification', 'parent_account')
        .order_by('internal_path')
    )

    # ── Step 3: Find Retained Earnings account (to exclude from Financing) ──
    retained_earnings_id = None
    try:
        re_mapping = SystemAccountMapping.objects.get(
            company=company, system_code='RETAINED_EARNINGS',
        )
        retained_earnings_id = re_mapping.account_id
    except SystemAccountMapping.DoesNotExist:
        pass  # No retained earnings mapped — skip exclusion

    # ── Step 4: Categorise accounts ──
    pl_accounts = []        # L1=4,5 → used for Net Income
    operating_bs = []       # BS accounts with cash_flow_category=OPERATING
    investing_accounts = [] # cash_flow_category=INVESTING
    financing_accounts = [] # cash_flow_category=FINANCING
    cash_accounts = []      # cash_flow_category=CASH
    # Contra-asset accounts (Accum Dep + Accum Amort) — excluded from
    # Investing and used to calculate the non-cash add-back in Operating
    contra_asset_account_ids = set()

    for account in all_accounts:
        l1_path = account.classification.internal_path.split('.')[0]
        l3_path = account.classification.internal_path
        cf_category = account.classification.cash_flow_category

        # P&L accounts → Net Income calculation
        if l1_path in PL_L1_PATHS:
            pl_accounts.append(account)
            continue

        # BS accounts → grouped by cash_flow_category
        if l1_path in BS_L1_PATHS:
            # Track contra-asset accounts for exclusion + add-back
            if l3_path in CONTRA_ASSET_L3_PATHS:
                contra_asset_account_ids.add(account.id)

            if cf_category == 'CASH':
                cash_accounts.append(account)
            elif cf_category == 'INVESTING':
                investing_accounts.append(account)
            elif cf_category == 'FINANCING':
                financing_accounts.append(account)
            else:
                # OPERATING or NULL — default to operating
                operating_bs.append(account)

    # ── Step 5: Calculate Net Income ──
    net_income = _calc_net_income(pl_accounts, period_balances)
    compare_net_income = (
        _calc_net_income(pl_accounts, compare_period_balances)
        if has_compare else None
    )

    # ── Step 6: Calculate Non-Cash Add-Back ──
    # Instead of summing expense accounts (which caused double-counting
    # with amortisation), we calculate the add-back from the CONTRA-ASSET
    # balance changes (Accumulated Depreciation + Accumulated Amortisation).
    #
    # This guarantees: add-back amount == what we exclude from Investing.
    # No double-counting is possible.
    #
    # Contra-asset accounts are credit-normal. When depreciation/amortisation
    # is posted (DR Expense / CR Accumulated), the contra-asset's raw net
    # becomes more negative. The change (closing - opening) is negative.
    # We take the absolute value to get the positive add-back amount.
    noncash_addback = ZERO
    for acct_id in contra_asset_account_ids:
        opening_net = opening_balances.get(acct_id, {}).get('net', ZERO)
        closing_net = closing_balances.get(acct_id, {}).get('net', ZERO)
        change = closing_net - opening_net  # Negative for normal dep/amort
        noncash_addback += abs(change)

    compare_noncash_addback = None
    if has_compare:
        compare_noncash_addback = ZERO
        for acct_id in contra_asset_account_ids:
            c_opening = compare_opening_balances.get(acct_id, {}).get('net', ZERO)
            c_closing = compare_closing_balances.get(acct_id, {}).get('net', ZERO)
            compare_noncash_addback += abs(c_closing - c_opening)

    # ── Step 7: Calculate Working Capital Changes (OPERATING BS accounts) ──
    operating_items, operating_total = _calc_balance_changes(
        operating_bs, opening_balances, closing_balances,
        exclude_ids={retained_earnings_id} if retained_earnings_id else set(),
    )

    compare_operating_items = None
    compare_operating_total = None
    if has_compare:
        compare_operating_items, compare_operating_total = _calc_balance_changes(
            operating_bs, compare_opening_balances, compare_closing_balances,
            exclude_ids={retained_earnings_id} if retained_earnings_id else set(),
        )

    # ── Step 8: Net Cash from Operating Activities ──
    net_operating = net_income + noncash_addback + operating_total
    compare_net_operating = (
        compare_net_income + compare_noncash_addback + compare_operating_total
        if has_compare else None
    )

    # ── Step 9: Calculate Investing Activities ──
    # Exclude both Accumulated Depreciation AND Accumulated Amortisation
    # (their changes are already captured by the non-cash add-back in Operating)
    investing_items, investing_total = _calc_balance_changes(
        investing_accounts, opening_balances, closing_balances,
        exclude_ids=contra_asset_account_ids,
    )

    compare_investing_items = None
    compare_investing_total = None
    if has_compare:
        compare_investing_items, compare_investing_total = _calc_balance_changes(
            investing_accounts, compare_opening_balances, compare_closing_balances,
            exclude_ids=contra_asset_account_ids,
        )

    # ── Step 10: Calculate Financing Activities ──
    # Exclude Retained Earnings (already captured in Net Income)
    financing_items, financing_total = _calc_balance_changes(
        financing_accounts, opening_balances, closing_balances,
        exclude_ids={retained_earnings_id} if retained_earnings_id else set(),
    )

    compare_financing_items = None
    compare_financing_total = None
    if has_compare:
        compare_financing_items, compare_financing_total = _calc_balance_changes(
            financing_accounts, compare_opening_balances, compare_closing_balances,
            exclude_ids={retained_earnings_id} if retained_earnings_id else set(),
        )

    # ── Step 11: Cash Reconciliation ──
    net_change = net_operating + investing_total + financing_total

    opening_cash = _calc_cash_balance(cash_accounts, opening_balances)
    closing_cash = opening_cash + net_change
    actual_closing_cash = _calc_cash_balance(cash_accounts, closing_balances)
    is_balanced = closing_cash == actual_closing_cash

    # Comparison reconciliation
    compare_net_change = None
    compare_opening_cash = None
    compare_closing_cash = None
    if has_compare:
        compare_net_change = (
            compare_net_operating + compare_investing_total + compare_financing_total
        )
        compare_opening_cash = _calc_cash_balance(
            cash_accounts, compare_opening_balances,
        )
        compare_closing_cash = compare_opening_cash + compare_net_change

    # ── Step 12: Build response ──
    result = {
        'report_title': 'Cash Flow Statement',
        'method': 'INDIRECT',
        'company_name': company.name,
        'base_currency': company.base_currency,
        'from_date': str(from_date),
        'to_date': str(to_date),
        'compare_from_date': str(compare_from_date) if has_compare else None,
        'compare_to_date': str(compare_to_date) if has_compare else None,

        # ── Operating Activities ──
        'operating_activities': {
            'net_income': str(net_income),
            'adjustments': {
                'depreciation_and_amortization': str(noncash_addback),
                'note': (
                    'Non-cash charges added back. Calculated from changes in '
                    'Accumulated Depreciation and Accumulated Amortisation '
                    'contra-asset accounts. These charges reduced Net Income '
                    'but did not use actual cash.'
                ),
            },
            'working_capital_changes': _stringify_items(operating_items),
            'working_capital_total': str(operating_total),
            'net_cash_from_operating': str(net_operating),
        },

        # ── Investing Activities ──
        'investing_activities': {
            'items': _stringify_items(investing_items),
            'net_cash_from_investing': str(investing_total),
        },

        # ── Financing Activities ──
        'financing_activities': {
            'items': _stringify_items(financing_items),
            'net_cash_from_financing': str(financing_total),
        },

        # ── Cash Reconciliation ──
        'cash_reconciliation': {
            'opening_cash_balance': str(opening_cash),
            'net_change_in_cash': str(net_change),
            'closing_cash_balance': str(closing_cash),
            'actual_closing_cash': str(actual_closing_cash),
            'is_balanced': is_balanced,
        },

        # ── Summary ──
        'summary': {
            'net_cash_from_operating': str(net_operating),
            'net_cash_from_investing': str(investing_total),
            'net_cash_from_financing': str(financing_total),
            'net_change_in_cash': str(net_change),
        },
    }

    # ── Add comparison data if applicable ──
    if has_compare:
        result['compare_operating_activities'] = {
            'net_income': str(compare_net_income),
            'depreciation_and_amortization': str(compare_noncash_addback),
            'working_capital_changes': _stringify_items(compare_operating_items),
            'working_capital_total': str(compare_operating_total),
            'net_cash_from_operating': str(compare_net_operating),
        }
        result['compare_investing_activities'] = {
            'items': _stringify_items(compare_investing_items),
            'net_cash_from_investing': str(compare_investing_total),
        }
        result['compare_financing_activities'] = {
            'items': _stringify_items(compare_financing_items),
            'net_cash_from_financing': str(compare_financing_total),
        }
        result['compare_cash_reconciliation'] = {
            'opening_cash_balance': str(compare_opening_cash),
            'net_change_in_cash': str(compare_net_change),
            'closing_cash_balance': str(compare_closing_cash),
        }
        result['compare_summary'] = {
            'net_cash_from_operating': str(compare_net_operating),
            'net_cash_from_investing': str(compare_investing_total),
            'net_cash_from_financing': str(compare_financing_total),
            'net_change_in_cash': str(compare_net_change),
        }
        # Change amounts
        result['changes'] = {
            'operating': str(net_operating - compare_net_operating),
            'investing': str(investing_total - compare_investing_total),
            'financing': str(financing_total - compare_financing_total),
            'net_change': str(net_change - compare_net_change),
        }

    return result


# ══════════════════════════════════════════════════
# NET INCOME CALCULATION
# ══════════════════════════════════════════════════

def _calc_net_income(pl_accounts, period_balances):
    """
    Calculate Net Income from P&L accounts' period activity.

    Income accounts (L1=4) are credit-normal → negative raw net = revenue
    Expense accounts (L1=5) are debit-normal → positive raw net = expense

    Net Income = Total Revenue − Total Expenses
               = (-sum of income nets) − (sum of expense nets)
               = -(sum of all P&L raw nets)

    This works because:
        Revenue net: -500,000 (credit balance)
        Expense net: +350,000 (debit balance)
        Sum = -150,000
        Net Income = -(-150,000) = 150,000 (profit)
    """
    total_pl_net = ZERO
    for acct in pl_accounts:
        bal = period_balances.get(acct.id)
        if bal:
            total_pl_net += bal['net']

    # Negate: positive raw sum = net loss, negative raw sum = net profit
    return -total_pl_net


# ══════════════════════════════════════════════════
# BALANCE CHANGE CALCULATOR
# ══════════════════════════════════════════════════

def _calc_balance_changes(accounts, opening_balances, closing_balances,
                           exclude_ids=None):
    """
    Calculate the cash flow effect of balance changes for a group of accounts.

    The universal formula: cash_effect = -(closing_net - opening_net)

    This works for ALL account types:
        Asset increase → cash was used → negative cash effect
        Asset decrease → cash was freed → positive cash effect
        Liability increase → cash was gained → positive cash effect
        Liability decrease → cash was used → negative cash effect

    Returns:
        (items_list, total_cash_effect)

        items_list: [{
            'account_id', 'code', 'name', 'classification_name',
            'normal_balance',
            'opening_balance', 'closing_balance', 'change', 'cash_effect',
        }]

        Only includes accounts with non-zero changes.
    """
    exclude_ids = exclude_ids or set()
    items = []
    total = ZERO

    for acct in accounts:
        if acct.id in exclude_ids:
            continue

        opening_net = ZERO
        ob = opening_balances.get(acct.id)
        if ob:
            opening_net = ob['net']

        closing_net = ZERO
        cb = closing_balances.get(acct.id)
        if cb:
            closing_net = cb['net']

        change = closing_net - opening_net
        if change == ZERO:
            continue  # No change → no cash effect

        # Cash effect: negate the raw change
        # Asset went up → cash went down (and vice versa for liabilities)
        cash_effect = -change

        items.append({
            'account_id': str(acct.id),
            'code': acct.code,
            'name': acct.name,
            'classification_name': acct.classification.name,
            'normal_balance': acct.normal_balance,
            'opening_balance': opening_net,    # Decimal (stringified later)
            'closing_balance': closing_net,
            'change': change,
            'cash_effect': cash_effect,
        })

        total += cash_effect

    # Sort by absolute cash effect descending (most impactful first)
    items.sort(key=lambda x: abs(x['cash_effect']), reverse=True)

    return items, total


# ══════════════════════════════════════════════════
# CASH BALANCE CALCULATOR
# ══════════════════════════════════════════════════

def _calc_cash_balance(cash_accounts, balances):
    """
    Calculate the total balance of all CASH-category accounts.

    Cash accounts are debit-normal (Assets). A positive raw net
    means the company has cash. We sum the raw nets directly.
    """
    total = ZERO
    for acct in cash_accounts:
        bal = balances.get(acct.id)
        if bal:
            total += bal['net']
    return total


# ══════════════════════════════════════════════════
# STRINGIFY HELPER
# ══════════════════════════════════════════════════

def _stringify_items(items):
    """Convert all Decimal values in items list to strings."""
    if items is None:
        return None
    result = []
    for item in items:
        result.append({
            'account_id': item['account_id'],
            'code': item['code'],
            'name': item['name'],
            'classification_name': item['classification_name'],
            'normal_balance': item['normal_balance'],
            'opening_balance': str(item['opening_balance']),
            'closing_balance': str(item['closing_balance']),
            'change': str(item['change']),
            'cash_effect': str(item['cash_effect']),
        })
    return result