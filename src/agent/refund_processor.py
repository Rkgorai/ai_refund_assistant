import os
import re
import sqlite3
import datetime
from langchain_core.messages import AIMessage
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.agent.guardrails import AgentState
from src.agent.tools import get_customer_orders, file_refund_ticket

def _check_order_eligibility(order_id: str, email: str) -> str | None:
    """Checks if an order is eligible for a refund. Returns an error message if not eligible, or None if eligible."""
    if not order_id or not str(order_id).isdigit() or len(str(order_id)) < 4:
        return None
        
    try:
        from src.db.db_service import get_order_eligibility_details
        order = get_order_eligibility_details(int(order_id), email)
        
        if not order:
            return None
            
        delivery_date_str, return_policy, refund_status = order
        
        if refund_status and refund_status != 'None':
            return f"It already has an active request (Status: {refund_status})."
            
        if return_policy == 'Non-Returnable':
            try:
                delivery_date = datetime.datetime.strptime(delivery_date_str, "%Y-%m-%d")
                if (datetime.datetime.now() - delivery_date).days > 7:
                    return "This item is marked as Non-Returnable."
            except ValueError:
                return "This item is marked as Non-Returnable."
        else:
            match = re.search(r'(\d+)', return_policy)
            if match:
                days = int(match.group(1))
                try:
                    delivery_date = datetime.datetime.strptime(delivery_date_str, "%Y-%m-%d")
                    expiration_date = delivery_date + datetime.timedelta(days=days)
                    if datetime.datetime.now() > expiration_date:
                        return f"The return window expired on {expiration_date.strftime('%Y-%m-%d')}."
                except ValueError:
                    pass
        return None
    except Exception as e:
        print(f"[DEBUG - Agent] Pre-check error: {e}")
        return None

def _extract_and_file_ticket(state: AgentState, email: str, order_id: str) -> dict:
    """Uses LLM to extract ticket details and file the ticket."""
    system_msg = f"""You are an AI Refund Assistant.
Customer Email: {email}
Context Order ID (if known): {order_id}

The user has already seen their list of orders.
Engage in a brief, polite conversation to understand the issue with their order.
CRITICAL INSTRUCTION: DO NOT use markdown headings, bold text, or numbered steps. Write naturally like a human customer support agent in 1-2 short sentences.
Once the user explicitly confirms BOTH the Order ID and the issue they are facing, respond EXACTLY with the following string and nothing else:
TICKET: ORDER_ID | ISSUE
Example: TICKET: 10060 | didn't like the fitting

If you need more details about the issue or which order they mean, just ask them naturally. Do NOT use the word TICKET unless you have enough information to file the support ticket.
"""
    llm = ChatGroq(model=os.getenv("MODEL_NAME"), temperature=0)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt | llm
    
    try:
        # LLMs struggle with large contexts, so we only pass the last 6 messages to the LLM
        # while keeping the full history in the LangGraph state.
        llm_messages = state["messages"][-6:]
        response = chain.invoke({"messages": llm_messages})
        final_msg = response.content
        
        # Bulletproof parsing logic (Handles missing XML tags, typos, and truncation)
        if "|" in final_msg and ("TICKET" in final_msg.upper() or "TICK:" in final_msg.upper()):
            parts = final_msg.split("|")
            left_part = parts[0]
            extracted_issue = parts[1].replace("</TICKET>", "").replace("/TICKET>", "").replace(">", "").strip()
            
            # Extract numbers from the left side of the pipe
            nums = re.findall(r'\d+', left_part)
            extracted_order_id = nums[-1] if nums else ""
            
            # The 8B model sometimes hallucinates and truncates the order ID (e.g. '101' instead of '10109')
            # If the ID is too short, we fall back to the one extracted by the Guardrails Classifier Node!
            if len(extracted_order_id) < 4 and order_id:
                extracted_order_id = order_id
                
            if not extracted_order_id or len(extracted_order_id) < 4:
                return {"messages": [AIMessage(content="Could you please confirm the exact Order ID you wish to return?")]}
            
            ticket_result = file_refund_ticket.invoke({
                "email": email,
                "order_id": extracted_order_id,
                "issue_description": extracted_issue
            })
            
            # Smooth out raw errors into natural customer service apologies
            if ticket_result.startswith("Error: "):
                ticket_result = ticket_result.replace("Error: ", "I apologize, but ")
            
            # Whether successful or an error (e.g. Non-Returnable), wipe the order_id from the state
            # so the next request starts with a clean slate!
            return {"messages": [AIMessage(content=ticket_result)], "current_order_id": None}
            
        return {"messages": [response]}
    except Exception as e:
        print(f"[DEBUG - Agent] Refund processor error: {e}")
        return {"messages": [AIMessage(content="I need a bit more clarification. Which exact order ID do you want to return, and what is the issue?")]}

def refund_processor_node(state: AgentState):
    """Handles checking orders and filing tickets manually to prevent LLM hallucination loops."""
    email = state.get("customer_email")
    order_id = state.get("current_order_id")
    
    # 1. Deterministic Tool Execution: Check if we've already shown the orders
    history_text = "\n".join([msg.content for msg in state["messages"] if hasattr(msg, "content")])
    if "Orders:" not in history_text:
        orders = get_customer_orders.invoke({"email": email})
        return {"messages": [AIMessage(content=f"Here are your past orders:\n\n{orders}\n\nPlease let me know which Order ID you are having an issue with.")]}
        
    # 2. Strict Pre-Check: If we have an Order ID, check eligibility BEFORE asking for the issue
    if order_id:
        error_msg = _check_order_eligibility(order_id, email)
        if error_msg:
            return {"messages": [AIMessage(content=f"I apologize, but we cannot process a request for Order {order_id}. {error_msg}")], "current_order_id": None}
            
    # 3. Extract final ticket details
    return _extract_and_file_ticket(state, email, order_id)
