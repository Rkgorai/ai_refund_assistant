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
  
  const wsRef = useRef<WebSocket | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    // Generate a unique session ID for this browser tab
    const sessionId = Math.random().toString(36).substring(7);
    
    // We proxy through Next.js to bypass all browser security blocks!
    // Connect to the exact same host and port as the webpage (e.g. 0.0.0.0:3000)
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
    wsRef.current.send(input);
    setInput("");
    setIsProcessing(true);
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
        </div>
        
        <div className="state-card" style={{ marginTop: 'auto', border: '1px solid rgba(88, 166, 255, 0.3)' }}>
          <div className="state-row">
            <span className="state-label" style={{ color: '#58a6ff' }}>LangGraph Engine Live</span>
            <span className="state-value" style={{ fontSize: '0.9rem', color: '#c9d1d9', marginTop: '0.5rem', lineHeight: '1.4' }}>
              All interactions are routed securely through the Python State Machine. Variables above update in real-time. Database queries require explicit confirmation.
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
