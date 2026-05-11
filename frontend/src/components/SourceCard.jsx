import { ExternalLink, Globe } from "lucide-react";

const getDomain = (url) => { try { return new URL(url).hostname.replace("www.", ""); } catch { return url; } };
const getFavicon = (url) => { try { return `https://www.google.com/s2/favicons?domain=${new URL(url).hostname}&sz=32`; } catch { return null; } };

export default function SourceCard({ source, index }) {
  const favicon = getFavicon(source.url);
  return (
    <a href={source.url} target="_blank" rel="noopener noreferrer" className="source-card">
      <div className="source-card-header">
        <div className="source-number">{index + 1}</div>
        {favicon
          ? <img src={favicon} alt="" className="source-favicon" onError={e => e.target.style.display="none"}/>
          : <Globe size={14} className="source-globe"/>}
        <span className="source-domain">{getDomain(source.url)}</span>
        <ExternalLink size={12} className="source-ext"/>
      </div>
      <p className="source-title">{source.title || "Untitled"}</p>
      {source.snippet && <p className="source-snippet">{source.snippet.slice(0, 120)}…</p>}
    </a>
  );
}
