import React, { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type {
  ChatMessageView,
  ConsentView,
  DiseaseKey,
  DiseaseSpecView,
  FhirExportView,
  PatientSummary,
  PatientView,
  PredictionCreateResponse,
  PredictionStoredView,
  RecordCategory,
  RecordSummary,
  RecordType,
  RecordView,
} from "../types";

type WorkspaceSubTab = "records" | "predictions" | "assistant" | "governance";

export function PatientWorkspacePage() {
  const { user } = useAuth();
  const [subTab, setSubTab] = useState<WorkspaceSubTab>("records");

  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string | null>(null);
  const [patientView, setPatientView] = useState<PatientView | null>(null);
  const [records, setRecords] = useState<RecordSummary[]>([]);
  const [decryptedRecords, setDecryptedRecords] = useState<Record<string, RecordView>>({});
  const [integrityStatus, setIntegrityStatus] = useState<Record<string, string>>({});
  const [consents, setConsents] = useState<ConsentView[]>([]);
  const [diseases, setDiseases] = useState<DiseaseSpecView[]>([]);
  const [selectedDisease, setSelectedDisease] = useState<DiseaseKey>("diabetes");
  const [featureValues, setFeatureValues] = useState<Record<string, number>>({});
  const [latestPrediction, setLatestPrediction] = useState<PredictionCreateResponse | null>(null);
  const [storedPredictions, setStoredPredictions] = useState<PredictionStoredView[]>([]);
  const [fhirExport, setFhirExport] = useState<FhirExportView | null>(null);
  const [chatHistory, setChatHistory] = useState<ChatMessageView[]>([]);
  const [chatPrompt, setChatPrompt] = useState(
    "Summarize the patient's latest encrypted disease risk drivers and clinical notes."
  );

  // Forms
  const [showNewPatientModal, setShowNewPatientModal] = useState(false);
  const [newMrn, setNewMrn] = useState("MRN-2026-102");
  const [newPatientName, setNewPatientName] = useState("Meera Nair");
  const [newPatientDob, setNewPatientDob] = useState("1988-03-21");
  const [newPatientBlood, setNewPatientBlood] = useState("O+");

  const [recType, setRecType] = useState<RecordType>("lab");
  const [recCategory, setRecCategory] = useState<RecordCategory>("cardiac");
  const [recTitle, setRecTitle] = useState("High-Sensitivity Troponin & Lipid Panel");
  const [recPayloadText, setRecPayloadText] = useState(
    JSON.stringify({ ldl_mg_dl: 138, hdl_mg_dl: 46, troponin_ng_ml: 0.012, notes: "Sinus rhythm" }, null, 2)
  );
  const [abePolicy, setAbePolicy] = useState("(role:doctor AND dept:cardiology) OR role:admin");

  const [consentGranteeId, setConsentGranteeId] = useState("");
  const [consentCategories, setConsentCategories] = useState("cardiac,labs,general");
  const [consentPurposes, setConsentPurposes] = useState("treatment,ai_prediction,export");

  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<boolean>(false);

  const activeDiseaseSpec = useMemo(
    () => diseases.find((d) => d.key === selectedDisease) ?? null,
    [diseases, selectedDisease]
  );

  useEffect(() => {
    if (!activeDiseaseSpec) return;
    const defaults: Record<string, number> = {};
    for (const f of activeDiseaseSpec.features) {
      defaults[f.name] = Number(f.mean.toFixed(2));
    }
    setFeatureValues(defaults);
  }, [activeDiseaseSpec]);

  const loadInitialCatalogs = useCallback(async () => {
    try {
      const [patientList, diseaseList] = await Promise.all([
        api.listPatients(),
        api.listDiseases(),
      ]);
      setPatients(patientList);
      setDiseases(diseaseList);
      if (patientList.length > 0 && !selectedPatientId) {
        setSelectedPatientId(patientList[0].id);
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to load workspace");
    }
  }, [selectedPatientId]);

  useEffect(() => {
    void loadInitialCatalogs();
  }, [loadInitialCatalogs]);

  const loadPatientData = useCallback(
    async (patientId: string) => {
      setErrorMessage(null);
      setDecryptedRecords({});
      setIntegrityStatus({});
      setFhirExport(null);

      const recordRows = await api.listRecords(patientId).catch(() => []);
      setRecords(recordRows);

      if (user?.role !== "auditor") {
        try {
          const p = await api.getPatient(patientId);
          setPatientView(p);
        } catch {
          setPatientView(null);
        }
        const preds = await api.listPredictions(patientId).catch(() => []);
        setStoredPredictions(preds);
        const chats = await api.listChatHistory(patientId).catch(() => []);
        setChatHistory(chats);
      } else {
        setPatientView(null);
        setStoredPredictions([]);
        setChatHistory([]);
      }

      if (user?.role === "patient" || user?.role === "admin") {
        const cRows = await api.listConsents(patientId).catch(() => []);
        setConsents(cRows);
        if (cRows.length > 0 && !consentGranteeId) {
          setConsentGranteeId(cRows[0].grantee_user_id);
        }
      } else {
        setConsents([]);
      }
    },
    [user?.role, consentGranteeId]
  );

  useEffect(() => {
    if (selectedPatientId) {
      void loadPatientData(selectedPatientId);
    }
  }, [selectedPatientId, loadPatientData]);

  const handleCreatePatient = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const created = await api.createPatient({
        mrn: newMrn,
        demographics: {
          name: newPatientName,
          dob: newPatientDob,
          blood_group: newPatientBlood,
        },
      });
      const updatedList = await api.listPatients();
      setPatients(updatedList);
      setSelectedPatientId(created.id);
      setShowNewPatientModal(false);
      setStatusMessage(`Registered patient ${created.mrn} with encrypted demographics.`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Could not create patient");
    } finally {
      setBusy(false);
    }
  };

  const handleCreateRecord = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId) return;
    setBusy(true);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const parsedPayload = JSON.parse(recPayloadText) as Record<string, unknown>;
      const created = await api.createRecord(selectedPatientId, {
        record_type: recType,
        category: recCategory,
        title: recTitle,
        payload: parsedPayload,
      });
      setDecryptedRecords((prev) => ({ ...prev, [created.id]: created }));
      await loadPatientData(selectedPatientId);
      setStatusMessage(`Saved encrypted record "${created.title}".`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to create record");
    } finally {
      setBusy(false);
    }
  };

  const handleDecryptRecord = async (recordId: string) => {
    if (!selectedPatientId) return;
    setErrorMessage(null);
    try {
      const dec = await api.getRecord(selectedPatientId, recordId);
      setDecryptedRecords((prev) => ({ ...prev, [recordId]: dec }));
      setStatusMessage(`Decrypted record ${recordId.slice(0, 8)} after consent & digest verification.`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Decryption denied");
    }
  };

  const handleVerifyRecord = async (recordId: string) => {
    if (!selectedPatientId) return;
    setErrorMessage(null);
    try {
      const ver = await api.verifyRecord(selectedPatientId, recordId);
      setIntegrityStatus((prev) => ({ ...prev, [recordId]: ver.integrity }));
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Integrity check failed");
    }
  };

  const handleShareAbe = async (recordId: string) => {
    if (!selectedPatientId) return;
    setErrorMessage(null);
    setBusy(true);
    try {
      await api.shareRecordWithPolicy(recordId, abePolicy);
      await loadPatientData(selectedPatientId);
      setStatusMessage(`Applied CP-ABE access policy to record ${recordId.slice(0, 8)}.`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "ABE share failed");
    } finally {
      setBusy(false);
    }
  };

  const handleOpenAbe = async (recordId: string) => {
    setErrorMessage(null);
    setBusy(true);
    try {
      const opened = await api.openAbeRecord(recordId);
      setDecryptedRecords((prev) => ({ ...prev, [recordId]: opened }));
      setStatusMessage(`Decrypted shared record via ${user?.username}'s attribute key.`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Attribute policy not satisfied");
    } finally {
      setBusy(false);
    }
  };

  const handleRunEncryptedPrediction = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId) return;
    setBusy(true);
    setErrorMessage(null);
    setStatusMessage(null);
    try {
      const pred = await api.createPrediction(selectedPatientId, selectedDisease, featureValues);
      setLatestPrediction(pred);
      const updated = await api.listPredictions(selectedPatientId);
      setStoredPredictions(updated);
      setStatusMessage(
        `Completed encrypted ${pred.disease} risk evaluation (${(pred.probability * 100).toFixed(1)}% — ${pred.risk_band} risk).`
      );
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Encrypted prediction failed");
    } finally {
      setBusy(false);
    }
  };

  const handleGrantConsent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPatientId || !consentGranteeId.trim()) return;
    setBusy(true);
    setErrorMessage(null);
    try {
      await api.grantConsent(selectedPatientId, {
        grantee_user_id: consentGranteeId.trim(),
        categories: consentCategories
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        purposes: consentPurposes
          .split(",")
          .map((s) => s.trim())
          .filter(Boolean),
      });
      await loadPatientData(selectedPatientId);
      setStatusMessage("Updated patient consent policy.");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Consent grant failed");
    } finally {
      setBusy(false);
    }
  };

  const handleRevokeConsent = async (consentId: string) => {
    if (!selectedPatientId) return;
    setBusy(true);
    setErrorMessage(null);
    try {
      await api.revokeConsent(consentId);
      await loadPatientData(selectedPatientId);
      setStatusMessage("Consent revoked — clinical access is now blocked for that grantee.");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Revoke failed");
    } finally {
      setBusy(false);
    }
  };

  const handleExportFhir = async () => {
    if (!selectedPatientId) return;
    setBusy(true);
    setErrorMessage(null);
    try {
      const res = await api.exportFhir(selectedPatientId);
      setFhirExport(res);
      setSubTab("governance");
      setStatusMessage(`Generated signed HL7 FHIR R4 Bundle (${res.resource_count} resources).`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "FHIR export failed");
    } finally {
      setBusy(false);
    }
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatPrompt.trim()) return;
    setBusy(true);
    setErrorMessage(null);
    try {
      const turn = await api.sendChat(chatPrompt, selectedPatientId);
      setChatHistory((prev) => [...prev, turn.user_message, turn.assistant_message]);
      setChatPrompt("");
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Clinical assistant error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="workspace-layout">
      {/* Left Sidebar: Patient Directory */}
      <aside className="patient-sidebar">
        <div className="sidebar-header">
          <div>
            <h3>Patients</h3>
            <span className="sidebar-count">{patients.length} active</span>
          </div>
          {(user?.role === "doctor" || user?.role === "admin") && (
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={() => setShowNewPatientModal((v) => !v)}
            >
              {showNewPatientModal ? "Cancel" : "+ New"}
            </button>
          )}
        </div>

        {showNewPatientModal && (
          <form onSubmit={(e) => void handleCreatePatient(e)} className="sidebar-form">
            <label>
              <span>MRN</span>
              <input value={newMrn} onChange={(e) => setNewMrn(e.target.value)} required />
            </label>
            <label>
              <span>Full Name</span>
              <input value={newPatientName} onChange={(e) => setNewPatientName(e.target.value)} required />
            </label>
            <div className="form-row-2">
              <label>
                <span>Birth Date</span>
                <input type="date" value={newPatientDob} onChange={(e) => setNewPatientDob(e.target.value)} required />
              </label>
              <label>
                <span>Blood Type</span>
                <input value={newPatientBlood} onChange={(e) => setNewPatientBlood(e.target.value)} required />
              </label>
            </div>
            <button type="submit" className="btn-primary btn-full" disabled={busy}>
              Save Encrypted Profile
            </button>
          </form>
        )}

        <div className="patient-directory">
          {patients.map((p) => {
            const isSelected = p.id === selectedPatientId;
            return (
              <button
                key={p.id}
                type="button"
                className={isSelected ? "patient-row active" : "patient-row"}
                onClick={() => setSelectedPatientId(p.id)}
              >
                <div className="patient-row-main">
                  <strong>{p.mrn}</strong>
                  <span className="status-dot" />
                </div>
                <span className="patient-row-id">ID: {p.id.slice(0, 8)}</span>
              </button>
            );
          })}
        </div>

        {user && (
          <div className="attribute-box">
            <span className="attribute-box-title">Active ABE Key Attributes</span>
            <div className="attr-list">
              {user.attributes.map((attr) => (
                <code key={attr} className="attr-chip">
                  {attr}
                </code>
              ))}
            </div>
          </div>
        )}
      </aside>

      {/* Main Clinical Workspace */}
      <div className="workspace-main">
        {statusMessage && (
          <div className="banner banner-success">
            <span>{statusMessage}</span>
            <button type="button" className="banner-close" onClick={() => setStatusMessage(null)}>
              ×
            </button>
          </div>
        )}
        {errorMessage && (
          <div className="banner banner-error">
            <span>{errorMessage}</span>
            <button type="button" className="banner-close" onClick={() => setErrorMessage(null)}>
              ×
            </button>
          </div>
        )}

        {/* Patient Summary Header Card */}
        <section className="patient-banner-card">
          <div className="patient-banner-top">
            <div className="patient-identity">
              <div className="patient-initials">
                {patientView?.demographics?.name
                  ? String(patientView.demographics.name)
                      .split(" ")
                      .map((n) => n[0])
                      .join("")
                      .slice(0, 2)
                  : "PT"}
              </div>
              <div>
                <div className="patient-title-row">
                  <h2>
                    {patientView?.demographics?.name
                      ? String(patientView.demographics.name)
                      : selectedPatientId
                        ? `Patient ${selectedPatientId.slice(0, 8)}`
                        : "Select a Patient"}
                  </h2>
                  {patientView && <span className="mrn-pill">{patientView.mrn}</span>}
                  <span className="crypto-tag">AES-256-GCM Verified</span>
                </div>
                {patientView ? (
                  <div className="demographics-strip">
                    <span>
                      <strong>DOB:</strong> {String(patientView.demographics.dob ?? "—")}
                    </span>
                    <span>•</span>
                    <span>
                      <strong>Gender:</strong> {String(patientView.demographics.gender ?? "—")}
                    </span>
                    <span>•</span>
                    <span>
                      <strong>Blood Group:</strong> {String(patientView.demographics.blood_group ?? "—")}
                    </span>
                    {patientView.demographics.phone ? (
                      <>
                        <span>•</span>
                        <span>
                          <strong>Contact:</strong> {String(patientView.demographics.phone)}
                        </span>
                      </>
                    ) : null}
                  </div>
                ) : (
                  <p className="muted-text">
                    {user?.role === "auditor"
                      ? "Auditor mode: Demographic plaintext is restricted; metadata and cryptographic digests are available."
                      : "Demographics encrypted or requires active patient consent."}
                  </p>
                )}
              </div>
            </div>

            {selectedPatientId && user?.role !== "auditor" && (
              <button
                type="button"
                className="btn-secondary"
                onClick={() => void handleExportFhir()}
                disabled={busy}
              >
                Export FHIR R4 Bundle
              </button>
            )}
          </div>

          {/* Sub-Navigation Bar */}
          <div className="subnav-bar">
            <button
              type="button"
              className={subTab === "records" ? "subnav-btn active" : "subnav-btn"}
              onClick={() => setSubTab("records")}
            >
              Clinical Records ({records.length})
            </button>
            {user?.role !== "auditor" && (
              <button
                type="button"
                className={subTab === "predictions" ? "subnav-btn active" : "subnav-btn"}
                onClick={() => setSubTab("predictions")}
              >
                Homomorphic AI Risk ({storedPredictions.length})
              </button>
            )}
            {user?.role !== "auditor" && (
              <button
                type="button"
                className={subTab === "assistant" ? "subnav-btn active" : "subnav-btn"}
                onClick={() => setSubTab("assistant")}
              >
                Clinical AI Assistant
              </button>
            )}
            {user?.role !== "auditor" && (
              <button
                type="button"
                className={subTab === "governance" ? "subnav-btn active" : "subnav-btn"}
                onClick={() => setSubTab("governance")}
              >
                Consent &amp; FHIR Export
              </button>
            )}
          </div>
        </section>

        {/* SUB-TAB 1: CLINICAL RECORDS & CP-ABE SHARING */}
        {subTab === "records" && (
          <div className="section-grid">
            <section className="card">
              <div className="card-header">
                <div>
                  <h3>Encrypted Medical Records</h3>
                  <p>
                    Each record is sealed with a per-row HKDF AES-256-GCM key and can be wrapped under a BN254 CP-ABE policy for cross-department sharing.
                  </p>
                </div>
              </div>

              {records.length === 0 ? (
                <div className="empty-state">
                  <p>No clinical records on file for this patient yet.</p>
                </div>
              ) : (
                <div className="record-stack">
                  {records.map((rec) => {
                    const dec = decryptedRecords[rec.id];
                    const ver = integrityStatus[rec.id];
                    return (
                      <div key={rec.id} className="record-item">
                        <div className="record-item-top">
                          <div className="record-tags">
                            <span className="pill pill-blue">{rec.record_type}</span>
                            <span className="pill pill-slate">{rec.category}</span>
                            <code className="mono-id">{rec.id.slice(0, 10)}</code>
                            <span className="record-date">
                              {new Date(rec.created_at).toLocaleDateString()}
                            </span>
                            {rec.abe_policy && (
                              <span className="pill pill-amber">Policy: {rec.abe_policy}</span>
                            )}
                            {ver && (
                              <span className={ver === "ok" ? "pill pill-green" : "pill pill-red"}>
                                SHA-256: {ver}
                              </span>
                            )}
                          </div>

                          <div className="btn-row">
                            {user?.role !== "auditor" && (
                              <button
                                type="button"
                                className="btn-secondary btn-sm"
                                onClick={() => void handleDecryptRecord(rec.id)}
                              >
                                Decrypt Record
                              </button>
                            )}
                            {user?.role !== "patient" && (
                              <button
                                type="button"
                                className="btn-secondary btn-sm"
                                onClick={() => void handleVerifyRecord(rec.id)}
                              >
                                Verify Integrity
                              </button>
                            )}
                            {(user?.role === "doctor" || user?.role === "admin") && (
                              <button
                                type="button"
                                className="btn-secondary btn-sm"
                                onClick={() => void handleShareAbe(rec.id)}
                                disabled={busy}
                              >
                                Apply ABE Policy
                              </button>
                            )}
                            {rec.abe_policy && (
                              <button
                                type="button"
                                className="btn-primary btn-sm"
                                onClick={() => void handleOpenAbe(rec.id)}
                                disabled={busy}
                              >
                                Open with ABE Key
                              </button>
                            )}
                          </div>
                        </div>

                        {dec && (
                          <div className="record-decrypted">
                            <div className="record-decrypted-title">{dec.title}</div>
                            <pre className="code-viewer">{JSON.stringify(dec.payload, null, 2)}</pre>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            {(user?.role === "doctor" || user?.role === "admin") && (
              <section className="card">
                <div className="card-header">
                  <div>
                    <h3>Add Clinical Record</h3>
                    <p>Encrypted before database commit.</p>
                  </div>
                </div>
                <form onSubmit={(e) => void handleCreateRecord(e)} className="form-stack">
                  <div className="form-row-2">
                    <label>
                      <span>Record Type</span>
                      <select value={recType} onChange={(e) => setRecType(e.target.value as RecordType)}>
                        <option value="lab">Lab Result</option>
                        <option value="note">Clinical Note</option>
                        <option value="vitals">Vitals</option>
                        <option value="prescription">Prescription</option>
                        <option value="imaging_meta">Imaging Metadata</option>
                      </select>
                    </label>
                    <label>
                      <span>Category</span>
                      <select
                        value={recCategory}
                        onChange={(e) => setRecCategory(e.target.value as RecordCategory)}
                      >
                        <option value="cardiac">Cardiac</option>
                        <option value="labs">Labs</option>
                        <option value="general">General</option>
                        <option value="mental">Mental Health</option>
                        <option value="imaging">Imaging</option>
                      </select>
                    </label>
                  </div>

                  <label>
                    <span>Record Title</span>
                    <input value={recTitle} onChange={(e) => setRecTitle(e.target.value)} required />
                  </label>

                  <label>
                    <span>Structured Clinical Payload (JSON)</span>
                    <textarea
                      rows={4}
                      value={recPayloadText}
                      onChange={(e) => setRecPayloadText(e.target.value)}
                    />
                  </label>

                  <label>
                    <span>Default CP-ABE Sharing Policy</span>
                    <input value={abePolicy} onChange={(e) => setAbePolicy(e.target.value)} />
                  </label>

                  <button type="submit" className="btn-primary" disabled={busy}>
                    Encrypt &amp; Save Record
                  </button>
                </form>
              </section>
            )}
          </div>
        )}

        {/* SUB-TAB 2: CKKS HOMOMORPHIC RISK PREDICTION */}
        {subTab === "predictions" && user?.role !== "auditor" && (
          <div className="section-stack">
            <section className="card">
              <div className="card-header-split">
                <div>
                  <h3>Homomorphic Encrypted Disease Risk Modeling</h3>
                  <p>
                    Features are normalized and encrypted under CKKS (N=8192) before leaving the hospital boundary. The cloud engine evaluates on ciphertexts only.
                  </p>
                </div>
                <div className="model-selector">
                  <span>Disease Model</span>
                  <select
                    value={selectedDisease}
                    onChange={(e) => setSelectedDisease(e.target.value as DiseaseKey)}
                  >
                    {diseases.map((d) => (
                      <option key={d.key} value={d.key}>
                        {d.label} ({d.features.length} inputs)
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {activeDiseaseSpec && (
                <form onSubmit={(e) => void handleRunEncryptedPrediction(e)}>
                  <div className="clinical-input-grid">
                    {activeDiseaseSpec.features.map((f) => (
                      <label key={f.name} className="clinical-input-cell">
                        <span className="input-label">{f.label}</span>
                        <input
                          type="number"
                          step="any"
                          min={f.min}
                          max={f.max}
                          value={featureValues[f.name] ?? f.mean}
                          onChange={(e) =>
                            setFeatureValues((prev) => ({
                              ...prev,
                              [f.name]: Number(e.target.value),
                            }))
                          }
                          required
                        />
                        <span className="input-range">
                          Normal range: {f.min} – {f.max} (avg {f.mean})
                        </span>
                      </label>
                    ))}
                  </div>
                  <div className="form-actions">
                    <button type="submit" className="btn-primary" disabled={busy}>
                      {busy ? "Running CKKS Evaluation…" : "Run Encrypted Risk Assessment"}
                    </button>
                  </div>
                </form>
              )}
            </section>

            {latestPrediction && (
              <section className="card highlight-card">
                <div className="prediction-header">
                  <div>
                    <span className={`risk-pill risk-${latestPrediction.risk_band}`}>
                      {latestPrediction.risk_band.toUpperCase()} RISK
                    </span>
                    <h4>
                      {latestPrediction.disease.toUpperCase()} —{" "}
                      {(latestPrediction.probability * 100).toFixed(1)}% Predicted Risk
                    </h4>
                    <p className="muted-text">
                      Plaintext XGBoost Reference:{" "}
                      {(latestPrediction.plaintext_reference_probability * 100).toFixed(1)}% •
                      Cloud Saw Plaintext: <strong>No (CKKS Ciphertext Only)</strong>
                      {latestPrediction.conformal
                        ? ` • 90% Conformal Interval: ±${(latestPrediction.conformal.half_width * 100).toFixed(1)}%`
                        : ""}
                    </p>
                  </div>
                </div>

                <div className="shap-section">
                  <h5>Top Clinical Risk Drivers ({latestPrediction.explanation.method})</h5>
                  <div className="shap-bars">
                    {latestPrediction.explanation.top_features.map((feat) => {
                      const pct = Math.min(100, Math.max(8, Math.abs(feat.contribution) * 140));
                      return (
                        <div key={feat.feature} className="shap-bar-row">
                          <div className="shap-bar-label">
                            <strong>{feat.label}</strong>
                            <span>Value: {feat.value}</span>
                          </div>
                          <div className="shap-bar-track">
                            <div
                              className={
                                feat.contribution >= 0
                                  ? "shap-bar-fill positive"
                                  : "shap-bar-fill negative"
                              }
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                          <code
                            className={
                              feat.contribution >= 0 ? "shap-val pos" : "shap-val neg"
                            }
                          >
                            {feat.contribution >= 0 ? "+" : ""}
                            {feat.contribution.toFixed(3)}
                          </code>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </section>
            )}

            {storedPredictions.length > 0 && (
              <section className="card">
                <div className="card-header">
                  <div>
                    <h3>Saved Risk Assessments ({storedPredictions.length})</h3>
                    <p>Decrypted on demand from AES-256-GCM storage.</p>
                  </div>
                </div>
                <div className="prediction-history-grid">
                  {storedPredictions.map((sp) => {
                    const prob = sp.result.encrypted_inference.probability * 100;
                    const top = sp.result.explanation?.top_features?.[0];
                    return (
                      <div key={sp.id} className="pred-history-card">
                        <div className="pred-history-top">
                          <strong>{sp.disease.toUpperCase()}</strong>
                          <span className={`risk-pill risk-${sp.risk_band}`}>{sp.risk_band}</span>
                        </div>
                        <div className="pred-history-prob">{prob.toFixed(1)}%</div>
                        {top && (
                          <span className="pred-history-driver">
                            Primary factor: {top.label} ({top.contribution >= 0 ? "+" : ""}
                            {top.contribution.toFixed(2)})
                          </span>
                        )}
                        <span className="pred-history-meta">
                          {sp.model_version} • {new Date(sp.created_at).toLocaleString()}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </section>
            )}
          </div>
        )}

        {/* SUB-TAB 3: CLINICAL AI ASSISTANT */}
        {subTab === "assistant" && user?.role !== "auditor" && (
          <section className="card">
            <div className="card-header">
              <div>
                <h3>Privacy-Preserving Clinical Assistant</h3>
                <p>
                  Identifiers (phones, emails, IDs) are automatically redacted before context assembly, and conversation history is encrypted at rest.
                </p>
              </div>
            </div>

            <div className="chat-stream">
              {chatHistory.length === 0 ? (
                <div className="empty-state">
                  <p>Ask a question about this patient&apos;s risk assessments or clinical records.</p>
                </div>
              ) : (
                chatHistory.map((m) => (
                  <div key={m.id} className={`chat-message chat-${m.role}`}>
                    <div className="chat-message-header">
                      <strong>{m.role === "user" ? "Clinician (PII Scrubbed)" : "Clinical Assistant"}</strong>
                      {m.agent_trace && (
                        <span className="trace-badge">
                          Pipeline: {m.agent_trace.map((t) => String(t.step)).join(" → ")}
                        </span>
                      )}
                    </div>
                    <p>{m.content}</p>
                  </div>
                ))
              )}
            </div>

            <form onSubmit={(e) => void handleSendChat(e)} className="chat-input-bar">
              <input
                value={chatPrompt}
                onChange={(e) => setChatPrompt(e.target.value)}
                placeholder="Ask a clinical question (try adding a phone number or email to see automatic PII redaction)…"
              />
              <button type="submit" className="btn-primary" disabled={busy}>
                Send Query
              </button>
            </form>
          </section>
        )}

        {/* SUB-TAB 4: CONSENT GOVERNANCE & FHIR EXPORT */}
        {subTab === "governance" && user?.role !== "auditor" && (
          <div className="section-stack">
            {(user?.role === "patient" || user?.role === "admin") && (
              <section className="card">
                <div className="card-header">
                  <div>
                    <h3>Patient Access Consents</h3>
                    <p>
                      Doctors can only decrypt records or run AI predictions when an active consent covers the category and purpose.
                    </p>
                  </div>
                </div>

                <form onSubmit={(e) => void handleGrantConsent(e)} className="consent-form-row">
                  <label>
                    <span>Grantee User ID</span>
                    <input
                      value={consentGranteeId}
                      onChange={(e) => setConsentGranteeId(e.target.value)}
                      placeholder="Doctor User UUID"
                      required
                    />
                  </label>
                  <label>
                    <span>Allowed Categories</span>
                    <input
                      value={consentCategories}
                      onChange={(e) => setConsentCategories(e.target.value)}
                    />
                  </label>
                  <label>
                    <span>Allowed Purposes</span>
                    <input
                      value={consentPurposes}
                      onChange={(e) => setConsentPurposes(e.target.value)}
                    />
                  </label>
                  <button type="submit" className="btn-primary" disabled={busy}>
                    Grant Access
                  </button>
                </form>

                <div className="record-stack">
                  {consents.map((c) => (
                    <div key={c.id} className="record-item-top">
                      <div>
                        <strong>Grantee ID:</strong> <code className="mono-id">{c.grantee_user_id}</code>{" "}
                        • <strong>Categories:</strong> {(c.scope.categories ?? []).join(", ")} •{" "}
                        <strong>Purposes:</strong> {(c.scope.purposes ?? []).join(", ")}
                      </div>
                      <button
                        type="button"
                        className="btn-danger btn-sm"
                        onClick={() => void handleRevokeConsent(c.id)}
                        disabled={busy}
                      >
                        Revoke Access
                      </button>
                    </div>
                  ))}
                </div>
              </section>
            )}

            <section className="card">
              <div className="card-header-split">
                <div>
                  <h3>HL7 FHIR R4 Interoperability Bundle</h3>
                  <p>
                    Exports consented patient demographics, observations, and AI risk assessments signed with SHA-256 and HMAC-SHA256.
                  </p>
                </div>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => void handleExportFhir()}
                  disabled={busy}
                >
                  Generate FHIR R4 Bundle
                </button>
              </div>

              {fhirExport && (
                <div className="fhir-output">
                  <div className="fhir-digests">
                    <span>
                      <strong>Resources:</strong> {fhirExport.resource_count}
                    </span>
                    <span>
                      <strong>SHA-256:</strong> <code>{fhirExport.bundle_sha256.slice(0, 24)}…</code>
                    </span>
                    <span>
                      <strong>HMAC-SHA256:</strong> <code>{fhirExport.checksum_hmac.slice(0, 24)}…</code>
                    </span>
                  </div>
                  <pre className="code-viewer">{JSON.stringify(fhirExport.bundle, null, 2)}</pre>
                </div>
              )}
            </section>
          </div>
        )}
      </div>
    </div>
  );
}
