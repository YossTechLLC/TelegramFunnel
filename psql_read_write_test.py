import psycopg2
import re

# Database connection details
DB_HOST = "1-17626c63-6acf-4d44-bc6b-cf70365b4ce2.us-central1.sql.goog"
DB_PORT = "5432"
DB_NAME = "telegram_funnel_db"  # Replace with your database name
DB_USER = "postgres"  # Replace with your username
DB_PASSWORD = "HerpDerp666ass$"  # Replace with your password
SSL_CERT = "/home/yosstechllc/telegram-bot1/TelegramFunnel/CERTS/client-cert.pem"
SSL_KEY = "/home/yosstechllc/telegram-bot1/TelegramFunnel/CERTS/client-key.pem"
SSL_ROOT_CERT = "/home/yosstechllc/telegram-bot1/TelegramFunnel/CERTS/server-ca.pem"
SSL_MODE = "verify-full"

# Validation functions
def validate_public_channel_chat_id(value):
    if len(value) <= 32 and re.match(r"^[@A-Za-z0-9_-]*$", value):
        return value
    raise ValueError("Invalid Public Channel Chat ID")

def validate_private_channel_chat_id(value):
    if len(value) <= 64 and re.match(r"^[-A-Za-z0-9_-]*$", value):
        return value
    raise ValueError("Invalid Private Channel Chat ID")

def validate_customer_chat_id(value):
    if isinstance(value, int) and 0 <= value < 10**16:
        return value
    raise ValueError("Invalid Customer Chat ID")

def validate_customer_subscription_time(value):
    if isinstance(value, str) and value.isdigit() and len(value) <= 3:
        return value
    raise ValueError("Invalid Customer Subscription Time")

def validate_wallet_address(value):
    if len(value) <= 128 and re.match(r"^[A-Za-z0-9]*$", value):
        return value
    raise ValueError("Invalid Wallet Address")

def validate_np_payment_id(value):
    if isinstance(value, int) and 0 <= value < 10**16:
        return value
    raise ValueError("Invalid NP Payment ID")

# Database operations
def connect_to_db():
    try:
        connection = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            sslmode=SSL_MODE,
            sslcert=SSL_CERT,
            sslkey=SSL_KEY,
            sslrootcert=SSL_ROOT_CERT,
        )
        return connection
    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}")
        raise

def insert_data(
    public_channel_chat_id, private_channel_chat_id, customer_chat_id,
    customer_subscription_time, client_wallet_address, host_wallet_address, np_payment_id
):
    connection = None
    try:
        # Validate inputs
        public_channel_chat_id = validate_public_channel_chat_id(public_channel_chat_id)
        private_channel_chat_id = validate_private_channel_chat_id(private_channel_chat_id)
        customer_chat_id = validate_customer_chat_id(customer_chat_id)
        customer_subscription_time = validate_customer_subscription_time(customer_subscription_time)
        client_wallet_address = validate_wallet_address(client_wallet_address)
        host_wallet_address = validate_wallet_address(host_wallet_address)
        np_payment_id = validate_np_payment_id(np_payment_id)

        # Insert data into the database
        connection = connect_to_db()
        cursor = connection.cursor()
        insert_query = """
            INSERT INTO telegram_payment_data (
                public_channel_chat_id, private_channel_chat_id, customer_chat_id,
                customer_subscription_time, client_wallet_address, host_wallet_address, np_payment_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """
        cursor.execute(
            insert_query,
            (
                public_channel_chat_id, private_channel_chat_id, customer_chat_id,
                customer_subscription_time, client_wallet_address, host_wallet_address, np_payment_id
            )
        )
        connection.commit()
        print("Data inserted successfully!")
    except ValueError as e:
        print(f"Validation error: {e}")
    except psycopg2.Error as e:
        print(f"Database error: {e}")
    finally:
        if connection:
            cursor.close()
            connection.close()

def read_data():
    connection = None
    try:
        connection = connect_to_db()
        cursor = connection.cursor()
        cursor.execute("SELECT * FROM telegram_payment_data;")
        rows = cursor.fetchall()
        print("Data from the database:")
        for row in rows:
            print(row)
    except psycopg2.Error as e:
        print(f"Database error: {e}")
    finally:
        if connection:
            cursor.close()
            connection.close()

# Example usage
if __name__ == "__main__":
    # Example: Insert data
    insert_data(
        public_channel_chat_id="@PublicChannelName",
        private_channel_chat_id="-1001234567890",
        customer_chat_id=1234567890123456,
        customer_subscription_time="31",
        client_wallet_address="Addr1q9d6v75mrxhk4ht32cfw3qxz56mvfs9xdk6yuwzfrdxr0lmx5uqjd2ce9n",
        host_wallet_address="0x8db29c6e2026d2a84ae716a7f9d8b4da72950566",
        np_payment_id=5558576557
    )

    # Example: Read data
    read_data()
