import { Trash2, Clock, ChevronRight } from "lucide-react";

const timeAgo = (d) => {
  const m = Math.floor((Date.now() - new Date(d)) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};

const DOT = { done:"#4ade80", error:"#f87171", planning:"#60a5fa", searching:"#60a5fa", scraping:"#f59e0b", embedding:"#f59e0b", writing:"#a78bfa", pending:"#94a3b8" };

export default function HistorySidebar({ history, onSelect, onDelete, activeId }) {
  if (!history.length) return (
    <div className="sidebar-empty"><Clock size={22}/><p>No research yet</p></div>
  );
  return (
    <div className="sidebar-list">
      {history.map(item => (
        <div key={item.id} className={`sidebar-item ${activeId === item.id ? "active" : ""}`} onClick={() => onSelect(item)}>
          <div className="sidebar-item-dot" style={{ background: DOT[item.status] || "#94a3b8" }}/>
          <div className="sidebar-item-body">
            <p className="sidebar-item-query">{item.query.slice(0, 58)}{item.query.length > 58 ? "…" : ""}</p>
            <span className="sidebar-item-time">{timeAgo(item.created_at)}</span>
          </div>
          <button className="sidebar-delete" onClick={e => { e.stopPropagation(); onDelete(item.id); }} title="Delete"><Trash2 size={13}/></button>
          <ChevronRight size={13} className="sidebar-chevron"/>
        </div>
      ))}
    </div>
  );
}
