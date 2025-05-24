import psycopg2

# Database connection details
DB_HOST = "34.58.246.248"  # Replace with your PostgreSQL IP address
DB_NAME = "client_table"        # Replace with your database name
DB_USER = "postgres"        # Replace with your database user
DB_PASSWORD = "Chigdabeast123$"  # Replace with your PostgreSQL password

def connect_to_db():
    """Connect to the PostgreSQL database."""
    try:
        # Connect to the PostgreSQL database
        connection = psycopg2.connect(
            host=DB_HOST,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        print("Connection to PostgreSQL successful!")
        return connection
    except Exception as e:
        print(f"Error connecting to PostgreSQL: {e}")
        return None

def insert_data(connection, name, age):
    """Insert data into the test_table."""
    try:
        cursor = connection.cursor()
        insert_query = "INSERT INTO test_table (name, age) VALUES (%s, %s)"
        cursor.execute(insert_query, (name, age))
        connection.commit()
        print("Data inserted successfully!")
    except Exception as e:
        print(f"Error inserting data: {e}")
    finally:
        cursor.close()

def query_data(connection):
    """Query data from the test_table."""
    try:
        cursor = connection.cursor()
        select_query = "SELECT * FROM test_table"
        cursor.execute(select_query)
        rows = cursor.fetchall()
        print("Data retrieved successfully:")
        for row in rows:
            print(row)
    except Exception as e:
        print(f"Error querying data: {e}")
    finally:
        cursor.close()

def main():
    """Main function to connect to the database, insert data, and query data."""
    connection = connect_to_db()
    if connection:
        # Insert example data
        insert_data(connection, "Alice", 30)
        insert_data(connection, "Bob", 25)

        # Query and print the data
        query_data(connection)

        # Close the connection
        connection.close()

if __name__ == "__main__":
    main()
