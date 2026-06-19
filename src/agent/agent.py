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
    
    response = agent.invoke({"messages": state["messages"]})
    return {"messages": [response["messages"][-1]]}

# --- Node: Refund Processor ---
def refund_processor_node(state: AgentState):
    """Handles checking orders and filing tickets using the DB tools."""
    llm = ChatGroq(model=os.getenv("MODEL_NAME"), temperature=0)
    tools = [get_customer_orders, file_refund_ticket]
    
    # We pass the extracted state info to the LLM so it doesn't have to guess
    email = state.get("customer_email")
    order_id = state.get("current_order_id", "Not provided yet")
    
    system_msg = f"""You are an AI Refund Assistant processing a refund request.
You have the following extracted information:
Customer Email: {email}
Order Context provided by user (if any): {order_id}

STRICT WORKFLOW TO FOLLOW:
1. ALWAYS call 'get_customer_orders' first using the email to get the list of their past orders.
2. If the user hasn't specified which order they mean, list their orders to them and ask which one they want to return.
3. If the user has specified an order (by ID, item ID, or item name), match it with the orders retrieved from the database.
4. BEFORE filing a ticket, you MUST display the matched order details to the user and explicitly ask for confirmation (e.g., "You selected Order 10002 for Laptop delivered on 2024-01-05. Is this correct?").
5. If the user says NO, ask them to select again.
6. If the user says YES, ask for the issue description (if not already provided).
7. Once confirmed and the issue is described, call 'file_refund_ticket' to submit the request.
"""

    agent = create_react_agent(llm, tools=tools, prompt=system_msg)
    response = agent.invoke({"messages": state["messages"]})
    return {"messages": [response["messages"][-1]]}

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
