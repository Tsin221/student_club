from django.http import JsonResponse


def success_response(data=None, message="操作成功", status=200):
    return JsonResponse(
        {
            "code": "SUCCESS",
            "message": message,
            "data": data,
        },
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )


def error_response(code, message, status):
    return JsonResponse(
        {
            "code": code,
            "message": message,
            "data": None,
        },
        status=status,
        json_dumps_params={"ensure_ascii": False},
    )
