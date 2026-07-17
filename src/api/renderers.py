"""One response envelope for the whole API.

Success bodies are wrapped here rather than in each view, so that DRF's own
generic machinery — `ModelViewSet.list`, `.create`, and friends, whose Responses
we never construct — is covered by the same rule as hand-written views:

    {"success": true, "message": "...", "data": {}}

Failures are already shaped by `api.exceptions.custom_exception_handler`:

    {"success": false, "message": "...", "errors": {}}

so this renderer leaves them alone.

Setting a message: a view can attach one to its Response,

    response = Response(serializer.data)
    response.success_message = 'Login successful.'

or a viewset can map action -> message with `EnvelopeMessageMixin`. Anything that
sets neither falls back to a generic sentence for its method and status.
"""

from rest_framework.renderers import JSONRenderer

ENVELOPE_KEYS = ('success', 'message', 'data')

# (method, status) -> sentence. Only consulted when a view names no message.
_DEFAULT_MESSAGES = {
    ('GET', 200): 'Retrieved successfully.',
    ('POST', 200): 'Request completed successfully.',
    ('POST', 201): 'Created successfully.',
    ('PUT', 200): 'Updated successfully.',
    ('PATCH', 200): 'Updated successfully.',
    ('DELETE', 200): 'Deleted successfully.',
}
_FALLBACK_MESSAGE = 'Request completed successfully.'


def _is_enveloped(data):
    """True if something already produced an envelope — don't wrap it twice."""
    return isinstance(data, dict) and 'success' in data


class EnvelopeJSONRenderer(JSONRenderer):
    """Wraps every successful body in the standard envelope."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        renderer_context = renderer_context or {}
        response = renderer_context.get('response')

        if self._should_wrap(data, response):
            data = {
                'success': True,
                'message': self._message(response, renderer_context),
                # A body-less success (there are none left, but be defensive) still
                # has to satisfy the contract's `data` key.
                'data': {} if data is None else data,
            }
            # Keep response.data in step with what actually goes on the wire.
            # Without this, `.data` would still hold the bare payload while the
            # client receives the envelope — two different answers to "what did this
            # endpoint return", and every test would assert the one nobody gets.
            # Re-rendering is safe: _is_enveloped() makes the second pass a no-op.
            response.data = data

        return super().render(data, accepted_media_type, renderer_context)

    def _should_wrap(self, data, response):
        if response is None:
            return False
        # 4xx/5xx already went through the exception handler.
        if response.status_code >= 400:
            return False
        return not _is_enveloped(data)

    def _message(self, response, renderer_context):
        message = getattr(response, 'success_message', None)
        if message:
            return message

        request = renderer_context.get('request')
        method = getattr(request, 'method', None)
        return _DEFAULT_MESSAGES.get((method, response.status_code), _FALLBACK_MESSAGE)


class EnvelopeMessageMixin:
    """Lets a viewset name a message per action.

        class RoleViewSet(EnvelopeMessageMixin, ModelViewSet):
            success_messages = {'list': 'Roles retrieved successfully.'}

    Applied in `finalize_response` because that is the one hook that sees every
    Response a generic viewset builds, whichever mixin produced it.
    """

    success_messages = {}

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)

        if not getattr(response, 'success_message', None):
            message = self.success_messages.get(getattr(self, 'action', None))
            if message:
                response.success_message = message

        return response
