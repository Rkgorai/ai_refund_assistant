import os
import sys
from dotenv import load_dotenv

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, ".env"))
sys.path.append(project_root)

from src.agent.refund_processor import refund_processor_node
from langchain_core.messages import HumanMessage, AIMessage

state = {
    "messages": [
        HumanMessage(content="rahul.s@example.com, refund OnePlus Nord Buds 2"),
        AIMessage(content="Here are your past orders:\n\nOrders:\n\n| Order ID | Item Name"),
        HumanMessage(content="10109")
    ],
    "customer_email": "rahul.s@example.com",
    "current_order_id": "10109",
    "intent": "refund_request"
}

res = refund_processor_node(state)
print("RESULT:", res)
