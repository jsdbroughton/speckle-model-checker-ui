import json
import os
import secrets
import string

import requests
from firebase_admin import auth
from firebase_admin.exceptions import FirebaseError
from firebase_functions import https_fn
from google.cloud import firestore

# Verify challenge exists and hasn't been used
db = firestore.Client()


# Get Speckle configuration from environment
def get_speckle_config():
    """Get Speckle application configuration from Firebase config."""
    try:
        return {
            "app_id": os.environ.get("SPECKLE_APP_ID"),
            "app_secret": os.environ.get("SPECKLE_APP_SECRET"),
            "server_url": os.environ.get(
                "SPECKLE_SERVER_URL", "https://app.speckle.systems"
            ),
        }
    except Exception:
        return {
            "app_id": None,
            "app_secret": None,
            "server_url": "https://app.speckle.systems",
        }


def init_speckle_auth(request):
    """Initialize Speckle authentication and return a login URL."""

    try:
        app_id = os.environ.get("SPECKLE_APP_ID")
        server_url = os.environ.get("SPECKLE_SERVER_URL", "https://app.speckle.systems")
        challenge_id = os.environ.get("SPECKLE_CHALLENGE_ID")

        if not app_id:
            return https_fn.Response(
                json.dumps({"error": "Speckle App ID is not configured"}),
                mimetype="application/json",
                status=500,
            )

        # Build authentication URL
        host_url = (
            request.host_url
            if hasattr(request, "host_url")
            else request.headers.get("Host", "")
        )
        if not host_url.startswith("http"):
            protocol = "https" if not host_url.startswith("localhost") else "http"
            host_url = f"{protocol}://{host_url}/"

        auth_url = f"{server_url}/authn/verify/{app_id}/{challenge_id}"

        return https_fn.Response(
            json.dumps(
                {
                    "challengeId": challenge_id,
                    "authUrl": auth_url,
                    "appId": app_id,
                    "appSecret": os.environ.get("SPECKLE_APP_SECRET"),
                }
            ),
            mimetype="application/json",
        )
    except Exception as e:
        print(f"Auth initialization error: {str(e)}")
        return https_fn.Response(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status=500,
        )


def get_user(request):
    """Get the current user's profile from the Speckle Server."""
    try:
        server_url = os.environ.get("SPECKLE_SERVER_URL", "https://app.speckle.systems")

        # token and refresh token are in the body of the POST request
        token = request.json.get("token")
        refresh_token = request.json.get("refreshToken")

        # Handle missing tokens by raising an exception
        if not token or not refresh_token:
            raise ValueError("Missing token or refresh token")

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
            f"{server_url}/graphql", headers=headers, json={"query": query}
        )

        if response.status_code != 200:
            raise ValueError(f"Failed to get user profile: HTTP {response.status_code}")

        data = response.json()
        user = data["data"]["activeUser"]

        # Generate random password for new users
        password = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(20)
        )

        # Create or update user in Firebase
        firebase_user = create_or_update_firebase_user(user, password)

        # Store Speckle tokens in Firestore
        db.collection("userTokens").document(firebase_user.uid).set(
            {
                "speckleId": user["id"],
                "speckleToken": token,
                "speckleRefreshToken": refresh_token,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        )

        # Create Firebase custom token
        custom_token = auth.create_custom_token(
            firebase_user.uid, {"speckleId": user["id"]}
        )

        # Ensure it's a proper string (not bytes)
        custom_token_str = (
            custom_token.decode() if isinstance(custom_token, bytes) else custom_token
        )

        # Single successful return path
        return https_fn.Response(
            json.dumps({"user": user, "customToken": custom_token_str}),
            mimetype="application/json",
        )
    except ValueError as e:
        # Handle expected errors with appropriate status codes
        print(f"Validation error in get_user: {str(e)}")
        return https_fn.Response(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status=400,
        )
    except Exception as e:
        # Handle unexpected errors
        print(f"Error getting user profile: {str(e)}")
        return https_fn.Response(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status=500,
        )


def create_or_update_firebase_user(user, password):
    """Handle creation or update of Firebase user with proper error handling."""
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


def exchange_token(request):
    """Exchange Speckle access code for a Firebase custom token."""
    try:
        # Retrieve the challenge ID from the cookie
        challenge_id = os.environ.get("SPECKLE_CHALLENGE_ID")

        if not request.args:
            return https_fn.Response(
                json.dumps({"error": "No request data provided"}),
                mimetype="application/json",
                status=400,
            )

        # Retrieve accessCode request_args
        access_code = request.args.get("access_code")

        authenticated = False

        if not access_code or not challenge_id:
            return https_fn.Response(
                json.dumps({"error": "Missing access code or challenge ID"}),
                mimetype="application/json",
                status=400,
            )

        # Exchange access code for Speckle token
        app_id = os.environ.get("SPECKLE_APP_ID")
        app_secret = os.environ.get("SPECKLE_APP_SECRET")
        server_url = os.environ.get("SPECKLE_SERVER_URL", "https://app.speckle.systems")

        token_exchange_url = f"{server_url}/auth/token"
        token_payload = {
            "accessCode": access_code,
            "appId": app_id,
            "appSecret": app_secret,
            "challenge": challenge_id,
        }

        token_response = requests.post(token_exchange_url, json=token_payload)

        if token_response.status_code != 200:
            return https_fn.Response(
                json.dumps(
                    {
                        "error": f"Failed to exchange token: {token_response.reason} ({token_response.status_code}) {json.loads(token_response.text)['err']}",
                        "access_code": access_code,
                        "challenge_id": challenge_id,
                        "app_id": app_id,
                        "app_secret": app_secret,
                        "response": token_response.status_code,
                    }
                ),
                mimetype="application/json",
                status=token_response.status_code,
            )
        else:
            authenticated = True

        token_data = token_response.json()

        print(f"Token data: {token_data}")

        # Get user profile from Speckle
        speckle_token = token_data["token"]
        refresh_token = token_data["refreshToken"]
        user_profile_url = f"{server_url}/graphql"

        profile_query = """
        query {
          activeUser {
            id
            name
            email
            avatar
          }
        }
        """

        profile_headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {speckle_token}",
        }

        profile_response = requests.post(
            user_profile_url,
            headers=profile_headers,
            json={"query": profile_query},
        )

        if profile_response.status_code != 200:
            return https_fn.Response(
                json.dumps({"error": "Failed to get user profile"}),
                mimetype="application/json",
                status=profile_response.status_code,
            )

        profile_data = profile_response.json()
        user_data = profile_data["data"]["activeUser"]

        password = "".join(
            secrets.choice(string.ascii_letters + string.digits) for _ in range(20)
        )

        # Create or update Firebase user
        try:
            firebase_user = auth.get_user_by_email(user_data["email"])

            # User exists, update properties if needed
            if (
                firebase_user.display_name != user_data["name"]
                or firebase_user.photo_url != user_data["avatar"]
            ):
                auth.update_user(
                    firebase_user.uid,
                    display_name=user_data["name"],
                    photo_url=user_data["avatar"],
                )

        except auth.UserNotFoundError:
            # Create new user
            firebase_user = auth.create_user(
                email=user_data["email"],
                display_name=user_data["name"],
                photo_url=user_data["avatar"],
                password=password,  # Add a random password
            )

        # Store Speckle tokens in Firestore
        db.collection("userTokens").document(firebase_user.uid).set(
            {
                "speckleId": user_data["id"],
                "speckleToken": token_data["token"],
                "speckleRefreshToken": token_data["refreshToken"],
                "updatedAt": firestore.SERVER_TIMESTAMP,
            }
        )

        # Create Firebase custom token
        ## add a user claim to link the firebase id with the speckle id and token
        custom_token = auth.create_custom_token(
            firebase_user.uid, {"speckleId": user_data["id"]}
        )

        # Ensure it's a proper string (not bytes)
        custom_token_str = custom_token.decode()

        # Check if running locally in Firebase Emulator
        IS_FIREBASE_EMULATOR = os.environ.get("FUNCTIONS_EMULATOR") == "true"

        if IS_FIREBASE_EMULATOR:
            FIREBASE_HOSTING_URL = "http://127.0.0.1:5000"  # Firebase Hosting Emulator

        else:
            FIREBASE_HOSTING_URL = f"https://{os.environ.get('GCLOUD_PROJECT')}.web.app"

        # Redirect URL for authentication callback
        redirect_url = f"{FIREBASE_HOSTING_URL}?authenticated={authenticated}&ft={custom_token_str}&sst={speckle_token}&ssrt={refresh_token}&suid={user_data['id']}"

        return https_fn.Response(
            status=302,
            headers={"Location": redirect_url},
        )
    except Exception as e:
        print(f"Token exchange error: {str(e)}")
        return https_fn.Response(
            json.dumps({"error": str(e)}),
            mimetype="application/json",
            status=500,
        )


"""
This Cloud Function uses Firebase Admin SDK with secure credentials loaded 
from Google Secret Manager at runtime.

Why this setup:
- The Firebase Admin SDK requires a private key to sign custom tokens.
- In local dev, we load from a service account JSON file.
- In production, Cloud Functions environments don't allow secure file bundling, 
  and relying on ADC often triggers IAM signBlob calls with permission issues.
- To avoid this, we store the service account JSON in Secret Manager.

Setup steps for future deployments:
1. Create the secret:
   gcloud secrets create firebase-service-account-key \
     --data-file=service-account-file.json

2. Grant secret access to the Cloud Function's service account:
   gcloud secrets add-iam-policy-binding firebase-service-account-key \
     --member="serviceAccount:554830443409-compute@developer.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"

3. Ensure google-cloud-secret-manager is in requirements.txt:
   pip install google-cloud-secret-manager
   pip freeze > requirements.txt

4. In code, load the credentials from Secret Manager (see load_firebase_cred_from_secret function).

5. Redeploy:
   gcloud functions deploy <function_name> \
     --region=us-central1 \
     --runtime=python311 \
     --trigger-http \
     --allow-unauthenticated \
     --set-env-vars=SPECKLE_APP_ID=...,SPECKLE_APP_SECRET=...,SPECKLE_CHALLENGE_ID=...,SPECKLE_SERVER_URL=...

Result:
- Secure, permission-clean, local and production token creation works without additional IAM complexity.
"""
