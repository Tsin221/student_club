from .responses import error_response


def csrf_failure(request, reason=""):
    return error_response(
        code="CSRF_FAILED",
        message="CSRF 校验失败",
        status=403,
    )
