import { useState, useEffect, useRef } from 'react';
import { api } from './api';
import SearchBar from './components/SearchBar';
import EmptyState from './components/EmptyState';
import ResponseArea from './components/ResponseArea';
import SourcePanel from './components/SourcePanel';
import UploadModal from './components/UploadModal';
import ApiKeyModal from './components/ApiKeyModal';

export default function App() {
  const [isApiKeyModalOpen, setIsApiKeyModalOpen] = useState(false);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [documents, setDocuments] = useState([]);
  
  const [chatHistory, setChatHistory] = useState([]);
  const [activeSources, setActiveSources] = useState([]);
  const [activeAnswer, setActiveAnswer] = useState("");
  const [highlightedSourceId, setHighlightedSourceId] = useState(null);
  
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [isRightSidebarOpen, setIsRightSidebarOpen] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(300);
  const [isDeleting, setIsDeleting] = useState(false);
  
  // Upload Queue State
  const [uploadQueue, setUploadQueue] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  
  // Right Sidebar State
  const [rightSidebarWidth, setRightSidebarWidth] = useState(360);
  const isResizing = useRef(false);
  const isRightResizing = useRef(false);

  const chatEndRef = useRef(null);

  // Scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatEndRef.current) {
      chatEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [chatHistory]);

  // Left Sidebar Resizing
  const startResizing = () => {
    isResizing.current = true;
    document.addEventListener('mousemove', handleResize);
    document.addEventListener('mouseup', stopResizing);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const handleResize = (e) => {
    if (isResizing.current) {
      const newWidth = Math.max(200, Math.min(e.clientX, 600));
      setSidebarWidth(newWidth);
    }
  };

  const stopResizing = () => {
    isResizing.current = false;
    document.removeEventListener('mousemove', handleResize);
    document.removeEventListener('mouseup', stopResizing);
    document.body.style.cursor = 'default';
    document.body.style.userSelect = '';
  };

  // Right Sidebar Resizing
  const startRightResizing = () => {
    isRightResizing.current = true;
    document.addEventListener('mousemove', handleRightResize);
    document.addEventListener('mouseup', stopRightResizing);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  };

  const handleRightResize = (e) => {
    if (isRightResizing.current) {
      const newWidth = Math.max(250, Math.min(window.innerWidth - e.clientX, 800));
      setRightSidebarWidth(newWidth);
    }
  };

  const stopRightResizing = () => {
    isRightResizing.current = false;
    document.removeEventListener('mousemove', handleRightResize);
    document.removeEventListener('mouseup', stopRightResizing);
    document.body.style.cursor = 'default';
    document.body.style.userSelect = '';
  };

  const fetchDocuments = async () => {
    try {
      const data = await api.getDocuments();
      if (data.documents) {
        setDocuments(data.documents);
      }
    } catch (error) {
      console.error('Failed to fetch documents:', error);
    }
  };

  const handleDeleteDocument = async (filename) => {
    setIsDeleting(true);
    // Optimistic UI update
    setDocuments(prev => prev.filter(doc => {
      const name = typeof doc === 'string' ? doc : (doc.name || doc.filename);
      return name !== filename;
    }));

    try {
      await api.deleteDocument(filename);
      await fetchDocuments();
    } catch (error) {
      console.error('Failed to delete document:', error);
      // Revert on failure
      await fetchDocuments();
    } finally {
      setIsDeleting(false);
    }
  };

  const handleClearAll = async () => {
    if (!window.confirm("Are you sure you want to delete all documents?")) return;
    setIsDeleting(true);
    setDocuments([]);
    try {
      await api.deleteAllDocuments();
      await fetchDocuments();
    } catch (error) {
      console.error('Failed to clear all documents:', error);
      await fetchDocuments();
    } finally {
      setIsDeleting(false);
    }
  };

  // Background Queue Processor
  useEffect(() => {
    const processQueue = async () => {
      if (uploadQueue.length === 0 || isUploading) return;
      setIsUploading(true);
      const file = uploadQueue[0];
      
      try {
        if (file.type === 'url') {
          await api.ingestUrl(file.data);
        } else {
          await api.ingest(file);
        }
        await fetchDocuments();
      } catch (error) {
        console.error('Failed to process item:', file.name || file.data, error);
      } finally {
        setUploadQueue(prev => prev.slice(1));
        setIsUploading(false);
      }
    };
    processQueue();
  }, [uploadQueue, isUploading]);

  const handleUploadStart = (files) => {
    setUploadQueue(prev => [...prev, ...files]);
  };

  useEffect(() => {
    fetchDocuments();
    api.getHistory().then(history => {
      if (history && history.length > 0) {
        setChatHistory(history);
      }
    }).catch(err => console.error("Failed to load history", err));
    
    if (!localStorage.getItem('groq_api_key')) {
      setIsApiKeyModalOpen(true);
    }
  }, []);

  useEffect(() => {
    if (chatHistory.length > 0) {
      api.saveHistory(chatHistory).catch(err => console.error("Failed to save history", err));
    }
  }, [chatHistory]);

  const handleSearch = async (query) => {
    if (!query) return;
    
    const formattedHistory = [];
    chatHistory.slice(-5).forEach(msg => {
      if (msg.question) formattedHistory.push({ role: 'user', content: msg.question });
      if (msg.answer) formattedHistory.push({ role: 'assistant', content: msg.answer });
    });
    
    const newMessageId = Date.now();
    setChatHistory(prev => [
      ...prev, 
      { id: newMessageId, question: query, answer: null, isSearching: true, sources: [] }
    ]);
    
    try {
      const data = await api.ask(query, formattedHistory);
      let rawSources = data.sources || [];
      let finalAnswer = data.answer || "";
      let finalSources = [];

      // Extract unique cited indices
      const regex = /\[(\d+)\]|【(\d+)】/g;
      const uniqueOriginalIndices = new Set();
      let match;
      while ((match = regex.exec(finalAnswer)) !== null) {
        if (match[1]) uniqueOriginalIndices.add(parseInt(match[1], 10) - 1);
        if (match[2]) uniqueOriginalIndices.add(parseInt(match[2], 10) - 1);
      }

      // If citations exist, remap them sequentially
      if (uniqueOriginalIndices.size > 0) {
        const originalToNewMap = new Map();
        let newIndexCounter = 1;
        for (const origIdx of uniqueOriginalIndices) {
          originalToNewMap.set(origIdx, newIndexCounter++);
          if (rawSources[origIdx]) {
            finalSources.push(rawSources[origIdx]);
          }
        }
        
        finalAnswer = finalAnswer.replace(/\[(\d+)\]|【(\d+)】/g, (m, p1, p2) => {
          const origIdx = parseInt(p1 || p2, 10) - 1;
          if (originalToNewMap.has(origIdx)) {
            return `[${originalToNewMap.get(origIdx)}]`;
          }
          return m;
        });
      } else {
        finalSources = rawSources;
      }
      
      setActiveSources(finalSources);
      setActiveAnswer(finalAnswer);
      if (finalSources.length > 0) {
        setIsRightSidebarOpen(true);
      }
      
      setTimeout(() => {
        setChatHistory(prev => prev.map(msg => 
          msg.id === newMessageId 
            ? { ...msg, answer: finalAnswer, isSearching: false, sources: finalSources } 
            : msg
        ));
      }, finalSources.length > 0 ? 800 : 0);
      
    } catch (error) {
      console.error('Search failed:', error);
      setChatHistory(prev => prev.map(msg => 
        msg.id === newMessageId 
          ? { ...msg, answer: "Sorry, I encountered an error while searching.", isSearching: false } 
          : msg
      ));
    }
  };

  const handleCitationHover = (id, messageSources) => {
    setHighlightedSourceId(id);
    
    setTimeout(() => {
      const card = document.getElementById(`source-${id}`);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      }
    }, 50);
  };

  const handleCitationLeave = () => {
    setHighlightedSourceId(null);
  };

  const handleCitationClick = (id, messageSources, answer) => {
    setActiveSources(messageSources);
    setActiveAnswer(answer || "");
    setIsRightSidebarOpen(true);
    setHighlightedSourceId(id);
    
    setTimeout(() => {
      const card = document.getElementById(`source-${id}`);
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 50);
  };

  return (
    <div className="app-notebook">
      
      {/* LEFT SIDEBAR (Documents) */}
      {isSidebarOpen ? (
        <>
          <div className="sidebar" style={{ width: sidebarWidth }}>
            <div className="sidebar-header">
              <h2>Sources</h2>
              <div style={{ display: 'flex', gap: '8px' }}>
                <button className="icon-btn" title="Clear all documents" onClick={handleClearAll} disabled={isDeleting}>
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                </button>
                <button className="icon-btn" title="Hide sources" onClick={() => setIsSidebarOpen(false)}>
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line></svg>
                </button>
              </div>
            </div>
            
            <div className="sidebar-actions">
              <button className="btn-add-source" onClick={() => setIsUploadOpen(true)}>
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
                Add sources
              </button>
            </div>

            <div className="doc-list" style={{ maxHeight: '100%' }}>
              {uploadQueue.length > 0 && (
                <div className="doc-item" style={{ color: 'var(--text-primary)', fontWeight: 500, background: 'var(--bg-hover)' }}>
                  <div className="loading-dots" style={{ padding: 0, marginRight: '8px' }}><span></span><span></span><span></span></div>
                  <span className="doc-name">Processing {uploadQueue.length} item{uploadQueue.length !== 1 ? 's' : ''}...</span>
                </div>
              )}
              {documents.map((doc, i) => {
                const docName = typeof doc === 'string' ? doc : (doc.name || doc.filename || 'Document');
                return (
                  <div key={i} className="doc-item">
                    <svg className="doc-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline></svg>
                    <span className="doc-name" title={docName}>{docName}</span>
                    <button className="icon-btn delete-btn" title="Delete document" onClick={() => handleDeleteDocument(docName)} disabled={isDeleting}>
                      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                    </button>
                  </div>
                );
              })}
            </div>
          </div>
          <div className="sidebar-resizer" onMouseDown={startResizing} />
        </>
      ) : (
        <div className="sidebar-collapsed">
          <button className="icon-btn" title="Show sources" onClick={() => setIsSidebarOpen(true)}>
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="15" y1="3" x2="15" y2="21"></line></svg>
          </button>
        </div>
      )}

      {/* MAIN CHAT */}
      <div className="main-chat">
        <div className="chat-header">
          <h2>Chat</h2>
        </div>
        
        <div className="chat-scroll">
          <div className="chat-content-wrapper">
             
             {/* Studio Workspace Header */}
             <div className="notebook-title">
               <div className="notebook-icon">
                 <svg viewBox="0 0 24 24" width="48" height="48" fill="var(--green-100)" stroke="var(--green-800)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
               </div>
               <h1>Studio Workspace</h1>
               <div className="notebook-meta">{documents.length} sources · {new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric'})}</div>
             </div>
             
             {chatHistory.length === 0 ? (
               <EmptyState onSuggest={handleSearch} />
             ) : (
               <div className="chat-history">
                 {chatHistory.map((chat) => (
                   <div key={chat.id} className="chat-message-block">
                     <ResponseArea 
                       question={chat.question} 
                       answer={chat.answer} 
                       isLoading={chat.isSearching}
                       sources={chat.sources}
                       onCitationHover={handleCitationHover}
                       onCitationLeave={handleCitationLeave}
                       onCitationClick={(id, sources) => handleCitationClick(id, sources, chat.answer)}
                     />
                   </div>
                 ))}
                 <div ref={chatEndRef} />
               </div>
             )}
          </div>
        </div>

        <div className="search-fixed">
          <div className="search-fixed-inner">
            <SearchBar onSearch={handleSearch} />
          </div>
        </div>
      </div>

      {/* RIGHT SIDEBAR (Retrieved Passages) */}
      {activeSources.length > 0 && (
        isRightSidebarOpen ? (
          <>
            <div className="sidebar-resizer" onMouseDown={startRightResizing} />
            <div className="sidebar" style={{ width: rightSidebarWidth }}>
              <div className="sidebar-header">
                <h2>Retrieved Passages</h2>
                <button className="icon-btn" title="Hide passages" onClick={() => setIsRightSidebarOpen(false)}>
                  <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="15" y1="3" x2="15" y2="21"></line></svg>
                </button>
              </div>
              <SourcePanel 
                sources={activeSources} 
                highlightedSourceId={highlightedSourceId} 
                activeAnswer={activeAnswer}
              />
            </div>
          </>
        ) : (
          <div className="sidebar-collapsed">
            <button className="icon-btn" title="Show passages" onClick={() => setIsRightSidebarOpen(true)}>
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><line x1="9" y1="3" x2="9" y2="21"></line></svg>
            </button>
          </div>
        )
      )}

      <UploadModal 
        isOpen={isUploadOpen} 
        onClose={() => setIsUploadOpen(false)} 
        onUploadStart={handleUploadStart}
      />
      <ApiKeyModal 
        isOpen={isApiKeyModalOpen}
        onSubmit={(key) => {
          localStorage.setItem('groq_api_key', key);
          setIsApiKeyModalOpen(false);
        }}
      />
    </div>
  );
}
