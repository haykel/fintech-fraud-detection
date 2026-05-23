import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError } from '../services/api';
import type { ExplanationResponse } from '../types';

export type AnalysisPhase = 'idle' | 'starting' | 'polling' | 'completed' | 'failed';

export interface UseExplanationResult {
  phase: AnalysisPhase;
  data: ExplanationResponse | null;
  error: string | null;
  startAnalysis: () => Promise<void>;
  reset: () => void;
}

const POLL_INTERVAL_MS = 2_000;
const POLL_TIMEOUT_MS = 120_000;

/**
 * Drives the Mistral agent: POST /analyze then polls /explanation until the
 * cache flips to status="completed" or "failed". Manages its own intervals.
 */
export function useExplanation(transactionId: string | null): UseExplanationResult {
  const [phase, setPhase] = useState<AnalysisPhase>('idle');
  const [data, setData] = useState<ExplanationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const pollTimerRef = useRef<number | null>(null);
  const stoppedRef = useRef<boolean>(false);

  const clearTimer = useCallback(() => {
    if (pollTimerRef.current !== null) {
      window.clearInterval(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    stoppedRef.current = true;
    clearTimer();
    setPhase('idle');
    setData(null);
    setError(null);
  }, [clearTimer]);

  const startAnalysis = useCallback(async () => {
    if (!transactionId) return;
    stoppedRef.current = false;
    clearTimer();
    setPhase('starting');
    setData(null);
    setError(null);

    try {
      await api.analyzeTransaction(transactionId);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Erreur au démarrage';
      setError(msg);
      setPhase('failed');
      return;
    }

    setPhase('polling');
    const startedAt = Date.now();

    pollTimerRef.current = window.setInterval(async () => {
      if (stoppedRef.current) return;
      try {
        const resp = await api.getExplanation(transactionId);
        if (stoppedRef.current) return;
        setData(resp);
        if (resp.status === 'completed') {
          clearTimer();
          setPhase('completed');
        } else if (resp.status === 'failed') {
          clearTimer();
          setError(resp.error ?? 'L\'agent a échoué');
          setPhase('failed');
        } else if (Date.now() - startedAt > POLL_TIMEOUT_MS) {
          clearTimer();
          setError('Timeout : agent toujours en cours après 2 min');
          setPhase('failed');
        }
      } catch (err) {
        // 404 is normal until the background task writes the first cache entry.
        if (err instanceof ApiError && err.status === 404) return;
        clearTimer();
        const msg = err instanceof ApiError ? err.message : 'Erreur de polling';
        setError(msg);
        setPhase('failed');
      }
    }, POLL_INTERVAL_MS);
  }, [clearTimer, transactionId]);

  // Cleanup on unmount or transactionId change.
  useEffect(() => {
    return () => {
      stoppedRef.current = true;
      clearTimer();
    };
  }, [clearTimer, transactionId]);

  return { phase, data, error, startAnalysis, reset };
}
