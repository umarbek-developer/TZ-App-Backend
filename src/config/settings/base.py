import os

import environ
from django.core.exceptions import ImproperlyConfigured

env = environ.Env()

BASE_DIR = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!

DEBUG = env("DEBUG") == "1"

# Application definition

INSTALLED_APPS = [
    'jazzmin',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # third-party apps
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'django_filters',
    'drf_spectacular',

    # own apps
    'apps.users',
    'apps.rbac',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

# The API itself renders no templates. This block exists for django.contrib.admin
# and the drf-spectacular UIs, which ship their own — hence APP_DIRS with no DIRS.
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ]
        }
    }
]

WSGI_APPLICATION = 'config.wsgi.application'

# Password validation
# https://docs.djangoproject.com/en/4.1/ref/settings/#auth-password-validators
# Enforced on registration by api.auth.serializers.user_serializers.RegisterSerializer.

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

REST_FRAMEWORK = {
    # JWT is the only authentication mechanism. Session/Basic are deliberately
    # absent: this is a stateless token API.
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    # Wraps every successful body in the standard envelope. See api/renderers.py.
    'DEFAULT_RENDERER_CLASSES': [
        'api.renderers.EnvelopeJSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    'DEFAULT_PAGINATION_CLASS': 'api.pagination.CustomPagination',
    'PAGE_SIZE': 10,
    # Secure by default: endpoints require a valid token unless they opt out with
    # an explicit AllowAny (register and login do).
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    # Every error response goes out in one envelope. See api/exceptions.py.
    'EXCEPTION_HANDLER': 'api.exceptions.custom_exception_handler',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'TZ-App Backend API',
    'DESCRIPTION': (
        'JWT authentication with role-based access control.\n\n'
        'Every response uses one envelope. Success:\n\n'
        '    {"success": true, "message": "...", "data": {}}\n\n'
        'Failure:\n\n'
        '    {"success": false, "message": "...", "errors": {}}\n\n'
        'Send the access token as `Authorization: Bearer <token>`.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': '/api/v1',
    # Views declare the payload they return; this rewrites each documented body
    # into the envelope the renderer actually sends, so docs cannot drift.
    'POSTPROCESSING_HOOKS': [
        'drf_spectacular.hooks.postprocess_schema_enums',
        'api.schema.envelope_responses',
    ],
}

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Tashkent'

USE_I18N = True

USE_TZ = False

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/
# The API serves no static assets of its own; this covers django.contrib.admin's.

STATIC_URL = '/static/'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

AUTH_USER_MODEL = 'users.User'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


DB_TYPE = env("DB_TYPE")

# PostgreSQL only. There is deliberately no sqlite fallback: a wrong DB_TYPE must
# fail loudly at startup rather than silently running the project on a different
# database than the one it is developed and tested against.
if DB_TYPE != "psql":
    raise ImproperlyConfigured(
        f'DB_TYPE must be "psql" (this project is PostgreSQL-only), got "{DB_TYPE}". '
        f"Update {os.path.join(BASE_DIR, '.env')}."
    )

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "CONN_MAX_AGE": 60,
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT"),
    }
}
