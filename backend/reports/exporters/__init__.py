# backend/reports/exporters/__init__.py

"""
Export renderers for financial reports.

USAGE IN VIEWS:
    from reports.exporters import maybe_export

    # Inside any report view's get() method, after generating the report dict:
    export_format = request.query_params.get('export')
    if export_format:
        return maybe_export(export_format, report_type, report_data, company_name)

SUPPORTED FORMATS:
    xlsx  — Excel workbook (openpyxl)
    csv   — Comma-separated values (stdlib csv) — transaction-level only
    pdf   — PDF document (reportlab)
    docx  — Word document (python-docx)

DEPENDENCIES:
    pip install openpyxl reportlab python-docx
"""

from django.http import HttpResponse
from rest_framework.response import Response
from rest_framework import status


# Valid export formats per report type
EXPORT_FORMATS = {
    # Summary/tree reports — no CSV (tree doesn't flatten well)
    'trial_balance':        {'xlsx', 'pdf', 'docx'},
    'balance_sheet':        {'xlsx', 'pdf', 'docx'},
    'income_statement':     {'xlsx', 'pdf', 'docx'},
    'cash_flow':            {'xlsx', 'pdf', 'docx'},
    # Transaction-level reports — CSV works here
    'general_ledger':       {'xlsx', 'csv', 'pdf', 'docx'},
    'account_transactions': {'xlsx', 'csv', 'pdf', 'docx'},
    'journal_entries':      {'xlsx', 'csv', 'pdf', 'docx'},
}

# Content types for each format
CONTENT_TYPES = {
    'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'csv': 'text/csv; charset=utf-8',
    'pdf': 'application/pdf',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
}

# File extensions
EXTENSIONS = {
    'xlsx': '.xlsx',
    'csv': '.csv',
    'pdf': '.pdf',
    'docx': '.docx',
}


def maybe_export(export_format, report_type, report_data, company_name):
    """
    Main dispatch function. Called by views when ?export= is present.

    Args:
        export_format: str — 'xlsx', 'csv', 'pdf', or 'docx'
        report_type: str — e.g. 'trial_balance', 'income_statement'
        report_data: dict — the complete report data from the service layer
        company_name: str — for the filename

    Returns:
        HttpResponse with file download, or DRF Response with error
    """
    export_format = export_format.lower().strip()

    # Validate format is supported globally
    if export_format not in CONTENT_TYPES:
        return Response(
            {
                'success': False,
                'message': (
                    'Invalid export format: "{}". '
                    'Valid options: xlsx, csv, pdf, docx.'
                ).format(export_format),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Validate format is supported for this report type
    valid_formats = EXPORT_FORMATS.get(report_type, set())
    if export_format not in valid_formats:
        return Response(
            {
                'success': False,
                'message': (
                    'Export format "{}" is not available for {}. '
                    'Valid options for this report: {}.'
                ).format(
                    export_format,
                    report_type.replace('_', ' ').title(),
                    ', '.join(sorted(valid_formats)),
                ),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Build safe filename
    safe_company = company_name.replace('"', '').replace(' ', '_')[:30]
    report_title = report_data.get('report_title', report_type).replace(' ', '_')
    filename = 'NidusERP_{company}_{report}{ext}'.format(
        company=safe_company,
        report=report_title,
        ext=EXTENSIONS[export_format],
    )

    # Dispatch to the appropriate renderer
    if export_format == 'xlsx':
        from .excel_renderer import render_excel
        file_bytes = render_excel(report_type, report_data)

    elif export_format == 'csv':
        from .csv_renderer import render_csv
        file_bytes = render_csv(report_type, report_data)

    elif export_format == 'pdf':
        from .pdf_renderer import render_pdf
        file_bytes = render_pdf(report_type, report_data)

    elif export_format == 'docx':
        from .docx_renderer import render_docx
        file_bytes = render_docx(report_type, report_data)

    # Build HTTP response with file download headers
    response = HttpResponse(
        file_bytes,
        content_type=CONTENT_TYPES[export_format],
    )
    response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)

    return response