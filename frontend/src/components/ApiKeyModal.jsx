import { useState } from 'react';

export default function ApiKeyModal({ isOpen, onSubmit }) {
  const [key, setKey] = useState('');

  if (!isOpen) return null;

  return (
    <div className="modal-overlay">
      <div className="modal-content" style={{ maxWidth: '400px' }}>
        <h2>Enter Groq API Key</h2>
        <p style={{ marginBottom: '16px', color: 'var(--text-secondary)' }}>
          To use the AI RAG engine, please provide your Groq API key.
        </p>
        <input 
          type="password" 
          placeholder="gsk_..." 
          value={key}
          onChange={(e) => setKey(e.target.value)}
          style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid var(--border-medium)', marginBottom: '16px' }}
        />
        <div className="modal-actions" style={{ justifyContent: 'flex-end' }}>
          <button 
            className="btn-primary" 
            onClick={() => onSubmit(key)}
            disabled={!key.trim()}
          >
            Save Key
          </button>
        </div>
      </div>
    </div>
  );
}
