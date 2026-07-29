from .responses import error_response
#CSRF证明请求来自可信页面

def csrf_failure(request, reason=""):
    return error_response(
        code="CSRF_FAILED",
        message="CSRF 校验失败",
        status=403,
    )
