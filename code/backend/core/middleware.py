import logging

from django.utils.deprecation import MiddlewareMixin

from .exceptions import ApiError
from .responses import error_response

#当后端接口发生异常时，统一把异常转换成固定格式的 JSON 响应，避免每个接口都重复写异常处理代码。
# 统一异常处理
# 统一前后端错误响应格式
# 区分业务异常和系统异常
# 记录服务器内部错误日志
# 防止敏感异常信息直接泄露给前端
# 减少每个接口中的重复代码
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
