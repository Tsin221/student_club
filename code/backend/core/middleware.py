import logging

from django.utils.deprecation import MiddlewareMixin

from .exceptions import ApiError
from .responses import error_response


logger = logging.getLogger(__name__)


class ApiExceptionMiddleware(MiddlewareMixin):
    def process_exception(self, request, exception):
        if isinstance(exception, ApiError):
            return error_response(
                code=exception.code,
                message=exception.message,
                status=exception.status,
            )

        logger.error(
            "Unhandled API exception",
            exc_info=(
                type(exception),
                exception,
                exception.__traceback__,
            ),
        )
        return error_response(
            code="INTERNAL_ERROR",
            message="服务器内部错误",
            status=500,
        )
