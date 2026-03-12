# backend/nidus_erp/pagination.py

from collections import OrderedDict
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """
    Custom pagination that includes total_count, page numbers,
    and page_size in the response. Used across all list endpoints.

    Query parameters:
        ?page=2          → Go to page 2
        ?page_size=50    → Show 50 items per page (max 100)

    Response format:
        {
            "success": true,
            "data": [...],
            "pagination": {
                "total_count": 934,
                "page": 2,
                "page_size": 20,
                "total_pages": 47,
                "next": "http://.../api/.../?page=3",
                "previous": "http://.../api/.../?page=1"
            }
        }
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('success', True),
            ('data', data),
            ('pagination', OrderedDict([
                ('total_count', self.page.paginator.count),
                ('page', self.page.number),
                ('page_size', self.get_page_size(self.request)),
                ('total_pages', self.page.paginator.num_pages),
                ('next', self.get_next_link()),
                ('previous', self.get_previous_link()),
            ]))
        ]))