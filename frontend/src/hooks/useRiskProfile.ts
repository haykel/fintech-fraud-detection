import { useCallback, useEffect, useState } from 'react';
import { api, ApiError } from '../services/api';
import type { AccountRiskProfile } from '../types';

export interface UseRiskProfileResult {
  data: AccountRiskProfile | null;
  loading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useRiskProfile(accountId: string): UseRiskProfileResult {
  const [data, setData] = useState<AccountRiskProfile | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(accountId));
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!accountId) {
      setData(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api.getRiskProfile(accountId);
      setData(result);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Erreur inattendue';
      setError(msg);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [accountId]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}
