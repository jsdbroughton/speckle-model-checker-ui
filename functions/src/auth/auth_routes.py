# src/auth/auth_routes.py
import json
import secrets
import string

import requests
from firebase_admin import auth
from google.cloud import firestore

from ..utils.auth_utils import (
    create_or_update_firebase_user,
    store_speckle_tokens,
)
from ..utils.config import Config
from ..utils.response_utils import error_response, success_response, redirect_response

# Initialize Firestore client and config
db = firestore.Client()
config = Config()


def init_speckle_auth(request):
    """Initialize Speckle authentication and return a login URL."""
    try:
        config.validate()

        # Build authentication URL
        challenge_id = config.SPECKLE_CHALLENGE_ID
        auth_url = config.get_speckle_auth_url(challenge_id)

        return success_response(
            {
                "challengeId": challenge_id,
                "authUrl": auth_url,
                "appId": config.SPECKLE_APP_ID,
                "appSecret": config.SPECKLE_APP_SECRET,
            },
            format="json",
        )
    except ValueError as e:
        return error_response(str(e), status=500, format="json")
    except Exception as e:
        return error_response(
            f"Auth initialization error: {str(e)}", status=500, format="json"
        )


def exchange_token(request):
    """Exchange Speckle access code for a Firebase custom token."""
    try:
        # Get required parameters
        access_code = request.args.get("access_code")
        challenge_id = config.SPECKLE_CHALLENGE_ID

        if not access_code:
            return error_response("Missing access code", status=400, format="json")

        # Exchange access code for Speckle token
        token_exchange_url = f"{config.SPECKLE_SERVER_URL}/auth/token"
        token_payload = {
            "accessCode": access_code,
            "appId": config.SPECKLE_APP_ID,
            "appSecret": config.SPECKLE_APP_SECRET,
            "challenge": challenge_id,
        }

        token_response = requests.post(token_exchange_url, json=token_payload)

        if token_response.status_code != 200:
            error_details = json.loads(token_response.text).get("err", "")
            return error_response(
                f"Failed to exchange token: {token_response.reason} ({token_response.status_code}) {error_details}",
                status=token_response.status_code,
                format="json",
            )

        token_data = token_response.json()
        speckle_token = token_data["token"]
        refresh_token = token_data["refreshToken"]

        # Get user profile from Speckle
        user_profile = get_user_profile(speckle_token)

        # Generate password for new users
        password = generate_secure_password()

        # Create or update Firebase user
        firebase_user = create_or_update_firebase_user(user_profile, password)

        # Store Speckle tokens in Firestore
        store_speckle_tokens(
            firebase_user.uid, user_profile["id"], speckle_token, refresh_token
        )

        # Create Firebase custom token
        custom_token = auth.create_custom_token(
            firebase_user.uid, {"speckleId": user_profile["id"]}
        )

        # Ensure it's a proper string (not bytes)
        custom_token_str = (
            custom_token.decode() if isinstance(custom_token, bytes) else custom_token
        )

        # Redirect URL for authentication callback
        redirect_url = f"{config.BASE_URL}?authenticated=True&ft={custom_token_str}&sst={speckle_token}&ssrt={refresh_token}&suid={user_profile['id']}"

        return redirect_response(redirect_url)

    except Exception as e:
        print(f"Token exchange error: {str(e)}")
        return error_response(str(e), status=500, format="json")


def get_user(request):
    """Get the current user's profile from the Speckle Server and create Firebase user."""
    try:
        # token and refresh token are in the body of the POST request
        token = request.json.get("token")
        refresh_token = request.json.get("refreshToken")

        # Handle missing tokens
        if not token or not refresh_token:
            return error_response(
                "Missing token or refresh token", status=400, format="json"
            )

        # Get user profile from Speckle
        user_profile = get_user_profile(token)

        # Generate random password for new users
        password = generate_secure_password()

        # Create or update user in Firebase
        firebase_user = create_or_update_firebase_user(user_profile, password)

        # Store Speckle tokens in Firestore
        store_speckle_tokens(
            firebase_user.uid, user_profile["id"], token, refresh_token
        )

        # Create Firebase custom token
        custom_token = auth.create_custom_token(
            firebase_user.uid, {"speckleId": user_profile["id"]}
        )

        # Ensure it's a proper string (not bytes)
        custom_token_str = (
            custom_token.decode() if isinstance(custom_token, bytes) else custom_token
        )

        # Return user info and custom token
        return success_response(
            {"user": user_profile, "customToken": custom_token_str}, format="json"
        )

    except ValueError as e:
        # Handle expected errors with appropriate status codes
        return error_response(str(e), status=400, format="json")
    except Exception as e:
        # Handle unexpected errors
        return error_response(str(e), status=500, format="json")


# Helper functions
def get_user_profile(token):
    """Get user profile from Speckle GraphQL API."""
    query = """
      query User{
        activeUser {
          id
          name
          email
          avatar
        }
      }
    """

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }

    response = requests.post(
        f"{config.SPECKLE_SERVER_URL}/graphql", headers=headers, json={"query": query}
    )

    if response.status_code != 200:
        raise ValueError(f"Failed to get user profile: HTTP {response.status_code}")

    data = response.json()
    user = data["data"]["activeUser"]

    return user


def generate_secure_password():
    """Generate a secure random password."""
    return "".join(
        secrets.choice(string.ascii_letters + string.digits) for _ in range(20)
    )
