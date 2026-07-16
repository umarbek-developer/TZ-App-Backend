"""Project-wide DRF exception handling.

Every error the API returns — validation, auth, permissions, not-found, and
anything unforeseen — comes back in one shape:

    {"success": false, "message": "...", "errors": {}}

`message` is a human-readable sentence. `errors` is field-scoped detail, and is an
empty object for errors that have no per-field breakdown.

Wired up via REST_FRAMEWORK['EXCEPTION_HANDLER'] in config/settings/base.py.
"""

import logging

from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

logger = logging.getLogger(__name__)

# Errors with no per-field breakdown get a sentence keyed off their status code.
# DRF's own `detail` is preferred when it says something more specific.
_DEFAULT_MESSAGES = {
    status.HTTP_400_BAD_REQUEST: 'Invalid request.',
    status.HTTP_401_UNAUTHORIZED: 'Authentication credentials were not provided or are invalid.',
    status.HTTP_403_FORBIDDEN: 'You do not have permission to perform this action.',
    status.HTTP_404_NOT_FOUND: 'Not found.',
    status.HTTP_405_METHOD_NOT_ALLOWED: 'Method not allowed.',
    status.HTTP_429_TOO_MANY_REQUESTS: 'Too many requests.',
}

_VALIDATION_MESSAGE = 'Validation failed.'
_SERVER_ERROR_MESSAGE = 'Internal server error.'

# Where a bare list of errors is filed, matching DRF's own convention.
NON_FIELD_ERRORS = 'non_field_errors'


def _as_errors(data):
    """Coerce DRF's validation payload into a dict.

    DRF hands back a dict for field errors, but a list for a serializer-level
    `ValidationError`, and occasionally a bare string. The envelope promises an
    object, so normalise the other two under `non_field_errors`.
    """
    if isinstance(data, dict):
        return data
    if isinstance(data, list):
        return {NON_FIELD_ERRORS: data}
    return {NON_FIELD_ERRORS: [data]}


def _as_message(data, status_code):
    """Pull a sentence out of DRF's payload, falling back on the status code."""
    default = _DEFAULT_MESSAGES.get(status_code, 'Request failed.')

    if isinstance(data, dict) and 'detail' in data:
        return str(data['detail'])
    if isinstance(data, list) and data and isinstance(data[0], str):
        return str(data[0])
    if isinstance(data, str):
        return data
    return default


def custom_exception_handler(exc, context):
    """Reshape every DRF error into the standard envelope.

    Delegates to DRF first and keeps the Response it builds — status code and
    headers included. That matters: DRF puts the `WWW-Authenticate` header on 401s,
    and rebuilding the response from scratch would drop it and quietly turn 401s
    into 403s.
    """
    response = drf_exception_handler(exc, context)

    if response is None:
        return _handle_unexpected(exc, context)

    if isinstance(exc, ValidationError):
        message = _VALIDATION_MESSAGE
        errors = _as_errors(response.data)
    else:
        message = _as_message(response.data, response.status_code)
        errors = {}

    response.data = {'success': False, 'message': message, 'errors': errors}
    return response


def _handle_unexpected(exc, context):
    """Anything DRF does not recognise: a bug, surfaced as a clean 500.

    The traceback goes to the logger rather than the response — an API must not
    leak internals to callers. Returning a Response (rather than None) stops DRF
    re-raising, which is what keeps the 500 JSON instead of Django's HTML error
    page, so the logging here is the only record: do not remove it.
    """
    view = context.get('view') if context else None
    logger.exception('Unhandled exception in %s', view.__class__.__name__ if view else 'view')

    return Response(
        {'success': False, 'message': _SERVER_ERROR_MESSAGE, 'errors': {}},
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
