# src/utils/response_utils.py
import json
from firebase_functions import https_fn
from ..utils.jinja_env import render_template


def error_response(message, status=400, format="html"):
    """Return a standardized error response in the requested format.

    Args:
        message (str): Error message
        status (int): HTTP status code
        format (str): Response format ("html" or "json")

    Returns:
        https_fn.Response: Formatted error response
    """
    if format == "json":
        return https_fn.Response(
            json.dumps({"error": message}),
            mimetype="application/json",
            status=status,
        )
    else:
        return https_fn.Response(
            render_template("error.html", message=message),
            mimetype="text/html",
            status=status,
        )


def success_response(data=None, message=None, status=200, format="html", template=None):
    """Return a standardized success response in the requested format.

    Args:
        data (any): Response data (for JSON)
        message (str): Success message
        status (int): HTTP status code
        format (str): Response format ("html" or "json")
        template (str): Template name (for HTML)

    Returns:
        https_fn.Response: Formatted success response
    """
    if format == "json":
        response_data = {}
        if data is not None:
            response_data = data if isinstance(data, dict) else {"data": data}
        if message:
            response_data["message"] = message

        return https_fn.Response(
            json.dumps(response_data),
            mimetype="application/json",
            status=status,
        )
    else:
        if template:
            context = data or {}
            if message:
                context["message"] = message
            return https_fn.Response(
                render_template(template, **context),
                mimetype="text/html",
                status=status,
            )
        else:
            return https_fn.Response(
                message or "",
                mimetype="text/html",
                status=status,
            )


def redirect_response(url, status=302):
    """Create a redirect response.

    Args:
        url (str): Redirect URL
        status (int): HTTP status code (default: 302)

    Returns:
        https_fn.Response: Redirect response
    """
    return https_fn.Response(
        status=status,
        headers={"Location": url},
    )


def file_response(content, filename, mimetype="application/octet-stream"):
    """Create a file download response.

    Args:
        content (str): File content
        filename (str): Download filename
        mimetype (str): MIME type

    Returns:
        https_fn.Response: File download response
    """
    return https_fn.Response(
        content,
        mimetype=mimetype,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
