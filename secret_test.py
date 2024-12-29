import os
from google.cloud import secretmanager

def fetch_telegram_token():
    """
    Fetches the Telegram bot TOKEN from Google Cloud Secret Manager.
    :return: The secret value as a string.
    """
    try:
        # Initialize Secret Manager client
        client = secretmanager.SecretManagerServiceClient()
        
        # Fetch the secret name from environment variables
        secret_name = os.getenv("TELEGRAM_BOT_SECRET_NAME")
        if not secret_name:
            raise ValueError("Environment variable TELEGRAM_BOT_SECRET_NAME is not set.")

        # Construct the full secret version path
        secret_path = f"{secret_name}/versions/latest"

        # Access the secret
        response = client.access_secret_version(request={"name": secret_path})
        token = response.payload.data.decode("UTF-8")
        return token
    except Exception as e:
        print(f"Error fetching the Telegram bot TOKEN: {e}")
        return None

if __name__ == "__main__":
    # Fetch and print the Telegram bot TOKEN
    token = fetch_telegram_token()
    if token:
        print(f"Telegram Bot TOKEN: {token}")
    else:
        print("Failed to retrieve the Telegram Bot TOKEN.")
