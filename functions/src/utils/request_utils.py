# src/utils/request_utils.py
import re
from urllib.parse import parse_qs


def extract_path_param(path, prefix, suffix=None):
    """Extract a parameter from a URL path.

    Args:
        path (str): The request path
        prefix (str): Path prefix before the parameter
        suffix (str, optional): Path suffix after the parameter

    Returns:
        str: Extracted parameter or None if not found

    Example:
        extract_path_param("/api/rulesets/123/rules", "/rulesets/", "/rules")
        returns "123"
    """
    if prefix not in path:
        return None

    param_with_suffix = path.split(prefix, 1)[1]

    if suffix and suffix in param_with_suffix:
        return param_with_suffix.split(suffix, 1)[0]

    # If no suffix, get the first path segment
    return param_with_suffix.split("/")[0]


def parse_form_data(request):
    """Parse form data from request.

    Handles both application/x-www-form-urlencoded and multipart/form-data.

    Args:
        request: HTTP request object

    Returns:
        dict: Parsed form data
    """
    # If request already has form attribute, use it
    if hasattr(request, "form") and request.form:
        return request.form.to_dict()

    # Check content type
    content_type = request.headers.get("Content-Type", "")

    if "application/x-www-form-urlencoded" in content_type:
        # Parse URL-encoded form data
        form_data = parse_qs(request.data.decode("utf-8"))
        return {k: v[0] if len(v) == 1 else v for k, v in form_data.items()}

    elif "multipart/form-data" in content_type:
        # This is more complex to parse manually
        # Typically Firebase Functions would handle this automatically
        # But we'll provide a fallback implementation
        boundary = content_type.split("boundary=")[1].strip()
        data = request.data.decode("utf-8")
        parts = data.split(f"--{boundary}")

        result = {}
        for part in parts:
            if not part.strip() or part.strip() == "--":
                continue

            # Extract headers and content
            headers, content = part.split("\r\n\r\n", 1)
            name_match = re.search(r'name="([^"]+)"', headers)

            if name_match:
                field_name = name_match.group(1)
                field_value = content.rsplit("\r\n", 1)[0]
                result[field_name] = field_value

        return result

    # Fallback to empty dict
    return {}


def get_location_origin(request):
    """Get the location origin from request headers.

    Args:
        request: HTTP request object

    Returns:
        str: Location origin URL
    """
    host_url = request.headers.get("Host", "")

    # Check if running in emulator mode with localhost
    if ("localhost" in host_url or "127.0.0.1" in host_url) and ":" in host_url:
        # Extract host without port
        base_host = host_url.split(":")[0]
        # Force the port to be 5000 (hosting emulator) instead of 5001 (functions emulator)
        host_url = f"{base_host}:5000"

    # Complete the URL with protocol if needed
    if not host_url.startswith("http"):
        protocol = (
            "https"
            if not ("localhost" in host_url or "127.0.0.1" in host_url)
            else "http"
        )
        location_origin = f"{protocol}://{host_url}"
    else:
        location_origin = host_url

    return location_origin
