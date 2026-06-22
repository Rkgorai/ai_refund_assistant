import sqlite3
import csv
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_csv_to_sqlite():
    db_path = os.path.join(project_root, "db", "crm.db")
    csv_dir = os.path.join(project_root, "db", "csv_data")
    
    # Create a connection to the SQLite database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Customers Table
    cursor.execute('DROP TABLE IF EXISTS customers')
    cursor.execute('''
    CREATE TABLE customers (
        customer_id INTEGER PRIMARY KEY,
        name TEXT,
        email TEXT,
        phone TEXT
    )''')
    with open(os.path.join(csv_dir, 'customers.csv'), 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader) # Skip header
        cleaned_rows = [[col.strip() if isinstance(col, str) else col for col in row] for row in reader]
        cursor.executemany('INSERT INTO customers VALUES (?, ?, ?, ?)', cleaned_rows)

    # 2. Items Table
    cursor.execute('DROP TABLE IF EXISTS items')
    cursor.execute('''
    CREATE TABLE items (
        item_id INTEGER PRIMARY KEY,
        name TEXT,
        description TEXT,
        category TEXT,
        base_price REAL,
        return_policy TEXT
    )''')
    with open(os.path.join(csv_dir, 'items.csv'), 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        cursor.executemany('INSERT INTO items VALUES (?, ?, ?, ?, ?, ?)', reader)

    # 3. Orders Table
    cursor.execute('DROP TABLE IF EXISTS orders')
    cursor.execute('''
    CREATE TABLE orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        item_id INTEGER,
        quantity INTEGER,
        order_date TEXT,
        delivery_date TEXT,
        total_amount REAL,
        payment_method TEXT,
        refund_status TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
        FOREIGN KEY (item_id) REFERENCES items (item_id)
    )''')
    with open(os.path.join(csv_dir, 'orders.csv'), 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        cursor.executemany('INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)', reader)

    # 4. Support Tickets Table
    cursor.execute('DROP TABLE IF EXISTS support_tickets')
    cursor.execute('''
    CREATE TABLE support_tickets (
        ticket_id INTEGER PRIMARY KEY,
        customer_id INTEGER,
        order_id INTEGER,
        issue_description TEXT,
        status TEXT,
        created_at TEXT,
        ticket_type TEXT,
        FOREIGN KEY (customer_id) REFERENCES customers (customer_id),
        FOREIGN KEY (order_id) REFERENCES orders (order_id)
    )''')
    with open(os.path.join(csv_dir, 'support_tickets.csv'), 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        cursor.executemany('INSERT INTO support_tickets VALUES (?, ?, ?, ?, ?, ?, ?)', reader)

    conn.commit()
    conn.close()
    print(f"Successfully loaded all CSV data into {db_path}")

if __name__ == "__main__":
    load_csv_to_sqlite()
