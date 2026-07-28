import json

from django.test import RequestFactory

from core.exceptions import ApiError
from core.middleware import ApiExceptionMiddleware
from core.responses import error_response, success_response
from core.views import csrf_failure


def response_body(response):
    return json.loads(response.content)


def test_success_response_uses_the_confirmed_envelope():
    response = success_response(
        data={"status": "ready"},
        message="基础检查通过",
    )

    assert response.status_code == 200
    assert response_body(response) == {
        "code": "SUCCESS",
        "message": "基础检查通过",
        "data": {"status": "ready"},
    }


def test_error_response_uses_null_data():
    response = error_response(
        code="INVALID_REQUEST",
        message="请求无效",
        status=400,
    )

    assert response.status_code == 400
    assert response_body(response) == {
        "code": "INVALID_REQUEST",
        "message": "请求无效",
        "data": None,
    }


def test_api_error_is_converted_to_the_confirmed_envelope():
    middleware = ApiExceptionMiddleware(lambda request: None)
    request = RequestFactory().get("/api/example")
    exception = ApiError(
        code="FORBIDDEN",
        message="无权访问",
        status=403,
    )

    response = middleware.process_exception(request, exception)

    assert response.status_code == 403
    assert response_body(response) == {
        "code": "FORBIDDEN",
        "message": "无权访问",
        "data": None,
    }


def test_unexpected_exception_is_converted_to_internal_error():
    middleware = ApiExceptionMiddleware(lambda request: None)
    request = RequestFactory().get("/api/example")

    response = middleware.process_exception(
        request,
        RuntimeError("sensitive internal detail"),
    )

    assert response.status_code == 500
    assert response_body(response) == {
        "code": "INTERNAL_ERROR",
        "message": "服务器内部错误",
        "data": None,
    }
    assert b"sensitive internal detail" not in response.content


def test_csrf_failure_uses_the_confirmed_error_code():
    request = RequestFactory().post("/api/example")

    response = csrf_failure(request, reason="test")

    assert response.status_code == 403
    assert response_body(response) == {
        "code": "CSRF_FAILED",
        "message": "CSRF 校验失败",
        "data": None,
    }
