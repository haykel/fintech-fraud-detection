// ==================== API shapes (aligned with backend `interfaces/api/routes/`) ====================

export type TransactionStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'BLOCKED';

/** Mirror of `application.queries.TransactionDTO`. */
export interface Transaction {
  id: string;
  account_id: string;
  amount: number;
  currency: string;
  merchant_id: string;
  merchant_name: string | null;
  timestamp: string; // ISO 8601
  status: TransactionStatus;
  is_fraud: boolean;
  risk_score: number;
  fraud_reason: string | null;
}

/** Response of `GET /api/accounts/{id}/transactions`. */
export interface TransactionHistoryResponse {
  transactions: Transaction[];
  total: number;
  limit: number;
  offset: number;
}

/** Filters supported by the transaction-history endpoint. */
export interface TransactionFilters {
  limit?: number;
  offset?: number;
  min_amount?: number;
  max_amount?: number;
  status?: TransactionStatus;
  is_fraud?: boolean;
  start_date?: string;
  end_date?: string;
}

/** Nested `risk_profile` field returned by `GET /api/accounts/{id}/risk-profile`. */
export interface RiskProfileSnapshot {
  historical_risk_score: number;
  transaction_count: number;
  fraud_count: number;
  fraud_rate: number;
  is_high_risk: boolean;
  last_updated: string;
}

/** Full payload from `GET /api/accounts/{id}/risk-profile`. */
export interface AccountRiskProfile {
  account_id: string;
  holder_name: string;
  status: string;
  risk_profile: RiskProfileSnapshot;
}

// ==================== Mistral agent (explanations route) ====================

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL' | 'UNKNOWN';
export type Recommendation =
  | 'APPROVE'
  | 'REVIEW'
  | 'BLOCK_TRANSACTION'
  | 'FREEZE_ACCOUNT';

export interface FraudAnalysisFactors {
  high_risk: string[];
  low_risk: string[];
}

export interface FraudAnalysisResult {
  risk_level: RiskLevel;
  risk_score: number;
  analysis: string;
  factors: FraudAnalysisFactors;
  recommendation: Recommendation;
  confidence: number;
}

export type ExplanationStatus = 'pending' | 'completed' | 'failed';

export interface ExplanationResponse {
  status: ExplanationStatus;
  result?: FraudAnalysisResult;
  error?: string;
}

export interface AnalyzeJobResponse {
  job_id: string;
  status: string;
  poll_url: string;
}

// ==================== UI-derived types ====================

export type AlertPriority = 'HIGH' | 'MEDIUM' | 'LOW';

/** Derived from transactions with `is_fraud=true`; built in `useFraudAlerts`. */
export interface FraudAlert {
  transaction_id: string;
  account_id: string;
  amount: number;
  currency: string;
  merchant_name: string | null;
  reason: string | null;
  priority: AlertPriority;
  risk_score: number;
  timestamp: string;
}

// ==================== Generic ====================

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}
