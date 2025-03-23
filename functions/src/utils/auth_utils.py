# src/utils/auth_utils.py
from functools import wraps

from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from google.cloud import firestore

from ..utils.config import Config
from ..utils.response_utils import error_response

# Initialize Firestore client
db = firestore.Client()
config = Config()


def require_auth(format="html"):
    """Decorator to require authentication for API endpoints.

    Args:
        format (str): Response format ("html" or "json")

    Returns:
        Function decorator that handles authentication
    """

    def decorator(func):
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Check for Authorization header
            auth_header = request.headers.get("Authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return error_response("Unauthorized", status=401, format=format)

            # Verify token
            id_token = auth_header.split("Bearer ")[1]
            try:
                decoded_token = safe_verify_id_token(id_token)
                request.user_id = decoded_token["uid"]
                request.user_email = decoded_token.get("email")
                return func(request, *args, **kwargs)
            except Exception as e:
                return error_response(
                    f"Authentication error: {str(e)}", status=401, format=format
                )

        return wrapper

    return decorator


def require_project_access(format="html"):
    """Decorator to verify user has access to a project."""

    def decorator(func):
        @require_auth(format=format)
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Extract project_id from path or query parameters
            project_id = None
            if "/projects/" in request.path:
                project_id = request.path.split("/projects/")[1].split("/")[0]
            else:
                project_id = request.args.get("projectId")

            if not project_id:
                return error_response("Missing project ID", status=400, format=format)

            # Get speckle token
            speckle_token = get_speckle_token_for_user(request.user_id)
            if not speckle_token:
                return error_response(
                    "Unable to access your Speckle token. Please sign out and sign in again.",
                    status=401,
                    format=format,
                )

            # Add token to request object for downstream use
            request.speckle_token = speckle_token
            request.project_id = project_id

            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_ruleset_ownership(format="html"):
    """Decorator to verify user owns a ruleset."""

    def decorator(func):
        @require_auth(format=format)
        @wraps(func)
        def wrapper(request, *args, **kwargs):
            # Extract ruleset_id from path or query parameters
            ruleset_id = None
            if "/rulesets/" in request.path:
                ruleset_id = request.path.split("/rulesets/")[1].split("/")[0]
            else:
                ruleset_id = request.args.get("ruleset_id")

            if not ruleset_id:
                return error_response("Missing ruleset ID", status=400, format=format)

            # Get the ruleset
            from ..utils.firestore_utils import get_ruleset

            ruleset = get_ruleset(ruleset_id)

            if not ruleset:
                return error_response("Ruleset not found", status=404, format=format)

            # Verify ownership
            if ruleset.get("userId") != request.user_id:
                return error_response(
                    "You don't have permission to access this ruleset",
                    status=403,
                    format=format,
                )

            # Add ruleset to request object for downstream use
            request.ruleset = ruleset
            request.ruleset_id = ruleset_id

            return func(request, *args, **kwargs)

        return wrapper

    return decorator


def safe_verify_id_token(id_token):
    """Safely verify Firebase ID token with retry for clock skew issues."""
    try:
        return auth.verify_id_token(id_token)
    except Exception as e:
        if "Token used too early" in str(e):
            # Wait 1 second and retry for clock skew issues
            import time

            time.sleep(1)
            return auth.verify_id_token(id_token)
        else:
            raise e


def get_speckle_token_for_user(user_id):
    """Get the Speckle token for a user from Firestore."""
    try:
        user_token_doc = db.collection("userTokens").document(user_id).get()
        if user_token_doc.exists:
            return user_token_doc.to_dict().get("speckleToken")
        return None
    except Exception:
        return None


def create_or_update_firebase_user(user, password):
    """Create or update a Firebase user from Speckle user data."""
    try:
        # Try to get existing user
        firebase_user = auth.get_user_by_email(user["email"])

        # User exists, check if we need to update properties
        try:
            if (
                firebase_user.display_name != user["name"]
                or firebase_user.photo_url != user["avatar"]
            ):
                # Update with photo URL if available
                auth.update_user(
                    firebase_user.uid,
                    display_name=user["name"],
                    photo_url=user["avatar"],
                )
        except (ValueError, FirebaseError) as e:
            # If updating with avatar fails, try without it
            print(f"Failed to update user with avatar, trying without: {str(e)}")
            auth.update_user(
                firebase_user.uid,
                display_name=user["name"],
            )
    except auth.UserNotFoundError:
        # Create new user
        try:
            # First try creating with avatar
            firebase_user = auth.create_user(
                email=user["email"],
                display_name=user["name"],
                photo_url=user["avatar"],
                password=password,
            )
        except (ValueError, FirebaseError) as e:
            # If creation with avatar fails, try without it
            print(f"Failed to create user with avatar, trying without: {str(e)}")
            firebase_user = auth.create_user(
                email=user["email"],
                display_name=user["name"],
                password=password,
            )

    return firebase_user


def store_speckle_tokens(user_id, speckle_id, token, refresh_token):
    """Store Speckle tokens in Firestore."""
    db.collection("userTokens").document(user_id).set(
        {
            "speckleId": speckle_id,
            "speckleToken": token,
            "speckleRefreshToken": refresh_token,
            "updatedAt": firestore.SERVER_TIMESTAMP,
        }
    )
