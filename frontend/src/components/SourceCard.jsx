import { useEffect, useState } from 'react';

function generateSnippet(text, answer) {
  if (!text) return null;
  if (!answer) return <div className="source-card-text">{text}</div>;
  
  // Extract words from the answer (min length 4) to find relevance
  const answerWords = new Set(
    (answer.toLowerCase().match(/\b\w{4,}\b/g) || [])
      .filter(w => !['this', 'that', 'with', 'from', 'what', 'have'].includes(w))
  );
  
  if (answerWords.size === 0) return <div className="source-card-text">{text}</div>;
  
  // Split the chunk into sentences
  const sentences = text.match(/[^.!?\n]+[.!?\n]+/g) || [text];
  
  let bestSentence = '';
  let bestScore = -1;
  let bestIndex = 0;
  
  sentences.forEach((sentence, i) => {
    const words = sentence.toLowerCase().match(/\b\w{4,}\b/g) || [];
    let score = 0;
    words.forEach(w => {
      if (answerWords.has(w)) score++;
    });
    if (score > bestScore) {
      bestScore = score;
      bestSentence = sentence;
      bestIndex = i;
    }
  });
  
  // If no good match, just return the text
  if (bestScore === 0) return <div className="source-card-text">{text}</div>;
  
  // Extract a 3-sentence snippet centered around the best sentence
  const startIdx = Math.max(0, bestIndex - 1);
  const endIdx = Math.min(sentences.length - 1, bestIndex + 1);
  const snippet = sentences.slice(startIdx, endIdx + 1).join(' ').trim();
  
  // We highlight the best matching sentence
  const escapedBest = bestSentence.trim().replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const highlightedSnippet = snippet.replace(new RegExp(escapedBest, 'i'), `<mark class="highlighted-text">$&</mark>`);
  
  return (
    <div 
      className="source-card-text" 
      dangerouslySetInnerHTML={{ __html: highlightedSnippet + (endIdx < sentences.length - 1 ? '...' : '') }} 
    />
  );
}

export default function SourceCard({ source, index, isHighlighted, activeAnswer }) {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Staggered animation
    const timer = setTimeout(() => {
      setIsVisible(true);
    }, index * 100);
    return () => clearTimeout(timer);
  }, [index]);

  return (
    <div 
      id={`source-${index + 1}`}
      className={`source-card ${isHighlighted ? 'highlighted' : ''}`}
      style={{
        opacity: isVisible ? 1 : 0,
        transform: isVisible ? 'translateY(0)' : 'translateY(8px)',
        transition: 'opacity 0.3s var(--ease-out), transform 0.3s var(--ease-out)'
      }}
    >
      <div className="source-card-header">
        <div className="source-card-title">
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
          </svg>
          {source.source || source.title || 'Source'}
        </div>
        {source.pages && source.pages.length > 0 && (
          <span className="source-card-page">Page {source.pages.join(', ')}</span>
        )}
      </div>
      {generateSnippet(source.text, activeAnswer)}
    </div>
  );
}
