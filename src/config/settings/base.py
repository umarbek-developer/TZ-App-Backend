# from pathlib import Path
import os

import environ
from django.core.exceptions import ImproperlyConfigured

env = environ.Env()

BASE_DIR = os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

SECRET_KEY = env("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!

DEBUG = env("DEBUG")
BASE_URL = env("BASE_URL")


if DEBUG == "1":
    DEBUG = True
else:
    DEBUG = False

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
    'apps.utils',
    'apps.users'
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

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR, 'templates'],
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
    'DEFAULT_PAGINATION_CLASS': 'api.pagination.CustomPagination',
    'PAGE_SIZE': 10,
    # Secure by default: endpoints require a valid token unless they opt out with
    # an explicit AllowAny (register and login do).
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.ScopedRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'login': '5/day',
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'TZ-App Backend API',
    'DESCRIPTION': 'JWT authentication API. RBAC is added in a later step.',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'SCHEMA_PATH_PREFIX': '/api/v1',
}



LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'Asia/Tashkent'

USE_I18N = True

USE_TZ = False

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/4.1/howto/static-files/

STATIC_URL = '/static/'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# Default primary key field type
# https://docs.djangoproject.com/en/4.1/ref/settings/#default-auto-field

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



EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = env("EMAIL_HOST")
EMAIL_HOST_PASSWORD = env("EMAIL_PASSWORD") # Generate in Gmail


BASE_URL_LINK = env("BASE_URL_LINK")


# CELERY SOZLAMALARI

CELERY_BROKER_URL = 'redis://localhost:6379/0'  # yoki Docker bo'lsa: redis://redis_br:6379/0
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'

# Agar SQLite bazadan broker sifatida foydalanmoqchi bo'lsangiz:
# CELERY_BROKER_URL = 'sqla+sqlite:///db.sqlite3'
# CELERY_RESULT_BACKEND = 'db+sqlite:///db.sqlite3'

CELERY_ACCEPT_CONTENT = ['application/json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_IGNORE_RESULT = False
CELERY_TASK_SOFT_TIME_LIMIT = 60

