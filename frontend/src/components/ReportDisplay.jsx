import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, Download, Check, RotateCcw } from "lucide-react";
import SourceCard from "./SourceCard";

const slugify = (s) => (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 60);

export default function ReportDisplay({ report, sources, query, onRerun }) {
  const [copied, setCopied] = useState(null);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(report);
      setCopied("ok");
    } catch {
      // Clipboard API is unavailable on plain-http origins other than localhost
      const ta = document.createElement("textarea");
      ta.value = report;
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      setCopied(ok ? "ok" : "fail");
    }
    setTimeout(() => setCopied(null), 2000);
  };

  const download = () => {
    const url  = URL.createObjectURL(new Blob([report], { type: "text/markdown" }));
    const a    = document.createElement("a");
    a.href     = url;
    a.download = `research-${slugify(query) || Date.now()}.md`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  };

  return (
    <div className="report-section">
      <div className="report-actions">
        <span className="report-badge">Report ready</span>
        <div className="report-btns">
          <button className="action-btn" onClick={copy}>
            {copied === "ok" ? <Check size={14}/> : <Copy size={14}/>}
            {copied === "ok" ? "Copied!" : copied === "fail" ? "Copy failed" : "Copy"}
          </button>
          <button className="action-btn" onClick={download}>
            <Download size={14}/> Download .md
          </button>
          {onRerun && (
            <button className="action-btn" onClick={onRerun} title="Run this query again for fresh results (the saved report is kept)">
              <RotateCcw size={14}/> Run again
            </button>
          )}
        </div>
      </div>

      <div className="markdown-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{ a: ({ node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer"/> }}
        >{report}</ReactMarkdown>
      </div>

      {sources?.length > 0 && (
        <div className="sources-section">
          <h3 className="sources-heading">Sources ({sources.length})</h3>
          <div className="sources-grid">
            {sources.map((s, i) => <SourceCard key={s.id || i} source={s} index={i}/>)}
          </div>
        </div>
      )}
    </div>
  );
}
