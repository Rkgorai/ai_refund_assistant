import os
import uuid
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message=".*create_react_agent.*")

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

import sys
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.agent.agent import build_agent_graph

def main():
    load_dotenv()
    
    if not os.environ.get("GROQ_API_KEY"):
        print("Error: GROQ_API_KEY not found in environment variables.")
        return

    print("Compiling LangGraph Agent...")
    app = build_agent_graph()

    print("\n" + "="*50)
    print("🤖 Advanced AI Refund Assistant (LangGraph)")
    print("Type 'exit' or 'quit' to stop.")
    print("="*50 + "\n")

    # LangGraph State Initialization
    state = {
        "messages": [],
        "intent": "",
        "customer_email": None,
        "current_order_id": None
    }
    
    # Optional thread configuration for future checkpoints
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    while True:
        try:
            user_input = input("You: ")
            if user_input.lower() in ['exit', 'quit']:
                break
            if not user_input.strip():
                continue
            
            # Append human message
            state["messages"].append(HumanMessage(content=user_input))
            
            # Run the LangGraph
            result_state = app.invoke(state, config)
            
            # Update local state so it persists across loop iterations
            state = result_state
            
            # The agent's final response will be the last message in the state
            final_message = state["messages"][-1]
            print(f"\nAssistant: {final_message.content}")
            
            # Debug info
            print(f"\n[Debug State] Intent: {state.get('intent')} | Email: {state.get('customer_email')} | Order: {state.get('current_order_id')}\n")
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\nError: {e}\n")

if __name__ == "__main__":
    main()
