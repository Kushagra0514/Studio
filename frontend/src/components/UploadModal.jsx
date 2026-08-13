import { useState } from 'react';

export default function UploadModal({ isOpen, onClose, onUploadStart }) {
  const [isDragging, setIsDragging] = useState(false);
  const [urlInput, setUrlInput] = useState('');

  if (!isOpen) return null;

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setIsDragging(true);
    } else if (e.type === 'dragleave') {
      setIsDragging(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      onUploadStart(Array.from(e.dataTransfer.files));
      onClose();
    }
  };

  const handleFileInput = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      onUploadStart(Array.from(e.target.files));
      onClose();
    }
  };

  return (
    <div className="modal-overlay visible" onClick={(e) => {
      if (e.target.className.includes('modal-overlay')) onClose();
    }}>
      <div className="modal">
        <h3>Upload documents</h3>
        <label 
          className={`upload-zone ${isDragging ? 'dragover' : ''}`}
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          style={{ display: 'block', width: '100%', marginBottom: '16px' }}
        >
          <input 
            type="file" 
            style={{ display: 'none' }} 
            onChange={handleFileInput}
            accept=".pdf,.docx,.txt"
            multiple
          />
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>
          </svg>
          <p>Drag and drop your PDFs, or <span>browse files</span></p>
          <p className="hint">Supports PDF, DOCX, and TXT files</p>
        </label>
        
        <div className="url-ingest-zone" style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
          <input 
            type="url" 
            placeholder="https://example.com" 
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            style={{ flex: 1, padding: '10px 12px', borderRadius: '8px', border: '1px solid var(--border-medium)', fontFamily: 'var(--font-body)' }}
          />
          <button 
            onClick={() => {
              if (urlInput) {
                onUploadStart([{ type: 'url', data: urlInput }]);
                setUrlInput('');
                onClose();
              }
            }}
            style={{ padding: '8px 16px', background: 'var(--green-800)', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 500 }}
          >
            Ingest URL
          </button>
        </div>

        <div className="modal-actions">
          <button className="btn-cancel" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}
