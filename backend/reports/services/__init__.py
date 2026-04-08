# backend/reports/services/__init__.py
#
# Service modules for financial report generation.
# Each module is a pure function layer — no models, no migrations.
#
# balance_engine.py         — Shared SQL aggregation (single source of truth)
# trial_balance.py          — Trial Balance + shared tree-building utilities
# balance_sheet.py          — Balance Sheet (Statement of Financial Position)
# income_statement.py       — Income Statement (Profit & Loss)
# general_ledger.py         — General Ledger (transaction-level detail, all accounts)
# account_transactions.py   — Account Transactions (drill-down, single account)
# cash_flow.py              — Cash Flow Statement (Indirect Method)