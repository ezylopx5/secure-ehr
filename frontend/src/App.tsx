import React, { useState } from "react";
import { ActiveTab, Layout } from "./components/Layout";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { AuditChainPage } from "./pages/AuditChainPage";
import { LoginPage } from "./pages/LoginPage";
import { PatientWorkspacePage } from "./pages/PatientWorkspacePage";

function AuthenticatedApp() {
  const { user, loading } = useAuth();
  const [activeTab, setActiveTab] = useState<ActiveTab>("workspace");

  if (loading && !user) {
    return <div className="loading-screen">Initializing cryptographic session…</div>;
  }

  if (!user) {
    return <LoginPage />;
  }

  return (
    <Layout activeTab={activeTab} onSelectTab={setActiveTab}>
      {activeTab === "audit" && (user.role === "admin" || user.role === "auditor") ? (
        <AuditChainPage />
      ) : (
        <PatientWorkspacePage />
      )}
    </Layout>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AuthenticatedApp />
    </AuthProvider>
  );
}
