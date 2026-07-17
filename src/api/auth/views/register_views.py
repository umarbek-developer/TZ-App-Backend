from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from api.auth.serializers.user_serializers import RegisterSerializer


@extend_schema(
    tags=['auth'],
    summary='Register a new user',
    description=(
        'Creates an active user account. The email must be unique '
        '(case-insensitive) and the two password fields must match. '
        'The created user can log in immediately — there is no verification step.'
    ),
    request=RegisterSerializer,
    responses={
        201: RegisterSerializer,
        400: OpenApiResponse(description='Validation failed (duplicate email, password mismatch).'),
    },
    examples=[
        OpenApiExample(
            'Valid registration',
            value={
                'first_name': 'John',
                'last_name': 'Doe',
                'middle_name': 'Smith',
                'email': 'john@gmail.com',
                'password': 'Password123!',
                'confirm_password': 'Password123!',
            },
            request_only=True,
        ),
    ],
)
class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        response = Response(serializer.data, status=status.HTTP_201_CREATED)
        response.success_message = 'Registration successful.'
        return response
