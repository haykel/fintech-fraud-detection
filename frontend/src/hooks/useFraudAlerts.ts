import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../services/api';
import type { AlertPriority, FraudAlert, Transaction } from '../types';

export interface UseFraudAlertsResult {
  data: FraudAlert[];
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

function priorityFromRiskScore(score: number): AlertPriority {
  if (score >= 0.85) return 'HIGH';
  if (score >= 0.6) return 'MEDIUM';
  return 'LOW';
}

function toAlert(t: Transaction): FraudAlert {
  return {
    transaction_id: t.id,
    account_id: t.account_id,
    amount: t.amount,
    currency: t.currency,
    merchant_name: t.merchant_name,
    reason: t.fraud_reason,
    priority: priorityFromRiskScore(t.risk_score),
    risk_score: t.risk_score,
    timestamp: t.timestamp,
  };
}

/**
 * The backend has no dedicated `/fraud-alerts` endpoint, so we derive alerts
 * from the account's transaction history filtered on `is_fraud=true`.
 */
export function useFraudAlerts(accountId: string, limit = 20): UseFraudAlertsResult {
  const [data, setData] = useState<FraudAlert[]>([]);
  const [loading, setLoading] = useState<boolean>(Boolean(accountId));
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!accountId) {
      setData([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api.getTransactionHistory(accountId, {
        is_fraud: true,
        limit,
      });
      setData(result.transactions.map(toAlert));
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Erreur inattendue';
      setError(msg);
      setData([]);
    } finally {
      setLoading(false);
    }
  }, [accountId, limit]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}
