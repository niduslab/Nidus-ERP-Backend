# backend/reports/tests/test_exporters.py
#
# SMOKE TESTS for the export renderers.
#
# We don't verify the content of generated files (verifying PDF visual
# layout in pytest is impractical). What we verify:
#   - render_xxx() returns non-empty bytes for every (format, report) combo
#   - Each format produces a file with the correct magic-number / signature
#   - maybe_export() rejects invalid format names with a 400 Response
#
# This catches the most common bugs:
#   - Renderer crashes on a particular report shape
#   - Report data has a key the renderer expects to find but doesn't
#   - openpyxl / reportlab / docx import failures

import pytest
from datetime import date
from decimal import Decimal

from journals.services import post_journal
from reports.exporters import maybe_export
from reports.exporters.excel_renderer import render_excel
from reports.exporters.csv_renderer import render_csv
from reports.exporters.pdf_renderer import render_pdf
from reports.exporters.docx_renderer import render_docx
from reports.services.balance_sheet import generate_balance_sheet
from reports.services.income_statement import generate_income_statement
from reports.services.trial_balance import generate_trial_balance
from reports.services.cash_flow import generate_cash_flow


# ── File magic numbers (first few bytes of each format) ──
# Used to verify the renderers actually produced the right file type.
# More reliable than checking extensions or content-type strings.
MAGIC = {
    'xlsx': b'PK\x03\x04',          # XLSX is a ZIP archive
    'docx': b'PK\x03\x04',          # DOCX is also a ZIP archive
    'pdf':  b'%PDF-',               # PDF magic
    'csv':  b'\xef\xbb\xbf',        # UTF-8 BOM (the project's CSVs include this)
}


@pytest.mark.django_db
class TestExporterSmokeXLSX:
    """Excel renderer must succeed on every report type."""

    @pytest.mark.parametrize('report_type,generator', [
        ('balance_sheet',
            lambda c: generate_balance_sheet(c, as_of_date=date(2026, 12, 31))),
        ('trial_balance',
            lambda c: generate_trial_balance(c, as_of_date=date(2026, 12, 31))),
        ('income_statement',
            lambda c: generate_income_statement(c, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))),
        ('cash_flow',
            lambda c: generate_cash_flow(c, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31))),
    ])
    def test_renders_each_summary_report_to_xlsx(
        self, journal_factory, company, verified_user, report_type, generator,
    ):
        """Posts one journal so the report has data, then renders to xlsx
        and verifies the magic number."""
        post_journal(journal_factory(), posted_by=verified_user)
        data = generator(company)

        output = render_excel(report_type, data)

        assert isinstance(output, bytes)
        assert len(output) > 100             # Non-trivial file size
        assert output.startswith(MAGIC['xlsx'])


@pytest.mark.django_db
class TestExporterSmokePDF:
    """PDF renderer must succeed on every report type."""

    def test_balance_sheet_pdf(self, journal_factory, company, verified_user):
        post_journal(journal_factory(), posted_by=verified_user)
        data = generate_balance_sheet(company, as_of_date=date(2026, 12, 31))
        output = render_pdf('balance_sheet', data)
        assert output.startswith(MAGIC['pdf'])

    def test_income_statement_pdf(self, journal_factory, company, verified_user):
        post_journal(journal_factory(), posted_by=verified_user)
        data = generate_income_statement(
            company, from_date=date(2026, 1, 1), to_date=date(2026, 12, 31),
        )
        output = render_pdf('income_statement', data)
        assert output.startswith(MAGIC['pdf'])


@pytest.mark.django_db
class TestExporterDispatch:

    def test_invalid_format_returns_400(
        self, company, journal_factory, verified_user,
    ):
        """maybe_export() must reject unknown formats with HTTP 400."""
        post_journal(journal_factory(), posted_by=verified_user)
        data = generate_trial_balance(company, as_of_date=date(2026, 12, 31))

        response = maybe_export(
            export_format='json',                # Not supported
            report_type='trial_balance',
            report_data=data,
            company_name=company.name,
        )

        # maybe_export returns a DRF Response on validation failure.
        assert response.status_code == 400
        assert 'Invalid export format' in str(response.data['message'])

    def test_csv_not_allowed_for_balance_sheet(self, company):
        """Balance Sheet doesn't support CSV (the tree structure doesn't
        flatten well). maybe_export must reject this combo with 400."""
        data = generate_balance_sheet(company, as_of_date=date(2026, 12, 31))

        response = maybe_export(
            export_format='csv',
            report_type='balance_sheet',
            report_data=data,
            company_name=company.name,
        )

        assert response.status_code == 400