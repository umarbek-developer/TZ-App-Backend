import math

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class CustomPagination(PageNumberPagination):
    """Project-wide pagination, wired as DEFAULT_PAGINATION_CLASS.

    The page travels under the response envelope's `data` key, so a list body
    reads `{"success": true, "message": "...", "data": {count, pages, results}}`.
    """

    page_size_query_param = "page_size"

    def get_paginated_response(self, data, **kwargs):
        return Response({
            'count': self.page.paginator.count,
            'pages': math.ceil(self.page.paginator.count / self.page.paginator.per_page),
            **kwargs,
            'results': data,
        })

    def get_paginated_response_schema(self, schema):
        return {
            'type': 'object',
            'required': ['count', 'pages', 'results'],
            'properties': {
                'count': {
                    'type': 'integer',
                    'example': 123,
                },
                # Declared because get_paginated_response returns it; without this
                # the schema would advertise a body the API does not send.
                'pages': {
                    'type': 'integer',
                    'example': 13,
                },
                'results': schema,
            },
        }
