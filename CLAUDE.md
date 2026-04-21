# NIDUS ERP — Complete Project Context
# Place this file at the project root. Claude Code reads it automatically.
# Last updated: 2026-04-19

## INSTRUCTIONS FOR CLAUDE
You are developing Nidus ERP, a Django REST Framework backend.
The user's preference: "Act as a senior ERP architect, follow accounting standards,
scalable design, industry best practices, security, and optimized databases.
Ask before violating best practice. Provide explanations of the code in comments."

---

## TECH STACK
- Python 3.14, Django 6.0.2, Django REST Framework 3.16.1
- SQLite (dev), PostgreSQL (prod planned)
- JWT auth via SimpleJWT 5.5.1 (ACCESS: 15 min, REFRESH: 7 days, rotate+blacklist)
- openpyxl 3.1.5 (Excel), reportlab 4.4.10 (PDF), python-docx 1.2.0 (DOCX)
- jazzmin 3.0.3 (Django admin styling), django-cors-headers 4.9.0
- django-extensions 4.1, python-dotenv 1.2.1, pillow 12.2.0, lxml 6.0.2
- No frontend yet — all testing via Postman
- OS: Windows 11, IDE: VS Code
- Project path: C:\NidusERP_s\Nidus-ERP-Backend\
- Venv: standard Python venv in project folder

## DEPENDENCIES (requirements.txt)
```
Django==6.0.2
djangorestframework==3.16.1
djangorestframework_simplejwt==5.5.1
django-cors-headers==4.9.0
django-extensions==4.1
django-jazzmin==3.0.3
openpyxl==3.1.5
reportlab==4.4.10
python-docx==1.2.0
python-dotenv==1.2.1
pillow==12.2.0
lxml==6.0.2
```

---

## PROJECT STRUCTURE
```
C:\NidusERP_s\Nidus-ERP-Backend\
└── backend/
    ├── manage.py
    ├── nidus_erp/                  # Django project config
    │   ├── settings.py             # TIME_ZONE='Asia/Dhaka', AUTH_USER_MODEL='authentication.User'
    │   ├── urls.py                 # Root URL config
    │   ├── pagination.py           # StandardResultsSetPagination (PAGE_SIZE=20, max=100)
    │   └── wsgi.py / asgi.py
    ├── authentication/             # Step 1: JWT auth, registration, email verification
    │   ├── models.py               # User (AbstractBaseUser, UUID PK, email-based)
    │   ├── serializers.py
    │   ├── views.py
    │   ├── urls.py
    │   └── admin.py
    ├── companies/                  # Step 2: Company CRUD, roles, invitations
    │   ├── models.py               # Company, CompanyUser, Invitation, DocumentSequence, CurrencyExchangeRate
    │   ├── serializers.py
    │   ├── views.py
    │   ├── urls.py
    │   └── admin.py
    ├── chartofaccounts/            # Step 3: CoA with infinite sub-accounts
    │   ├── models.py               # AccountClassification, Account, SystemAccountMapping
    │   ├── seed.py                 # Default CoA data (L3 tuples + account tuples with cash_flow_category)
    │   ├── services.py             # generate_default_classifications(), generate_default_accounts()
    │   ├── serializers.py          # AccountSerializer with cash_flow_category
    │   ├── views.py                # 13 endpoints including tree view
    │   ├── admin.py                # Jazzmin admin with bulk actions
    │   ├── custom_coa_template.py  # Excel template download with Cash Flow Category column
    │   ├── custom_coa_validator.py # Validates uploaded CoA with cash_flow_category
    │   └── migrations/
    │       ├── 0001_initial.py through 0004_*.py
    │       ├── 0005_accountclassification_cash_flow_category.py  # AddField
    │       ├── 0006_backfill_cash_flow_category.py               # Data migration
    │       └── 0007_add_accumulated_amortisation.py              # L3 1.11.1125 + account 11251
    ├── journals/                   # Step 4: Manual journals, ledger entries, bulk import
    │   ├── models.py               # ManualJournal, ManualJournalLine, LedgerEntry
    │   ├── serializers.py
    │   ├── views.py                # 12 endpoints
    │   ├── urls.py
    │   └── admin.py                # Bulk post/void actions
    └── reports/                    # Step 5: Financial reports ✅ COMPLETE
        ├── __init__.py / apps.py
        ├── urls.py                 # 6 report endpoints
        ├── views.py                # 6 API views (1084 lines)
        ├── services/               # Pure function services (2528 lines total)
        │   ├── __init__.py
        │   ├── balance_engine.py       # Single SQL query per date — THE source of truth
        │   ├── trial_balance.py        # TB + shared helpers used by BS, IS
        │   ├── balance_sheet.py        # BS with auto retained earnings + signed amounts
        │   ├── income_statement.py     # Zoho Books-style P&L, 5 sections, signed amounts
        │   ├── general_ledger.py       # GL with separate debit/credit fields
        │   ├── account_transactions.py # AT with separate debit/credit fields
        │   └── cash_flow.py            # IAS 7 indirect method
        └── exporters/              # File export renderers (2454 lines total)
            ├── __init__.py             # Dispatch: maybe_export(format, report_type, data, company)
            ├── styles.py               # Shared colours, fonts, helpers
            ├── excel_renderer.py       # openpyxl — all 7 report types
            ├── csv_renderer.py         # CSV — GL, AT, JE only
            ├── pdf_renderer.py         # reportlab — all 7 report types
            └── docx_renderer.py        # python-docx — all 7 report types
```

---

## ROOT URLS (nidus_erp/urls.py)
```python
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/companies/', include('companies.urls')),
    path('api/companies/<uuid:company_id>/', include('chartofaccounts.urls')),
    path('api/companies/<uuid:company_id>/', include('journals.urls')),
    path('api/companies/<uuid:company_id>/', include('reports.urls')),
]
```

## INSTALLED_APPS
```python
INSTALLED_APPS = [
    'jazzmin', 'django.contrib.admin', 'django_extensions',
    'django.contrib.auth', 'django.contrib.contenttypes',
    'django.contrib.sessions', 'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework', 'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist', 'corsheaders',
    'authentication', 'companies', 'chartofaccounts', 'journals', 'reports',
]
```

## KEY SETTINGS
```python
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
AUTH_USER_MODEL = 'authentication.User'
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': ['rest_framework_simplejwt.authentication.JWTAuthentication'],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_PAGINATION_CLASS': 'nidus_erp.pagination.StandardResultsSetPagination',
    'PAGE_SIZE': 20,
}
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'  # Dev only
CORS_ALLOWED_ORIGINS = ['http://localhost:3000', 'http://localhost:5173']
```

---

## ALL DATABASE MODELS

### User (authentication/models.py)
```
id              UUID PK (auto)
email           EmailField, unique, db_index — USERNAME_FIELD
full_name       CharField(100)
phone           CharField(20), nullable
is_email_verified  BooleanField (default False)
email_verification_code  CharField(6), nullable
email_verification_code_expires  DateTimeField, nullable
is_active       BooleanField (default True)
is_staff        BooleanField (default False)
date_joined     DateTimeField (default now)
updated_at      DateTimeField (auto_now)
```
Custom UserManager, AbstractBaseUser + PermissionsMixin, USERNAME_FIELD='email', REQUIRED_FIELDS=['full_name']

### Company (companies/models.py)
```
id              UUID PK
owner           FK → User (PROTECT)
name            CharField(200)
trade_name      CharField(200), nullable
industry        CharField(50), choices=IndustryChoices
tax_id          CharField(50), nullable — BIN / Tax ID
base_currency   CharField(3), default='BDT'
fiscal_year_start_month  IntegerField, default=7
company_size    CharField, choices=CompanySizeChoices
is_vat_registered  BooleanField
is_vds_withholding_entity  BooleanField
lock_date       DateField, nullable — transactions before this are frozen
reporting_method  CharField (ACCRUAL/CASH/BOTH, default ACCRUAL)
address, city, postal_code, country (default 'Bangladesh')
phone, website, time_zone (default 'Asia/Dhaka')
subscription_plan  CharField, choices=SubscriptionPlanChoices (FREE_TRIAL default)
is_active       BooleanField (default True)
created_at, updated_at
```

### CompanyUser (companies/models.py)
```
id, user FK, company FK, role CharField, joined_at
Roles: OWNER, ADMIN, ACCOUNTANT, AUDITOR, SALES
unique_together: (user, company)
Permission constants:
  COA_WRITE_ROLES = [OWNER, ADMIN, ACCOUNTANT]
  JOURNAL_WRITE_ROLES = [OWNER, ADMIN, ACCOUNTANT]
  AUDITOR = read-only
```

### Invitation (companies/models.py)
```
id, company FK, invited_by FK, email, role, status (PENDING/ACCEPTED/DECLINED/EXPIRED)
token UUID, created_at, expires_at
```

### DocumentSequence (companies/models.py)
```
id, company FK, module CharField, prefix CharField, next_number IntegerField, padding IntegerField
```
Uses select_for_update() + F() for atomic increment. Example: MANUAL_JOURNAL → MJ-0001, MJ-0002

### CurrencyExchangeRate (companies/models.py)
```
id, company FK, currency_code CharField(3), rate_to_base DecimalField, effective_date, source
```

### AccountClassification (chartofaccounts/models.py)
```
id              UUID PK
company         FK → Company
parent          FK → self, nullable
name            CharField(200)
internal_path   CharField(500), db_index — e.g., '1.10.1010'
cash_flow_category  CharField — OPERATING, INVESTING, FINANCING, CASH
created_at, updated_at
```
@property layer → len(internal_path.split('.')) → 1, 2, or 3

### Account (chartofaccounts/models.py)
```
id              UUID PK
company         FK → Company
classification  FK → AccountClassification (always L3)
parent_account  FK → self, nullable (infinite sub-account depth)
name            CharField(200)
code            CharField(30) — unique per company
internal_path   CharField(500), db_index — e.g., '1.10.1010.0001'
normal_balance  CharField — 'DEBIT' or 'CREDIT'
currency        CharField(3), default='BDT'
is_sub_account  BooleanField
is_active, is_system_account, is_deletable
description     TextField, nullable
created_at, updated_at
```

### SystemAccountMapping (chartofaccounts/models.py)
```
id, company FK, account FK, system_code CharField (unique per company)
Codes: RETAINED_EARNINGS, ACCUMULATED_DEPRECIATION, ACCUMULATED_AMORTISATION,
       OWNER_CAPITAL, BANK_FEES, INTEREST_EXPENSE, FX_LOSS, INCOME_TAX_EXPENSE, LOSS_ON_DISPOSAL
```

### ManualJournal (journals/models.py)
```
id UUID, company FK, entry_number (auto MJ-YYYY-NNNN), date, description, reference
status: DRAFT → POSTED → VOID (with auto reversal)
journal_type: ADJUSTMENT, PURCHASE, SALES, PAYROLL, DEPRECIATION, AMORTISATION, OPENING_BALANCE, TRANSFER
currency, exchange_rate, reversal_of (self FK), voided_by_entry (self FK)
created_by FK, updated_by FK, source CharField, created_at, updated_at
```

### ManualJournalLine (journals/models.py)
```
id UUID, journal FK, account FK, entry_type (DEBIT/CREDIT), amount Decimal(19,4)
description, tax_profile FK (nullable — for future tax module)
```

### LedgerEntry (journals/models.py) — THE CORE TABLE
```
id UUID, company FK, ledger_account FK, date
entry_type (DEBIT/CREDIT), amount Decimal(19,4), currency, exchange_rate Decimal(12,6)
base_amount Decimal(19,4) = amount × exchange_rate
journal_type, source_module (MANUAL_JOURNAL, future SALES_INVOICE, PURCHASE_BILL)
note, content_type FK + object_id UUID (GenericFK → source line), created_at
```
Only POSTED journals create LedgerEntry. Balance = SUM(DEBIT base_amount) − SUM(CREDIT base_amount).

---

## ALL API ENDPOINTS (41 total)

### Step 1 — Authentication (7)
POST /api/auth/register/ | /api/auth/login/ | /api/auth/logout/
POST /api/auth/verify-email/ | /api/auth/resend-otp/ | /api/auth/token/refresh/
GET  /api/auth/me/

### Step 2 — Company Management (9)
POST/GET /api/companies/
GET/PATCH /api/companies/{id}/
POST /api/companies/{id}/invite/ | /api/companies/{id}/respond-invitation/
PATCH /api/companies/{id}/members/{user_id}/role/
DELETE /api/companies/{id}/members/{user_id}/
GET /api/companies/{id}/members/

### Step 3 — Chart of Accounts (13)
GET/POST /api/companies/{id}/accounts/
GET/PATCH /api/companies/{id}/accounts/{aid}/
POST /api/companies/{id}/accounts/{aid}/deactivate/ | reactivate/
GET/POST /api/companies/{id}/classifications/
GET /api/companies/{id}/chart-of-accounts/tree/ | /api/companies/{id}/system-accounts/
POST /api/companies/{id}/coa/template/download/ | /api/companies/{id}/coa/upload/

### Step 4 — Manual Journal Entries (12)
POST/GET /api/companies/{id}/journal-entries/
GET/PATCH/DELETE /api/companies/{id}/journal-entries/{eid}/
POST /api/companies/{id}/journal-entries/{eid}/post/ | void/
GET /api/companies/{id}/accounts/{aid}/ledger/ | balance/
GET /api/companies/{id}/journal-entries/bulk-import/template/
POST /api/companies/{id}/journal-entries/bulk-import/upload/

### Step 5 — Financial Reports (6) ✅ COMPLETE
GET /api/companies/{id}/reports/trial-balance/?as_of_date&filter_mode&compare_date&layout
GET /api/companies/{id}/reports/balance-sheet/?as_of_date&filter_mode&compare_date
GET /api/companies/{id}/reports/income-statement/?from_date&to_date&filter_mode&compare_from_date&compare_to_date
GET /api/companies/{id}/reports/general-ledger/?from_date&to_date&account_id&journal_type&page&page_size
GET /api/companies/{id}/reports/account-transactions/?account_id&from_date&to_date
GET /api/companies/{id}/reports/cash-flow/?from_date&to_date&method&compare_from_date&compare_to_date
All support ?export=xlsx|csv|pdf|docx

---

## CHART OF ACCOUNTS — FULL CLASSIFICATION HIERARCHY

### L1 → L2 → L3 (with cash_flow_category)
```
1 Asset
  1.10 Current Asset
    1.10.1010  Cash                        CASH
    1.10.1020  Bank                        CASH
    1.10.1030  Inventory                   OPERATING
    1.10.1040  Tax Receivables             OPERATING
    1.10.1050  Advances & Prepayments      OPERATING
    1.10.1060  Receivables                 OPERATING
    1.10.1070  Other Current Asset         OPERATING
  1.11 Non-Current Asset
    1.11.1110  Property Plant & Equipment  INVESTING
    1.11.1120  Accumulated Depreciation    INVESTING
    1.11.1125  Accumulated Amortisation    INVESTING  ← migration 0007
    1.11.1130  Intangible Assets           INVESTING
    1.11.1140  Investments                 INVESTING
    1.11.1150  Other Non-Current Assets    INVESTING
2 Liability
  2.20 Short-Term Liabilities
    2.20.2010  Accounts Payables           OPERATING
    2.20.2020  Accrued Expense             OPERATING
    2.20.2030  Withholding Tax & VAT       OPERATING
    2.20.2040  Short-Term Loans            FINANCING
    2.20.2050  Unearned Revenue            OPERATING
    2.20.2060  Suspense & Clearing         OPERATING
    2.20.2070  Other Current Liabilities   OPERATING
    2.20.2080  Provisions                  OPERATING
  2.21 Long-Term Liabilities
    2.21.2110  Long-Term Loans             FINANCING
    2.21.2120  Other Long-Term Liabilities FINANCING
3 Equity
  3.30 Owner's Equity & Reserves
    3.30.3010  Owner's Equity              FINANCING
4 Income
  4.40 Operating Income
    4.40.4010  Revenue                     OPERATING
  4.41 Non-Operating Income
    4.41.4110  Interest & Investment Income OPERATING
    4.41.4120  Rent Income                 OPERATING
    4.41.4130  Other Income                OPERATING
5 Expense
  5.50 Cost of Sales
    5.50.5010  Cost of Goods Sold/Services OPERATING
  5.51 Operating Expense
    5.51.5110  Payroll & Employee Costs    OPERATING
    5.51.5120  Premises & Utilities        OPERATING
    5.51.5130  Administrative & General    OPERATING
    5.51.5140  Depreciation & Amortisation OPERATING
    5.51.5150  Sales & Marketing Expense   OPERATING
    5.51.5160  Other Operating Expense     OPERATING
    5.51.5170  Research & Development      OPERATING
  5.52 Non-Operating Expense
    5.52.5210  Financial Expense           OPERATING
    5.52.5220  Tax Expense                 OPERATING
    5.52.5230  Other Non-Operating Expense OPERATING
```

### System Account Mappings
```
RETAINED_EARNINGS          → 30102 Retained Earnings
ACCUMULATED_DEPRECIATION   → 11201 Accumulated Depreciation
ACCUMULATED_AMORTISATION   → 11251 Accumulated Amortisation
OWNER_CAPITAL              → 30101 Owner Capital
BANK_FEES                  → 52101 Bank Fees & Charges
INTEREST_EXPENSE           → 52102 Interest Expense
FX_LOSS                    → 52103 FX Loss
INCOME_TAX_EXPENSE         → 52201 Income Tax Expense
LOSS_ON_DISPOSAL           → 52301 Loss on Asset Disposal
```

---

## REPORTS APP — DETAILED ARCHITECTURE

### Core Principles
- READ-ONLY app — no models, no migrations
- balance_engine.py: Single SQL query per date → {account_id: {total_debit, total_credit, net}}
- NEVER filters by is_active — inactive accounts may hold balances
- All Decimals during tree construction, single stringify pass at end
- Uses 'layout' param NOT 'format' (DRF reserves 'format')

### Shared Helpers (trial_balance.py, imported by BS/IS)
_build_account_node(), _has_included_descendant(), _get_included_account_ids(),
_stringify_accounts(), FILTER_ALL, FILTER_WITH_TRANSACTIONS, FILTER_NON_ZERO

### Trial Balance — Debit + Credit columns, infinite sub-account nesting, comparison support

### Balance Sheet — Zoho-style single `amount` field in JSON (dr/cr stripped)
Sign: Asset debit_positive=True; Liability/Equity debit_positive=False
Retained earnings auto-calc, equation check: total_assets == total_liabilities_and_equity

### Income Statement — Zoho Books 5-section P&L, single `amount` in JSON (dr/cr stripped)
Sections: Operating Income → COGS → GROSS PROFIT → Operating Expenses → OPERATING PROFIT
         → Non-Op Income → Non-Op Expenses → NET PROFIT/LOSS
Sign: Revenue debit_positive=False; Expense debit_positive=True

### General Ledger — Separate debit/credit fields per transaction, paginated at account level

### Account Transactions — Single-account drill-down, separate debit/credit fields

### Cash Flow — IAS 7 indirect, contra-asset add-back (ACCUM_DEP_L3_PATH='1.11.1120',
ACCUM_AMORT_L3_PATH='1.11.1125'), direct method returns 501

---

## SIGN CONVENTION (CRITICAL — DO NOT CHANGE)

### Balance Engine: net = SUM(DEBIT base_amount) − SUM(CREDIT base_amount)

### _stringify_section(section, has_compare, debit_positive)
| Section | debit_positive | L3 amount | own_debit → | own_credit → |
|---|---|---|---|---|
| Asset | True | dr − cr | + | − |
| Liability | False | cr − dr | − | + |
| Equity | False | cr − dr | − | + |
| Revenue | False | cr − dr | − | + |
| Expense | True | dr − cr | + | − |

### Section Total Negation
```python
total_assets = _sum_section_total(assets)              # AS-IS
total_liabilities = -_sum_section_total(liabilities)   # NEGATE
total_operating_income = -_sum_section_total(op_income) # NEGATE
total_cogs = _sum_section_total(cogs)                   # AS-IS
```

---

## EXPORT LAYER

### Format Matrix
| Report | xlsx | csv | pdf | docx | Column Style |
|---|---|---|---|---|---|
| Trial Balance | ✅ | ❌ | ✅ | ✅ | Debit + Credit |
| Balance Sheet | ✅ | ❌ | ✅ | ✅ | Single Amount |
| Income Statement | ✅ | ❌ | ✅ | ✅ | Single Amount |
| General Ledger | ✅ | ✅ | ✅ | ✅ | Debit + Credit |
| Account Trans | ✅ | ✅ | ✅ | ✅ | Debit + Credit |
| Cash Flow | ✅ | ❌ | ✅ | ✅ | Single Amount |
| Journal Entries | ✅ | ✅ | ✅ | ✅ | Debit + Credit |

### Styling
- Fonts: Arial (Excel/DOCX), Helvetica (PDF)
- L1: Deep Indigo #1A237E | L2: Strong Blue #1565C0 | L3: Dark Teal #00695C
- TOTAL: Deep Indigo #1A237E | Accounts: Black #333333
- Filenames: NidusERP_{Company}_{Report}.{ext}
- CSV: UTF-8 with BOM

---

## USER'S TEST DATABASE
Company: "Rahim Trading Ltd", BDT, fiscal_year_start_month=7
322 accounts, 6 sub-accounts, 164 classifications, 7296 posted journals, 15206 ledger entries

---

## KNOWN PENDING ITEMS

### A) Fixes in current sprint (will be closed by Phases 1–4 of the April 2026 plan)
1. N+1 queries on `ManualJournalListSerializer` (Phase 1 — fixed)
2. Rate limiting on `/api/auth/login/` and `/api/auth/resend-otp/` (Phase 2)
3. Password reset flow (Phase 2)
4. JE export endpoint — renderers exist, view missing (Phase 3)
5. `drf-spectacular` for OpenAPI docs at `/api/schema/` and `/api/docs/` (Phase 3)
6. Automated test suite (Phase 4)

### B) Real bugs / missing logic to close after test suite
7. **`Company.has_financial_records()`** — currently hardcoded `return False`. Must query
   `LedgerEntry.objects.filter(company=self).exists()`. Gates whether the owner can still
   change `base_currency` or `fiscal_year_start_month` after books have been opened.
8. **Auto-create `DocumentSequence` rows on company creation.** Currently must be created
   manually in admin. Add to `generate_default_coa()` and `generate_custom_coa()` in
   `chartofaccounts/services.py` — create MANUAL_JOURNAL sequence at minimum so the very
   first journal post does not fail.
9. **`AccountDeleteView` ledger-entry guard.** Block delete when
   `LedgerEntry.objects.filter(ledger_account=account).exists()`. Currently a TODO comment.
10. Pass
11. **Lock-date endpoint** — `PATCH /api/companies/<id>/settings/lock-date/`. Serializer
    exists, view not yet wired. Currently set via Django admin only.

### C) Admin-only features deferred to Settings UI phase
12. CRUD views for `TaxProfile`, `CurrencyExchangeRate`, `DocumentSequence` (serializers done)
13. System account reassignment — `PATCH /api/companies/<id>/system-accounts/<mapping_id>/`

### D) Accounting features blocked on future modules
14. Cash Flow direct method → returns 501 (needs Sales/Purchase modules — Steps 11/12)
15. Non-cash disposal gains/losses → needs Fixed Asset module
16. Unrealized FX add-back → needs Period-End/FX module (Step 15)
17. Amortisation journals may need re-posting if any were booked before
    migration 0007 split 11251 from 11302
18. Reporting method (ACCRUAL/CASH/BOTH) — field exists on `Company`, filtering logic
    deferred to a later reporting pass

---

## UPCOMING STEPS (DEVELOPMENT ROADMAP)

### Step 6 — Frontend (React + Vite)
React 18+, Vite, React Router v6, Tailwind CSS or Ant Design.
Axios with JWT interceptor (auto-refresh on 401).
Pages: Login, Register, Dashboard, CoA Tree, Journal Entry form, Report viewers with export buttons.

### Step 7 — Contacts Module (backend/contacts/)
Contact model: id, company FK, type (CUSTOMER/VENDOR/BOTH), name, email, phone, address, tax_id,
credit_limit, payment_terms_days, is_active. Sub-records: ContactBankDetails, ContactPerson.
CRUD endpoints + list with type/active/search filters.

### Step 8 — Items / Products Module (backend/items/)
Item model: type (GOODS/SERVICE), name, sku, unit, track_inventory flag.
ItemPrice: selling_price, cost_price. ItemTax: tax_profile FK.
ItemAccount: sales_account FK, purchase_account FK, inventory_account FK.
CRUD endpoints.

### Step 9 — Sales Persons Module (backend/salespersons/)
SalesPerson: company FK, user FK (optional), name, email, commission_rate.
Assigned to sales transactions. CRUD endpoints.

### Step 10 — Tax Module (backend/tax/)
TaxRate: name, rate %, type (VAT/SD/WHT/INCOME_TAX), is_compound.
TaxGroup: groups multiple rates. TaxProfile: reusable configs for items/transactions.
Bangladesh-specific: VAT 15%, Supplementary Duty, Withholding Tax.
Connects to ManualJournalLine.tax_profile FK (already exists).

### Step 11 — Sales Module (backend/sales/)
SalesInvoice + SalesInvoiceLine (item, qty, price, tax, account).
SalesOrder → SalesInvoice → Payment workflow. CreditNote for returns.
Auto-creates LedgerEntry on posting (Receivables Dr, Revenue Cr, Tax Cr).
Enables Cash Flow direct method (sales receipts = operating inflow).

### Step 12 — Purchase Module (backend/purchases/)
PurchaseBill + PurchaseBillLine. PurchaseOrder → Bill → Payment workflow.
DebitNote for returns. Auto-creates LedgerEntry (Expense/Inventory Dr, Payables Cr, Tax Dr).
Enables Cash Flow direct method (supplier payments = operating outflow).

### Step 13 — Expense Module (backend/expenses/)
Simplified single-entry for day-to-day expenses. Receipt upload (image/PDF).
Auto-creates journal: Expense Dr, Cash/Bank Cr.
Approval workflow: DRAFT → PENDING_APPROVAL → APPROVED → POSTED.

### Step 14 — Inventory Module (backend/inventory/)
InventoryMovement per item per warehouse. StockAdjustment for corrections.
FIFO or weighted-average costing (company setting). Affects COGS on sales.
Links to Items (track_inventory flag).

### Step 15 — Period-End / FX Module (backend/periodend/)
Period closing, year-end close (income/expense → Retained Earnings).
FX revaluation at period-end rates. Unrealized FX gain/loss journals.
Enables Cash Flow unrealized FX add-back.

### Step 16 — Budget Module (backend/budgets/)
Budget per fiscal year with BudgetLines per account per month.
Budget vs Actual report. Variance analysis (amount + percentage).

### Step 17 — Banking / Reconciliation Module (backend/banking/)
BankAccount maps to Account. Import bank statements (CSV/OFX/QIF).
Match bank transactions to ledger entries. Auto-categorise recurring.

### Step 18 — Settings Module (backend/settings/)
Company preferences, logo, email templates, payment terms, number formats, custom fields.

### Step 19 — Dashboard
Revenue/expenses/profit/cash widgets. Monthly trends, expense breakdown, receivables aging.
Quick actions, period selector.

### Step 20 — Deployment
PostgreSQL, Docker (Django + Gunicorn + Nginx), env vars, HTTPS, CI/CD (GitHub Actions),
WhiteNoise/S3 for static, DB backups, Sentry monitoring.

---

## DESIGN PATTERNS TO FOLLOW

### Service Layer Pattern
Business logic in services/ — views are thin (parse params → call service → return Response).

### LedgerEntry as Single Source of Truth
Every module creating financial transactions MUST write to LedgerEntry:
```python
LedgerEntry.objects.create(
    company=company, ledger_account=account, date=date,
    entry_type='DEBIT', amount=amount, currency=currency,
    exchange_rate=rate, base_amount=amount*rate,
    journal_type='SALES', source_module='SALES_INVOICE',
    note='...', content_type=ContentType.objects.get_for_model(Line), object_id=line.id,
)
```

### Document Status Lifecycle
DRAFT → POSTED → VOID. DRAFT: editable, no ledger. POSTED: frozen, creates LedgerEntry.
VOID: creates reversing entry, both read-only.

### Permission Model
Views check CompanyUser role. Read: all. Write: OWNER+ADMIN+ACCOUNTANT. AUDITOR: read-only.

### UUID PKs everywhere. Decimal(19,4) for money — never float.