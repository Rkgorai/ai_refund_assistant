import os
import sys
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Ensure imports work regardless of where the script is executed from
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.append(project_root)

from src.agent.agent import build_agent_graph
from langchain_core.messages import HumanMessage

load_dotenv()

app = FastAPI(title="AI Refund Assistant API")

# Allow Next.js frontend to communicate without CORS issues
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("Compiling LangGraph State Machine...")
graph = build_agent_graph()
print("LangGraph Agent ready to accept WebSocket connections!")

# In-memory session state store for managing multiple users/tabs
sessions = {}

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await websocket.accept()
    if session_id not in sessions:
        sessions[session_id] = {
            "messages": [],
            "intent": "",
            "customer_email": None,
            "current_order_id": None
        }
        
    config = {"configurable": {"thread_id": session_id}}
    
    try:
        while True:
            # Wait for user input from the Next.js chat interface
            data = await websocket.receive_text()
            
            # Tell the frontend the agent is processing
            await websocket.send_json({"type": "status", "content": "processing"})
            
            # Fetch the current state for this session and append the new message
            state = sessions[session_id]
            state["messages"].append(HumanMessage(content=data))
            
            # Execute the LangGraph synchronously in a thread to avoid blocking FastAPI
            result_state = await asyncio.to_thread(graph.invoke, state, config)
            
            # Update local session memory
            sessions[session_id] = result_state
            
            # Extract variables for the Admin Dashboard
            ai_message = result_state["messages"][-1].content
            intent = result_state.get("intent", "")
            email = result_state.get("customer_email")
            order_id = result_state.get("current_order_id")
            
            # 1. Push the real-time technical state to the right-side dashboard
            await websocket.send_json({
                "type": "state_update",
                "state": {
                    "intent": intent,
                    "email": email,
                    "order_id": order_id
                }
            })
            
            # 2. Push the final agent response to the left-side chat window
            await websocket.send_json({
                "type": "message",
                "content": ai_message
            })
            
    except WebSocketDisconnect:
        print(f"Client {session_id} disconnected")

if __name__ == "__main__":
    import uvicorn
    # Starts the FastAPI server on port 8000
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
