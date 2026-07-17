from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from api.auth.serializers.user_serializers import LogoutSerializer


@extend_schema(
    tags=['auth'],
    summary='Log out',
    description=(
        'Blacklists the supplied refresh token so it can no longer be exchanged '
        'for new access tokens. The current access token is not revoked and stays '
        'valid until it expires — that is inherent to stateless JWT.\n\n'
        'Returns `{"success": true, "message": "Logged out successfully.", "data": {}}`.'
    ),
    request=LogoutSerializer,
    responses={
        200: OpenApiResponse(description='Refresh token blacklisted.'),
        400: OpenApiResponse(description='Token is invalid, expired, or already blacklisted.'),
        401: OpenApiResponse(description='Authentication credentials were not provided.'),
    },
)
class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            RefreshToken(serializer.validated_data['refresh']).blacklist()
        except TokenError as exc:
            raise serializers.ValidationError(
                {'refresh': 'Token is invalid, expired, or already blacklisted.'}
            ) from exc

        # 200 rather than 205: every response carries the envelope, and HTTP
        # forbids a body on 205.
        response = Response(status=status.HTTP_200_OK)
        response.success_message = 'Logged out successfully.'
        return response
