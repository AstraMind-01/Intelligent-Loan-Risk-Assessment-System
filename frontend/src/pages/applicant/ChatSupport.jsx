import React, { useState, useRef, useEffect } from 'react';
import { mockChatMessages } from '../../utils/mockData';
import { Send, Bot, User } from 'lucide-react';

const botResponses = [
  "Your application LA-2024-001 is currently Under Review. An officer has been assigned and you should receive an update within 2-3 business days.",
  "For a Home Purchase loan, you'll need: Government ID, Bank Statements (3 months), Tax Returns, Pay Stubs, and Proof of Address. You can upload these in the Document Upload section.",
  "Your risk score of 742 indicates Low Risk. The main factors are your strong credit history and stable employment. Your DTI ratio of 28% is well within acceptable limits.",
  "Our AI model uses SHAP (SHapley Additive exPlanations) to provide transparent explanations of risk factors. Each factor's contribution is clearly shown in your Risk Report.",
  "You can use the Eligibility Simulator to see how changes in your financial profile would affect your risk score. Try adjusting your DTI ratio or loan amount to see the impact.",
  "Processing times vary by loan type. Home Purchase loans typically take 5-10 business days, while personal loans may be processed within 2-3 business days.",
];

export default function ChatSupport() {
  const [messages, setMessages] = useState(mockChatMessages);
  const [input, setInput] = useState('');
  const endRef = useRef(null);
  const responseIndex = useRef(0);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const sendMessage = () => {
    if (!input.trim()) return;
    const userMsg = { id: Date.now(), sender: 'user', text: input.trim() };
    setMessages(prev => [...prev, userMsg]);
    setInput('');

    // Simulate bot response
    setTimeout(() => {
      const botMsg = {
        id: Date.now() + 1,
        sender: 'bot',
        text: botResponses[responseIndex.current % botResponses.length],
      };
      responseIndex.current++;
      setMessages(prev => [...prev, botMsg]);
    }, 1000);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  return (
    <div className="slide-up">
      <div className="page-header">
        <h1>Chat Support</h1>
        <p>Get instant answers about your loan application, risk assessment, or documentation.</p>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <div className="chat-container">
          <div className="chat-messages">
            {messages.map(msg => (
              <div key={msg.id} className={`chat-bubble ${msg.sender}`}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                  {msg.sender === 'bot' ? <Bot size={14} color="#D4AF37" /> : <User size={14} />}
                  <span style={{ fontSize: '0.6875rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: msg.sender === 'bot' ? 'var(--color-gold)' : 'var(--color-ivory-muted)' }}>
                    {msg.sender === 'bot' ? 'AI Assistant' : 'You'}
                  </span>
                </div>
                {msg.text}
              </div>
            ))}
            <div ref={endRef} />
          </div>
          <div className="chat-input-bar">
            <input
              className="form-input"
              placeholder="Ask about your application, risk score, or documents..."
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              style={{ flex: 1 }}
            />
            <button className="btn btn-primary" onClick={sendMessage}><Send size={18} /></button>
          </div>
        </div>
      </div>
    </div>
  );
}
