import os
import sys
import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from src.voice.stt import stt_router, load_stt_model
from src.voice.tts import tts_router

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

app.include_router(stt_router, prefix="/api")
app.include_router(tts_router, prefix="/api")

from src.agent.tools import preload_vector_store

@app.on_event("startup")
async def load_models():
    print("Loading AI Models at startup to prevent lag...")
    load_stt_model()
    preload_vector_store()

print("Compiling LangGraph State Machine...")
graph = build_agent_graph()
print("LangGraph Agent ready to accept WebSocket connections!")

# In-memory session state store for managing multiple users/tabs
sessions = {}

async def handle_json_payload(payload: dict, session_id: str, websocket: WebSocket) -> bool:
    """Handles structured JSON commands from the frontend. Returns True if handled, False otherwise."""
    if payload.get("type") == "fetch_tickets":
        from src.db.db_service import get_tickets_by_email
        email = sessions[session_id].get("customer_email")
        if email:
            tickets = get_tickets_by_email(email)
            await websocket.send_json({"type": "ticket_data", "tickets": tickets})
        else:
            await websocket.send_json({"type": "ticket_data", "tickets": []})
        return True
        
    if payload.get("type") == "fetch_orders":
        from src.db.db_service import get_orders_by_email
        email = sessions[session_id].get("customer_email")
        if email:
            orders = get_orders_by_email(email)
            await websocket.send_json({"type": "order_data", "orders": orders})
        else:
            await websocket.send_json({"type": "order_data", "orders": []})
        return True
        
    if payload.get("type") == "clear_chat":
        sessions[session_id] = {
            "messages": [],
            "intent": "",
            "customer_email": None,
            "current_order_id": None
        }
        return True
        
    return False


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
    else:
        # Task 2: Persistent Session Sync
        # If the user refreshes, restore their exact chat history and dashboard state!
        history = []
        for m in sessions[session_id]["messages"]:
            if hasattr(m, "content"):
                role = "user" if isinstance(m, HumanMessage) else "ai"
                history.append({"role": role, "content": m.content})
        
        await websocket.send_json({"type": "sync_history", "history": history})
        await websocket.send_json({
            "type": "state_update",
            "state": {
                "intent": sessions[session_id].get("intent", ""),
                "email": sessions[session_id].get("customer_email"),
                "order_id": sessions[session_id].get("current_order_id")
            }
        })
        
    config = {"configurable": {"thread_id": session_id}}
    
    try:
        while True:
            # Wait for user input from the Next.js chat interface
            data = await websocket.receive_text()
            
            # Task 1: Check if the frontend is sending a structured JSON command instead of a chat message
            try:
                payload = json.loads(data)
                if isinstance(payload, dict):
                    handled = await handle_json_payload(payload, session_id, websocket)
                    if handled:
                        continue
            except json.JSONDecodeError:
                # If it's not JSON, it's a standard text chat message. Proceed normally.
                pass
            
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
