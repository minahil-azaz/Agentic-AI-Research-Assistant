import { useState } from "react";
import { Search, Loader2 } from "lucide-react";

const SUGGESTIONS = [
  "Latest advances in explainable AI for healthcare",
  "How does retrieval-augmented generation work?",
  "State of the art in medical image segmentation",
  "Best vector databases for production RAG systems",
];

export default function ChatInput({ onSubmit, isLoading }) {
  const [value, setValue] = useState("");

  const submit = (e) => {
    e.preventDefault();
    const q = value.trim();
    if (!q || isLoading) return;
    onSubmit(q);
    setValue("");
  };

  return (
    <div className="input-section">
      <form onSubmit={submit} className="search-form">
        <div className="search-box">
          <Search size={20} className="search-icon"/>
          <textarea
            className="search-textarea"
            placeholder="Ask anything — the agent will search, read and synthesise sources for you…"
            value={value}
            onChange={e => setValue(e.target.value)}
            onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(e); } }}
            rows={2}
            disabled={isLoading}
          />
          <button type="submit" className="search-btn" disabled={isLoading || !value.trim()}>
            {isLoading ? <><Loader2 size={16} className="spin"/> Working…</> : "Research"}
          </button>
        </div>
      </form>
      {!isLoading && (
        <div className="suggestions">
          <span className="suggestions-label">Try:</span>
          {SUGGESTIONS.map(s => (
            <button key={s} className="suggestion-chip" onClick={() => setValue(s)}>{s}</button>
          ))}
        </div>
      )}
    </div>
  );
}
