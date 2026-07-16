from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView


@extend_schema(
    tags=['admin'],
    summary='Health-check test view',
    description="This is a test view",
    # Declared explicitly: an APIView gives drf-spectacular nothing to infer a
    # response shape from, which otherwise errors out schema generation.
    responses={
        200: OpenApiResponse(
            response=inline_serializer(
                name='TestResponse',
                fields={'detail': serializers.CharField()},
            ),
            description='Service is reachable.',
        )
    },
)
class TestView(APIView):

    def get(self, request):
        return Response({"detail": 'Hello, world!'}, status=status.HTTP_200_OK)
