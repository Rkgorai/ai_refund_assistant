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
    """Prompts the user for missing information required to process a refund."""
    email = state.get("customer_email")
    order_id = state.get("current_order_id")
    
    if not email:
        msg = "I can certainly help you with a refund. Could you please provide your email address first?"
    elif not order_id:
        msg = "Thank you. Could you please provide the Order ID for the item you wish to return?"
    else:
        msg = "Please provide more details."
        
    return {"messages": [AIMessage(content=msg)]}

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
You have the following verified information:
Customer Email: {email}
Order ID Context: {order_id}

Use 'get_customer_orders' to check their eligibility and 'file_refund_ticket' to submit the request if appropriate.
Explain the status clearly to the user."""

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
        return "policy"
    elif intent == "refund_request":
        # State-driven guardrail for missing info
        if not state.get("customer_email") or not state.get("current_order_id"):
            return "ask_for_info"
        else:
            return "process_refund"
    
    return "off_topic" # Fallback

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
            "policy": "policy_rag_node",
            "ask_for_info": "ask_for_info",
            "process_refund": "refund_processor_node"
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
