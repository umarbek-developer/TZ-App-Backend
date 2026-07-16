from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from api.auth.serializers.user_serializers import ProfileSerializer


@extend_schema_view(
    get=extend_schema(
        tags=['auth'],
        summary='Retrieve the current user',
        responses={
            200: ProfileSerializer,
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
        },
    ),
    patch=extend_schema(
        tags=['auth'],
        summary='Update the current user',
        description=(
            'Partially updates the requesting user. `is_active`, `id` and '
            '`date_joined` are read-only.'
        ),
        request=ProfileSerializer,
        responses={
            200: ProfileSerializer,
            400: OpenApiResponse(description='Validation failed.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
        },
    ),
    delete=extend_schema(
        tags=['auth'],
        summary='Soft-delete the current user',
        description=(
            'Sets `is_active=False` and blacklists every outstanding refresh token '
            'for the account. Existing access tokens stop working immediately '
            'because SimpleJWT rejects tokens belonging to inactive users '
            '(CHECK_USER_IS_ACTIVE). The account can no longer log in.'
        ),
        responses={
            204: OpenApiResponse(description='Account deactivated and tokens revoked.'),
            401: OpenApiResponse(description='Authentication credentials were not provided.'),
        },
    ),
)
class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(ProfileSerializer(request.user).data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = ProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request):
        user = request.user
        user.is_active = False
        # update_fields keeps the save() override from rewriting the password hash.
        user.save(update_fields=['is_active'])

        # Blacklist every outstanding refresh token, not just the caller's current
        # one: a soft-deleted account must not stay reachable from a session on
        # another device.
        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)

        return Response(status=status.HTTP_204_NO_CONTENT)
