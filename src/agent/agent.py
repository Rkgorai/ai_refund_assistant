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
from src.agent.tools import search_return_policy
from src.agent.refund_processor import refund_processor_node

# --- Node: Ask for Info ---
def ask_for_info(state: AgentState):
    """Fallback node if essential information is missing."""
    return {"messages": [AIMessage(content="I can certainly help you with your orders or a refund. Could you please provide your email address first?")]}

# --- Node: Policy RAG ---
def policy_rag_node(state: AgentState):
    """Handles policy questions using the search tool."""
    llm = ChatGroq(model=os.getenv("MODEL_NAME"), temperature=0)
    tools = [search_return_policy]
    
    system_prompt = """You are an AI Refund Assistant. Use the search_return_policy tool to answer the user's policy question accurately.
CRITICAL INSTRUCTIONS:
1. Provide a direct, concise answer in 1-3 short paragraphs.
2. DO NOT use markdown headings (like ## Step 1), bullet points, or repetitive numbered lists.
3. Write naturally like a human customer support agent.
4. If you cannot find the answer in the policy, say so politely."""

    # We use LangGraph's native prebuilt agent instead of legacy AgentExecutor
    agent = create_react_agent(
        llm, 
        tools=tools, 
        prompt=system_prompt
    )
    
    try:
        response = agent.invoke({"messages": state["messages"]})
        return {"messages": [response["messages"][-1]]}
    except Exception as e:
        print(f"[DEBUG - Agent] Policy RAG error: {e}")
        return {"messages": [AIMessage(content="I'm sorry, I encountered an internal logic error while searching policies. Could you please rephrase your question?")]}

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
