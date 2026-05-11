import { useState } from "react";
import { BookOpen, Eye, EyeOff, Loader2 } from "lucide-react";
import { login, register } from "../api/auth";

export default function AuthPage({ onAuth }) {
  const [mode,     setMode]     = useState("login");
  const [form,     setForm]     = useState({ username: "", email: "", password: "", password2: "" });
  const [errors,   setErrors]   = useState({});
  const [loading,  setLoading]  = useState(false);
  const [showPass, setShowPass] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrors({});
    setLoading(true);
    try {
      if (mode === "login") await login({ username: form.username, password: form.password });
      else                  await register(form);
      onAuth();
    } catch (err) {
      if (err && typeof err === "object") {
        // Map the backend 'error' key to 'general' so it displays in the UI
        const newErrors = { ...err };
        if (err.error && !err.general) newErrors.general = err.error;
        setErrors(newErrors);
      } else {
        setErrors({ general: "Something went wrong. Please try again." });
      }
    } finally {
      setLoading(false);
    }
  };

  const switchMode = () => { setMode(m => m === "login" ? "register" : "login"); setErrors({}); };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <div className="auth-logo"><BookOpen size={26} /><span>AI Research Assistant</span></div>
        <h2 className="auth-title">{mode === "login" ? "Welcome back" : "Create account"}</h2>
        <p className="auth-sub">{mode === "login" ? "Sign in to your account." : "Start for free — no credit card needed."}</p>

        {errors.general && <div className="auth-error">{errors.general}</div>}

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="auth-field">
            <label>Username</label>
            <input type="text" value={form.username} onChange={set("username")} placeholder="your_username" disabled={loading} autoComplete="username" />
            {errors.username && <span className="field-error">{errors.username}</span>}
          </div>

          {mode === "register" && (
            <div className="auth-field">
              <label>Email</label>
              <input type="email" value={form.email} onChange={set("email")} placeholder="you@example.com" disabled={loading} autoComplete="email" />
              {errors.email && <span className="field-error">{errors.email}</span>}
            </div>
          )}

          <div className="auth-field">
            <label>Password</label>
            <div className="pass-wrap">
              <input type={showPass ? "text" : "password"} value={form.password} onChange={set("password")} placeholder={mode === "register" ? "Min. 8 characters" : "••••••••"} disabled={loading} autoComplete={mode === "login" ? "current-password" : "new-password"} />
              <button type="button" className="eye-btn" onClick={() => setShowPass(v => !v)}>{showPass ? <EyeOff size={15}/> : <Eye size={15}/>}</button>
            </div>
            {errors.password && <span className="field-error">{errors.password}</span>}
          </div>

          {mode === "register" && (
            <div className="auth-field">
              <label>Confirm password</label>
              <div className="pass-wrap">
                <input type={showPass ? "text" : "password"} value={form.password2} onChange={set("password2")} placeholder="Repeat password" disabled={loading} autoComplete="new-password" />
              </div>
              {errors.password2 && <span className="field-error">{errors.password2}</span>}
            </div>
          )}

          <button type="submit" className="auth-btn" disabled={loading}>
            {loading
              ? <><Loader2 size={16} className="spin" />{mode === "login" ? "Signing in…" : "Creating account…"}</>
              : mode === "login" ? "Sign in" : "Create account"}
          </button>
        </form>

        <p className="auth-switch">
          {mode === "login" ? "Don't have an account?" : "Already have an account?"}
          <button className="auth-switch-btn" onClick={switchMode}>{mode === "login" ? "Register" : "Sign in"}</button>
        </p>
      </div>
    </div>
  );
}
