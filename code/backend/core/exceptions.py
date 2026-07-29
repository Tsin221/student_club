#定义一个自定义的接口异常类型，主要用于在业务代码里统一表示“发生了一个可预期的业务错误”。
class ApiError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        # 业务错误代码
        self.code = code
        #错误提示
        self.message = message
        #http状态码
        self.status = status
