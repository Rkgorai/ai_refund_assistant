from typing import TypedDict, Annotated, List, Optional, Literal
import operator
from langchain_core.messages import BaseMessage, AIMessage
from pydantic import BaseModel, Field
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
import os

# --- 1. Graph State Definition ---
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    intent: str
    customer_email: Optional[str]
    current_order_id: Optional[str]

# --- 2. Intent Classification ---
class IntentClassification(BaseModel):
    intent: Literal["policy_query", "refund_request", "greeting", "off_topic"] = Field(description="The classified intent.")
    customer_email: Optional[str] = Field(None, description="The customer's email if provided.")
    current_order_id: Optional[str] = Field(None, description="The order ID, item name, or product details if provided by the user.")

def classify_intent_node(state: AgentState):
    """Node that uses a fast LLM to classify the user's intent and extract entities."""
    llm = ChatGroq(model="qwen/qwen3-32b", temperature=0)
    structured_llm = llm.with_structured_output(IntentClassification)
    
    messages = state.get("messages", [])
    if not messages:
        return {"intent": "off_topic"}
        
    history_text = "\n".join([f"{type(msg).__name__}: {msg.content}" for msg in messages[-5:]])
    
    system_prompt = """You are an intent classification engine for an e-commerce refund assistant.
Analyze the user's latest message IN THE CONTEXT of the recent conversation and determine the intent.
Options:
- policy_query: Asking about return policies, replacement rules, timeframes, etc.
- refund_request: Asking to return an item, get a refund, check an order, or file a ticket. Or providing requested info (like an email or order ID) to proceed with a refund.
- greeting: Simple greetings (hello, hi, how are you).
- off_topic: Anything else not related to e-commerce, shopping, refunds, or policies.

Extract the email address or order ID if the user provides them.
If they are not provided, return null for them."""

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "Recent conversation:\n{history}\n\nClassify the intent of the last HumanMessage.")
    ])
    
    chain = prompt | structured_llm
    try:
        result = chain.invoke({"history": history_text})
        
        # Return updates to the state
        updates = {"intent": result.intent}
        
        # Only update email/order if they were explicitly found in this message
        if result.customer_email:
            email_val = str(result.customer_email).strip()
            if email_val.lower() not in ["none", "null", "n/a", ""]:
                updates["customer_email"] = email_val
                
        if result.current_order_id:
            order_val = str(result.current_order_id).strip()
            if order_val.lower() not in ["none", "null", "n/a", ""]:
                if not order_val.isdigit() or len(order_val) < 4:
                    # The LLM extracted a product name or partial ID.
                    # Let's perform a smart lookup in the database to find the actual Order ID!
                    email = result.customer_email or state.get("customer_email")
                    if email:
                        from src.db.db_service import smart_lookup_order_id
                        match = smart_lookup_order_id(email, order_val)
                        if match:
                            updates["current_order_id"] = match
                        else:
                            # Fallback: couldn't find the item, keep the string just in case
                            updates["current_order_id"] = order_val
                    else:
                        updates["current_order_id"] = order_val
                else:
                    updates["current_order_id"] = order_val
                
        print(f"[DEBUG - Guardrails] Intent classified as: {result.intent}")
        if updates.get("current_order_id"):
            print(f"[DEBUG - Guardrails] Resolved Order ID context to: {updates['current_order_id']}")
            
        return updates
    except Exception as e:
        print(f"[DEBUG - Guardrails] LLM structured output parsing failed: {e}. Defaulting to safe fallback.")
        return {"intent": "refund_request"}

# --- 3. Guardrail Nodes ---
def off_topic_responder(state: AgentState):
    """Node to firmly refuse off-topic questions."""
    msg = "I am an AI Refund Assistant. I can only help you with e-commerce returns, refunds, and policy questions. I cannot answer queries outside of this domain."
    return {"messages": [AIMessage(content=msg)]}

def greeting_node(state: AgentState):
    """Node to handle basic greetings."""
    msg = "Hello! I am the AI Refund Assistant. I can help you understand our return policies or process a refund request. How can I assist you today?"
    return {"messages": [AIMessage(content=msg)]}
