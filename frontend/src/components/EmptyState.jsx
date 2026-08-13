export default function EmptyState({ onSuggest }) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon">
        <svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
      </div>
      <h2>Search your documents</h2>
      <p>Ask a question and get precise answers with citations pulled directly from your uploaded PDFs.</p>
    </div>
  );
}
