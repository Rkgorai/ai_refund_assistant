// frontend/src/app/page.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./globals.css";

type Message = {
  role: "user" | "ai";
  content: string;
};

type AgentState = {
  intent: string;
  email: string | null;
  order_id: string | null;
};

type Ticket = {
  ticket_id: number;
  order_id: number;
  issue_description: string;
  status: string;
  created_at: string;
  ticket_type: string | null;
};

type Order = {
  order_id: number;
  item_name: string;
  order_date: string;
  delivery_date: string;
  refund_status: string;
  return_policy: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "ai", content: "Hello! I am your AI Refund Assistant. How can I help you today?" }
  ]);
  const [input, setInput] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [agentState, setAgentState] = useState<AgentState>({
    intent: "None",
    email: null,
    order_id: null,
  });
  
  // Ticket Modal State
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [showTickets, setShowTickets] = useState(false);
  
  // Orders Modal State
  const [orders, setOrders] = useState<Order[]>([]);
  const [showOrders, setShowOrders] = useState(false);
  
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Session Persistence logic (Task 2)
    let sessionId = localStorage.getItem("refund_agent_session");
    if (!sessionId) {
      sessionId = Math.random().toString(36).substring(7);
      localStorage.setItem("refund_agent_session", sessionId);
    }
    
    // We proxy through Next.js to bypass all browser security blocks!
    const host = typeof window !== 'undefined' ? window.location.host : 'localhost:3000';
    const ws = new WebSocket(`ws://${host}/ws/${sessionId}`);
    
    ws.onopen = () => {
      setIsConnected(true);
    };

    ws.onclose = () => {
      setIsConnected(false);
      setIsProcessing(false);
    };

    ws.onerror = (error) => {
      console.error("WebSocket Error:", error);
      setIsConnected(false);
      setIsProcessing(false);
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === "status") {
        setIsProcessing(data.content === "processing");
      } else if (data.type === "state_update") {
        setAgentState(data.state);
      } else if (data.type === "message") {
        setMessages(prev => [...prev, { role: "ai", content: data.content }]);
        setIsProcessing(false);
      } else if (data.type === "sync_history") {
        // Restore persistent chat history
        if (data.history.length > 0) {
           setMessages(data.history);
        }
      } else if (data.type === "ticket_data") {
        // Display fetched tickets
        setTickets(data.tickets);
        setShowTickets(true);
      } else if (data.type === "order_data") {
        // Display fetched orders
        setOrders(data.orders);
        setShowOrders(true);
      }
    };
    
    wsRef.current = ws;
    
    return () => {
      ws.close();
    };
  }, []);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isProcessing]);

  const sendMessage = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !wsRef.current) return;
    
    setMessages(prev => [...prev, { role: "user", content: input }]);
    
    // Check if input might be JSON, if so, send it raw, otherwise format as plain text string
    wsRef.current.send(input);
    setInput("");
    setIsProcessing(true);
  };
  
  const fetchTickets = () => {
    if (wsRef.current && isConnected) {
      // Send a structured command to fetch tickets (Task 1)
      wsRef.current.send(JSON.stringify({ type: "fetch_tickets" }));
    }
  };
  
  const exportChat = () => {
    const chatText = messages.map(m => `${m.role.toUpperCase()}:\n${m.content}\n`).join('\n---\n');
    const blob = new Blob([chatText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `chat_export_${new Date().toISOString().replace(/[:.]/g, '-')}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };
  
  const clearChat = () => {
    if (wsRef.current && isConnected) {
      wsRef.current.send(JSON.stringify({ type: "clear_chat" }));
      setMessages([{ role: "ai", content: "Hello! I am your AI Refund Assistant. How can I help you today?" }]);
      setAgentState({ intent: "None", email: null, order_id: null });
    }
  };

  return (
    <div className="container">
      {/* Left Chat Section */}
      <div className="chat-section">
        <div className="chat-header">Refund Assistant AI</div>
        
        <div className="chat-history" ref={scrollRef}>
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              {msg.role === "ai" ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {msg.content}
                </ReactMarkdown>
              ) : (
                msg.content
              )}
            </div>
          ))}
          {isProcessing && (
            <div className="message ai" style={{ opacity: 0.7 }}>
              <span className="typing-indicator">Processing request through LangGraph...</span>
            </div>
          )}
        </div>
        
        <form className="input-area" onSubmit={sendMessage}>
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message to the agent..."
            disabled={isProcessing}
          />
          <button type="submit" disabled={isProcessing || !input.trim() || !isConnected}>
            {isConnected ? "Send" : "Disconnected"}
          </button>
        </form>
      </div>

      {/* Right Dashboard Section */}
      <div className="dashboard-section">
        <div className="dashboard-header">
          <div className={`status-dot ${isProcessing ? 'processing' : ''}`}></div>
          System State Dashboard
        </div>
        
        <div className="state-card">
          <div className="state-row">
            <span className="state-label">Extracted Intent</span>
            <span className={`state-value ${!agentState.intent || agentState.intent === 'None' ? 'empty' : ''}`}>
              {agentState.intent || "Waiting..."}
            </span>
          </div>
          
          <div className="state-row">
            <span className="state-label">Verified Email</span>
            <span className={`state-value ${!agentState.email ? 'empty' : ''}`}>
              {agentState.email || "Missing"}
            </span>
          </div>
          
          <div className="state-row">
            <span className="state-label">Active Order Context</span>
            <span className={`state-value ${!agentState.order_id ? 'empty' : ''}`}>
              {agentState.order_id || "None selected"}
            </span>
          </div>
          
          {/* Action Buttons */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem', marginTop: '1rem' }}>
            <button 
              className="action-btn"
              onClick={() => wsRef.current?.send(JSON.stringify({ type: "fetch_orders" }))}
              disabled={!agentState.email || !isConnected}
            >
              View My Orders
            </button>
            <button 
              className="action-btn"
              onClick={fetchTickets}
              disabled={!agentState.email || !isConnected}
            >
              View My Support Tickets
            </button>
            <div style={{ display: 'flex', gap: '0.8rem' }}>
              <button 
                className="action-btn secondary"
                onClick={exportChat}
                style={{ backgroundColor: 'transparent', border: '1px solid rgba(139, 148, 158, 0.5)', color: '#8b949e', flex: 1, fontSize: '0.85rem' }}
              >
                Export Chat
              </button>
              <button 
                className="action-btn secondary"
                onClick={clearChat}
                style={{ backgroundColor: 'transparent', border: '1px solid rgba(255, 123, 114, 0.5)', color: '#ff7b72', flex: 1, fontSize: '0.85rem' }}
              >
                Clear Chat
              </button>
            </div>
          </div>
        </div>
        
        <div className="state-card" style={{ marginTop: 'auto', border: '1px solid rgba(88, 166, 255, 0.3)' }}>
          <div className="state-row">
            <span className="state-label" style={{ color: '#58a6ff' }}>LangGraph Engine Live</span>
            <span className="state-value" style={{ fontSize: '0.9rem', color: '#c9d1d9', marginTop: '0.5rem', lineHeight: '1.4' }}>
              All interactions are routed securely through the Python State Machine. Sessions persist automatically on reload.
            </span>
          </div>
        </div>
      </div>
      
      {/* Ticket Modal */}
      {showTickets && (
        <div className="modal-overlay" onClick={() => setShowTickets(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Your Support Tickets</h3>
              <button className="close-btn" onClick={() => setShowTickets(false)}>×</button>
            </div>
            <div className="modal-body">
              {tickets.length === 0 ? (
                <p style={{ color: '#8b949e', fontStyle: 'italic' }}>No tickets found for {agentState.email}</p>
              ) : (
                <table className="ticket-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Order</th>
                      <th>Type</th>
                      <th>Issue</th>
                      <th>Status</th>
                      <th>Date</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tickets.map(t => (
                      <tr key={t.ticket_id}>
                        <td>#{t.ticket_id}</td>
                        <td>{t.order_id}</td>
                        <td>
                          {t.ticket_type === 'Return' ? (
                            <span style={{ color: '#ff7b72', fontWeight: 500 }}>Return</span>
                          ) : t.ticket_type === 'Replacement' ? (
                            <span style={{ color: '#79c0ff', fontWeight: 500 }}>Replacement</span>
                          ) : (
                            <span style={{ color: '#8b949e' }}>{t.ticket_type || 'Legacy'}</span>
                          )}
                        </td>
                        <td>{t.issue_description}</td>
                        <td><span className={`badge ${t.status.toLowerCase()}`}>{t.status}</span></td>
                        <td>{new Date(t.created_at).toLocaleDateString()}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
      
      {/* Orders Modal */}
      {showOrders && (
        <div className="modal-overlay" onClick={() => setShowOrders(false)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Your Recent Orders</h3>
              <button className="close-btn" onClick={() => setShowOrders(false)}>×</button>
            </div>
            <div className="modal-body">
              {orders.length === 0 ? (
                <p style={{ color: '#8b949e', fontStyle: 'italic' }}>No orders found for {agentState.email}</p>
              ) : (
                <table className="ticket-table">
                  <thead>
                    <tr>
                      <th>Order ID</th>
                      <th>Item</th>
                      <th>Delivered</th>
                      <th>Status</th>
                      <th>Policy</th>
                    </tr>
                  </thead>
                  <tbody>
                    {orders.map(o => (
                      <tr key={o.order_id}>
                        <td>#{o.order_id}</td>
                        <td>{o.item_name}</td>
                        <td>{new Date(o.delivery_date).toLocaleDateString()}</td>
                        <td>
                          {o.refund_status ? (
                            <span className="badge open">{o.refund_status}</span>
                          ) : (
                            <span style={{ color: '#8b949e' }}>Active</span>
                          )}
                        </td>
                        <td>{o.return_policy}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
