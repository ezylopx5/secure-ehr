import React, { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../context/AuthContext";
import type {
  ChatMessageView,
  ConsentView,
  CryptoLabResponse,
  DiseaseKey,
  DiseaseSpecView,
  FhirExportView,
  PatientSummary,
  PatientView,
  PredictionCreateResponse,
  PredictionStoredView,
  RecordCategory,
  RecordIntegrityView,
  RecordSummary,
  RecordType,
  RecordView,
} from "../types";

type WorkspaceSubTab =
  | "records"
  | "cryptolab"
  | "predictions"
  | "assistant"
  | "governance";

const QUICK_PROMPTS = [
  "Summarize the patient's cardiovascular biomarkers and lipid panel status.",
  "Explain the primary TreeSHAP drivers from the latest disease risk assessment.",
  "Patient phone 9876543210 and email aarav.patel@clinic.org — verify PII scrubbing and clinical summary.",
];

function formatFieldLabel(key: string): string {
  return key
    .replace(/_/g, " ")
    .replace(/\b(mg|dl|ng|ml|mmhg|bpm|pct|bmi|ldl|hdl|spo2)\b/gi, (m) => m.toUpperCase())
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export function PatientWorkspacePage() {
  const { user } = useAuth();
  const [subTab, setSubTab] = useState<WorkspaceSubTab>("records");

  const [patients, setPatients] = useState<PatientSummary[]>([]);
  const [selectedPatientId, setSelectedPatientId] = useState<string>("");
  const [patientView, setPatientView] = useState<PatientView | null>(null);

  const [records, setRecords] = useState<RecordSummary[]>([]);
  const [decryptedRecords, setDecryptedRecords] = useState<Record<string, RecordView>>({});
  const [showRawJson, setShowRawJson] = useState<Record<string, boolean>>({});
  const [integrityDetails, setIntegrityDetails] = useState<Record<string, RecordIntegrityView>>({});

  const [diseases, setDiseases] = useState<DiseaseSpecView[]>([]);
  const [selectedDisease, setSelectedDisease] = useState<DiseaseKey>("heart");
  const [featureValues, setFeatureValues] = useState<Record<string, number>>({});
  const [latestPrediction, setLatestPrediction] = useState<PredictionCreateResponse | null>(null);
  const [storedPredictions, setStoredPredictions] = useState<PredictionStoredView[]>([]);

  const [consents, setConsents] = useState<ConsentView[]>([]);
  const [consentGranteeId, setConsentGranteeId] = useState<string>("");
  const [consentCategories, setConsentCategories] = useState<string>("cardiac,labs,general");
  const [consentPurposes, setConsentPurposes] = useState<string>("treatment,ai_prediction,export");

  const [fhirExport, setFhirExport] = useState<FhirExportView | null>(null);

  const [chatHistory, setChatHistory] = useState<ChatMessageView[]>([]);
  const [chatPrompt, setChatPrompt] = useState<string>(
    "Summarize the patient's latest encrypted disease risk drivers and clinical notes."
  );

  // Interactive Cryptography Lab state
  const [labText, setLabText] = useState<string>(
    "Patient Aarav Patel | MRN-DEMO-0001 | LDL=138 mg/dL | Troponin=0.012 ng/mL"
  );
  const [labDesKey, setLabDesKey] = useState<string>("AEGISEHR");
  const [cryptoLabResult, setCryptoLabResult] = useState<CryptoLabResponse | null>(null);

  // New Patient Modal state
  const [showNewPatientModal, setShowNewPatientModal] = useState(false);
  const [newMrn, setNewMrn] = useState("MRN-2026-0104");
  const [newPatientName, setNewPatientName] = useState("Meera Nair");
  const [newPatientDob, setNewPatientDob] = useState("1988-05-19");
  const [newPatientBlood, setNewPatientBlood] = useState("O+");

  // New Record Form
  const [recType, setRecType] = useState<RecordType>("lab");
  const [recCategory, setRecCategory] = useState<RecordCategory>("cardiac");
  const [recTitle, setRecTitle] = useState("High-Sensitivity Troponin & Lipid Panel");
  const [recPayloadText, setRecPayloadText] = useState(
    JSON.stringify(
      {
        ldl_mg_dl: 138,
        hdl_mg_dl: 46,
        troponin_ng_ml: 0.012,
        notes: "Sinus rhythm, mildly elevated LDL cholesterol.",
      },
      null,
      2
    )
  );
  const [abePolicy, setAbePolicy] = useState(
    "(role:doctor AND dept:cardiology) OR role:admin"
  );

  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<boolean>(false);

  const activeDiseaseSpec = diseases.find((d) => d.key === selectedDisease);

  useEffect(() => {
    if (!activeDiseaseSpec) return;
    const defaults: Record<string, number> = {};
    for (const f of activeDiseaseSpec.features) {
      defaults[f.name] = Number(f.mean.toFixed(2));
    }
    setFeatureValues(defaults);
  }, [activeDiseaseSpec]);

  const applyFeaturePreset = (preset: "baseline" | "elevated" | "healthy") => {
    if (!activeDiseaseSpec) return;
    const next: Record<string, number> = {};
    for (const f of activeDiseaseSpec.features) {
      if (preset === "baseline") {
        next[f.name] = Number(f.mean.toFixed(2));
      } else if (preset === "elevated") {
        const bumped = Math.min(f.max, f.mean + 0.85 * f.std);
        next[f.name] = Number(bumped.toFixed(2));
      } else {
        const lowered = Math.max(f.min, f.mean - 0.65 * f.std);
        next[f.name] = Number(lowered.toFixed(2));
      }
    }
    setFeatureValues(next);
  };

  const loadInitialCatalogs = useCallback(async () => {
    try {
      const [patientRows, diseaseSpecs, labInit] = await Promise.all([
        api.listPatients(),
        api.listDiseases(),
        api.runCryptoLab(
          "Patient Aarav Patel | MRN-DEMO-0001 | LDL=138 mg/dL | Troponin=0.012 ng/mL",
          "AEGISEHR"
        ).catch(() => null),
      ]);
      setPatients(patientRows);
      setDiseases(diseaseSpecs);
      if (labInit) {
        setCryptoLabResult(labInit);
      }
      if (patientRows.length > 0 && !selectedPatientId) {
        setSelectedPatientId(patientRows[0].id);
      }
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Failed to load workspace data");
    }
  }, [selectedPatientId]);

  useEffect(() => {
    void loadInitialCatalogs();
  }, [loadInitialCatalogs]);

  const loadPatientData = useCallback(
    async (patientId: string) => {
      setErrorMessage(null);
      setDecryptedRecords({});
      setIntegrityDetails({});
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

        // Automatically decrypt the first 2 records so the clinical view is immediately populated
        const autoDec: Record<string, RecordView> = {};
        await Promise.all(
          recordRows.slice(0, 2).map(async (r) => {
            try {
              const dec = await api.getRecord(patientId, r.id);
              autoDec[r.id] = dec;
            } catch {
              // ignore if unconsented
            }
          })
        );
        setDecryptedRecords(autoDec);
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
      setStatusMessage(`Registered patient ${created.mrn} with encrypted demographics & MD5/SHA-256 digests.`);
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
      setStatusMessage(`Encrypted and saved record "${created.title}" with MD5 & SHA-256 message digests.`);
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
      setStatusMessage(`Decrypted record ${recordId.slice(0, 8)} after consent & message digest verification.`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Decryption denied");
    }
  };

  const handleVerifyRecord = async (recordId: string) => {
    if (!selectedPatientId) return;
    setErrorMessage(null);
    try {
      const ver = await api.verifyRecord(selectedPatientId, recordId);
      setIntegrityDetails((prev) => ({ ...prev, [recordId]: ver }));
      setStatusMessage(
        `Message Digest Verified (${ver.integrity}) — MD5: ${ver.md5?.slice(0, 12) ?? "ok"}… | SHA-256: ${ver.sha256?.slice(0, 12) ?? "ok"}…`
      );
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
      setStatusMessage(`Wrapped record ${recordId.slice(0, 8)} for cross-department sharing (${abePolicy}).`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Key share failed");
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
      setStatusMessage(`Decrypted shared record via ${user?.username}'s authorized key.`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Access policy not satisfied");
    } finally {
      setBusy(false);
    }
  };

  const handleRunCryptoLab = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setErrorMessage(null);
    try {
      const res = await api.runCryptoLab(labText, labDesKey);
      setCryptoLabResult(res);
      setStatusMessage(
        "Executed DES, RSA, Diffie–Hellman, One-Time Pad, Hill Cipher, and MD5/SHA-256 digests."
      );
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "Crypto Lab execution failed");
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
        `Completed encrypted ${pred.disease.toUpperCase()} risk evaluation (${(pred.probability * 100).toFixed(1)}% — ${pred.risk_band.toUpperCase()} risk).`
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
      setStatusMessage("Updated patient consent policy and appended event to audit chain.");
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
      setStatusMessage("Consent revoked — clinical decryption is immediately blocked for that grantee.");
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
      setStatusMessage(`Generated signed HL7 FHIR R4 Bundle (${res.resource_count} clinical resources).`);
    } catch (err) {
      setErrorMessage(err instanceof Error ? err.message : "FHIR export failed");
    } finally {
      setBusy(false);
    }
  };

  const handleSendChat = async (e: React.FormEvent, customPrompt?: string) => {
    e.preventDefault();
    const text = (customPrompt ?? chatPrompt).trim();
    if (!text) return;
    setBusy(true);
    setErrorMessage(null);
    try {
      const turn = await api.sendChat(text, selectedPatientId);
      setChatHistory((prev) => [...prev, turn.user_message, turn.assistant_message]);
      if (!customPrompt) {
        setChatPrompt("");
      }
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
            <h3>Patient Cohort</h3>
            <span className="sidebar-count">{patients.length} encrypted profile(s)</span>
          </div>
          {(user?.role === "doctor" || user?.role === "admin") && (
            <button
              type="button"
              className="btn-secondary btn-sm"
              onClick={() => setShowNewPatientModal((v) => !v)}
            >
              {showNewPatientModal ? "Cancel" : "+ Enroll"}
            </button>
          )}
        </div>

        {showNewPatientModal && (
          <form onSubmit={(e) => void handleCreatePatient(e)} className="sidebar-form">
            <label>
              <span>Medical Record Number (MRN)</span>
              <input value={newMrn} onChange={(e) => setNewMrn(e.target.value)} required />
            </label>
            <label>
              <span>Full Legal Name</span>
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
              Encrypt &amp; Save Patient
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
                  <span className="status-dot" title="Encrypted Record" />
                </div>
                <span className="patient-row-id">UUID: {p.id.slice(0, 12)}…</span>
              </button>
            );
          })}
        </div>

        {user && (
          <div className="attribute-box">
            <div className="attribute-box-header">
              <span className="attribute-box-title">Active Crypto &amp; Role Keys</span>
              <span className="attribute-count-badge">{user.attributes.length} keys</span>
            </div>
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
            <div className="banner-content">
              <span className="banner-dot banner-dot-ok" />
              <span>{statusMessage}</span>
            </div>
            <button type="button" className="banner-close" onClick={() => setStatusMessage(null)}>
              ×
            </button>
          </div>
        )}
        {errorMessage && (
          <div className="banner banner-error">
            <div className="banner-content">
              <span className="banner-dot banner-dot-err" />
              <span>{errorMessage}</span>
            </div>
            <button type="button" className="banner-close" onClick={() => setErrorMessage(null)}>
              ×
            </button>
          </div>
        )}

        {/* Executive Security & Clinical Telemetry Strip */}
        <div className="kpi-grid">
          <div className="kpi-card">
            <span className="kpi-label">Encrypted Clinical Records</span>
            <div className="kpi-value-row">
              <strong className="kpi-value">{records.length}</strong>
              <span className="kpi-tag kpi-tag-blue">DES / OTP / AES</span>
            </div>
            <span className="kpi-sub">Block &amp; stream cipher protection</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Key Exchange &amp; Sharing</span>
            <div className="kpi-value-row">
              <strong className="kpi-value">Active</strong>
              <span className="kpi-tag kpi-tag-teal">RSA &amp; Diffie–Hellman</span>
            </div>
            <span className="kpi-sub">Asymmetric key wrapping &amp; DHKE</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Message Digest Integrity</span>
            <div className="kpi-value-row">
              <strong className="kpi-value">Verified</strong>
              <span className="kpi-tag kpi-tag-green">MD5 &amp; SHA-256</span>
            </div>
            <span className="kpi-sub">128-bit MD5 + 256-bit SHA digests</span>
          </div>

          <div className="kpi-card">
            <span className="kpi-label">Classical &amp; AI Suite</span>
            <div className="kpi-value-row">
              <strong className="kpi-value">6 Ciphers</strong>
              <span className="kpi-tag kpi-tag-purple">Hill + OTP + AI</span>
            </div>
            <span className="kpi-sub">2×2 Hill matrix + 4 Disease ML models</span>
          </div>
        </div>

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
                  <span className="crypto-tag">
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                      <path d="m9 12 2 2 4-4" />
                    </svg>
                    DES / RSA Encrypted • MD5 &amp; SHA-256 Verified
                  </span>
                </div>
                {patientView ? (
                  <div className="demographics-strip">
                    <span className="demo-meta-chip">
                      <strong>DOB:</strong> {String(patientView.demographics.dob ?? "—")}
                    </span>
                    <span className="demo-meta-chip">
                      <strong>Gender:</strong> {String(patientView.demographics.gender ?? "—")}
                    </span>
                    <span className="demo-meta-chip">
                      <strong>Blood Group:</strong> {String(patientView.demographics.blood_group ?? "—")}
                    </span>
                    {patientView.demographics.phone ? (
                      <span className="demo-meta-chip">
                        <strong>Contact:</strong> {String(patientView.demographics.phone)}
                      </span>
                    ) : null}
                  </div>
                ) : (
                  <p className="muted-text">
                    {user?.role === "auditor"
                      ? "Auditor mode: Demographic plaintext is restricted; MD5/SHA-256 message digests and audit blocks are accessible."
                      : "Demographics encrypted or requires active patient consent."}
                  </p>
                )}
              </div>
            </div>

            {selectedPatientId && user?.role !== "auditor" && (
              <div className="banner-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => void handleExportFhir()}
                  disabled={busy}
                >
                  Export HL7 FHIR R4 Bundle
                </button>
              </div>
            )}
          </div>

          {/* Sub-Navigation Bar */}
          <div className="subnav-bar">
            <button
              type="button"
              className={subTab === "records" ? "subnav-btn active" : "subnav-btn"}
              onClick={() => setSubTab("records")}
            >
              <span>Clinical Records (DES / RSA / MD5)</span>
              <span className="subnav-count">{records.length}</span>
            </button>
            <button
              type="button"
              className={subTab === "cryptolab" ? "subnav-btn active" : "subnav-btn"}
              onClick={() => setSubTab("cryptolab")}
            >
              <span>Crypto Algorithms Lab</span>
              <span className="subnav-count">6 Ciphers</span>
            </button>
            {user?.role !== "auditor" && (
              <button
                type="button"
                className={subTab === "predictions" ? "subnav-btn active" : "subnav-btn"}
                onClick={() => setSubTab("predictions")}
              >
                <span>Encrypted AI Disease Risk</span>
                <span className="subnav-count">{storedPredictions.length}</span>
              </button>
            )}
            {user?.role !== "auditor" && (
              <button
                type="button"
                className={subTab === "assistant" ? "subnav-btn active" : "subnav-btn"}
                onClick={() => setSubTab("assistant")}
              >
                <span>Clinical AI Assistant</span>
                <span className="subnav-count">PII-Scrubbed</span>
              </button>
            )}
            {user?.role !== "auditor" && (
              <button
                type="button"
                className={subTab === "governance" ? "subnav-btn active" : "subnav-btn"}
                onClick={() => setSubTab("governance")}
              >
                <span>Consent &amp; FHIR R4</span>
              </button>
            )}
          </div>
        </section>

        {/* SUB-TAB 1: CLINICAL RECORDS & DIGEST VERIFICATION */}
        {subTab === "records" && (
          <div className="section-grid">
            <section className="card">
              <div className="card-header">
                <div>
                  <h3>Encrypted Medical Records &amp; Message Digest Verification</h3>
                  <p>
                    Records are encrypted at rest, shared across departments via RSA / policy key wrapping, and verified for tamper detection using <strong>MD5 (128-bit)</strong> and <strong>SHA-256 (256-bit)</strong> message digests.
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
                    const ver = integrityDetails[rec.id];
                    const isRaw = Boolean(showRawJson[rec.id]);
                    const entries = dec ? Object.entries(dec.payload ?? {}) : [];
                    return (
                      <div key={rec.id} className="record-item">
                        <div className="record-item-top">
                          <div className="record-tags">
                            <span className="pill pill-blue">{rec.record_type.toUpperCase()}</span>
                            <span className="pill pill-slate">{rec.category.toUpperCase()}</span>
                            <code className="mono-id">ID: {rec.id.slice(0, 8)}</code>
                            <span className="record-date">
                              {new Date(rec.created_at).toLocaleDateString()}
                            </span>
                            {rec.abe_policy && (
                              <span className="pill pill-amber" title="Shared Policy">
                                RSA/Policy: {rec.abe_policy}
                              </span>
                            )}
                            {ver && (
                              <span
                                className={
                                  ver.integrity === "ok" ? "pill pill-green" : "pill pill-red"
                                }
                              >
                                MD5 &amp; SHA-256: {ver.integrity.toUpperCase()}
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
                                {dec ? "Re-Decrypt" : "Decrypt Record"}
                              </button>
                            )}
                            <button
                              type="button"
                              className="btn-secondary btn-sm"
                              onClick={() => void handleVerifyRecord(rec.id)}
                            >
                              Verify MD5 &amp; SHA-256
                            </button>
                            {(user?.role === "doctor" || user?.role === "admin") && (
                              <button
                                type="button"
                                className="btn-secondary btn-sm"
                                onClick={() => void handleShareAbe(rec.id)}
                                disabled={busy}
                              >
                                Share via RSA / Policy
                              </button>
                            )}
                            {rec.abe_policy && (
                              <button
                                type="button"
                                className="btn-primary btn-sm"
                                onClick={() => void handleOpenAbe(rec.id)}
                                disabled={busy}
                              >
                                Open Shared Key
                              </button>
                            )}
                          </div>
                        </div>

                        {ver && (ver.md5 || ver.sha256) && (
                          <div className="digest-proof-box">
                            <div>
                              <strong>MD5 Message Digest (128-bit):</strong>{" "}
                              <code>{ver.md5}</code>
                            </div>
                            <div>
                              <strong>SHA-256 Message Digest (256-bit):</strong>{" "}
                              <code>{ver.sha256}</code>
                            </div>
                          </div>
                        )}

                        {dec && (
                          <div className="record-decrypted">
                            <div className="record-decrypted-header">
                              <div className="record-decrypted-title">{dec.title}</div>
                              <div className="btn-row">
                                <button
                                  type="button"
                                  className="btn-ghost btn-sm"
                                  onClick={() => {
                                    setLabText(`${dec.title}: ${JSON.stringify(dec.payload)}`);
                                    setSubTab("cryptolab");
                                  }}
                                >
                                  Send to Crypto Lab →
                                </button>
                                <button
                                  type="button"
                                  className="btn-ghost btn-sm"
                                  onClick={() =>
                                    setShowRawJson((prev) => ({
                                      ...prev,
                                      [rec.id]: !prev[rec.id],
                                    }))
                                  }
                                >
                                  {isRaw ? "Show Clinical Cards" : "View Raw JSON"}
                                </button>
                              </div>
                            </div>

                            {!isRaw && entries.length > 0 ? (
                              <div className="biomarker-grid">
                                {entries.map(([k, v]) => (
                                  <div
                                    key={k}
                                    className={
                                      typeof v === "string" && v.length > 28
                                        ? "biomarker-cell biomarker-cell-wide"
                                        : "biomarker-cell"
                                    }
                                  >
                                    <span className="biomarker-label">{formatFieldLabel(k)}</span>
                                    <strong className="biomarker-value">
                                      {typeof v === "object" ? JSON.stringify(v) : String(v)}
                                    </strong>
                                  </div>
                                ))}
                              </div>
                            ) : (
                              <pre className="code-viewer">
                                {JSON.stringify(dec.payload, null, 2)}
                              </pre>
                            )}
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
                    <h3>Add Encrypted Clinical Record</h3>
                    <p>Generates MD5 &amp; SHA-256 digests and encrypts before commit.</p>
                  </div>
                </div>
                <form onSubmit={(e) => void handleCreateRecord(e)} className="form-stack">
                  <div className="form-row-2">
                    <label>
                      <span>Record Type</span>
                      <select value={recType} onChange={(e) => setRecType(e.target.value as RecordType)}>
                        <option value="lab">Lab Result</option>
                        <option value="note">Clinical Note</option>
                        <option value="vitals">Outpatient Vitals</option>
                        <option value="prescription">Prescription</option>
                        <option value="imaging_meta">Imaging Metadata</option>
                      </select>
                    </label>
                    <label>
                      <span>Clinical Category</span>
                      <select
                        value={recCategory}
                        onChange={(e) => setRecCategory(e.target.value as RecordCategory)}
                      >
                        <option value="cardiac">Cardiac</option>
                        <option value="labs">Laboratory</option>
                        <option value="general">General Medicine</option>
                        <option value="mental">Behavioral / Mental</option>
                        <option value="imaging">Radiology / Imaging</option>
                      </select>
                    </label>
                  </div>

                  <label>
                    <span>Record Title</span>
                    <input value={recTitle} onChange={(e) => setRecTitle(e.target.value)} required />
                  </label>

                  <label>
                    <span>Structured Clinical Biomarkers (JSON)</span>
                    <textarea
                      rows={4}
                      value={recPayloadText}
                      onChange={(e) => setRecPayloadText(e.target.value)}
                    />
                  </label>

                  <label>
                    <span>Department Access Policy</span>
                    <input value={abePolicy} onChange={(e) => setAbePolicy(e.target.value)} />
                  </label>

                  <button type="submit" className="btn-primary btn-full" disabled={busy}>
                    Encrypt &amp; Save Record
                  </button>
                </form>
              </section>
            )}
          </div>
        )}

        {/* SUB-TAB 2: INTERACTIVE CRYPTOGRAPHY LAB (SYLLABUS ALGORITHMS) */}
        {subTab === "cryptolab" && (
          <div className="section-stack">
            <section className="card">
              <div className="card-header">
                <div>
                  <h3>Interactive Cryptography Workbench (6 Syllabus Algorithms)</h3>
                  <p>
                    Test and inspect live mathematical execution of <strong>MD5 &amp; SHA-256 Message Digests</strong>, <strong>Diffie–Hellman Key Exchange</strong>, <strong>RSA Cryptosystem</strong>, <strong>Data Encryption Standard (DES)</strong>, <strong>One-Time Pad (OTP)</strong>, and <strong>Hill Cipher</strong> on clinical EHR data.
                  </p>
                </div>
              </div>

              <form onSubmit={(e) => void handleRunCryptoLab(e)} className="crypto-lab-form">
                <label className="crypto-lab-input-main">
                  <span>Clinical Plaintext Message (M)</span>
                  <input
                    value={labText}
                    onChange={(e) => setLabText(e.target.value)}
                    placeholder="Enter clinical text or patient biomarkers…"
                    required
                  />
                </label>
                <label className="crypto-lab-input-key">
                  <span>64-Bit DES Key (8 ASCII chars)</span>
                  <input
                    value={labDesKey}
                    onChange={(e) => setLabDesKey(e.target.value)}
                    maxLength={8}
                    required
                  />
                </label>
                <button type="submit" className="btn-primary btn-lg" disabled={busy}>
                  {busy ? "Computing Ciphers…" : "Execute All 6 Algorithms →"}
                </button>
              </form>
            </section>

            {cryptoLabResult && (
              <div className="crypto-lab-grid">
                {/* 1. MD5 & SHA Message Digests */}
                <section className="card crypto-algo-card">
                  <div className="crypto-algo-header">
                    <span className="pill pill-green">1. Message Digest &amp; Integrity</span>
                    <span className="crypto-verified-tag">
                      {cryptoLabResult.digests.integrity_ok ? "✓ Integrity Verified" : "Mismatch"}
                    </span>
                  </div>
                  <h4>MD5 (128-bit) &amp; SHA-256 (256-bit)</h4>
                  <p className="muted-text">
                    Generates irreversible cryptographic hashes to detect unauthorized clinical tampering.
                  </p>
                  <div className="crypto-kv-list">
                    <div className="crypto-kv-item">
                      <span>MD5 Digest (128-bit hex)</span>
                      <code>{cryptoLabResult.digests.md5}</code>
                    </div>
                    <div className="crypto-kv-item">
                      <span>SHA-1 Digest (160-bit hex)</span>
                      <code>{cryptoLabResult.digests.sha1}</code>
                    </div>
                    <div className="crypto-kv-item">
                      <span>SHA-256 Digest (256-bit hex)</span>
                      <code>{cryptoLabResult.digests.sha256}</code>
                    </div>
                  </div>
                </section>

                {/* 2. Diffie-Hellman Key Exchange */}
                <section className="card crypto-algo-card">
                  <div className="crypto-algo-header">
                    <span className="pill pill-blue">2. Asymmetric Key Exchange</span>
                    <span className="crypto-verified-tag">
                      {cryptoLabResult.diffie_hellman.keys_match
                        ? "✓ Shared Secret Matched"
                        : "Mismatch"}
                    </span>
                  </div>
                  <h4>Diffie–Hellman Key Exchange (DHKE)</h4>
                  <p className="muted-text">
                    Establishes a shared secret key K = g^(ab) mod p between Hospital (Alice) and Specialist/Cloud (Bob) over an insecure channel.
                  </p>
                  <div className="crypto-kv-list">
                    <div className="crypto-kv-row-2">
                      <div className="crypto-kv-item">
                        <span>Public Prime (p) &amp; Base (g)</span>
                        <code>
                          p = {cryptoLabResult.diffie_hellman.prime_p}, g ={" "}
                          {cryptoLabResult.diffie_hellman.generator_g}
                        </code>
                      </div>
                      <div className="crypto-kv-item">
                        <span>Derived 64-bit Session Key</span>
                        <code>{cryptoLabResult.diffie_hellman.derived_des_key_hex}</code>
                      </div>
                    </div>
                    <div className="crypto-kv-row-2">
                      <div className="crypto-kv-item">
                        <span>Hospital Public A = g^a mod p</span>
                        <code>{cryptoLabResult.diffie_hellman.alice_public_A}</code>
                      </div>
                      <div className="crypto-kv-item">
                        <span>Specialist Public B = g^b mod p</span>
                        <code>{cryptoLabResult.diffie_hellman.bob_public_B}</code>
                      </div>
                    </div>
                    <div className="crypto-kv-item">
                      <span>Shared Secret S = B^a mod p = A^b mod p</span>
                      <code>
                        Alice: {cryptoLabResult.diffie_hellman.shared_secret_alice} == Bob:{" "}
                        {cryptoLabResult.diffie_hellman.shared_secret_bob}
                      </code>
                    </div>
                  </div>
                </section>

                {/* 3. RSA Cryptosystem */}
                <section className="card crypto-algo-card">
                  <div className="crypto-algo-header">
                    <span className="pill pill-amber">3. Public-Key Cryptosystem</span>
                    <span className="crypto-verified-tag">
                      {cryptoLabResult.rsa.verified ? "✓ Decryption Verified" : "Error"}
                    </span>
                  </div>
                  <h4>RSA Encryption &amp; Decryption</h4>
                  <p className="muted-text">
                    Asymmetric encryption using n = p × q, φ(n) = (p−1)(q−1), C = M^e mod n, and M = C^d mod n.
                  </p>
                  <div className="crypto-kv-list">
                    <div className="crypto-kv-row-2">
                      <div className="crypto-kv-item">
                        <span>Primes (p, q) &amp; Modulus (n)</span>
                        <code>
                          p={cryptoLabResult.rsa.p}, q={cryptoLabResult.rsa.q}, n=
                          {cryptoLabResult.rsa.modulus_n}
                        </code>
                      </div>
                      <div className="crypto-kv-item">
                        <span>Public (e) &amp; Private (d)</span>
                        <code>
                          e={cryptoLabResult.rsa.public_exponent_e}, d=
                          {cryptoLabResult.rsa.private_exponent_d}
                        </code>
                      </div>
                    </div>
                    <div className="crypto-kv-item">
                      <span>Ciphertext Blocks C = M^e mod n (first 10 blocks)</span>
                      <code>
                        [{cryptoLabResult.rsa.ciphertext_blocks.slice(0, 10).join(", ")}…]
                      </code>
                    </div>
                    <div className="crypto-kv-item">
                      <span>Decrypted Plaintext M = C^d mod n</span>
                      <code>{cryptoLabResult.rsa.decrypted_text}</code>
                    </div>
                  </div>
                </section>

                {/* 4. Data Encryption Standard (DES) */}
                <section className="card crypto-algo-card">
                  <div className="crypto-algo-header">
                    <span className="pill pill-blue">4. Symmetric Block Cipher</span>
                    <span className="crypto-verified-tag">
                      {cryptoLabResult.des.verified ? "✓ 16-Round Feistel OK" : "Error"}
                    </span>
                  </div>
                  <h4>Data Encryption Standard (DES)</h4>
                  <p className="muted-text">
                    64-bit block cipher with Initial Permutation (IP), 16 Feistel rounds (Expansion E, 8 S-boxes, P-box), and 48-bit round subkeys.
                  </p>
                  <div className="crypto-kv-list">
                    <div className="crypto-kv-item">
                      <span>64-Bit DES Key (ASCII)</span>
                      <code>{cryptoLabResult.des.key_ascii}</code>
                    </div>
                    <div className="crypto-kv-item">
                      <span>DES Ciphertext (Hex)</span>
                      <code>{cryptoLabResult.des.ciphertext_hex}</code>
                    </div>
                    <div className="crypto-kv-item">
                      <span>Decrypted Plaintext (Reversed 16 Subkeys)</span>
                      <code>{cryptoLabResult.des.decrypted_text}</code>
                    </div>
                  </div>
                </section>

                {/* 5. One-Time Pad (OTP) */}
                <section className="card crypto-algo-card">
                  <div className="crypto-algo-header">
                    <span className="pill pill-slate">5. Information-Theoretic Stream Cipher</span>
                    <span className="crypto-verified-tag">
                      {cryptoLabResult.one_time_pad.verified ? "✓ Perfect Secrecy XOR" : "Error"}
                    </span>
                  </div>
                  <h4>One-Time Pad (Vernam XOR Cipher)</h4>
                  <p className="muted-text">
                    Bitwise XOR (C_i = P_i ⊕ K_i) with a fresh, equal-length random key stream K.
                  </p>
                  <div className="crypto-kv-list">
                    <div className="crypto-kv-item">
                      <span>Random Pad Key Stream K (Hex)</span>
                      <code>{cryptoLabResult.one_time_pad.pad_key_hex}</code>
                    </div>
                    <div className="crypto-kv-item">
                      <span>OTP Ciphertext C = P ⊕ K (Hex)</span>
                      <code>{cryptoLabResult.one_time_pad.ciphertext_hex}</code>
                    </div>
                    <div className="crypto-kv-item">
                      <span>Recovered Plaintext P = C ⊕ K</span>
                      <code>{cryptoLabResult.one_time_pad.decrypted_text}</code>
                    </div>
                  </div>
                </section>

                {/* 6. Hill Cipher */}
                <section className="card crypto-algo-card">
                  <div className="crypto-algo-header">
                    <span className="pill pill-amber">6. Polygraphic Matrix Cipher</span>
                    <span className="crypto-verified-tag">
                      {cryptoLabResult.hill_cipher.verified ? "✓ Matrix Inverse OK" : "Error"}
                    </span>
                  </div>
                  <h4>Hill Cipher (2×2 Matrix mod 26)</h4>
                  <p className="muted-text">
                    Encrypts letter digrams via C = K · P mod 26 and decrypts via modular inverse matrix K⁻¹ mod 26.
                  </p>
                  <div className="crypto-kv-list">
                    <div className="crypto-kv-row-2">
                      <div className="crypto-kv-item">
                        <span>Key Matrix K (mod 26)</span>
                        <code>
                          [[{cryptoLabResult.hill_cipher.key_matrix[0].join(", ")}], [
                          {cryptoLabResult.hill_cipher.key_matrix[1].join(", ")}]]
                        </code>
                      </div>
                      <div className="crypto-kv-item">
                        <span>Normalized Alphabetic Input</span>
                        <code>{cryptoLabResult.hill_cipher.normalized_plaintext}</code>
                      </div>
                    </div>
                    <div className="crypto-kv-item">
                      <span>Hill Ciphertext (C = K·P mod 26)</span>
                      <code>{cryptoLabResult.hill_cipher.ciphertext}</code>
                    </div>
                    <div className="crypto-kv-item">
                      <span>Decrypted Output (P = K⁻¹·C mod 26)</span>
                      <code>{cryptoLabResult.hill_cipher.decrypted_text}</code>
                    </div>
                  </div>
                </section>
              </div>
            )}
          </div>
        )}

        {/* SUB-TAB 3: ENCRYPTED AI DISEASE RISK PREDICTION */}
        {subTab === "predictions" && user?.role !== "auditor" && (
          <div className="section-stack">
            <section className="card">
              <div className="card-header-split">
                <div>
                  <h3>Encrypted Multi-Disease AI Risk Modeling</h3>
                  <p>
                    Patient biomarkers are normalized and encrypted before cloud evaluation. Supports 4 clinical cohorts (Diabetes, Coronary Heart Disease, Liver Disease, Chronic Kidney Disease) with TreeSHAP explainability.
                  </p>
                </div>
                <div className="model-controls">
                  <div className="model-selector">
                    <span>Disease Cohort Model</span>
                    <select
                      value={selectedDisease}
                      onChange={(e) => setSelectedDisease(e.target.value as DiseaseKey)}
                    >
                      {diseases.map((d) => (
                        <option key={d.key} value={d.key}>
                          {d.label} ({d.features.length} biomarkers)
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="preset-bar">
                    <span className="preset-label">Clinical Presets:</span>
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={() => applyFeaturePreset("healthy")}
                    >
                      Low-Risk Profile
                    </button>
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={() => applyFeaturePreset("baseline")}
                    >
                      Cohort Mean
                    </button>
                    <button
                      type="button"
                      className="btn-secondary btn-sm"
                      onClick={() => applyFeaturePreset("elevated")}
                    >
                      High-Risk Profile
                    </button>
                  </div>
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
                          Ref: {f.min} – {f.max} (μ={f.mean})
                        </span>
                      </label>
                    ))}
                  </div>
                  <div className="form-actions">
                    <button type="submit" className="btn-primary btn-lg" disabled={busy}>
                      {busy
                        ? "Encrypting Biomarkers & Evaluating Risk…"
                        : "Run Encrypted AI Risk Assessment →"}
                    </button>
                  </div>
                </form>
              )}
            </section>

            {latestPrediction && (
              <section className="card highlight-card">
                <div className="prediction-summary-grid">
                  <div>
                    <div className="prediction-badges">
                      <span className={`risk-pill risk-${latestPrediction.risk_band}`}>
                        {latestPrediction.risk_band.toUpperCase()} RISK BAND
                      </span>
                      <span className="pill pill-green">
                        Encrypted Cloud Inference (Plaintext Exposed: FALSE)
                      </span>
                      <span className="pill pill-blue">
                        Model: {latestPrediction.model_version}
                      </span>
                    </div>
                    <h4 className="prediction-title">
                      {latestPrediction.disease.toUpperCase()} —{" "}
                      {(latestPrediction.probability * 100).toFixed(1)}% Predicted Probability
                    </h4>
                    <p className="muted-text">
                      Plaintext XGBoost Reference:{" "}
                      <strong>
                        {(latestPrediction.plaintext_reference_probability * 100).toFixed(1)}%
                      </strong>
                      {latestPrediction.conformal
                        ? ` • 90% Confidence Interval: ±${(latestPrediction.conformal.half_width * 100).toFixed(1)}%`
                        : ""}
                    </p>
                  </div>

                  <div className="risk-meter-box">
                    <div className="risk-meter-labels">
                      <span>0% (Low)</span>
                      <span>50% (Moderate)</span>
                      <span>100% (High)</span>
                    </div>
                    <div className="risk-meter-track">
                      <div
                        className={`risk-meter-fill risk-fill-${latestPrediction.risk_band}`}
                        style={{
                          width: `${Math.min(100, Math.max(4, latestPrediction.probability * 100))}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>

                <div className="shap-section">
                  <div className="shap-header">
                    <h5>TreeSHAP Biomarker Attribution ({latestPrediction.explanation.method})</h5>
                    <div className="shap-legend">
                      <span className="legend-item">
                        <span className="legend-dot pos" /> Increases Risk
                      </span>
                      <span className="legend-item">
                        <span className="legend-dot neg" /> Protective / Lowers Risk
                      </span>
                    </div>
                  </div>
                  <div className="shap-bars">
                    {latestPrediction.explanation.top_features.map((feat) => {
                      const pct = Math.min(100, Math.max(8, Math.abs(feat.contribution) * 140));
                      return (
                        <div key={feat.feature} className="shap-bar-row">
                          <div className="shap-bar-label">
                            <strong>{feat.label}</strong>
                            <span>Observed: {feat.value}</span>
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
                    <h3>Saved Encrypted Risk Assessments ({storedPredictions.length})</h3>
                    <p>Decrypted on demand from encrypted database storage.</p>
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
                            Top driver: <strong>{top.label}</strong> ({top.contribution >= 0 ? "+" : ""}
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

        {/* SUB-TAB 4: CLINICAL AI ASSISTANT */}
        {subTab === "assistant" && user?.role !== "auditor" && (
          <section className="card">
            <div className="card-header">
              <div>
                <h3>Privacy-Preserving Clinical AI Assistant</h3>
                <p>
                  Direct identifiers (phone numbers, emails, IDs) are scrubbed via regex pipeline before context assembly, and every conversation turn is stored encrypted at rest.
                </p>
              </div>
            </div>

            <div className="prompt-chips-bar">
              <span className="preset-label">Suggested Queries:</span>
              {QUICK_PROMPTS.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="prompt-chip"
                  disabled={busy}
                  onClick={(e) => {
                    setChatPrompt(q);
                    void handleSendChat(e, q);
                  }}
                >
                  {q.length > 62 ? `${q.slice(0, 62)}…` : q}
                </button>
              ))}
            </div>

            <div className="chat-stream">
              {chatHistory.length === 0 ? (
                <div className="empty-state">
                  <p>
                    Select a suggested clinical query above or enter a custom question below to synthesize this patient&apos;s consented records and risk assessments.
                  </p>
                </div>
              ) : (
                chatHistory.map((m) => (
                  <div key={m.id} className={`chat-message chat-${m.role}`}>
                    <div className="chat-message-header">
                      <div className="chat-author">
                        <span className={`chat-role-dot dot-${m.role}`} />
                        <strong>
                          {m.role === "user"
                            ? "Clinician Query (PII-Scrubbed)"
                            : "AegisEHR Clinical Synthesizer"}
                        </strong>
                      </div>
                      {m.agent_trace && (
                        <span className="trace-badge">
                          Pipeline: {m.agent_trace.map((t) => String(t.step)).join(" → ")}
                        </span>
                      )}
                    </div>
                    <div className="chat-message-body">{m.content}</div>
                  </div>
                ))
              )}
            </div>

            <form onSubmit={(e) => void handleSendChat(e)} className="chat-input-bar">
              <input
                value={chatPrompt}
                onChange={(e) => setChatPrompt(e.target.value)}
                placeholder="Ask a clinical question (include a phone or email to verify automatic PII redaction)…"
              />
              <button type="submit" className="btn-primary" disabled={busy}>
                {busy ? "Synthesizing…" : "Send Clinical Query"}
              </button>
            </form>
          </section>
        )}

        {/* SUB-TAB 5: CONSENT GOVERNANCE & FHIR EXPORT */}
        {subTab === "governance" && user?.role !== "auditor" && (
          <div className="section-stack">
            {(user?.role === "patient" || user?.role === "admin") && (
              <section className="card">
                <div className="card-header">
                  <div>
                    <h3>Patient-Controlled Access Consents</h3>
                    <p>
                      Physicians can only decrypt records or invoke AI risk models when an active, non-expired consent covers both the clinical category and purpose.
                    </p>
                  </div>
                </div>

                <form onSubmit={(e) => void handleGrantConsent(e)} className="consent-form-row">
                  <label>
                    <span>Grantee User UUID</span>
                    <input
                      value={consentGranteeId}
                      onChange={(e) => setConsentGranteeId(e.target.value)}
                      placeholder="Doctor User UUID"
                      required
                    />
                  </label>
                  <label>
                    <span>Permitted Categories</span>
                    <input
                      value={consentCategories}
                      onChange={(e) => setConsentCategories(e.target.value)}
                    />
                  </label>
                  <label>
                    <span>Permitted Purposes</span>
                    <input
                      value={consentPurposes}
                      onChange={(e) => setConsentPurposes(e.target.value)}
                    />
                  </label>
                  <button type="submit" className="btn-primary" disabled={busy}>
                    Grant Consent
                  </button>
                </form>

                <div className="record-stack">
                  {consents.map((c) => (
                    <div key={c.id} className="record-item">
                      <div className="record-item-top">
                        <div className="record-tags">
                          <span className="pill pill-green">ACTIVE CONSENT</span>
                          <span>
                            <strong>Grantee:</strong>{" "}
                            <code className="mono-id">{c.grantee_user_id}</code>
                          </span>
                          <span>
                            <strong>Categories:</strong> {(c.scope.categories ?? []).join(", ")}
                          </span>
                          <span>
                            <strong>Purposes:</strong> {(c.scope.purposes ?? []).join(", ")}
                          </span>
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
                    Exports consented patient demographics (`Patient`), clinical biomarkers (`Observation`), and AI risk evaluations (`RiskAssessment`) signed with SHA-256 and HMAC-SHA256 digests.
                  </p>
                </div>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={() => void handleExportFhir()}
                  disabled={busy}
                >
                  Generate Signed FHIR R4 Bundle
                </button>
              </div>

              {fhirExport && (
                <div className="fhir-output">
                  <div className="fhir-digests">
                    <span className="pill pill-blue">
                      Resources: {fhirExport.resource_count}
                    </span>
                    <span className="pill pill-green">
                      SHA-256: {fhirExport.bundle_sha256.slice(0, 20)}…
                    </span>
                    <span className="pill pill-amber">
                      HMAC-SHA256: {fhirExport.checksum_hmac.slice(0, 20)}…
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
