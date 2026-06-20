import os
import sys
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*create_react_agent.*")

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if project_root not in sys.path:
    sys.path.append(project_root)

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import AIMessage, SystemMessage, HumanMessage
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.agent.guardrails import AgentState, classify_intent_node, off_topic_responder, greeting_node
from src.agent.tools import search_return_policy, get_customer_orders, file_refund_ticket

# --- Node: Ask for Info ---
def ask_for_info(state: AgentState):
    """Fallback node if essential information is missing."""
    return {"messages": [AIMessage(content="I can certainly help you with your orders or a refund. Could you please provide your email address first?")]}

# --- Node: Policy RAG ---
def policy_rag_node(state: AgentState):
    """Handles policy questions using the search tool."""
    llm = ChatGroq(model=os.getenv("MODEL_NAME"), temperature=0)
    tools = [search_return_policy]
    
    # We use LangGraph's native prebuilt agent instead of legacy AgentExecutor
    agent = create_react_agent(
        llm, 
        tools=tools, 
        prompt="You are an AI Refund Assistant. Use the search_return_policy tool to answer the user's policy question accurately."
    )
    
    try:
        response = agent.invoke({"messages": state["messages"]})
        return {"messages": [response["messages"][-1]]}
    except Exception as e:
        print(f"[DEBUG - Agent] Policy RAG error: {e}")
        return {"messages": [AIMessage(content="I'm sorry, I encountered an internal logic error while searching policies. Could you please rephrase your question?")]}

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
    if order_id and str(order_id).isdigit() and len(str(order_id)) >= 4:
        import sqlite3
        import datetime
        import re
        try:
            conn = sqlite3.connect("db/crm.db")
            cursor = conn.cursor()
            cursor.execute('''
                SELECT o.delivery_date, i.return_policy, o.refund_status 
                FROM orders o
                JOIN items i ON o.item_id = i.item_id
                JOIN customers c ON o.customer_id = c.customer_id
                WHERE o.order_id = ? AND c.email = ?
            ''', (int(order_id), email))
            order = cursor.fetchone()
            conn.close()
            
            if order:
                delivery_date_str, return_policy, refund_status = order
                error_msg = None
                
                if refund_status and refund_status != 'None':
                    error_msg = f"It already has an active request (Status: {refund_status})."
                elif return_policy == 'Non-Returnable':
                    try:
                        delivery_date = datetime.datetime.strptime(delivery_date_str, "%Y-%m-%d")
                        if (datetime.datetime.now() - delivery_date).days > 7:
                            error_msg = "This item is marked as Non-Returnable."
                    except ValueError:
                        error_msg = "This item is marked as Non-Returnable."
                else:
                    match = re.search(r'(\d+)', return_policy)
                    if match:
                        days = int(match.group(1))
                        try:
                            delivery_date = datetime.datetime.strptime(delivery_date_str, "%Y-%m-%d")
                            expiration_date = delivery_date + datetime.timedelta(days=days)
                            if datetime.datetime.now() > expiration_date:
                                error_msg = f"The return window expired on {expiration_date.strftime('%Y-%m-%d')}."
                        except ValueError:
                            pass
                            
                if error_msg:
                    return {"messages": [AIMessage(content=f"I apologize, but we cannot process a request for Order {order_id}. {error_msg}")], "current_order_id": None}
        except Exception as e:
            print(f"[DEBUG - Agent] Pre-check error: {e}")
            
    # 3. Extract final ticket details
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
            import re
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

# --- Routing Logic ---
def route_intent(state: AgentState):
    """Routes the graph based on the classified intent."""
    intent = state.get("intent")
    
    if intent == "off_topic":
        return "off_topic"
    elif intent == "greeting":
        return "greeting"
    elif intent == "policy_query":
        return "policy_rag_node"
    elif intent == "refund_request":
        # We only strictly need the email to proceed to the processor.
        # The ReAct agent will handle listing orders and getting confirmation natively.
        if not state.get("customer_email"):
            return "ask_for_info"
        return "refund_processor_node"
    return "off_topic_responder" # Fallback

# --- Build Graph ---
def build_agent_graph():
    workflow = StateGraph(AgentState)
    
    # Add Nodes
    workflow.add_node("classifier", classify_intent_node)
    workflow.add_node("off_topic_responder", off_topic_responder)
    workflow.add_node("greeting_node", greeting_node)
    workflow.add_node("ask_for_info", ask_for_info)
    workflow.add_node("policy_rag_node", policy_rag_node)
    workflow.add_node("refund_processor_node", refund_processor_node)
    
    # Set Entry Point
    workflow.set_entry_point("classifier")
    
    # Add Conditional Edges
    workflow.add_conditional_edges(
        "classifier",
        route_intent,
        {
            "off_topic": "off_topic_responder",
            "greeting": "greeting_node",
            "policy_rag_node": "policy_rag_node",
            "ask_for_info": "ask_for_info",
            "refund_processor_node": "refund_processor_node",
            "off_topic_responder": "off_topic_responder"
        }
    )
    
    # End Edges
    workflow.add_edge("off_topic_responder", END)
    workflow.add_edge("greeting_node", END)
    workflow.add_edge("ask_for_info", END)
    workflow.add_edge("policy_rag_node", END)
    workflow.add_edge("refund_processor_node", END)
    
    return workflow.compile()

# Example usage to verify compilation
if __name__ == "__main__":
    app = build_agent_graph()
    print("Agent Graph successfully compiled!")
