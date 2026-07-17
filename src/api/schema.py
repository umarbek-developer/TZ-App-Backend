"""drf-spectacular postprocessing: document the response envelope.

Views declare the *payload* they return (`responses={200: RoleSerializer}`), which
keeps them readable. The envelope is applied at render time by
`api.renderers.EnvelopeJSONRenderer`, so the published schema would otherwise
describe a body the API never sends.

This hook closes that gap by wrapping every documented response the same way the
renderer wraps the real one — so the two cannot drift apart as endpoints are added.
"""

_SUCCESS_ENVELOPE_DESCRIPTION = 'Standard success envelope.'
_ERROR_ENVELOPE_DESCRIPTION = 'Standard error envelope.'


def _success_envelope(payload_schema):
    return {
        'type': 'object',
        'required': ['success', 'message', 'data'],
        'properties': {
            'success': {'type': 'boolean', 'enum': [True], 'example': True},
            'message': {'type': 'string', 'example': 'Retrieved successfully.'},
            'data': payload_schema,
        },
        'description': _SUCCESS_ENVELOPE_DESCRIPTION,
    }


def _error_envelope(message_example):
    return {
        'type': 'object',
        'required': ['success', 'message', 'errors'],
        'properties': {
            'success': {'type': 'boolean', 'enum': [False], 'example': False},
            'message': {'type': 'string', 'example': message_example},
            'errors': {
                'type': 'object',
                'additionalProperties': True,
                'description': (
                    'Field-scoped detail. Empty for errors with no per-field breakdown.'
                ),
                'example': {},
            },
        },
        'description': _ERROR_ENVELOPE_DESCRIPTION,
    }


_ERROR_EXAMPLES = {
    '400': 'Validation failed.',
    '401': 'Authentication credentials were not provided.',
    '403': 'You do not have permission to perform this action.',
    '404': 'Not found.',
    '405': 'Method not allowed.',
    '429': 'Too many requests.',
    '500': 'Internal server error.',
}


def _error_example_for(code):
    return _ERROR_EXAMPLES.get(code, 'Request failed.')


def envelope_responses(result, generator, request, public):
    """Wrap every documented response body in the envelope the API actually sends."""
    for methods in result.get('paths', {}).values():
        for operation in methods.values():
            if not isinstance(operation, dict):
                continue
            for code, response in operation.get('responses', {}).items():
                if code.startswith('2'):
                    _wrap_success(response)
                else:
                    _wrap_error(response, code)
    return result


def _wrap_success(response):
    content = response.get('content')
    if not content:
        # A declared-but-body-less success (e.g. OpenApiResponse(description=...)).
        # The API still sends the envelope, with an empty data object.
        response['content'] = {
            'application/json': {'schema': _success_envelope({'type': 'object', 'example': {}})}
        }
        return

    for media in content.values():
        schema = media.get('schema')
        if schema is not None:
            media['schema'] = _success_envelope(schema)


def _wrap_error(response, code):
    # Errors carry no payload schema, so whatever a view declared is replaced
    # outright by the envelope the exception handler produces.
    response['content'] = {
        'application/json': {'schema': _error_envelope(_error_example_for(code))}
    }
