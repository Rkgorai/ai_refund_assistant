import os
import datetime
import json
import re
from langchain_core.messages import AIMessage
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from pydantic import BaseModel, Field
from typing import Optional

from src.agent.guardrails import AgentState
from src.agent.tools import get_customer_orders, file_refund_ticket, search_return_policy

class TicketDecision(BaseModel):
    should_evaluate: bool = Field(description="True if the user has provided both the order ID and a clear reason for the return/issue.")
    order_id: Optional[str] = Field(description="The numeric order ID the user wants to return.")
    issue_description: Optional[str] = Field(description="The reason for the return or issue.")
    ai_response: str = Field(description="If should_evaluate is False, what should the AI say to the user to get the missing information? Keep it to 1 sentence.")

class PolicyEvaluation(BaseModel):
    is_eligible: bool = Field(description="True if the return/replacement is allowed according to the policy.")
    rejection_reason: Optional[str] = Field(description="If not eligible, why? Explain based on the policy in 1 sentence.")
    ticket_type: Optional[str] = Field(description="If eligible, is this a 'Return' or 'Replacement'?")

def _evaluate_policy_with_rag(order_id: str, email: str, issue_description: str) -> dict:
    from src.db.db_service import get_order_eligibility_details
    order = get_order_eligibility_details(int(order_id), email)
    if not order:
        return {"messages": [AIMessage(content="I'm sorry, I couldn't find that order. Please check the order ID and try again.")], "current_order_id": None}
        
    delivery_date_str, return_policy, refund_status, category, item_name = order
    
    if refund_status and refund_status != 'None':
        return {"messages": [AIMessage(content=f"I apologize, but we cannot process a request for Order {order_id}. It already has an active request (Status: {refund_status}).")], "current_order_id": None}

    # Query FAISS Vector Store for exact policy
    try:
        query = f"Return policy for {category} {item_name}. Issue: {issue_description}"
        policy_text = search_return_policy.invoke({"query": query})
    except Exception as e:
        print(f"[DEBUG - Agent] Vector store query error: {e}")
        policy_text = "Standard 7-day return policy applies." # Safe fallback
    
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    
    system_msg = f"""You are a strict Return Policy Evaluator.
Today's Date: {current_date}
Delivery Date: {delivery_date_str}
Item: {item_name} (Category: {category})
Item DB Policy: {return_policy}
Customer Issue: {issue_description}

Official Policy Retrieved:
---
{policy_text}
---

Determine if the user is eligible for a return or replacement based STRICTLY on the Official Policy and the dates provided.
If the policy requires the item to be unused or unopened and the user has used/opened it, deny it.
If the return window has expired based on the dates, deny it.

You MUST respond ONLY with a valid JSON object matching this schema. Do not include markdown ticks.
{{
  "is_eligible": true,
  "rejection_reason": "Explanation if false",
  "ticket_type": "Return or Replacement"
}}"""

    llm = ChatGroq(model=os.getenv("MODEL_NAME"), temperature=0)
    from langchain_core.messages import SystemMessage
    try:
        response = llm.invoke([SystemMessage(content=system_msg)])
        
        json_str = response.content.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:-3].strip()
        elif json_str.startswith("```"):
            json_str = json_str[3:-3].strip()
            
        json_match = re.search(r'\{.*\}', json_str, re.DOTALL)
        if not json_match:
            raise ValueError("No JSON found in policy evaluator response")
            
        data = json.loads(json_match.group(0))
        eval_result = PolicyEvaluation(**data)
        
        if eval_result.is_eligible:
            # Enforce database policy limits
            final_ticket_type = eval_result.ticket_type or "Return"
            if "Replacement" in return_policy:
                final_ticket_type = "Replacement"
                
            # File ticket
            ticket_result = file_refund_ticket.invoke({
                "email": email,
                "order_id": order_id,
                "issue_description": issue_description,
                "ticket_type": final_ticket_type
            })
            if ticket_result.startswith("Error: "):
                ticket_result = ticket_result.replace("Error: ", "I apologize, but ")
            return {"messages": [AIMessage(content=ticket_result)], "current_order_id": None}
        else:
            return {"messages": [AIMessage(content=f"I apologize, but your request cannot be processed. {eval_result.rejection_reason}")], "current_order_id": None}
            
    except Exception as e:
        print(f"[DEBUG - Agent] Policy evaluation error: {e}")
        return {"messages": [AIMessage(content="I encountered an error while evaluating the policy. Please try again or contact support.")], "current_order_id": None}

def refund_processor_node(state: AgentState):
    """Handles checking orders and evaluating tickets via RAG instead of hardcoded rules."""
    email = state.get("customer_email")
    order_id = state.get("current_order_id")
    
    # 1. Deterministic Tool Execution: Check if we've already shown the orders
    history_text = "\n".join([msg.content for msg in state["messages"] if hasattr(msg, "content")])
    if "Orders:" not in history_text:
        orders = get_customer_orders.invoke({"email": email})
        return {"messages": [AIMessage(content=f"Here are your past orders:\n\n{orders}\n\nPlease let me know which Order ID you are having an issue with, and provide a brief description of the issue.")]}
        
    system_msg = f"""You are an AI Refund Assistant.
Customer Email: {email}
Context Order ID: {order_id}

Determine if you have enough information to evaluate a refund request.
You need BOTH the Order ID and a clear issue description from the user.
If you have both, set should_evaluate to true.
If you are missing either, set should_evaluate to false and provide a brief 1-sentence ai_response asking for the missing info.

You MUST respond ONLY with a valid JSON object matching this schema. Do not include markdown ticks.
{{
  "should_evaluate": false,
  "order_id": "10109",
  "issue_description": "Broken screen",
  "ai_response": "What is the issue?"
}}"""

    llm = ChatGroq(model=os.getenv("MODEL_NAME"), temperature=0)
    
    from langchain_core.messages import SystemMessage
    prompt = ChatPromptTemplate.from_messages([
        SystemMessage(content=system_msg),
        MessagesPlaceholder(variable_name="messages")
    ])
    chain = prompt | llm
    
    try:
        llm_messages = state["messages"][-6:]
        response = chain.invoke({"messages": llm_messages})
        
        json_str = response.content.strip()
        if json_str.startswith("```json"):
            json_str = json_str[7:-3].strip()
        elif json_str.startswith("```"):
            json_str = json_str[3:-3].strip()
            
        json_match = re.search(r'\{.*\}', json_str, re.DOTALL)
        if not json_match:
            print(f"[DEBUG] No JSON in output: {response.content}")
            raise ValueError("No JSON found in response")
            
        data = json.loads(json_match.group(0))
        result = TicketDecision(**data)
        
        if result.should_evaluate and result.order_id and result.issue_description:
            extracted_order_id = str(result.order_id)
            
            # Sanity check fallback to context order_id
            if len(extracted_order_id) < 4 and order_id:
                extracted_order_id = order_id
                
            if len(extracted_order_id) < 4:
                return {"messages": [AIMessage(content="Could you please confirm the exact Order ID you wish to return?")]}
                
            # Evaluate using RAG and DB
            return _evaluate_policy_with_rag(extracted_order_id, email, result.issue_description)
            
        else:
            # We don't have enough info, ask the user
            return {"messages": [AIMessage(content=result.ai_response)]}
            
    except Exception as e:
        print(f"[DEBUG - Agent] Refund processor parsing error: {e}")
        return {"messages": [AIMessage(content="I need a bit more clarification. Which exact order ID do you want to return, and what is the issue?")]}
