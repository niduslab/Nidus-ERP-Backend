# backend/journals/export.py

"""
Journal Entries export assembly.

Responsibility:
    Assemble a payload in the shape expected by reports/exporters/*.
    The renderers already exist — they live in reports.exporters and are
    already hooked up via reports.exporters.maybe_export(). This module
    is the thin bridge between the filtered ManualJournal queryset and
    that renderer contract.

Why a separate module (not views.py, not services.py):
    views.py  = HTTP concerns (request parsing, permissions, response)
    services.py = write-side business logic (create/post/void journals)
    export.py  = read-side output assembly (this file)

    Keeping these distinct means a unit test for the export shape never
    has to construct an HttpRequest or depend on transaction semantics.

Output shape (what renderers expect — see reports/exporters/*_renderer.py):
    {
        'report_title':   'Journal Entries',
        'company_name':   str,
        'base_currency':  str,
        'from_date':      str (ISO) or '',
        'to_date':        str (ISO) or '',
        'journals': [
            {
                'entry_number': str,
                'date':         str (ISO),
                'status':       str,   # DRAFT / POSTED / VOID
                'journal_type': str,
                'description':  str,
                'reference':    str,
                'currency':     str,
                'exchange_rate': str,
                'lines': [
                    {
                        'account_code': str,
                        'account_name': str,
                        'entry_type':   'DEBIT' | 'CREDIT',
                        'amount':       str (Decimal stringified),
                    },
                    ...
                ],
            },
            ...
        ],
    }
"""

from django.db.models import Q

from .models import ManualJournal


# Safety cap — refuse to export absurdly large result sets.
# With an average of 4-6 lines per journal, 10k journals = up to 60k rows —
# already close to Excel's effective comfortable limit. Past this, the user
# should narrow their filters.
MAX_EXPORT_JOURNALS = 10_000


def build_export_payload(company, filters=None):
    """
    Build the renderer-ready payload for Journal Entries export.

    Args:
        company: Company instance (caller has already verified membership).
        filters: dict of optional filters, identical to the list endpoint:
            - status       (str, upper-cased by caller)
            - journal_type (str, upper-cased by caller)
            - date_from    (date or ISO str)
            - date_to      (date or ISO str)
            - search       (str, free-text across entry_number/description/reference)

    Returns:
        (payload_dict, count) where count is the total number of journals
        included. The caller uses `count` for logging and the safety cap check.

    Raises:
        ValueError — if the filtered queryset exceeds MAX_EXPORT_JOURNALS.
                     The view translates this into an HTTP 400 response.

    Performance:
        prefetch_related('lines__account') pulls every line + its account in
        at most 2 additional queries, regardless of journal count. Without
        it, iterating journal.lines.all() would fire one query per journal
        (N+1). select_related('created_by') is NOT used here because the
        export payload doesn't include the creator — a deliberate omission
        to keep the exported file focused on accounting data.
    """
    filters = filters or {}

    # ── Base queryset ──
    qs = (
        ManualJournal.objects
        .filter(company=company)
        .prefetch_related('lines__account')   # 2-query fan-out for all lines
        .order_by('date', 'entry_number')     # Deterministic output order
    )

    # ── Apply the same filter surface as the list endpoint ──
    # Each filter is independent; all are AND-combined, matching how users
    # already think about the list view.
    if filters.get('status'):
        qs = qs.filter(status=filters['status'])

    if filters.get('journal_type'):
        qs = qs.filter(journal_type=filters['journal_type'])

    if filters.get('date_from'):
        qs = qs.filter(date__gte=filters['date_from'])

    if filters.get('date_to'):
        qs = qs.filter(date__lte=filters['date_to'])

    if filters.get('search'):
        term = filters['search']
        qs = qs.filter(
            Q(entry_number__icontains=term) |
            Q(description__icontains=term) |
            Q(reference__icontains=term)
        )

    # ── Safety cap ──
    # Use .count() here (a cheap COUNT(*) query) BEFORE materialising the
    # full queryset. If the user asked for too much, fail fast without
    # loading anything into memory.
    total = qs.count()
    if total > MAX_EXPORT_JOURNALS:
        raise ValueError(
            'Result set too large for export: {} journals found, limit is {}. '
            'Please narrow your filters (e.g., set date_from/date_to or filter by status).'
            .format(total, MAX_EXPORT_JOURNALS)
        )

    # ── Build the renderer-expected dict ──
    # Stringify Decimals and dates because the renderers all handle str I/O —
    # keeping the data types uniform avoids per-renderer type checks and
    # matches the shape the renderers already consume from the reports app.
    journals_payload = []
    for journal in qs:
        lines_payload = []
        for line in journal.lines.all():   # Uses the prefetched cache — no extra queries
            lines_payload.append({
                'account_code': line.account.code,
                'account_name': line.account.name,
                'entry_type':   line.entry_type,
                'amount':       str(line.amount),
            })

        journals_payload.append({
            'entry_number': journal.entry_number,
            'date':         str(journal.date),
            'status':       journal.status,
            'journal_type': journal.journal_type or '',
            'description':  journal.description or '',
            'reference':    journal.reference or '',
            'currency':     journal.currency,
            'exchange_rate': str(journal.exchange_rate),
            'lines':        lines_payload,
        })

    # ── Build an "applied filters" summary for the renderer header ──
    # We intentionally include ONLY filters the user actually sent — a clean,
    # readable summary at the top of the PDF/DOCX that mirrors what they
    # typed in the query string. Empty/missing filters are dropped, not
    # shown as 'All' or '—', so the header stays tight when no filters
    # were applied. This matches Zoho Books / QuickBooks / Xero convention.
    #
    # Keys are the ORIGINAL API query-param names (status, journal_type,
    # date_from, date_to, search) so the output matches what the user
    # remembers typing. Values are human-readable strings ready to render.
    applied_filters = []
    if filters.get('status'):
        applied_filters.append(('Status', filters['status']))
    if filters.get('journal_type'):
        applied_filters.append(('Journal Type', filters['journal_type']))
    if filters.get('date_from'):
        applied_filters.append(('Date From', str(filters['date_from'])))
    if filters.get('date_to'):
        applied_filters.append(('Date To', str(filters['date_to'])))
    if filters.get('search'):
        applied_filters.append(('Search', str(filters['search'])))

    payload = {
        'report_title':  'Journal Entries',
        'company_name':  company.name,
        'base_currency': company.base_currency,
        # Echo the date filters back so the renderer's header block can
        # display them. Empty strings when no filter was applied.
        'from_date': str(filters['date_from']) if filters.get('date_from') else '',
        'to_date':   str(filters['date_to'])   if filters.get('date_to')   else '',
        # Structured filters list — renderers (PDF/DOCX) render this as
        # the "Applied filters:" block beneath the report title. List of
        # (label, value) tuples so display order matches filter importance.
        'applied_filters': applied_filters,
        # Total count for the renderer to show "Total entries: N" in the
        # header — helpful context when filters are applied.
        'journal_count': total,
        'journals':  journals_payload,
    }

    return payload, total