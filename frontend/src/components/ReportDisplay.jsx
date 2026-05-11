import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Copy, Download, Check } from "lucide-react";
import SourceCard from "./SourceCard";

export default function ReportDisplay({ report, sources }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    await navigator.clipboard.writeText(report);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const download = () => {
    const a   = document.createElement("a");
    a.href    = URL.createObjectURL(new Blob([report], { type: "text/markdown" }));
    a.download = `research-${Date.now()}.md`;
    a.click();
  };

  return (
    <div className="report-section">
      <div className="report-actions">
        <span className="report-badge">Report ready</span>
        <div className="report-btns">
          <button className="action-btn" onClick={copy}>
            {copied ? <Check size={14}/> : <Copy size={14}/>}
            {copied ? "Copied!" : "Copy"}
          </button>
          <button className="action-btn" onClick={download}>
            <Download size={14}/> Download .md
          </button>
        </div>
      </div>

      <div className="markdown-body">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{report}</ReactMarkdown>
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
