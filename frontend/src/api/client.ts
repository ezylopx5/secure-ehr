import type {
  AuditBlockView,
  AuditVerifyView,
  ChatMessageView,
  ChatTurnResponse,
  ConsentView,
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
  TokenPair,
  UserView,
} from "../types";

const isLocalDev =
  typeof window !== "undefined" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1") &&
  window.location.port === "5173";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ??
  (isLocalDev ? "http://127.0.0.1:8000/api" : "/api");
const ACCESS_KEY = "secure_ehr_access_token";
const REFRESH_KEY = "secure_ehr_refresh_token";

export function getAccessToken(): string | null {
  return sessionStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return sessionStorage.getItem(REFRESH_KEY);
}

export function saveTokens(tokens: TokenPair): void {
  sessionStorage.setItem(ACCESS_KEY, tokens.access_token);
  sessionStorage.setItem(REFRESH_KEY, tokens.refresh_token);
}

export function clearTokens(): void {
  sessionStorage.removeItem(ACCESS_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }
  const token = getAccessToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (res.status === 401 && retry && getRefreshToken() && !path.startsWith("/auth/")) {
    const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: getRefreshToken() }),
    });
    if (refreshRes.ok) {
      const pair = (await refreshRes.json()) as TokenPair;
      saveTokens(pair);
      return request<T>(path, options, false);
    }
  }

  if (!res.ok) {
    let message = `HTTP ${res.status}`;
    try {
      const errBody = (await res.json()) as { detail?: unknown };
      if (typeof errBody.detail === "string") {
        message = errBody.detail;
      } else if (errBody.detail) {
        message = JSON.stringify(errBody.detail);
      }
    } catch {
      message = res.statusText || message;
    }
    throw new Error(message);
  }

  return (await res.json()) as T;
}

export const api = {
  login(username: string, password: string): Promise<TokenPair> {
    return request<TokenPair>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    });
  },

  register(payload: {
    username: string;
    email: string;
    password: string;
    full_name: string;
    organization?: string;
    department?: string;
  }): Promise<UserView> {
    return request<UserView>("/auth/register", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  me(): Promise<UserView> {
    return request<UserView>("/auth/me");
  },

  listPatients(): Promise<PatientSummary[]> {
    return request<PatientSummary[]>("/patients");
  },

  getPatient(patientId: string): Promise<PatientView> {
    return request<PatientView>(`/patients/${patientId}`);
  },

  createPatient(payload: {
    mrn: string;
    demographics: Record<string, unknown>;
    user_id?: string | null;
  }): Promise<PatientView> {
    return request<PatientView>("/patients", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  updatePatient(patientId: string, demographics: Record<string, unknown>): Promise<PatientView> {
    return request<PatientView>(`/patients/${patientId}`, {
      method: "PUT",
      body: JSON.stringify({ demographics }),
    });
  },

  listRecords(patientId: string): Promise<RecordSummary[]> {
    return request<RecordSummary[]>(`/patients/${patientId}/records`);
  },

  getRecord(patientId: string, recordId: string): Promise<RecordView> {
    return request<RecordView>(`/patients/${patientId}/records/${recordId}`);
  },

  createRecord(
    patientId: string,
    payload: {
      record_type: RecordType;
      category: RecordCategory;
      title: string;
      payload: Record<string, unknown>;
    }
  ): Promise<RecordView> {
    return request<RecordView>(`/patients/${patientId}/records`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  verifyRecord(patientId: string, recordId: string): Promise<RecordIntegrityView> {
    return request<RecordIntegrityView>(`/patients/${patientId}/records/${recordId}/verify`);
  },

  shareRecordWithPolicy(recordId: string, policy: string): Promise<RecordSummary> {
    return request<RecordSummary>(`/records/${recordId}/share`, {
      method: "POST",
      body: JSON.stringify({ policy }),
    });
  },

  openAbeRecord(recordId: string): Promise<RecordView> {
    return request<RecordView>(`/records/${recordId}/open-abe`, {
      method: "POST",
    });
  },

  listConsents(patientId: string): Promise<ConsentView[]> {
    return request<ConsentView[]>(`/patients/${patientId}/consents`);
  },

  grantConsent(
    patientId: string,
    payload: {
      grantee_user_id: string;
      categories: string[];
      purposes: string[];
      expires_at?: string | null;
    }
  ): Promise<ConsentView> {
    return request<ConsentView>(`/patients/${patientId}/consents`, {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },

  revokeConsent(consentId: string): Promise<ConsentView> {
    return request<ConsentView>(`/consents/${consentId}/revoke`, {
      method: "POST",
    });
  },

  listDiseases(): Promise<DiseaseSpecView[]> {
    return request<DiseaseSpecView[]>("/diseases");
  },

  createPrediction(
    patientId: string,
    disease: DiseaseKey,
    features: Record<string, number>
  ): Promise<PredictionCreateResponse> {
    return request<PredictionCreateResponse>(`/patients/${patientId}/predictions`, {
      method: "POST",
      body: JSON.stringify({ disease, features }),
    });
  },

  listPredictions(patientId: string): Promise<PredictionStoredView[]> {
    return request<PredictionStoredView[]>(`/patients/${patientId}/predictions`);
  },

  exportFhir(patientId: string): Promise<FhirExportView> {
    return request<FhirExportView>(`/patients/${patientId}/fhir`, {
      method: "POST",
    });
  },

  sendChat(prompt: string, patientId?: string | null): Promise<ChatTurnResponse> {
    return request<ChatTurnResponse>("/chat", {
      method: "POST",
      body: JSON.stringify({ prompt, patient_id: patientId ?? null }),
    });
  },

  listChatHistory(patientId?: string | null): Promise<ChatMessageView[]> {
    const query = patientId ? `?patient_id=${encodeURIComponent(patientId)}` : "";
    return request<ChatMessageView[]>(`/chat/history${query}`);
  },

  getAuditChain(limit = 200): Promise<AuditBlockView[]> {
    return request<AuditBlockView[]>(`/audit/chain?limit=${limit}`);
  },

  verifyAuditChain(): Promise<AuditVerifyView> {
    return request<AuditVerifyView>("/audit/verify");
  },
};
