import { useState, useEffect, useCallback } from "react";
import { BookOpen, PanelLeftClose, PanelLeft, Sparkles, LogOut, User } from "lucide-react";
import AuthPage       from "./components/AuthPage";
import ChatInput      from "./components/ChatInput";
import AgentStatus    from "./components/AgentStatus";
import ReportDisplay  from "./components/ReportDisplay";
import HistorySidebar from "./components/HistorySidebar";
import { createResearch, streamResearch, listResearch, getResearch, deleteResearch } from "./api/research";
import { logout, getUser, getToken } from "./api/auth";
import "./styles.css";

export default function App() {
  const [authed,        setAuthed]        = useState(() => !!getToken());
  const [user,          setUser]          = useState(() => getUser());
  const [sidebarOpen,   setSidebarOpen]   = useState(true);
  const [history,       setHistory]       = useState([]);
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

  useEffect(() => {
    if (authed) listResearch().then(setHistory).catch(() => {});
  }, [authed]);

  const handleAuth = () => { setAuthed(true); setUser(getUser()); };

  const handleLogout = async () => {
    await logout();
    setAuthed(false); setUser(null); setHistory([]); resetState();
  };

  const resetState = () => {
    setCurrentStep(null); setStatusMessage(""); setSubSearches([]);
    setSourceCount(0); setReport(null); setSources([]); setError(null);
  };

  const handleSubmit = useCallback(async (query) => {
    resetState();
    setIsLoading(true);
    setActiveQuery(query);

    let queryId;
    try {
      const { id } = await createResearch(query);
      queryId = id;
      setActiveId(id);
    } catch {
      setError("Failed to start research. Is the backend running?");
      setIsLoading(false);
      return;
    }

    const cleanup = streamResearch(queryId, (type, data) => {
      switch (type) {
        case "connected":    break;
        case "status":       setCurrentStep(data.step); setStatusMessage(data.message); break;
        case "plan":         setSubSearches(data.sub_searches || []); break;
        case "source_found": setSourceCount(n => n + 1); break;
        case "report":       setReport(data.report); break;
        case "sources":      setSources(data.sources || []); break;
        case "done":
          setIsLoading(false);
          setCurrentStep("done");
          getResearch(queryId).then(q => { setSources(q.sources || []); listResearch().then(setHistory).catch(() => {}); });
          cleanup();
          break;
        case "error":
          setError(data.message || "Something went wrong.");
          setIsLoading(false);
          cleanup();
          break;
        default: break;
      }
    });
  }, []);

  const handleSelectHistory = useCallback(async (item) => {
    if (isLoading) return;
    resetState();
    setActiveId(item.id);
    setActiveQuery(item.query);
    if (item.status === "done") {
      try {
        const full = await getResearch(item.id);
        setReport(full.report);
        setSources(full.sources || []);
        setCurrentStep("done");
      } catch { setError("Could not load this report."); }
    } else {
      setError(`Query status: ${item.status}`);
    }
  }, [isLoading]);

  const handleDelete = useCallback(async (id) => {
    try {
      await deleteResearch(id);
      setHistory(h => h.filter(q => q.id !== id));
      if (activeId === id) { resetState(); setActiveId(null); setActiveQuery(""); }
    } catch {}
  }, [activeId]);

  if (!authed) return <AuthPage onAuth={handleAuth}/>;

  const showWelcome = !isLoading && !report && !error && !currentStep;

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
        <div className="sidebar-header">
          <div className="logo"><BookOpen size={17}/><span>Research</span></div>
          <button className="icon-btn" onClick={() => setSidebarOpen(false)}><PanelLeftClose size={17}/></button>
        </div>
        <div className="sidebar-scroll">
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
          {!sidebarOpen && <button className="icon-btn" onClick={() => setSidebarOpen(true)}><PanelLeft size={17}/></button>}
          <div className="topbar-title"><Sparkles size={15}/><span>AI Research Assistant</span></div>
          <div className="topbar-stack">
            <span className="badge">Gemini 1.5 Flash</span>
            <span className="badge">Tavily</span>
            <span className="badge">pgvector</span>
          </div>
        </header>

        <div className="content">
          {showWelcome && (
            <div className="welcome">
              <h1 className="welcome-title">What do you want to<br/><em>research today?</em></h1>
              <p className="welcome-sub">Ask any question. The agent plans sub-searches, reads sources, indexes them in pgvector, and writes a cited report — fully automated.</p>
            </div>
          )}

          {activeQuery && (isLoading || report) && (
            <div className="active-query-label">
              <span className="active-query-tag">Query</span>
              <p className="active-query-text">{activeQuery}</p>
            </div>
          )}

          {isLoading && currentStep && (
            <AgentStatus currentStep={currentStep} statusMessage={statusMessage} subSearches={subSearches} sourceCount={sourceCount}/>
          )}

          {error && <div className="error-box"><strong>Error:</strong> {error}</div>}

          {report && <ReportDisplay report={report} sources={sources}/>}
        </div>

        <div className="input-wrapper">
          <ChatInput onSubmit={handleSubmit} isLoading={isLoading}/>
        </div>
      </main>
    </div>
  );
}
