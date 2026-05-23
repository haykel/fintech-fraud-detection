import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../services/api';
import type { TransactionFilters, TransactionHistoryResponse } from '../types';

export interface UseTransactionsResult {
  data: TransactionHistoryResponse | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useTransactions(
  accountId: string,
  filters: TransactionFilters = {},
): UseTransactionsResult {
  const [data, setData] = useState<TransactionHistoryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(accountId));
  const [error, setError] = useState<string | null>(null);

  // Stable JSON key so the effect only re-fires on real change.
  const filtersKey = JSON.stringify(filters);

  const fetchTransactions = useCallback(async () => {
    if (!accountId) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api.getTransactionHistory(accountId, JSON.parse(filtersKey));
      setData(result);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Erreur inattendue';
      setError(msg);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [accountId, filtersKey]);

  useEffect(() => {
    void fetchTransactions();
  }, [fetchTransactions]);

  return { data, loading, error, refetch: fetchTransactions };
}
