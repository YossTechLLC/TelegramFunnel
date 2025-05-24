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
        messagebox.showerror("Database Error", str(e))
        return [], []

def build_gui():
    colnames, rows = fetch_data()

    root = tk.Tk()
    root.title("Telegram Payment Config Viewer")
    root.geometry("1200x600")

    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True)

    tree = ttk.Treeview(frame, columns=colnames, show="headings")
    for col in colnames:
        tree.heading(col, text=col)
        tree.column(col, width=150, anchor="w")

    for row in rows:
        tree.insert("", "end", values=row)

    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    vsb.pack(side="right", fill="y")
    hsb.pack(side="bottom", fill="x")
    tree.pack(side="left", fill="both", expand=True)

    root.mainloop()

if __name__ == "__main__":
    build_gui()
