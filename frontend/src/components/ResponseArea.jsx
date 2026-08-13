import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function ResponseArea({ question, answer, isLoading, sources, onCitationHover, onCitationClick, onCitationLeave }) {
  if (!question) return null;

  // Preprocess answer to convert [1] and 【1】 into [1](#cite-1) and fix malformed markdown tables
  let processedAnswer = answer ? answer.replace(/\[(\d+)\]/g, '[$1](#cite-$1)') : '';
  processedAnswer = processedAnswer.replace(/【(\d+)】/g, '[$1](#cite-$1)');
  processedAnswer = processedAnswer.replace(/\|\s+\|/g, '|\n|');

  const components = {
    a: ({ node, href, children, ...props }) => {
      if (href && href.startsWith('#cite-')) {
        const sourceId = href.replace('#cite-', '');
        return (
          <span 
            className="cite" 
            onMouseEnter={() => onCitationHover(sourceId, sources)}
            onMouseLeave={onCitationLeave}
            onClick={() => onCitationClick(sourceId, sources)}
            {...props}
          >
            {sourceId}
          </span>
        );
      }
      return <a href={href} target="_blank" rel="noopener noreferrer" {...props}>{children}</a>;
    }
  };

  return (
    <div className="response-container visible">
      <div className="chat-bubble-user">
        <div className="bubble-content">{question}</div>
      </div>
      <div className="chat-bubble-ai">
        <div className="bubble-icon">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="var(--green-100)" stroke="var(--green-800)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
        </div>
        <div className="bubble-content response-body">
          {isLoading ? (
            <div className="loading-dots"><span></span><span></span><span></span></div>
          ) : (
            <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
              {processedAnswer}
            </ReactMarkdown>
          )}
        </div>
      </div>
    </div>
  );
}
