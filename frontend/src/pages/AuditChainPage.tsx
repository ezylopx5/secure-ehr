import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { AuditBlockView, AuditVerifyView } from "../types";

export function AuditChainPage() {
  const [blocks, setBlocks] = useState<AuditBlockView[]>([]);
  const [verification, setVerification] = useState<AuditVerifyView | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const loadChain = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAuditChain(200);
      setBlocks(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load audit chain");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadChain();
  }, [loadChain]);

  const handleVerify = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.verifyAuditChain();
      setVerification(res);
      await loadChain();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Verification failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="panel-stack">
      <div className="kpi-grid">
        <div className="kpi-card">
          <span className="kpi-label">Chained Audit Blocks</span>
          <div className="kpi-value-row">
            <strong className="kpi-value">{blocks.length}</strong>
            <span className="kpi-tag kpi-tag-blue">Append-Only</span>
          </div>
          <span className="kpi-sub">Genesis + clinical &amp; security events</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Hash Link Function</span>
          <div className="kpi-value-row">
            <strong className="kpi-value">SHA-256</strong>
            <span className="kpi-tag kpi-tag-teal">Canonical JSON</span>
          </div>
          <span className="kpi-sub">prev_hash → block_hash pointer</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Block Authentication</span>
          <div className="kpi-value-row">
            <strong className="kpi-value">HMAC-SHA256</strong>
            <span className="kpi-tag kpi-tag-purple">HKDF Subkey</span>
          </div>
          <span className="kpi-sub">Domain info: ehr:hmac:audit</span>
        </div>

        <div className="kpi-card">
          <span className="kpi-label">Verification Status</span>
          <div className="kpi-value-row">
            <strong className="kpi-value">
              {verification ? (verification.valid ? "VALID" : "TAMPERED") : "READY"}
            </strong>
            <span className="kpi-tag kpi-tag-green">O(n) Verifiable</span>
          </div>
          <span className="kpi-sub">Detects any row mutation or deletion</span>
        </div>
      </div>

      <section className="card">
        <div className="section-header">
          <div>
            <h2>Tamper-Evident Cryptographic Audit Blockchain</h2>
            <p className="muted">
              Every login, record decryption, CP-ABE policy wrap, CKKS prediction, and consent change is cryptographically linked to the preceding block and signed via HMAC-SHA256.
            </p>
          </div>
          <div className="btn-row">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => void loadChain()}
              disabled={loading}
            >
              Refresh Ledger
            </button>
            <button
              type="button"
              className="btn-primary"
              onClick={() => void handleVerify()}
              disabled={loading}
            >
              {loading ? "Verifying Hashes & HMACs…" : "Verify Full Chain & Signatures"}
            </button>
          </div>
        </div>

        {error && <div className="banner banner-error">{error}</div>}

        {verification && (
          <div className={`verify-banner ${verification.valid ? "ok" : "bad"}`}>
            <strong>
              {verification.valid
                ? "✓ CRYPTOGRAPHIC CHAIN INTEGRITY VERIFIED"
                : "✕ CHAIN TAMPERING DETECTED"}
            </strong>
            <span>Blocks verified: {verification.length}</span>
            {verification.reason && <span>Reason: {verification.reason}</span>}
          </div>
        )}

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Seq</th>
                <th>Timestamp (UTC)</th>
                <th>Actor Identity</th>
                <th>Event Action</th>
                <th>Target Resource</th>
                <th>Hash Link (Prev → Current)</th>
                <th>HMAC-SHA256 Signature</th>
                <th>Event Metadata</th>
              </tr>
            </thead>
            <tbody>
              {blocks.map((b) => (
                <tr key={b.index}>
                  <td>
                    <code className="seq-badge">#{b.index}</code>
                  </td>
                  <td className="nowrap">{new Date(b.timestamp).toLocaleString()}</td>
                  <td>
                    <code className="mono-id">{b.actor}</code>
                  </td>
                  <td>
                    <span className="pill pill-blue">{b.action}</span>
                  </td>
                  <td>
                    <code className="mono-id">{b.resource}</code>
                  </td>
                  <td>
                    <code
                      className="hash-chain-cell"
                      title={`prev: ${b.prev_hash}\ncurr: ${b.block_hash}`}
                    >
                      {b.prev_hash.slice(0, 8)}… → {b.block_hash.slice(0, 8)}…
                    </code>
                  </td>
                  <td>
                    <code className="hmac-cell" title={b.hmac_sig}>
                      {b.hmac_sig.slice(0, 12)}…
                    </code>
                  </td>
                  <td>
                    <code className="json-inline">{JSON.stringify(b.details)}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
