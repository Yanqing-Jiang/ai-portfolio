import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

/**
 * AnalyticsPage for the Next Gen Analytics (Memory) project.
 * This is a light-weight adaptation of the SQL analytics page with
 * additional UI elements for cache awareness.
 */
const AnalyticsPage: React.FC = () => {
  // User query and streaming state
  const [query, setQuery] = useState('');
  const [analysis, setAnalysis] = useState('');

  // Cache metrics
  const [cacheSize, setCacheSize] = useState(0);
  const [cacheHitRate, setCacheHitRate] = useState(0);
  const [sqlHistory, setSqlHistory] = useState<{ sql: string; reused: boolean }[]>([]);
  const [executionPath, setExecutionPath] = useState<string[]>([]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAnalysis('');
    setExecutionPath([]);
    // Placeholder for streaming call to backend
    setExecutionPath(['planning', 'sql_executor']);
    setSqlHistory((h) => [...h, { sql: 'SELECT 1', reused: false }]);
  };

  const handleClearCache = () => {
    // Placeholder; would call backend endpoint
    setCacheSize(0);
    setCacheHitRate(0);
  };

  const handleViewCache = () => {
    // Placeholder; this would open a modal with cache contents
    alert('Cache contents not implemented');
  };

  return (
    <div className="analytics-memory">
      <h1>Next Gen Analytics (Memory)</h1>
      <form onSubmit={handleSubmit}>
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Ask about financial metrics..."
        />
        <button type="submit">Run</button>
      </form>

      <div className="cache-controls">
        <button onClick={handleViewCache}>View Cache</button>
        <button onClick={handleClearCache}>Clear Cache</button>
      </div>

      <div className="cache-stats">
        <span>Cache Size: {cacheSize} items</span>
        <span>Hit Rate: {cacheHitRate}%</span>
      </div>

      <div className="execution-path">
        <h3>Execution Path</h3>
        <ol>
          {executionPath.map((node) => (
            <li key={node}>{node}</li>
          ))}
        </ol>
      </div>

      <div className="sql-history">
        <h3>SQL History</h3>
        <ul>
          {sqlHistory.map((h, i) => (
            <li key={i}>
              <code>{h.sql}</code>
              {h.reused && <span className="badge badge-success">reused</span>}
            </li>
          ))}
        </ul>
      </div>

      <div className="analysis">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{analysis}</ReactMarkdown>
      </div>
    </div>
  );
};

export default AnalyticsPage;
