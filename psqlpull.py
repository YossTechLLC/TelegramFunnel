import psycopg2
import tkinter as tk
from tkinter import ttk, messagebox

# === PostgreSQL Connection Details ===
DB_HOST = '34.58.246.248'
DB_PORT = 5432
DB_NAME = 'client_table  '
DB_USER = 'postgres'
DB_PASSWORD = 'Chigdabeast123$'

def fetch_data():
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        cur = conn.cursor()
        cur.execute("SELECT * FROM telegram_payment_config ORDER BY id DESC;")
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        cur.close()
        conn.close()
        return colnames, rows
    except Exception as e:
        print("❌ Database Error:", e)
        return [], []

def display_in_terminal():
    colnames, rows = fetch_data()
    if not rows:
        print("No data found.")
        return

    # Print headers
    print("\n" + " | ".join(colnames))
    print("-" * 120)

    # Print each row
    for row in rows:
        print(" | ".join(str(cell) for cell in row))

if __name__ == "__main__":
    display_in_terminal()

