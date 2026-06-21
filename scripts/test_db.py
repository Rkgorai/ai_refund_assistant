import sqlite3
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def check_db():
    db_path = os.path.join(project_root, "db", "crm.db")
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}!")
        return

    # Use row_factory to get dictionary-like access
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    tables = ['customers', 'items', 'orders', 'support_tickets']
    print(f"--- Checking SQLite Database: {db_path} ---\n")
    
    for table in tables:
        try:
            # Get count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"✅ Table '{table}' has {count} rows.")
            
            # Print the first row as a sample with column names
            if count > 0:
                cursor.execute(f"SELECT * FROM {table} LIMIT 1")
                sample = cursor.fetchone()
                print("   Sample row: {")
                for key in sample.keys():
                    print(f"      {key}: {repr(sample[key])}")
                print("   }")
        except sqlite3.OperationalError as e:
            print(f"❌ Error checking table '{table}': {e}\n")

    conn.close()

if __name__ == "__main__":
    check_db()
