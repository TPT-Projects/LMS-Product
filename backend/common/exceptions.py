from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Return every API error in one shape.

        { "detail": "Human readable message", "code": "...", "errors": {field: [messages]} }

    `errors` is present only for validation errors.
    """
    response = exception_handler(exc, context)
    if response is None:
        return None

    data = response.data
    if isinstance(data, dict) and "detail" in data:
        body = {"detail": str(data["detail"]), "code": getattr(data["detail"], "code", None)}
    elif isinstance(data, dict):
        non_field = data.get("non_field_errors")
        body = {
            "detail": str(non_field[0]) if non_field else "Please check the highlighted fields.",
            "code": "validation_error",
            "errors": data,
        }
    else:
        body = {"detail": str(data[0]) if data else "Request failed.", "code": "error"}

    response.data = body
    return response
