export type UserRole = "admin" | "doctor" | "patient" | "auditor";
export type RecordType = "note" | "lab" | "vitals" | "prescription" | "imaging_meta";
export type RecordCategory = "cardiac" | "general" | "mental" | "labs" | "imaging";
export type DiseaseKey = "diabetes" | "heart" | "liver" | "kidney";

export interface TokenPair {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface UserView {
  id: string;
  username: string;
  email: string;
  full_name: string;
  role: UserRole;
  organization: string;
  department: string;
  attributes: string[];
  is_active: boolean;
  created_at: string;
}

export interface PatientSummary {
  id: string;
  user_id: string | null;
  mrn: string;
  created_at: string;
  updated_at: string;
}

export interface PatientView extends PatientSummary {
  demographics: Record<string, unknown>;
  created_by: string | null;
}

export interface RecordSummary {
  id: string;
  patient_id: string;
  record_type: RecordType;
  category: RecordCategory;
  abe_policy: string | null;
  created_by: string | null;
  created_at: string;
}

export interface RecordView extends RecordSummary {
  title: string;
  payload: Record<string, unknown>;
}

export interface RecordIntegrityView {
  record_id: string;
  integrity: string;
}

export interface ConsentView {
  id: string;
  patient_id: string;
  grantee_user_id: string;
  scope: {
    categories?: string[];
    purposes?: string[];
  };
  status: string;
  granted_at: string;
  expires_at: string | null;
  revoked_at: string | null;
}

export interface DiseaseFeatureView {
  name: string;
  label: string;
  min: number;
  max: number;
  mean: number;
  std: number;
}

export interface DiseaseSpecView {
  key: DiseaseKey;
  label: string;
  features: DiseaseFeatureView[];
}

export interface TopFeatureAttribution {
  feature: string;
  label: string;
  value: number;
  contribution: number;
}

export interface PredictionExplanation {
  method: string;
  top_features: TopFeatureAttribution[];
}

export interface ConformalInterval {
  alpha: number;
  half_width: number;
  note: string;
}

export interface PredictionCreateResponse {
  prediction_id: string;
  patient_id: string;
  disease: DiseaseKey;
  model_version: string;
  risk_band: "low" | "moderate" | "high";
  probability: number;
  raw_score: number;
  plaintext_reference_probability: number;
  cloud_saw_plaintext: boolean;
  explanation: PredictionExplanation;
  conformal: ConformalInterval | null;
  synthetic_model: boolean;
  created_at: string;
}

export interface PredictionStoredView {
  id: string;
  patient_id: string;
  disease: DiseaseKey;
  model_version: string;
  risk_band: "low" | "moderate" | "high";
  features: {
    raw: Record<string, number>;
    normalized: number[];
    feature_names: string[];
  };
  result: {
    disease: DiseaseKey;
    encrypted_inference: {
      raw_score: number;
      probability: number;
      he_scheme: string;
      he_params: string;
      cloud_saw_plaintext: boolean;
    };
    plaintext_reference_probability: number;
    explanation: PredictionExplanation;
    conformal: ConformalInterval | null;
    synthetic_model: boolean;
    distilled_from: string;
    he_params: string;
  };
  created_by: string | null;
  created_at: string;
}

export interface FhirExportView {
  export_id: string;
  patient_id: string;
  resource_count: number;
  bundle_sha256: string;
  checksum_hmac: string;
  bundle: Record<string, unknown>;
  created_at: string;
}

export interface ChatMessageView {
  id: string;
  user_id: string;
  patient_id: string | null;
  role: "user" | "assistant";
  content: string;
  agent_trace: Array<Record<string, unknown>> | null;
  created_at: string;
}

export interface ChatTurnResponse {
  user_message: ChatMessageView;
  assistant_message: ChatMessageView;
}

export interface AuditBlockView {
  index: number;
  timestamp: string;
  actor: string;
  action: string;
  resource: string;
  details: Record<string, unknown>;
  prev_hash: string;
  block_hash: string;
  hmac_sig: string;
}

export interface AuditVerifyView {
  valid: boolean;
  length: number;
  first_bad_index: number | null;
  reason: string | null;
}
