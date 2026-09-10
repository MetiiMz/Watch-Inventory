# -*- coding: utf-8 -*-
"""Standard DRF error rendering.

``ApiError`` (raised by the service layer) is rendered as
``{"error": "<message>", "ok": false}`` with its HTTP status code — the
same shape ``static/js/app.js`` reads on failures.  DRF's own validation
errors keep their default field-keyed shape.
"""
import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

log = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """Map :class:`inventory.api.services.ApiError` onto a DRF response."""
    from inventory.api.services import ApiError

    response = drf_exception_handler(exc, context)
    if response is None and isinstance(exc, ApiError):
        return Response({"ok": False, "error": exc.message},
                        status=exc.status_code)
    return response
