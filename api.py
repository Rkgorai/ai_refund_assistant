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
                if not isinstance(payload, dict):
                    raise json.JSONDecodeError("Payload is not a dictionary", data, 0)
                    
                if payload.get("type") == "fetch_tickets":
                    import sqlite3
                    email = sessions[session_id].get("customer_email")
                    if email:
                        conn = sqlite3.connect("db/crm.db")
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT t.ticket_id, t.order_id, t.issue_description, t.status, t.created_at, t.ticket_type
                            FROM support_tickets t
                            JOIN customers c ON t.customer_id = c.customer_id
                            WHERE c.email = ?
                            ORDER BY t.created_at DESC
                        ''', (email,))
                        tickets = [dict(row) for row in cursor.fetchall()]
                        conn.close()
                        await websocket.send_json({"type": "ticket_data", "tickets": tickets})
                    else:
                        await websocket.send_json({"type": "ticket_data", "tickets": []})
                    continue
                    
                if payload.get("type") == "fetch_orders":
                    import sqlite3
                    email = sessions[session_id].get("customer_email")
                    if email:
                        conn = sqlite3.connect("db/crm.db")
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        cursor.execute('''
                            SELECT o.order_id, i.name as item_name, o.order_date, o.delivery_date, o.refund_status, i.return_policy 
                            FROM orders o
                            JOIN items i ON o.item_id = i.item_id
                            JOIN customers c ON o.customer_id = c.customer_id
                            WHERE c.email = ?
                            ORDER BY o.delivery_date DESC
                        ''', (email,))
                        orders = [dict(row) for row in cursor.fetchall()]
                        conn.close()
                        await websocket.send_json({"type": "order_data", "orders": orders})
                    else:
                        await websocket.send_json({"type": "order_data", "orders": []})
                    continue
                if payload.get("type") == "clear_chat":
                    sessions[session_id] = {
                        "messages": [],
                        "intent": "",
                        "customer_email": None,
                        "current_order_id": None
                    }
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
