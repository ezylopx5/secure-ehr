import React, { useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const DEMO_ACCOUNTS = [
  {
    role: "Doctor",
    name: "Dr. Priya Shah",
    dept: "Cardiology",
    username: "doctor1",
    password: "Doctor12345",
    summary: "Manage clinical records, run encrypted risk models & share policies",
  },
  {
    role: "Patient",
    name: "Aarav Patel",
    dept: "Patient Portal",
    username: "patient1",
    password: "Patient12345",
    summary: "Review personal health records, risk reports & manage doctor consent",
  },
  {
    role: "Auditor",
    name: "Security Compliance",
    dept: "Audit & Integrity",
    username: "auditor1",
    password: "Auditor12345",
    summary: "Verify record SHA-256 digests & inspect the HMAC audit ledger",
  },
  {
    role: "Admin",
    name: "System Administrator",
    dept: "Hospital Operations",
    username: "admin",
    password: "Admin12345",
    summary: "Onboard patients, manage access & oversee platform health",
  },
];

export function LoginPage() {
  const { login, error, loading } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("doctor1");
  const [password, setPassword] = useState("Doctor12345");
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [localMsg, setLocalMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalMsg(null);
    if (mode === "register") {
      try {
        await api.register({
          username,
          email,
          password,
          full_name: fullName,
          organization: "nitsurat-hospital",
          department: "general",
        });
        setLocalMsg("Account created and cryptographic key pair issued. Signing in…");
        await login(username, password);
      } catch (err) {
        setLocalMsg(err instanceof Error ? err.message : "Registration failed");
      }
      return;
    }
    try {
      await login(username, password);
    } catch {
      // handled by context
    }
  };

  return (
    <div className="auth-layout">
      <div className="auth-shell">
        <div className="auth-left">
          <div className="auth-brand">
            <div className="brand-mark">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="M9 12h6" />
                <path d="M12 9v6" />
              </svg>
            </div>
            <span>AegisEHR</span>
          </div>

          <div className="auth-hero">
            <h1>Privacy-Preserving Clinical Intelligence</h1>
            <p>
              End-to-end encrypted patient records, fine-grained attribute access control, and homomorphic disease risk modeling in one clinical workspace.
            </p>
          </div>

          <div className="auth-features">
            <div className="feature-pill">
              <span className="dot dot-teal" />
              <div>
                <strong>Encrypted at Rest</strong>
                <span>Per-record AES-256-GCM envelope keys with SHA-256 verification</span>
              </div>
            </div>
            <div className="feature-pill">
              <span className="dot dot-blue" />
              <div>
                <strong>Homomorphic Risk Scoring</strong>
                <span>CKKS encrypted inference with local TreeSHAP explainability</span>
              </div>
            </div>
            <div className="feature-pill">
              <span className="dot dot-indigo" />
              <div>
                <strong>Patient-Controlled Consent</strong>
                <span>Real-time consent enforcement &amp; tamper-evident audit chain</span>
              </div>
            </div>
          </div>
        </div>

        <div className="auth-right">
          <div className="auth-form-header">
            <h2>{mode === "login" ? "Sign in to your account" : "Create a patient account"}</h2>
            <p>Select a demo profile below or sign in with credentials.</p>
          </div>

          <div className="segmented-control">
            <button
              type="button"
              className={mode === "login" ? "seg-btn active" : "seg-btn"}
              onClick={() => setMode("login")}
            >
              Sign In
            </button>
            <button
              type="button"
              className={mode === "register" ? "seg-btn active" : "seg-btn"}
              onClick={() => setMode("register")}
            >
              New Patient Registration
            </button>
          </div>

          <form onSubmit={(e) => void handleSubmit(e)} className="form-stack">
            <label>
              <span>Username</span>
              <input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="e.g. doctor1"
                required
                minLength={3}
              />
            </label>

            {mode === "register" && (
              <>
                <label>
                  <span>Full Name</span>
                  <input
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="Full legal name"
                    required
                  />
                </label>
                <label>
                  <span>Email Address</span>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@example.com"
                    required
                  />
                </label>
              </>
            )}

            <label>
              <span>Password</span>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </label>

            {(error || localMsg) && <div className="banner banner-error">{localMsg || error}</div>}

            <button type="submit" className="btn-primary btn-full" disabled={loading}>
              {loading
                ? "Signing in…"
                : mode === "login"
                  ? "Continue to Workspace"
                  : "Register & Continue"}
            </button>
          </form>

          <div className="demo-divider">
            <span>Quick Demo Access</span>
          </div>

          <div className="demo-grid">
            {DEMO_ACCOUNTS.map((acct) => (
              <button
                key={acct.username}
                type="button"
                className="demo-card"
                onClick={() => {
                  setUsername(acct.username);
                  setPassword(acct.password);
                  void login(acct.username, acct.password);
                }}
              >
                <div className="demo-card-top">
                  <strong>{acct.name}</strong>
                  <span className={`role-badge role-${acct.role.toLowerCase()}`}>
                    {acct.role}
                  </span>
                </div>
                <span className="demo-card-sub">{acct.dept}</span>
                <p className="demo-card-desc">{acct.summary}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
