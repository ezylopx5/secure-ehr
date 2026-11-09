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
      <section className="card">
        <div className="section-header">
          <div>
            <h2>Tamper-Evident Audit Blockchain</h2>
            <p className="muted">
              Every state transition is linked via SHA-256 block hashes and signed with the KeyManager&apos;s HKDF-derived HMAC-SHA256 audit key.
            </p>
          </div>
          <div className="btn-row">
            <button type="button" className="btn-secondary" onClick={() => void loadChain()} disabled={loading}>
              Refresh Blocks
            </button>
            <button type="button" className="btn-primary" onClick={() => void handleVerify()} disabled={loading}>
              Verify Chain &amp; HMAC Signatures
            </button>
          </div>
        </div>

        {error && <div className="alert-banner">{error}</div>}

        {verification && (
          <div className={`verify-banner ${verification.valid ? "ok" : "bad"}`}>
            <strong>
              {verification.valid ? "CHAIN INTEGRITY VERIFIED" : "CHAIN TAMPERING DETECTED"}
            </strong>
            <span>Blocks verified: {verification.length}</span>
            {verification.reason && <span>Reason: {verification.reason}</span>}
          </div>
        )}

        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Timestamp (UTC)</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Resource</th>
                <th>Prev Hash → Block Hash</th>
                <th>HMAC-SHA256</th>
                <th>Details</th>
              </tr>
            </thead>
            <tbody>
              {blocks.map((b) => (
                <tr key={b.index}>
                  <td>
                    <code>#{b.index}</code>
                  </td>
                  <td>{new Date(b.timestamp).toLocaleString()}</td>
                  <td>
                    <code>{b.actor}</code>
                  </td>
                  <td>
                    <span className="badge">{b.action}</span>
                  </td>
                  <td>
                    <code>{b.resource}</code>
                  </td>
                  <td>
                    <code title={`prev: ${b.prev_hash}\ncurr: ${b.block_hash}`}>
                      {b.prev_hash.slice(0, 10)}… → {b.block_hash.slice(0, 10)}…
                    </code>
                  </td>
                  <td>
                    <code title={b.hmac_sig}>{b.hmac_sig.slice(0, 12)}…</code>
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
