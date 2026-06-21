import sqlite3
import datetime
from typing import List, Dict, Optional, Tuple

import os

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(project_root, "db", "crm.db")

def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_customer_id_by_email(email: str) -> Optional[int]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT customer_id FROM customers WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    return row["customer_id"] if row else None

def get_tickets_by_email(email: str) -> List[Dict]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.ticket_id, t.order_id, t.issue_description, t.status, t.created_at, t.ticket_type
        FROM support_tickets t
        JOIN customers c ON t.customer_id = c.customer_id
        WHERE c.email = ?
        ORDER BY t.created_at DESC
    ''', (email,))
    tickets = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return tickets

def get_orders_by_email(email: str) -> List[Dict]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT o.order_id, i.name as item_name, o.order_date, o.delivery_date, o.refund_status, i.return_policy 
        FROM orders o
        JOIN items i ON o.item_id = i.item_id
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE c.email = ?
        ORDER BY o.delivery_date DESC
    ''', (email,))
    orders = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return orders

def smart_lookup_order_id(email: str, search_term: str) -> Optional[str]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT o.order_id 
        FROM orders o
        JOIN items i ON o.item_id = i.item_id
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE c.email = ? AND (i.name LIKE ? OR CAST(o.order_id AS TEXT) LIKE ?)
        ORDER BY o.delivery_date DESC LIMIT 1
    ''', (email, f'%{search_term}%', f'%{search_term}%'))
    match = cursor.fetchone()
    conn.close()
    return str(match["order_id"]) if match else None

def get_order_eligibility_details(order_id: int, email: str) -> Optional[Tuple[str, str, str, str, str]]:
    conn = _get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT o.delivery_date, i.return_policy, o.refund_status, i.category, i.name as item_name
        FROM orders o
        JOIN items i ON o.item_id = i.item_id
        JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.order_id = ? AND c.email = ?
    ''', (order_id, email))
    order = cursor.fetchone()
    conn.close()
    if order:
        return (order["delivery_date"], order["return_policy"], order["refund_status"], order["category"], order["item_name"])
    return None

def file_ticket_and_update_order(customer_id: int, order_id: int, issue_description: str, ticket_type: str) -> None:
    conn = _get_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    cursor.execute('''
        INSERT INTO support_tickets (customer_id, order_id, issue_description, status, created_at, ticket_type)
        VALUES (?, ?, ?, 'Open', ?, ?)
    ''', (customer_id, order_id, issue_description, now, ticket_type))
    
    cursor.execute("UPDATE orders SET refund_status = ? WHERE order_id = ?", (f"{ticket_type} Requested", order_id))
    conn.commit()
    conn.close()
