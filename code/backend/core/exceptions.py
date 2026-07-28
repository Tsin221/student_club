class ApiError(Exception):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
