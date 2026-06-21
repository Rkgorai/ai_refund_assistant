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
  const [sessionId, setSessionId] = useState<string>("");
  
  // Voice Feature State
  const [isListening, setIsListening] = useState(false);
  const isListeningRef = useRef(false);
  const [voiceMode, setVoiceMode] = useState(false);
  const voiceModeRef = useRef(false);
  const recognitionRef = useRef<any>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    // Initialize Web Speech API for interim visual feedback only
    if (typeof window !== "undefined") {
      const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
      if (SpeechRecognition) {
        recognitionRef.current = new SpeechRecognition();
        recognitionRef.current.continuous = false; // Siri mode: stop automatically when user stops speaking
        recognitionRef.current.interimResults = true;
        
        recognitionRef.current.onresult = (event: any) => {
          let interimTranscript = '';
          let finalTranscript = '';
          
          for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
              finalTranscript += event.results[i][0].transcript;
            } else {
              interimTranscript += event.results[i][0].transcript;
            }
          }
          // Show the words as they speak simultaneously
          setInput(finalTranscript + interimTranscript);
        };

        // Auto-stop recording when speech ends (like Siri)
        recognitionRef.current.onend = () => {
          if (isListeningRef.current) {
            if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
              mediaRecorderRef.current.stop();
            }
            setIsListening(false);
          }
        };
      }
    }
  }, []);

  useEffect(() => {
    voiceModeRef.current = voiceMode;
    isListeningRef.current = isListening;
  }, [voiceMode, isListening]);

  useEffect(() => {
    // Session Persistence logic (Task 2)
    let sid = localStorage.getItem("refund_agent_session");
    if (!sid) {
      sid = Math.random().toString(36).substring(7);
      localStorage.setItem("refund_agent_session", sid);
    }
    setSessionId(sid);
    
    // We proxy through Next.js to bypass all browser security blocks!
    const host = typeof window !== 'undefined' ? window.location.host : 'localhost:3000';
    const ws = new WebSocket(`ws://${host}/ws/${sid}`);
    
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
        
        // Output TTS if Voice Mode is active
        if (voiceModeRef.current) {
          fetch("/api/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: data.content })
          })
          .then(response => response.blob())
          .then(blob => {
            const url = URL.createObjectURL(blob);
            const audio = new Audio(url);
            audio.play();
            audio.onended = () => URL.revokeObjectURL(url);
          })
          .catch(e => console.error("TTS fetch failed", e));
        }
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
  
  const toggleMicrophone = async () => {
    if (isListening) {
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch (e) {}
      }
      if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
        mediaRecorderRef.current.stop();
      }
      setIsListening(false);
    } else {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorderRef.current = mediaRecorder;
        audioChunksRef.current = [];
        
        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) {
            audioChunksRef.current.push(event.data);
          }
        };
        
        mediaRecorder.onstop = async () => {
          const audioBlob = new Blob(audioChunksRef.current, { type: "audio/webm" });
          stream.getTracks().forEach(track => track.stop());
          
          const formData = new FormData();
          formData.append("audio", audioBlob, "recording.webm");
          
          setIsProcessing(true);
          try {
            const response = await fetch("/api/transcribe", {
              method: "POST",
              body: formData
            });
            const data = await response.json();
            
            if (data.text) {
              const finalInput = data.text;
              setInput("");
              
              // Auto-submit the voice query instantly just like Siri
              if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                setMessages(prev => [...prev, { role: "user", content: finalInput }]);
                wsRef.current.send(finalInput);
              }
            }
          } catch (e) {
            console.error("Transcription failed", e);
            setIsProcessing(false);
          }
        };
        
        // Start visual feedback
        setInput("");
        if (recognitionRef.current) {
          try { recognitionRef.current.start(); } catch (e) {}
        }
        
        mediaRecorder.start();
        setIsListening(true);
      } catch (err) {
        console.error("Error accessing microphone", err);
        alert("Microphone access denied or not available.");
      }
    }
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

  const getIntentBadge = (intent: string) => {
    if (!intent || intent === 'None') return <span className="badge none">Waiting...</span>;
    switch(intent) {
      case 'refund_request': return <span className="badge success">Refund Request</span>;
      case 'policy_query': return <span className="badge info">Policy Query</span>;
      case 'greeting': return <span className="badge default">Greeting</span>;
      case 'off_topic': return <span className="badge warning">Off Topic</span>;
      default: return <span className="badge default">{intent}</span>;
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
          <button 
            type="button" 
            className={`mic-btn ${isListening ? 'listening' : ''}`}
            onClick={toggleMicrophone}
            title={isListening ? "Stop listening" : "Start Voice Input"}
          >
            🎤
          </button>
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={isListening ? "Listening..." : "Type your message to the agent..."}
            disabled={isProcessing || isListening}
          />
          <button type="submit" disabled={isProcessing || !input.trim() || !isConnected}>
            {isConnected ? "Send" : "Disconnected"}
          </button>
        </form>
      </div>

      {/* Right Dashboard Section */}
      <div className="dashboard-section">
        <div className="dashboard-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div className={`status-dot ${isProcessing ? 'processing' : ''}`}></div>
            <span className="gradient-text">System State Dashboard</span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            {/* Voice Mode Toggle */}
            <div className="voice-toggle" onClick={() => setVoiceMode(!voiceMode)} title="Toggle AI Text-to-Speech">
              <span style={{ fontSize: '0.75rem', fontWeight: 600, color: voiceMode ? '#58a6ff' : '#8b949e', letterSpacing: '0.5px' }}>VOICE MODE</span>
              <div className={`toggle-switch ${voiceMode ? 'on' : 'off'}`}>
                <div className="toggle-knob"></div>
              </div>
            </div>
            {sessionId && <span style={{ fontSize: '0.75rem', color: '#8b949e', fontFamily: 'monospace', background: 'rgba(255,255,255,0.05)', padding: '2px 6px', borderRadius: '4px' }}>Session: {sessionId}</span>}
          </div>
        </div>
        
        <div style={{ fontSize: '0.85rem', color: isProcessing ? 'var(--accent-color)' : '#2ea043', marginTop: '-1rem', fontWeight: 600, letterSpacing: '0.5px', display: 'flex', alignItems: 'center', gap: '6px' }}>
          <div style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: isProcessing ? 'var(--accent-color)' : '#2ea043', animation: 'pulse 1.5s infinite' }}></div>
          AGENT STATUS: {isProcessing ? 'PROCESSING...' : 'IDLE'}
        </div>
        
        <div className="state-card">
          <div className="state-row">
            <span className="state-label">Extracted Intent</span>
            <div className="state-value" style={{ marginTop: '0.3rem' }}>
              {getIntentBadge(agentState.intent)}
            </div>
          </div>
          
          <div className="state-row">
            <span className="state-label">Verified Email</span>
            <span className={`state-value ${!agentState.email ? 'empty' : ''}`} style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {!agentState.email && agentState.order_id && <span style={{ color: '#ff7b72', fontSize: '1.2rem', lineHeight: 1 }}>⚠</span>}
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
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', marginTop: '0.5rem' }}>
            <button 
              className="action-btn-small"
              onClick={() => wsRef.current?.send(JSON.stringify({ type: "fetch_orders" }))}
              disabled={!agentState.email || !isConnected}
            >
              View Orders
            </button>
            <button 
              className="action-btn-small"
              onClick={fetchTickets}
              disabled={!agentState.email || !isConnected}
            >
              Support Tickets
            </button>
            <button 
              className="action-btn-small secondary"
              onClick={exportChat}
            >
              Export Chat
            </button>
            <button 
              className="action-btn-small danger"
              onClick={clearChat}
            >
              Clear Chat
            </button>
          </div>
        </div>
        
        <div className="state-card">
          <div className="dashboard-subheader" style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem' }}>Quick Debug Prompts</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            <button className="pill-btn" onClick={() => setInput("What is the return policy for clothes?")}>Policy Check</button>
            <button className="pill-btn" onClick={() => setInput("My email is rahul@example.com")}>Set Email</button>
            <button className="pill-btn" onClick={() => setInput("I want to return my last order")}>Trigger Return</button>
          </div>
        </div>

        <div className="state-card" style={{ marginTop: 'auto', background: 'linear-gradient(145deg, rgba(88, 166, 255, 0.05) 0%, rgba(0, 0, 0, 0) 100%)', border: '1px solid rgba(88, 166, 255, 0.3)' }}>
          <div className="state-row">
            <span className="state-label" style={{ color: '#58a6ff' }}>LangGraph Engine Live</span>
            <span className="state-value" style={{ fontSize: '0.9rem', color: '#c9d1d9', marginTop: '0.5rem', lineHeight: '1.5' }}>
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
