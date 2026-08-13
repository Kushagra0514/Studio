import SourceCard from './SourceCard';

export default function SourcePanel({ sources, highlightedSourceId, activeAnswer }) {
  return (
    <div className="panel-sources">
      <div className="sources-header">
        <h2>Sources {sources.length > 0 && <span className="sources-count">({sources.length})</span>}</h2>
      </div>
      <div className="sources-scroll" id="sourcesArea">
        {sources.length === 0 ? (
          <div className="sources-empty">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
            </svg>
            <p>Source passages will appear here when you ask a question</p>
          </div>
        ) : (
          sources.map((source, i) => (
            <SourceCard 
              key={i} 
              index={i} 
              source={source} 
              isHighlighted={highlightedSourceId === String(i + 1)}
              activeAnswer={activeAnswer}
            />
          ))
        )}
      </div>
    </div>
  );
}
