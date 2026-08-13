export const api = {
  async ask(question, chatHistory = []) {
    const groqApiKey = localStorage.getItem('groq_api_key') || '';
    const res = await fetch('/api/ask', {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'X-Groq-Api-Key': groqApiKey
      },
      body: JSON.stringify({ question, chat_history: chatHistory })
    });
    if (!res.ok) throw new Error('Failed to fetch answer');
    return res.json();
  },

  async getDocuments() {
    const res = await fetch('/api/documents');
    if (!res.ok) throw new Error('Failed to fetch documents');
    return res.json();
  },

  async ingest(file) {
    const formData = new FormData();
    formData.append('file', file);
    const res = await fetch('/api/ingest', {
      method: 'POST',
      body: formData
    });
    if (!res.ok) throw new Error('Failed to upload file');
    return res.json();
  },

  async ingestUrl(url) {
    const res = await fetch('/api/ingest/url', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url })
    });
    if (!res.ok) throw new Error('Failed to ingest URL');
    return res.json();
  },

  async deleteDocument(filename) {
    const res = await fetch(`/api/documents/${encodeURIComponent(filename)}`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Failed to delete document');
    return res.json();
  },

  async deleteAllDocuments() {
    const res = await fetch(`/api/documents`, {
      method: 'DELETE'
    });
    if (!res.ok) throw new Error('Failed to delete all documents');
    return res.json();
  },
  
  getHistory: async () => {
    const res = await fetch(`/api/history`);
    if (!res.ok) return [];
    return res.json();
  },
  
  saveHistory: async (history) => {
    await fetch(`/api/history`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(history),
    });
  }
};
