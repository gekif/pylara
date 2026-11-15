"""HTTP and validation exceptions."""


class HttpException(Exception):
    def __init__(self, status_code: int, message: str = ""):
        self.status_code = status_code
        self.message = message or _default_message(status_code)
        super().__init__(self.message)


class ValidationException(Exception):
    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__("The given data was invalid.")


class NotFoundException(HttpException):
    def __init__(self, message: str = "Not Found"):
        super().__init__(404, message)


class UnauthorizedException(HttpException):
    def __init__(self, message: str = "Unauthorized"):
        super().__init__(401, message)


class ForbiddenException(HttpException):
    def __init__(self, message: str = "Forbidden"):
        super().__init__(403, message)


def _default_message(code: int) -> str:
    messages = {
        400: "Bad Request", 401: "Unauthorized", 403: "Forbidden",
        404: "Not Found", 405: "Method Not Allowed", 422: "Unprocessable Entity",
        500: "Internal Server Error",
    }
    return messages.get(code, "Error")
