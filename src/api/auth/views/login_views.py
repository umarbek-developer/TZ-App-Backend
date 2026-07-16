from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.auth.serializers.user_serializers import LoginSerializer, TokenPairSerializer


@extend_schema(
    tags=['auth'],
    summary='Log in and obtain a JWT pair',
    description=(
        'Authenticates by email and password and returns a refresh/access token '
        'pair. Send the access token as `Authorization: Bearer <access>` on '
        'subsequent requests. Inactive (soft-deleted) accounts are rejected.'
    ),
    request=LoginSerializer,
    responses={
        200: TokenPairSerializer,
        401: OpenApiResponse(description='Invalid credentials, or the account is inactive.'),
    },
    examples=[
        OpenApiExample(
            'Valid login',
            value={'email': 'john@gmail.com', 'password': 'Password123!'},
            request_only=True,
        ),
    ],
)
class LoginView(APIView):
    permission_classes = [AllowAny]
    # The default JWTAuthentication is kept deliberately, even though this endpoint
    # is public. DRF downgrades AuthenticationFailed to 403 when a view has no
    # authenticator to build a WWW-Authenticate header from; keeping it means bad
    # credentials correctly return 401.

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
