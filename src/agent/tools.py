import datetime
from langchain_core.tools import tool

# Handle absolute imports correctly depending on where the script is run from
import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.rag.vectorstore import FaissVectorStore
from pydantic import BaseModel, Field

class RefundTicketSchema(BaseModel):
    email: str = Field(description="The customer's email address")
    order_id: str = Field(description="The numeric ID of the order")
    issue_description: str = Field(description="The reason for the return or refund")

class CustomerOrdersSchema(BaseModel):
    email: str = Field(description="The customer's email address")

_VECTOR_STORE_CACHE = None

@tool
def search_return_policy(query: str) -> str:
    """
    Search the official return policy documents for specific rules about returns, refunds, or replacements.
    Always use this tool when a customer asks if they are allowed to return an item, or questions about the return window.
    """
    global _VECTOR_STORE_CACHE
    try:
        if _VECTOR_STORE_CACHE is None:
            _VECTOR_STORE_CACHE = FaissVectorStore(persist_dir="db/vector_store")
            _VECTOR_STORE_CACHE.load()
            
        results = _VECTOR_STORE_CACHE.query(query, top_k=3)
        if not results:
            return "No relevant policy found."
        return "\n\n---\n\n".join([r["metadata"]["text"] for r in results if "metadata" in r])
    except Exception as e:
        return f"Error querying policy database: {e}"

@tool(args_schema=CustomerOrdersSchema)
def get_customer_orders(email: str) -> str:
    """
    Retrieve all past orders for a customer using their email address.
    Returns the order ID, item name, delivery date, refund status, and the specific return policy for the item.
    """
    try:
        from src.db.db_service import get_customer_id_by_email, get_orders_by_email
        
        if not get_customer_id_by_email(email):
            return "Customer not found in the database."
            
        orders = get_orders_by_email(email)
        
        if not orders:
            return "No orders found for this customer."
            
        result = "Orders:\n\n"
        result += "| Order ID | Item Name | Delivered | Status | Policy |\n"
        result += "|---|---|---|---|---|\n"
        for o in orders:
            status = o['refund_status'] if o['refund_status'] else 'None'
            result += f"| {o['order_id']} | {o['item_name']} | {o['delivery_date']} | {status} | {o['return_policy']} |\n"
        return result
    except Exception as e:
        return f"Database error: {e}"

@tool(args_schema=RefundTicketSchema)
def file_refund_ticket(email: str, order_id: str, issue_description: str) -> str:
    """
    File a formal support ticket to process a refund or replacement for a customer's order.
    Only use this if the item is eligible for return/replacement based on the policy and delivery date.
    """
    try:
        from src.db.db_service import get_customer_id_by_email, get_order_eligibility_details, file_ticket_and_update_order
        
        try:
            order_id_int = int(order_id)
        except ValueError:
            return f"Error: '{order_id}' is not a valid numerical Order ID."
            
        customer_id = get_customer_id_by_email(email)
        if not customer_id:
            return "Error: Customer not found."
            
        order = get_order_eligibility_details(order_id_int, email)
        if not order:
            return "Error: Order not found or does not belong to this customer."
            
        delivery_date_str, return_policy, refund_status = order
        
        if refund_status and refund_status != 'None':
            return f"Error: Order {order_id_int} already has an active request (Status: {refund_status}). Multiple tickets for the same order are not allowed."
        
        # Strict Server-Side Validation
        if return_policy == 'Non-Returnable':
            try:
                delivery_date = datetime.datetime.strptime(delivery_date_str, "%Y-%m-%d")
                if (datetime.datetime.now() - delivery_date).days <= 7:
                    issue_lower = issue_description.lower()
                    if any(word in issue_lower for word in ["wrong", "different", "incorrect", "not what i ordered", "another"]):
                        return "Error: If you received a different product than ordered, please contact customer support via complaints@example.com."
            except ValueError:
                pass
            return "Error: This item is Non-Returnable."
            
        import re
        match = re.search(r'(\d+)', return_policy)
        if match:
            days = int(match.group(1))
            try:
                # Assuming delivery_date is in 'YYYY-MM-DD' format
                delivery_date = datetime.datetime.strptime(delivery_date_str, "%Y-%m-%d")
                expiration_date = delivery_date + datetime.timedelta(days=days)
                current_date = datetime.datetime.now()
                
                if current_date > expiration_date:
                    return f"Error: The return window expired on {expiration_date.strftime('%Y-%m-%d')}. The item was delivered on {delivery_date_str} and the policy is '{return_policy}'."
            except ValueError:
                pass # Fallback if date parsing fails
            
        # Determine ticket type based on policy
        ticket_type = "Replacement" if "Replacement" in return_policy else "Return"
        
        file_ticket_and_update_order(customer_id, order_id_int, issue_description, ticket_type)
        
        if "Replacement" in return_policy:
            return f"Successfully filed support ticket for Order {order_id_int}. Your replacement is processed and a new item will be shipped to you shortly after the original item is picked up."
        else:
            return f"Successfully filed support ticket for Order {order_id_int}. Your return request is done and will be refunded to your original payment method after pickup."
    except Exception as e:
        return f"Database error: {e}"
