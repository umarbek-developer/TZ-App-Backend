from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


class RegisterSerializer(serializers.ModelSerializer):
    """Creates a new active user from an email/password pair."""

    password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text='Validated against AUTH_PASSWORD_VALIDATORS.',
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={'input_type': 'password'},
        help_text='Must match password.',
    )

    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'middle_name',
            'email',
            'password',
            'confirm_password',
        ]
        read_only_fields = ['id']
        extra_kwargs = {
            'first_name': {'required': True, 'allow_blank': False},
            'last_name': {'required': True, 'allow_blank': False},
        }

    def validate_email(self, value):
        # Emails are matched case-insensitively at login, so store one canonical
        # form. Without this, Alice@x.com and alice@x.com are two rows that both
        # answer to the same login.
        value = User.objects.normalize_email(value).lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError(
                {'confirm_password': 'Password fields do not match.'}
            )
        return attrs

    def create(self, validated_data):
        validated_data.pop('confirm_password')
        password = validated_data.pop('password')
        # is_active is passed explicitly because the model defaults it to False
        # (a leftover from the template's OTP-verification flow). This API has no
        # verification step, so a registered user must be able to log in at once.
        return User.objects.create_user(password=password, is_active=True, **validated_data)


class LoginSerializer(serializers.Serializer):
    """Validates credentials and returns a refresh/access token pair."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    def validate(self, attrs):
        # AuthenticationFailed (not ValidationError) so the response is 401 rather
        # than 400 — the caller failed to identify, which is what 401 means.
        try:
            user = User.objects.get(email__iexact=attrs['email'])
        except User.DoesNotExist as exc:
            raise AuthenticationFailed('Invalid email or password.') from exc

        if not user.check_password(attrs['password']):
            raise AuthenticationFailed('Invalid email or password.')

        if not user.is_active:
            raise AuthenticationFailed('This account is inactive.')

        attrs['user'] = user
        return attrs

    def to_representation(self, instance):
        refresh = RefreshToken.for_user(instance['user'])
        return {'refresh': str(refresh), 'access': str(refresh.access_token)}


class LogoutSerializer(serializers.Serializer):
    """Accepts the refresh token to blacklist."""

    refresh = serializers.CharField(help_text='The refresh token to invalidate.')


class ProfileSerializer(serializers.ModelSerializer):
    """Read/update representation of the requesting user."""

    class Meta:
        model = User
        fields = [
            'id',
            'first_name',
            'last_name',
            'middle_name',
            'email',
            'is_active',
            'date_joined',
        ]
        # is_active is read-only on purpose: it is the soft-delete flag, and a
        # writable one would let a user reactivate their own deleted account.
        read_only_fields = ['id', 'is_active', 'date_joined']

    def validate_email(self, value):
        value = User.objects.normalize_email(value).lower()
        if User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError('A user with this email already exists.')
        return value


class TokenPairSerializer(serializers.Serializer):
    """Response shape for a successful login. Documentation only."""

    refresh = serializers.CharField()
    access = serializers.CharField()
