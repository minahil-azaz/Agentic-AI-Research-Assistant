import { useState, useEffect, useCallback, useRef } from "react";
import { BookOpen, PanelLeftClose, PanelLeft, Sparkles, LogOut, User, Plus } from "lucide-react";
import AuthPage       from "./components/AuthPage";
import ChatInput      from "./components/ChatInput";
import AgentStatus    from "./components/AgentStatus";
import ReportDisplay  from "./components/ReportDisplay";
import HistorySidebar from "./components/HistorySidebar";
import { createResearch, streamResearch, listResearch, getResearch, deleteResearch, getHealth } from "./api/research";
import { logout, getUser, getToken } from "./api/auth";
import "./styles.css";

const RUNNING      = ["pending", "planning", "searching", "scraping", "embedding", "writing"];
const POLL_MS      = 3000;
const POLL_TIMEOUT = 10 * 60 * 1000;

export default function App() {
  const [authed,        setAuthed]        = useState(() => !!getToken());
  const [user,          setUser]          = useState(() => getUser());
  const [sidebarOpen,   setSidebarOpen]   = useState(true);
  const [history,       setHistory]       = useState([]);
  const [historyError,  setHistoryError]  = useState(null);
  const [activeId,      setActiveId]      = useState(null);
  const [isLoading,     setIsLoading]     = useState(false);
  const [currentStep,   setCurrentStep]   = useState(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [subSearches,   setSubSearches]   = useState([]);
  const [sourceCount,   setSourceCount]   = useState(0);
  const [report,        setReport]        = useState(null);
  const [sources,       setSources]       = useState([]);
  const [activeQuery,   setActiveQuery]   = useState("");
  const [error,         setError]         = useState(null);
  const [health,        setHealth]        = useState(null);

  // Stops the stream/poll for whatever query is on screen. Events from a query the
  // user navigated away from are ignored via viewRef so they can't overwrite the view.
  const stopRef = useRef(() => {});
  const viewRef = useRef(0);

  const refreshHistory = useCallback(() => {
    return listResearch()
      .then(h => { setHistory(h); setHistoryError(null); })
      .catch(() => setHistoryError("Could not load history."));
  }, []);

  useEffect(() => {
    if (authed) refreshHistory();
  }, [authed, refreshHistory]);

  useEffect(() => {
    getHealth().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => () => stopRef.current(), []);

  const resetState = () => {
    setCurrentStep(null); setStatusMessage(""); setSubSearches([]);
    setSourceCount(0); setReport(null); setSources([]); setError(null);
  };

  // Detach from the current query and start a fresh view. Returns a guard that
  // is true only while that view is still the one on screen.
  const beginView = () => {
    stopRef.current();
    stopRef.current = () => {};
    const view = ++viewRef.current;
    resetState();
    setIsLoading(false);
    return () => viewRef.current === view;
  };

  const showResult = (q) => {
    if (q.status === "done") {
      setReport(q.report);
      setSources(q.sources || []);
      setCurrentStep("done");
      setIsLoading(false);
    } else if (q.status === "error") {
      setError(q.status_message || "Research failed.");
      setIsLoading(false);
    } else {
      setCurrentStep(q.status === "pending" ? "planning" : q.status);
      setStatusMessage(q.status_message || "Working…");
      setIsLoading(true);
    }
  };

  // Fallback when the live stream isn't available: poll the stored record.
  const pollQuery = (id, isCurrent) => {
    const started = Date.now();
    let timer;
    const tick = async () => {
      if (!isCurrent()) return;
      try {
        const q = await getResearch(id);
        if (!isCurrent()) return;
        showResult(q);
        if (!RUNNING.includes(q.status)) { refreshHistory(); return; }
      } catch {
        if (!isCurrent()) return;
      }
      if (Date.now() - started > POLL_TIMEOUT) {
        setIsLoading(false);
        setError("This research is taking too long or was interrupted (for example by a server restart). Try running it again.");
        return;
      }
      timer = setTimeout(tick, POLL_MS);
    };
    tick();
    stopRef.current = () => clearTimeout(timer);
  };

  const handleSubmit = useCallback(async (query) => {
    const isCurrent = beginView();
    setIsLoading(true);
    setActiveQuery(query);
    setCurrentStep("planning");
    setStatusMessage("Starting…");

    let queryId;
    try {
      const { id } = await createResearch(query);
      queryId = id;
    } catch {
      if (!isCurrent()) return;
      setError("Failed to start research. Is the backend running?");
      setIsLoading(false);
      setCurrentStep(null);
      return;
    }
    if (!isCurrent()) return;
    setActiveId(queryId);
    refreshHistory();

    const close = streamResearch(queryId, (type, data) => {
      if (!isCurrent()) return;
      switch (type) {
        case "connected":    break;
        case "status":       setCurrentStep(data.step); setStatusMessage(data.message); break;
        case "plan":         setSubSearches(data.sub_searches || []); break;
        case "source_found": setSourceCount(n => n + 1); break;
        case "report":       setReport(data.report); break;
        case "sources":      setSources(data.sources || []); break;
        case "running":      // stream re-opened while the agent is still working elsewhere
        case "disconnected":
          close();
          pollQuery(queryId, isCurrent);
          break;
        case "error":
          setError(data.message || "Something went wrong.");
          setIsLoading(false);
          close();
          refreshHistory();
          break;
        case "done":
          close();
          // Reload the stored record so the view matches what history will show
          getResearch(queryId)
            .then(q => { if (isCurrent()) showResult(q); })
            .catch(() => { if (isCurrent()) setIsLoading(false); })
            .finally(refreshHistory);
          break;
        default: break;
      }
    });
    stopRef.current = close;
  }, [refreshHistory]);

  const handleSelectHistory = useCallback(async (item) => {
    if (item.id === activeId && (isLoading || report)) return;
    const isCurrent = beginView();
    setActiveId(item.id);
    setActiveQuery(item.query);
    setIsLoading(true);
    try {
      const full = await getResearch(item.id);
      if (!isCurrent()) return;
      showResult(full);
      if (RUNNING.includes(full.status)) pollQuery(item.id, isCurrent);
    } catch {
      if (!isCurrent()) return;
      setIsLoading(false);
      setError("Could not load this report.");
    }
  }, [activeId, isLoading, report]);

  const handleNew = () => {
    beginView();
    setActiveId(null);
    setActiveQuery("");
  };

  const handleDelete = useCallback(async (id) => {
    if (!window.confirm("Delete this research from your history?")) return;
    try {
      await deleteResearch(id);
      setHistory(h => h.filter(q => q.id !== id));
      if (activeId === id) { beginView(); setActiveId(null); setActiveQuery(""); }
    } catch {
      setHistoryError("Could not delete that item. Try again.");
    }
  }, [activeId]);

  const handleAuth = () => { setAuthed(true); setUser(getUser()); };

  const handleLogout = async () => {
    beginView();
    await logout();
    setAuthed(false); setUser(null); setHistory([]); setActiveId(null); setActiveQuery("");
  };

  if (!authed) return <AuthPage onAuth={handleAuth}/>;

  const showWelcome = !isLoading && !report && !error && !activeQuery;

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
        <div className="sidebar-header">
          <div className="logo"><BookOpen size={17}/><span>Research</span></div>
          <div className="sidebar-header-btns">
            <button className="icon-btn" onClick={handleNew} title="New research"><Plus size={17}/></button>
            <button className="icon-btn" onClick={() => setSidebarOpen(false)} title="Hide sidebar"><PanelLeftClose size={17}/></button>
          </div>
        </div>
        <div className="sidebar-scroll">
          {historyError && (
            <div className="sidebar-error">
              {historyError} <button className="link-btn" onClick={refreshHistory}>Retry</button>
            </div>
          )}
          <HistorySidebar history={history} onSelect={handleSelectHistory} onDelete={handleDelete} activeId={activeId}/>
        </div>
        <div className="sidebar-footer">
          <div className="sidebar-user"><User size={13}/><span>{user?.username || "User"}</span></div>
          <button className="icon-btn" onClick={handleLogout} title="Log out"><LogOut size={14}/></button>
        </div>
      </aside>

      {/* ── Main ── */}
      <main className="main">
        <header className="topbar">
          {!sidebarOpen && <button className="icon-btn" onClick={() => setSidebarOpen(true)} title="Show sidebar"><PanelLeft size={17}/></button>}
          <div className="topbar-title"><Sparkles size={15}/><span>AI Research Assistant</span></div>
          <div className="topbar-stack">
            {health && (
              <span className={`badge ${health.gemini_mock ? "badge-warn" : ""}`}
                    title={health.gemini_mock ? "No GEMINI_API_KEY or FORCE_MOCK_GEMINI=True: reports are extractive mocks" : "Active Gemini model"}>
                {health.gemini_mock ? "Gemini: mock" : health.gemini_model}
              </span>
            )}
            {health && !health.tavily_configured && <span className="badge badge-warn" title="TAVILY_API_KEY is not set">Tavily: missing key</span>}
            {health?.tavily_configured && <span className="badge">Tavily</span>}
            {health?.embeddings_mock
              ? <span className="badge badge-warn" title="FORCE_MOCK_EMBEDDINGS=True: retrieval uses keyword hashing">Embeddings: mock</span>
              : <span className="badge">pgvector</span>}
          </div>
        </header>

        <div className="content">
          {showWelcome && (
            <div className="welcome">
              <h1 className="welcome-title">What do you want to<br/><em>research today?</em></h1>
              <p className="welcome-sub">Ask any question. The agent plans sub-searches, reads sources, indexes them in pgvector, and writes a cited report — fully automated.</p>
            </div>
          )}

          {activeQuery && (
            <div className="active-query-label">
              <span className="active-query-tag">Query</span>
              <p className="active-query-text">{activeQuery}</p>
            </div>
          )}

          {isLoading && currentStep && (
            <AgentStatus currentStep={currentStep} statusMessage={statusMessage} subSearches={subSearches} sourceCount={sourceCount}/>
          )}

          {error && (
            <div className="error-box">
              <strong>Error:</strong> {error}
              {activeQuery && !isLoading && (
                <button className="link-btn" onClick={() => handleSubmit(activeQuery)}>Try again</button>
              )}
            </div>
          )}

          {report && <ReportDisplay report={report} sources={sources} query={activeQuery}
                                   onRerun={!isLoading && activeQuery ? () => handleSubmit(activeQuery) : null}/>}
        </div>

        <div className="input-wrapper">
          <ChatInput onSubmit={handleSubmit} isLoading={isLoading}/>
        </div>
      </main>
    </div>
  );
}
