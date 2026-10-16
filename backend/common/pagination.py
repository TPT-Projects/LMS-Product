import math

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

ALLOWED_PAGE_SIZES = (25, 50, 100, 200)
DEFAULT_PAGE_SIZE = 25


class StandardPagination(PageNumberPagination):
    """Server-side paging used by every list (spec section 6, "Tables").

    `page_size` must be 25, 50, 100 or 200. Any other value falls back to 25.
    """

    page_size = DEFAULT_PAGE_SIZE
    page_size_query_param = "page_size"
    max_page_size = max(ALLOWED_PAGE_SIZES)

    def get_page_size(self, request) -> int:
        raw = request.query_params.get(self.page_size_query_param)
        try:
            size = int(raw) if raw is not None else DEFAULT_PAGE_SIZE
        except ValueError:
            return DEFAULT_PAGE_SIZE
        return size if size in ALLOWED_PAGE_SIZES else DEFAULT_PAGE_SIZE

    def get_paginated_response(self, data) -> Response:
        count = self.page.paginator.count
        page_size = self.page.paginator.per_page
        return Response(
            {
                "count": count,
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
                "page": self.page.number,
                "page_size": page_size,
                "total_pages": max(1, math.ceil(count / page_size)),
                "results": data,
            }
        )
