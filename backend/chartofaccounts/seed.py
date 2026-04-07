# backend/chartofaccounts/seed.py

"""
Seed data for the Chart of Accounts.

This file is the SINGLE SOURCE OF TRUTH for the default CoA structure.
Every other file (template, validator, services) imports from here.

STRUCTURE:
    CLASSIFICATIONS — Defines Layers 1, 2, and 3 (the tree skeleton)
    DEFAULT_ACCOUNTS — Defines Layer 4 accounts (the ledger-level leaves)

CLASSIFICATION TUPLE FORMAT:
    (internal_path, name, cash_flow_category)

    cash_flow_category is only set for Layer 3 classifications.
    Layer 1 and Layer 2 get None.

    Values: 'OPERATING', 'INVESTING', 'FINANCING', 'CASH', or None

CASH FLOW CATEGORY MAPPING RATIONALE:
    CASH:       Cash and Bank accounts — these are the RESULT of the
                Cash Flow Statement, not an activity. Their opening/closing
                balances form the verification line.
    OPERATING:  Working capital items (AR, AP, Inventory, Prepaid, Accrued)
                and all P&L classifications (Revenue, Expenses). In the
                indirect method, all P&L flows through Net Income, and
                working capital changes are adjustments.
    INVESTING:  Long-term asset purchases/sales (PPE, Investments,
                Intangibles) and their contra accounts.
    FINANCING:  Debt and equity transactions (Loans, Owner Capital,
                Dividends, Drawings).
"""


# ──────────────────────────────────────────────
# LAYER 1, 2, AND 3 CLASSIFICATIONS
# ──────────────────────────────────────────────
# Format: (internal_path, name, cash_flow_category)
# cash_flow_category: None for L1/L2, set for L3

CLASSIFICATIONS = [

    # ── ASSET ──
    ('1',           'Asset',                            None),
    ('1.10',        'Current Asset',                    None),
    ('1.10.1010',   'Cash',                             'CASH'),
    ('1.10.1020',   'Bank',                             'CASH'),
    ('1.10.1030',   'Inventory',                        'OPERATING'),
    ('1.10.1040',   'Tax Receivables',                  'OPERATING'),
    ('1.10.1050',   'Advances & Prepayments',           'OPERATING'),
    ('1.10.1060',   'Receivables',                      'OPERATING'),
    ('1.10.1070',   'Other Current Asset',              'OPERATING'),
    ('1.11',        'Non-Current Asset',                None),
    ('1.11.1110',   'Property Plant & Equipment',       'INVESTING'),
    ('1.11.1120',   'Accumulated Depreciation',         'INVESTING'),
    ('1.11.1130',   'Intangible Assets',                'INVESTING'),
    ('1.11.1140',   'Investments',                      'INVESTING'),
    ('1.11.1150',   'Other Non-Current Assets',         'INVESTING'),

    # ── LIABILITY ──
    ('2',           'Liability',                        None),
    ('2.20',        'Short-Term Liabilities',           None),
    ('2.20.2010',   'Accounts Payables',                'OPERATING'),
    ('2.20.2020',   'Accrued Expense',                  'OPERATING'),
    ('2.20.2030',   'Withholding Tax & VAT',            'OPERATING'),
    ('2.20.2040',   'Short-Term Loans',                 'FINANCING'),
    ('2.20.2050',   'Unearned Revenue',                 'OPERATING'),
    ('2.20.2060',   'Suspense & Clearing',              'OPERATING'),
    ('2.20.2070',   'Other Current Liabilities',        'OPERATING'),
    ('2.20.2080',   'Provisions',                       'OPERATING'),
    ('2.21',        'Long-Term Liabilities',            None),
    ('2.21.2110',   'Long-Term Loans',                  'FINANCING'),
    ('2.21.2120',   'Other Long-Term Liabilities',      'FINANCING'),

    # ── EQUITY ──
    ('3',           'Equity',                           None),
    ('3.30',        "Owner's Equity & Reserves",        None),
    ('3.30.3010',   "Owner's Equity",                   'FINANCING'),

    # ── INCOME ──
    ('4',           'Income',                           None),
    ('4.40',        'Operating Income',                 None),
    ('4.40.4010',   'Revenue',                          'OPERATING'),
    ('4.41',        'Non-Operating Income',             None),
    ('4.41.4110',   'Interest & Investment Income',     'OPERATING'),
    ('4.41.4120',   'Rent Income',                      'OPERATING'),
    ('4.41.4130',   'Other Income',                     'OPERATING'),

    # ── EXPENSE ──
    ('5',           'Expense',                          None),
    ('5.50',        'Cost of Sales',                    None),
    ('5.50.5010',   'Cost of Goods Sold/Services',      'OPERATING'),
    ('5.51',        'Operating Expense',                None),
    ('5.51.5110',   'Payroll & Employee Costs',         'OPERATING'),
    ('5.51.5120',   'Premises & Utilities',             'OPERATING'),
    ('5.51.5130',   'Administrative & General',         'OPERATING'),
    ('5.51.5140',   'Depreciation & Amortisation',      'OPERATING'),
    ('5.51.5150',   'Sales & Marketing Expense',        'OPERATING'),
    ('5.51.5160',   'Other Operating Expense',          'OPERATING'),
    ('5.51.5170',   'Research & Development Expense',   'OPERATING'),
    ('5.52',        'Non-Operating Expense',            None),
    ('5.52.5210',   'Financial Expense',                'OPERATING'),
    ('5.52.5220',   'Tax Expense',                      'OPERATING'),
    ('5.52.5230',   'Other Non-Operating Expense',      'OPERATING'),
]


# ──────────────────────────────────────────────
# LAYER 4 DEFAULT ACCOUNTS
# ──────────────────────────────────────────────
# Format:
#   (classification_path, account_code, name, normal_balance, is_system, is_deletable, system_code)

# STATISTICS:
#   Total accounts:  104
#   System accounts:  43  (is_system=True, used by ERP modules)
#   Non-deletable:    45  (43 system + 2 paired accounts)
#   Deletable:        59  (user can remove these)
# ──────────────────────────────────────────────

DEFAULT_ACCOUNTS = [

    # ════════════════════════════════════
    # ASSET ACCOUNTS
    # ════════════════════════════════════

    # ── Cash ──
    ('1.10.1010', '10101', 'Petty Cash',                  'DEBIT', True,  False, 'PETTY_CASH'),
    ('1.10.1010', '10102', 'Sales Cash',                  'DEBIT', True,  False, 'SALES_CASH'),
    ('1.10.1010', '10103', 'Undeposited Fund/Cheque',     'DEBIT', True,  False, 'UNDEPOSITED_FUNDS'),

    # ── Bank ──
    ('1.10.1020', '10201', 'Bank',                        'DEBIT', True,  False, 'BANK'),
    ('1.10.1020', '10202', 'Mobile Banking',              'DEBIT', False, True,  None),

    # ── Inventory ──
    ('1.10.1030', '10301', 'Inventory',                   'DEBIT', True,  False, 'INVENTORY'),
    ('1.10.1030', '10302', 'Inventory of Finished Goods', 'DEBIT', True,  False, 'FINISHED_GOODS'),
    ('1.10.1030', '10303', 'Inventory of Raw Materials',  'DEBIT', True,  False, 'RAW_MATERIALS'),
    ('1.10.1030', '10304', 'Working Process Inventory',   'DEBIT', False, True,  None),

    # ── Tax Receivables ──
    ('1.10.1040', '10401', 'Advance Income Tax',             'DEBIT', True,  False, 'ADVANCE_INCOME_TAX'),
    ('1.10.1040', '10402', 'Input VAT Receivables',          'DEBIT', True,  False, 'INPUT_VAT'),
    ('1.10.1040', '10403', 'Withholding Tax Receivables',    'DEBIT', True,  False, 'WHT_RECEIVABLE'),
    ('1.10.1040', '10404', 'Supplementary Duty Receivable',  'DEBIT', False, True,  None),

    # ── Advances & Prepayments ──
    ('1.10.1050', '10501', 'Security Deposits',       'DEBIT', False, True, None),
    ('1.10.1050', '10502', 'Employee Advance',        'DEBIT', False, True, None),
    ('1.10.1050', '10503', 'Prepaid Rent',            'DEBIT', False, True, None),
    ('1.10.1050', '10504', 'Prepaid Insurance',       'DEBIT', False, True, None),
    ('1.10.1050', '10505', 'Other Advance Payments',  'DEBIT', False, True, None),

    # ── Receivables ──
    ('1.10.1060', '10601', 'Accounts Receivable',             'DEBIT',  True,  False, 'ACCOUNTS_RECEIVABLE'),
    ('1.10.1060', '10602', 'Notes Receivable',                'DEBIT',  False, True,  None),
    ('1.10.1060', '10603', 'Allowance for Doubtful Accounts', 'CREDIT', False, False, None),
    ('1.10.1060', '10604', 'Loan to Others',                  'DEBIT',  False, True,  None),
    ('1.10.1060', '10605', 'Other Receivables',               'DEBIT',  False, True,  None),

    # ── Other Current Asset ──
    ('1.10.1070', '10701', 'Other Current Asset', 'DEBIT', False, True, None),

    # ── Property Plant & Equipment ──
    ('1.11.1110', '11101', 'Furnitures & Fixtures',     'DEBIT', False, True, None),
    ('1.11.1110', '11102', 'Computers & IT Equipment',  'DEBIT', False, True, None),
    ('1.11.1110', '11103', 'Machinery & Equipment',     'DEBIT', False, True, None),
    ('1.11.1110', '11104', 'Vehicles',                  'DEBIT', False, True, None),
    ('1.11.1110', '11105', 'Land & Buildings',          'DEBIT', False, True, None),

    # ── Accumulated Depreciation ──
    ('1.11.1120', '11201', 'Accumulated Depreciation', 'CREDIT', True, False, 'ACCUMULATED_DEPRECIATION'),

    # ── Intangible Assets ──
    ('1.11.1130', '11301', 'Patents & Trademarks', 'DEBIT', False, True, None),
    ('1.11.1130', '11302', 'Software & License',   'DEBIT', False, True, None),
    ('1.11.1130', '11303', 'Goodwill',             'DEBIT', False, True, None),

    # ── Investments ──
    ('1.11.1140', '11401', 'Investments', 'DEBIT', False, True, None),

    # ── Other Non-Current Assets ──
    ('1.11.1150', '11501', 'Other Non-Current Assets', 'DEBIT', False, True, None),

    # ════════════════════════════════════
    # LIABILITY ACCOUNTS
    # ════════════════════════════════════

    # ── Accounts Payables ──
    ('2.20.2010', '20101', 'Accounts Payable', 'CREDIT', True, False, 'ACCOUNTS_PAYABLE'),

    # ── Accrued Expense ──
    ('2.20.2020', '20201', 'Accrued Expense',             'CREDIT', True,  False, 'ACCRUED_EXPENSE'),
    ('2.20.2020', '20202', 'Accrued Salaries & Wages',    'CREDIT', False, True,  None),
    ('2.20.2020', '20203', 'Provident Fund Payable',      'CREDIT', False, True,  None),
    ('2.20.2020', '20204', 'Gratuity Payable',            'CREDIT', False, True,  None),

    # ── Withholding Tax & VAT ──
    ('2.20.2030', '20301', 'Withholding Tax Payable',      'CREDIT', True,  False, 'WHT_PAYABLE'),
    ('2.20.2030', '20302', 'Output VAT Payable',           'CREDIT', True,  False, 'OUTPUT_VAT'),
    ('2.20.2030', '20303', 'Income Tax Payable',           'CREDIT', True,  False, 'INCOME_TAX_PAYABLE'),
    ('2.20.2030', '20304', 'Supplementary Duty Payable',   'CREDIT', False, True,  None),
    ('2.20.2030', '20305', 'Other Tax & Duties Payable',   'CREDIT', False, True,  None),

    # ── Short-Term Loans ──
    ('2.20.2040', '20401', 'Short-Term Bank Loan',  'CREDIT', False, True, None),
    ('2.20.2040', '20402', 'Bank Overdraft',         'CREDIT', False, True, None),
    ('2.20.2040', '20403', 'Credit Card Payable',    'CREDIT', False, True, None),

    # ── Unearned Revenue ──
    ('2.20.2050', '20501', 'Unearned Revenue',                    'CREDIT', True, False, 'UNEARNED_REVENUE'),
    ('2.20.2050', '20502', 'Customer Deposits/Advances Received', 'CREDIT', True, False, 'CUSTOMER_DEPOSITS'),

    # ── Suspense & Clearing ──
    ('2.20.2060', '20601', 'Suspense Account',  'CREDIT', True, False, 'SUSPENSE'),
    ('2.20.2060', '20602', 'Clearing Account',  'CREDIT', True, False, 'CLEARING'),

    # ── Other Current Liabilities ──
    ('2.20.2070', '20701', 'Opening Balance Offset',    'CREDIT', True,  False, 'OPENING_BALANCE_OFFSET'),
    ('2.20.2070', '20702', 'Other Current Liabilities', 'CREDIT', False, True,  None),

    # ── Provisions (IAS 37) ──
    ('2.20.2080', '20801', 'General Provisions', 'CREDIT', False, True, None),

    # ── Long-Term Loans ──
    ('2.21.2110', '21101', 'Long-Term Loans', 'CREDIT', False, True, None),

    # ── Other Long-Term Liabilities ──
    ('2.21.2120', '21201', 'Other Long-Term Liabilities', 'CREDIT', False, True, None),

    # ════════════════════════════════════
    # EQUITY ACCOUNTS
    # ════════════════════════════════════

    # ── Owner's Equity ──
    ('3.30.3010', '30101', 'Owner Capital',      'CREDIT', True, False, 'OWNER_CAPITAL'),
    ('3.30.3010', '30102', 'Retained Earnings',  'CREDIT', True, False, 'RETAINED_EARNINGS'),
    ('3.30.3010', '30103', 'Drawing',            'DEBIT',  True, False, 'DRAWING'),
    ('3.30.3010', '30104', 'Dividends',          'DEBIT',  False, True, None),

    # ════════════════════════════════════
    # INCOME ACCOUNTS
    # ════════════════════════════════════

    # ── Revenue ──
    ('4.40.4010', '40101', 'Sales',                       'CREDIT', True,  False, 'SALES'),
    ('4.40.4010', '40102', 'Shipping Charge',             'CREDIT', False, True,  None),
    ('4.40.4010', '40103', 'Adjustment & Other Charges',  'CREDIT', False, True,  None),
    ('4.40.4010', '40104', 'Sales Discount',              'DEBIT',  True,  False, 'SALES_DISCOUNT'),
    ('4.40.4010', '40105', 'Sales Returns & Allowances',  'DEBIT',  True,  False, 'SALES_RETURNS'),
    ('4.40.4010', '40106', 'Service Revenue',             'CREDIT', True,  False, 'SERVICE_REVENUE'),

    # ── Interest & Investment Income ──
    ('4.41.4110', '41101', 'Interest Income',  'CREDIT', False, True, None),
    ('4.41.4110', '41102', 'Dividend Income',  'CREDIT', False, True, None),

    # ── Rent Income ──
    ('4.41.4120', '41201', 'Rent Income', 'CREDIT', False, True, None),

    # ── Other Income ──
    ('4.41.4130', '41301', 'Commission Income',      'CREDIT', False, True,  None),
    ('4.41.4130', '41302', 'Gain on Asset Disposal',  'CREDIT', True,  False, 'GAIN_ON_DISPOSAL'),
    ('4.41.4130', '41303', 'FX Gain (Realized)',      'CREDIT', True,  False, 'FX_GAIN'),
    ('4.41.4130', '41304', 'Other Income',            'CREDIT', False, True,  None),

    # ════════════════════════════════════
    # EXPENSE ACCOUNTS
    # ════════════════════════════════════

    # ── Cost of Sales ──
    ('5.50.5010', '50101', 'Cost of Goods Sold',  'DEBIT',  True,  False, 'COGS'),
    ('5.50.5010', '50102', 'Cost of Services',    'DEBIT',  True,  False, 'COST_OF_SERVICES'),
    ('5.50.5010', '50103', 'Purchase Discount',              'CREDIT', True,  False, 'PURCHASE_DISCOUNT'),
    ('5.50.5010', '50104', 'Purchase Returns & Allowances',  'CREDIT', True,  False, 'PURCHASE_RETURNS'),
    ('5.50.5010', '50105', 'Inventory Adjustment',           'DEBIT',  True,  False, 'INVENTORY_ADJUSTMENT'),

    # ── Payroll & Employee Costs ──
    ('5.51.5110', '51101', 'Salaries and Wages',        'DEBIT', False, True, None),
    ('5.51.5110', '51102', 'Employee Benefits Expense',  'DEBIT', False, True, None),
    ('5.51.5110', '51103', 'Provident Fund Expense',     'DEBIT', False, True, None),

    # ── Premises & Utilities ──
    ('5.51.5120', '51201', 'Utilities Expense',      'DEBIT', False, True, None),
    ('5.51.5120', '51202', 'Rent Expense',           'DEBIT', False, True, None),
    ('5.51.5120', '51203', 'Repair & Maintenance',   'DEBIT', False, True, None),

    # ── Administrative & General ──
    ('5.51.5130', '51301', 'Telephone and Internet Expense',     'DEBIT', False, True,  None),
    ('5.51.5130', '51302', 'Travel and Transportation Expense',  'DEBIT', False, True,  None),
    ('5.51.5130', '51303', 'Insurance Expense',                  'DEBIT', False, True,  None),
    ('5.51.5130', '51304', 'Office Supplies',                    'DEBIT', False, True,  None),
    ('5.51.5130', '51305', 'Legal & Professional Fees',          'DEBIT', False, True,  None),
    ('5.51.5130', '51306', 'Bad Debt Expense',                   'DEBIT', False, False, None),
    ('5.51.5130', '51307', 'Rounding Adjustment',                'DEBIT', False, True,  None),

    # ── Depreciation & Amortisation ──
    ('5.51.5140', '51401', 'Depreciation Expense',   'DEBIT', True, False, 'DEPRECIATION_EXPENSE'),
    ('5.51.5140', '51402', 'Amortisation Expense',   'DEBIT', True, False, 'AMORTISATION_EXPENSE'),

    # ── Sales & Marketing Expense ──
    ('5.51.5150', '51501', 'Advertising & Marketing',    'DEBIT', False, True, None),
    ('5.51.5150', '51502', 'Sales Commission Expense',   'DEBIT', False, True, None),

    # ── Other Operating Expense ──
    ('5.51.5160', '51601', 'Other Operating Expense', 'DEBIT', False, True, None),

    # ── Research & Development Expense ──
    ('5.51.5170', '51701', 'Research & Development Expense', 'DEBIT', False, True, None),

    # ── Financial Expense ──
    ('5.52.5210', '52101', 'Bank Fees & Charges', 'DEBIT', True,  False, 'BANK_FEES'),
    ('5.52.5210', '52102', 'Interest Expense',    'DEBIT', True,  False, 'INTEREST_EXPENSE'),
    ('5.52.5210', '52103', 'FX Loss',             'DEBIT', True,  False, 'FX_LOSS'),

    # ── Tax Expense ──
    ('5.52.5220', '52201', 'Income Tax Expense', 'DEBIT', True, False, 'INCOME_TAX_EXPENSE'),

    # ── Other Non-Operating Expense ──
    ('5.52.5230', '52301', 'Loss on Asset Disposal', 'DEBIT', True,  False, 'LOSS_ON_DISPOSAL'),
    ('5.52.5230', '52302', 'Other Expense',          'DEBIT', False, True,  None),
]