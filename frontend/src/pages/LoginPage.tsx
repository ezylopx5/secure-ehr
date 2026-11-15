import React, { useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";

const DEMO_ACCOUNTS = [
  {
    role: "Doctor",
    initials: "PS",
    name: "Dr. Priya Shah",
    dept: "Cardiology • Primary Physician",
    username: "doctor1",
    password: "Doctor12345",
    summary: "Decrypt consented records, run CKKS disease models & author CP-ABE policies",
  },
  {
    role: "Patient",
    initials: "AP",
    name: "Aarav Patel",
    dept: "Patient Portal • MRN-DEMO-0001",
    username: "patient1",
    password: "Patient12345",
    summary: "Inspect personal lab panels, review AI risk drivers & grant/revoke doctor access",
  },
  {
    role: "Auditor",
    initials: "SC",
    name: "Security Compliance",
    dept: "Zero-Knowledge Integrity Audit",
    username: "auditor1",
    password: "Auditor12345",
    summary: "Verify SHA-256 record digests & validate the HMAC-SHA256 audit blockchain",
  },
  {
    role: "Admin",
    initials: "SA",
    name: "System Administrator",
    dept: "Hospital Operations • Break-Glass",
    username: "admin",
    password: "Admin12345",
    summary: "Onboard encrypted patient profiles, oversee governance & audit system health",
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
        setLocalMsg("Account created and BN254 CP-ABE key pair issued. Signing in…");
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
          <div>
            <div className="auth-brand">
              <div className="brand-mark">
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  <path d="M9 12h6" />
                  <path d="M12 9v6" />
                </svg>
              </div>
              <div>
                <span className="auth-brand-name">AegisEHR</span>
                <span className="auth-brand-tag">Clinical Cryptographic Platform</span>
              </div>
            </div>

            <div className="auth-hero">
              <div className="auth-kicker">ZERO-TRUST HEALTHCARE INFRASTRUCTURE</div>
              <h1>Privacy-Preserving Clinical Intelligence</h1>
              <p>
                Every medical record is sealed with per-row HKDF AES-256-GCM keys, shared across departments via BN254 elliptic-curve pairings, and evaluated under CKKS homomorphic encryption.
              </p>
            </div>

            <div className="auth-metrics-grid">
              <div className="auth-metric-box">
                <span className="auth-metric-val">AES-256-GCM</span>
                <span className="auth-metric-lbl">Per-Row HKDF Envelope</span>
              </div>
              <div className="auth-metric-box">
                <span className="auth-metric-val">BN254 CP-ABE</span>
                <span className="auth-metric-lbl">Bilinear Pairing Policy</span>
              </div>
              <div className="auth-metric-box">
                <span className="auth-metric-val">CKKS N=8192</span>
                <span className="auth-metric-lbl">Homomorphic ML Scoring</span>
              </div>
              <div className="auth-metric-box">
                <span className="auth-metric-val">HL7 FHIR R4</span>
                <span className="auth-metric-lbl">HMAC Signed Bundles</span>
              </div>
            </div>
          </div>

          <div className="auth-features">
            <div className="feature-pill">
              <span className="dot dot-teal" />
              <div>
                <strong>Cryptographic Envelope &amp; Tamper Proofing</strong>
                <span>Row-UUID AAD binding + canonical SHA-256 integrity verification</span>
              </div>
            </div>
            <div className="feature-pill">
              <span className="dot dot-blue" />
              <div>
                <strong>Explainable Multi-Disease AI</strong>
                <span>Diabetes, Heart, Liver &amp; Kidney XGBoost + TreeSHAP + 90% Conformal bounds</span>
              </div>
            </div>
            <div className="feature-pill">
              <span className="dot dot-indigo" />
              <div>
                <strong>LangGraph Assistant &amp; Immutable Ledger</strong>
                <span>Automated PII scrubbing with an append-only HMAC-SHA256 audit blockchain</span>
              </div>
            </div>
          </div>
        </div>

        <div className="auth-right">
          <div className="auth-form-header">
            <h2>{mode === "login" ? "Sign in to Clinical Portal" : "Register Patient Account"}</h2>
            <p>Authenticate with credentials or launch an instant role persona below.</p>
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
            <div className="form-row-2">
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
            </div>

            {mode === "register" && (
              <div className="form-row-2">
                <label>
                  <span>Full Legal Name</span>
                  <input
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    placeholder="e.g. Meera Sharma"
                    required
                  />
                </label>
                <label>
                  <span>Email Address</span>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="name@hospital.org"
                    required
                  />
                </label>
              </div>
            )}

            {(error || localMsg) && <div className="banner banner-error">{localMsg || error}</div>}

            <button type="submit" className="btn-primary btn-full btn-lg" disabled={loading}>
              {loading
                ? "Authenticating & Loading Key Ring…"
                : mode === "login"
                  ? "Enter Clinical Workspace →"
                  : "Generate Keys & Register →"}
            </button>
          </form>

          <div className="demo-divider">
            <span>One-Click Persona Launch</span>
          </div>

          <div className="demo-grid">
            {DEMO_ACCOUNTS.map((acct) => (
              <button
                key={acct.username}
                type="button"
                className={
                  username === acct.username ? "demo-card demo-card-selected" : "demo-card"
                }
                onClick={() => {
                  setUsername(acct.username);
                  setPassword(acct.password);
                  void login(acct.username, acct.password);
                }}
              >
                <div className="demo-card-top">
                  <div className="demo-card-identity">
                    <span className={`demo-avatar role-${acct.role.toLowerCase()}`}>
                      {acct.initials}
                    </span>
                    <div>
                      <strong>{acct.name}</strong>
                      <span className="demo-card-sub">{acct.dept}</span>
                    </div>
                  </div>
                  <span className={`role-badge role-${acct.role.toLowerCase()}`}>
                    {acct.role}
                  </span>
                </div>
                <p className="demo-card-desc">{acct.summary}</p>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
