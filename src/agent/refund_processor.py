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
    """Uses LLM with structured output to extract ticket details and file the ticket deterministically."""
    from pydantic import BaseModel, Field
    from typing import Optional
    
    class TicketDecision(BaseModel):
        should_file_ticket: bool = Field(description="True if the user has provided both the order ID and a clear reason for the return/issue.")
        order_id: Optional[str] = Field(description="The numeric order ID the user wants to return.")
        issue_description: Optional[str] = Field(description="The reason for the return or issue.")
        ai_response: str = Field(description="If should_file_ticket is False, what should the AI say to the user to get the missing information? Keep it to 1 sentence.")

    system_msg = f"""You are an AI Refund Assistant.
Customer Email: {email}
Context Order ID: {order_id}

Determine if you have enough information to file a support ticket.
You need BOTH the Order ID and a clear issue description from the user.
If you have both, set should_file_ticket to true.
If you are missing either, set should_file_ticket to false and provide a brief 1-sentence ai_response asking for the missing info."""

    llm = ChatGroq(model=os.getenv("MODEL_NAME"), temperature=0)
    structured_llm = llm.with_structured_output(TicketDecision)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_msg),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt | structured_llm
    
    try:
        # LLMs struggle with large contexts, so we only pass the last 6 messages
        llm_messages = state["messages"][-6:]
        result: TicketDecision = chain.invoke({"messages": llm_messages})
        
        if result.should_file_ticket and result.order_id and result.issue_description:
            # We have everything we need, file the ticket deterministically
            extracted_order_id = str(result.order_id)
            
            # Sanity check fallback to context order_id if LLM hallucinated a short string
            if len(extracted_order_id) < 4 and order_id:
                extracted_order_id = order_id
                
            if len(extracted_order_id) < 4:
                return {"messages": [AIMessage(content="Could you please confirm the exact Order ID you wish to return?")]}
                
            ticket_result = file_refund_ticket.invoke({
                "email": email,
                "order_id": extracted_order_id,
                "issue_description": result.issue_description
            })
            
            if ticket_result.startswith("Error: "):
                ticket_result = ticket_result.replace("Error: ", "I apologize, but ")
                
            return {"messages": [AIMessage(content=ticket_result)], "current_order_id": None}
            
        else:
            # We don't have enough info, ask the user
            return {"messages": [AIMessage(content=result.ai_response)]}
            
    except Exception as e:
        print(f"[DEBUG - Agent] Refund processor structured parsing error: {e}")
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
