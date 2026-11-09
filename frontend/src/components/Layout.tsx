import React from "react";
import { useAuth } from "../context/AuthContext";

export type ActiveTab = "workspace" | "audit";

interface LayoutProps {
  activeTab: ActiveTab;
  onSelectTab: (tab: ActiveTab) => void;
  children: React.ReactNode;
}

export function Layout({ activeTab, onSelectTab, children }: LayoutProps) {
  const { user, login, logout } = useAuth();
  const canViewAudit = user?.role === "admin" || user?.role === "auditor";

  const quickSwitch = async (username: string, password: string) => {
    await login(username, password);
    if (username === "auditor1") {
      onSelectTab("audit");
    } else {
      onSelectTab("workspace");
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-left">
          <div className="brand-mark" aria-hidden="true">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M9 12h6" />
              <path d="M12 9v6" />
            </svg>
          </div>
          <div className="brand-text">
            <span className="brand-title">AegisEHR</span>
            <span className="brand-divider">/</span>
            <span className="brand-section">Clinical Portal</span>
          </div>

          <nav className="nav-tabs">
            <button
              type="button"
              className={activeTab === "workspace" ? "tab-btn active" : "tab-btn"}
              onClick={() => onSelectTab("workspace")}
            >
              Patient Workspace
            </button>
            {canViewAudit && (
              <button
                type="button"
                className={activeTab === "audit" ? "tab-btn active" : "tab-btn"}
                onClick={() => onSelectTab("audit")}
              >
                Audit Ledger
              </button>
            )}
          </nav>
        </div>

        <div className="topbar-right">
          <div className="role-switcher" title="Switch demo role">
            <span className="switcher-label">View as</span>
            <button
              type="button"
              className={user?.username === "doctor1" ? "switch-chip active" : "switch-chip"}
              onClick={() => void quickSwitch("doctor1", "Doctor12345")}
            >
              Doctor
            </button>
            <button
              type="button"
              className={user?.username === "patient1" ? "switch-chip active" : "switch-chip"}
              onClick={() => void quickSwitch("patient1", "Patient12345")}
            >
              Patient
            </button>
            <button
              type="button"
              className={user?.username === "auditor1" ? "switch-chip active" : "switch-chip"}
              onClick={() => void quickSwitch("auditor1", "Auditor12345")}
            >
              Auditor
            </button>
            <button
              type="button"
              className={user?.username === "admin" ? "switch-chip active" : "switch-chip"}
              onClick={() => void quickSwitch("admin", "Admin12345")}
            >
              Admin
            </button>
          </div>

          {user && (
            <div className="user-profile">
              <div className="user-avatar">
                {user.full_name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")
                  .slice(0, 2)
                  .toUpperCase()}
              </div>
              <div className="user-meta">
                <div className="user-name-row">
                  <span className="user-name">{user.full_name}</span>
                  <span className={`role-badge role-${user.role}`}>{user.role}</span>
                </div>
                <span className="user-dept">
                  {user.department} • {user.organization}
                </span>
              </div>
              <button type="button" className="btn-ghost" onClick={logout}>
                Sign out
              </button>
            </div>
          )}
        </div>
      </header>

      <main className="main-container">{children}</main>
    </div>
  );
}
