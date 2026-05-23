import axios, { AxiosError, AxiosInstance } from 'axios';
import type {
  AccountRiskProfile,
  AnalyzeJobResponse,
  ExplanationResponse,
  Transaction,
  TransactionFilters,
  TransactionHistoryResponse,
} from '../types';

// ===== Configuration =====

// Falls back to relative `/api` so the Vite dev proxy can forward to the backend.
const BASE_URL = import.meta.env.VITE_API_URL || '';
const REQUEST_TIMEOUT_MS = 10_000;
const MAX_RETRIES = 2;
const RETRYABLE_STATUSES = new Set([408, 429, 500, 502, 503, 504]);

const client: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: REQUEST_TIMEOUT_MS,
  headers: { 'Content-Type': 'application/json' },
});

// ===== Retry interceptor (exponential backoff, idempotent verbs only) =====

interface RetryConfig {
  retryCount?: number;
}

client.interceptors.response.use(undefined, async (error: AxiosError) => {
  const config = error.config as (typeof error.config & RetryConfig) | undefined;
  if (!config) return Promise.reject(error);

  const method = (config.method || 'get').toLowerCase();
  const isIdempotent = method === 'get' || method === 'head';
  const status = error.response?.status;
  const isNetworkError = !error.response;
  const retryable = isIdempotent && (isNetworkError || (status && RETRYABLE_STATUSES.has(status)));

  config.retryCount = config.retryCount ?? 0;
  if (!retryable || config.retryCount >= MAX_RETRIES) {
    return Promise.reject(error);
  }

  config.retryCount += 1;
  const delay = 2 ** (config.retryCount - 1) * 500; // 500ms, 1s
  await new Promise((resolve) => setTimeout(resolve, delay));
  return client.request(config);
});

// ===== Error mapper =====

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

function toApiError(error: unknown): ApiError {
  if (axios.isAxiosError(error)) {
    const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
    const status = error.response?.status;
    if (status === 404) return new ApiError(detail ?? 'Ressource introuvable', 404);
    if (error.code === 'ECONNABORTED') return new ApiError('La requête a expiré (10s)', 408);
    if (!error.response) return new ApiError('Impossible de joindre l\'API backend', 0);
    return new ApiError(detail ?? error.message, status, error.response.data);
  }
  return new ApiError(error instanceof Error ? error.message : 'Erreur inconnue');
}

// ===== Public API surface =====

export const api = {
  async health(): Promise<{ status: string; service: string; version: string }> {
    try {
      const { data } = await client.get('/health');
      return data;
    } catch (e) {
      throw toApiError(e);
    }
  },

  async getTransaction(transactionId: string): Promise<Transaction> {
    try {
      const { data } = await client.get<Transaction>(`/api/transactions/${transactionId}`);
      return data;
    } catch (e) {
      throw toApiError(e);
    }
  },

  async getTransactionHistory(
    accountId: string,
    filters: TransactionFilters = {},
  ): Promise<TransactionHistoryResponse> {
    try {
      const { data } = await client.get<TransactionHistoryResponse>(
        `/api/accounts/${accountId}/transactions`,
        { params: filters },
      );
      return data;
    } catch (e) {
      throw toApiError(e);
    }
  },

  async getRiskProfile(accountId: string): Promise<AccountRiskProfile> {
    try {
      const { data } = await client.get<AccountRiskProfile>(
        `/api/accounts/${accountId}/risk-profile`,
      );
      return data;
    } catch (e) {
      throw toApiError(e);
    }
  },

  // ---- Mistral agent endpoints ----

  async analyzeTransaction(transactionId: string): Promise<AnalyzeJobResponse> {
    try {
      const { data } = await client.post<AnalyzeJobResponse>(
        `/api/transactions/${transactionId}/analyze`,
      );
      return data;
    } catch (e) {
      throw toApiError(e);
    }
  },

  async getExplanation(transactionId: string): Promise<ExplanationResponse> {
    try {
      const { data } = await client.get<ExplanationResponse>(
        `/api/transactions/${transactionId}/explanation`,
      );
      return data;
    } catch (e) {
      throw toApiError(e);
    }
  },
};

export type Api = typeof api;
