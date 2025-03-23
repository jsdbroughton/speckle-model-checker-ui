# main.py
import json
import logging

import firebase_admin
from firebase_admin import credentials
from firebase_functions import options
from google.api_core.exceptions import GoogleAPICallError
from google.cloud import secretmanager

from src.utils.route_handlers import create_application_router

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_firebase_cred_with_fallback():
    """Load Firebase credentials from Secret Manager or fall back to ADC."""
    try:
        client = secretmanager.SecretManagerServiceClient()
        secret_name = "projects/speckle-model-checker/secrets/firebase-service-account-key/versions/latest"
        response = client.access_secret_version(name=secret_name)
        secret_payload = response.payload.data.decode("UTF-8")
        cred_info = json.loads(secret_payload)
        logger.info("Loaded Firebase credentials from Secret Manager.")
        return credentials.Certificate(cred_info)
    except GoogleAPICallError as e:
        logger.warning(
            f"Could not load secret (probably emulator or no permission): {e}"
        )
        logger.info("Falling back to ADC / default credentials.")
        return None  # Will trigger default ADC fallback


# Initialize Firebase (only if not already initialized)
if not firebase_admin._apps:
    cred = load_firebase_cred_with_fallback()
    if cred:
        firebase_admin.initialize_app(cred)
    else:
        firebase_admin.initialize_app()  # Use ADC or environment creds

# Define CORS options
cors_config = options.CorsOptions(
    cors_origins=[r".*"],  # Allow all origins
    cors_methods=["get", "post", "put", "delete", "patch"],
    # cors_headers=["Authorization", "Content-Type"],
)

# Create the application router
router = create_application_router(cors_config)

# Generate Firebase Functions
functions = router.generate_functions()

# Export all generated functions to make them available to Firebase
globals().update(functions)

# Log the registered functions
function_names = list(functions.keys())
logger.info(
    f"Registered {len(function_names)} Firebase Functions: {', '.join(function_names)}"
)
