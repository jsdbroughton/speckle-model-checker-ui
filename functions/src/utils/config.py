# src/utils/config.py
import os


class Config:
    """Application configuration from environment variables."""

    def __init__(self):
        # Firebase configuration
        self.FIREBASE_PROJECT_ID = os.environ.get("GCLOUD_PROJECT")

        # Speckle configuration
        self.SPECKLE_APP_ID = os.environ.get("SPECKLE_APP_ID")
        self.SPECKLE_APP_SECRET = os.environ.get("SPECKLE_APP_SECRET")
        self.SPECKLE_CHALLENGE_ID = os.environ.get("SPECKLE_CHALLENGE_ID")
        self.SPECKLE_SERVER_URL = os.environ.get(
            "SPECKLE_SERVER_URL", "https://app.speckle.systems"
        )

        # Application environment
        self.IS_EMULATOR = os.environ.get("FUNCTIONS_EMULATOR") == "true"

    @property
    def BASE_URL(self):
        """Get the base URL for the application."""
        if self.IS_EMULATOR:
            return "http://127.0.0.1:5000"  # Firebase Hosting Emulator default
        else:
            return f"https://{self.FIREBASE_PROJECT_ID}.web.app"

    @property
    def AUTH_CALLBACK_URL(self):
        """Get the full URL for authentication callbacks."""
        return f"{self.BASE_URL}/auth-callback.html"

    def get_speckle_auth_url(self, challenge_id):
        """Build the Speckle authentication URL."""
        return f"{self.SPECKLE_SERVER_URL}/authn/verify/{self.SPECKLE_APP_ID}/{challenge_id}"

    def validate(self):
        """Validate the configuration."""
        missing = []
        if not self.SPECKLE_APP_ID:
            missing.append("SPECKLE_APP_ID")
        if not self.SPECKLE_APP_SECRET:
            missing.append("SPECKLE_APP_SECRET")
        if not self.SPECKLE_CHALLENGE_ID:
            missing.append("SPECKLE_CHALLENGE_ID")

        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}"
            )

        return True
