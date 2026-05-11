import { CheckCircle2, Circle, Loader2 } from "lucide-react";

const STEPS = [
  { key: "planning",  label: "Planning"  },
  { key: "searching", label: "Searching" },
  { key: "scraping",  label: "Reading"   },
  { key: "embedding", label: "Indexing"  },
  { key: "writing",   label: "Writing"   },
];

export default function AgentStatus({ currentStep, statusMessage, subSearches, sourceCount }) {
  const idx = STEPS.findIndex(s => s.key === currentStep);

  return (
    <div className="agent-status">
      <div className="pipeline">
        {STEPS.map((step, i) => {
          const done   = idx > i;
          const active = idx === i;
          return (
            <div key={step.key} className={`pipeline-step ${done ? "done" : active ? "active" : "idle"}`}>
              <div className="step-icon">
                {done   ? <CheckCircle2 size={16}/> :
                 active ? <Loader2 size={16} className="spin"/> :
                          <Circle size={16}/>}
              </div>
              <div className="step-info">
                <span className="step-label">{step.label}</span>
                {active && <span className="step-desc">{statusMessage}</span>}
              </div>
              {i < STEPS.length - 1 && <div className={`step-connector ${done ? "done" : ""}`}/>}
            </div>
          );
        })}
      </div>

      {subSearches?.length > 0 && (
        <div className="sub-searches">
          <p className="sub-label">Search queries</p>
          {subSearches.map((q, i) => (
            <div key={i} className="sub-query"><span className="sub-idx">{i+1}</span><span>{q}</span></div>
          ))}
        </div>
      )}

      {sourceCount > 0 && (
        <p className="source-count-live">{sourceCount} source{sourceCount !== 1 ? "s" : ""} found…</p>
      )}
    </div>
  );
}
