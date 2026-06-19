import sqlite3
import datetime
from langchain_core.tools import tool

# Handle absolute imports correctly depending on where the script is run from
import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.rag.vectorstore import FaissVectorStore

DB_PATH = "db/crm.db"

@tool
def search_return_policy(query: str) -> str:
    """
    Search the official return policy documents for specific rules about returns, refunds, or replacements.
    Always use this tool when a customer asks if they are allowed to return an item, or questions about the return window.
    """
    try:
        store = FaissVectorStore(persist_dir="db/vector_store")
        store.load()
        results = store.query(query, top_k=3)
        if not results:
            return "No relevant policy found."
        return "\n\n---\n\n".join([r["metadata"]["text"] for r in results if "metadata" in r])
    except Exception as e:
        return f"Error querying policy database: {e}"

@tool
def get_customer_orders(email: str) -> str:
    """
    Retrieve all past orders for a customer using their email address.
    Returns the order ID, item name, delivery date, refund status, and the specific return policy for the item.
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT customer_id FROM customers WHERE email = ?", (email,))
        customer = cursor.fetchone()
        if not customer:
            conn.close()
            return "Customer not found in the database."
            
        cursor.execute('''
            SELECT o.order_id, i.name, o.order_date, o.delivery_date, o.refund_status, i.return_policy 
            FROM orders o
            JOIN items i ON o.item_id = i.item_id
            WHERE o.customer_id = ?
        ''', (customer['customer_id'],))
        
        orders = cursor.fetchall()
        conn.close()
        
        if not orders:
            return "No orders found for this customer."
            
        result = "Orders:\n"
        for o in orders:
            result += f"- Order ID {o['order_id']}: {o['name']} | Delivered: {o['delivery_date']} | Status: {o['refund_status']} | Item Policy: {o['return_policy']}\n"
        return result
    except Exception as e:
        return f"Database error: {e}"

@tool
def file_refund_ticket(email: str, order_id: str, issue_description: str) -> str:
    """
    File a formal support ticket to process a refund or replacement for a customer's order.
    Only use this if the item is eligible for return/replacement based on the policy and delivery date.
    """
    try:
        order_id_int = int(order_id)
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Verify customer
        cursor.execute("SELECT customer_id FROM customers WHERE email = ?", (email,))
        customer = cursor.fetchone()
        if not customer:
            conn.close()
            return "Error: Customer not found."
            
        # Verify order
        cursor.execute("SELECT order_id FROM orders WHERE order_id = ? AND customer_id = ?", (order_id_int, customer[0]))
        order = cursor.fetchone()
        if not order:
            conn.close()
            return "Error: Order not found or does not belong to this customer."
            
        # Insert ticket
        now = datetime.datetime.now().isoformat()
        cursor.execute('''
            INSERT INTO support_tickets (customer_id, order_id, issue_description, status, created_at)
            VALUES (?, ?, ?, 'Open', ?)
        ''', (customer[0], order_id_int, issue_description, now))
        
        # Update order status to 'Requested'
        cursor.execute("UPDATE orders SET refund_status = 'Requested' WHERE order_id = ?", (order_id_int,))
        
        conn.commit()
        conn.close()
        
        return f"Successfully filed support ticket for Order {order_id_int}."
    except Exception as e:
        return f"Database error: {e}"
