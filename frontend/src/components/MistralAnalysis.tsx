import { useExplanation } from '../hooks/useExplanation';
import { LoadingSpinner } from './LoadingSpinner';
import type { FraudAnalysisResult, Recommendation, RiskLevel } from '../types';

interface MistralAnalysisProps {
  transactionId: string | null;
}

const RECOMMENDATION_LABELS: Record<Recommendation, string> = {
  APPROVE: 'Approuver',
  REVIEW: 'À revoir',
  BLOCK_TRANSACTION: 'Bloquer la transaction',
  FREEZE_ACCOUNT: 'Geler le compte',
};

const RISK_TONES: Record<RiskLevel, 'ok' | 'warn' | 'danger' | 'crit' | 'muted'> = {
  LOW: 'ok',
  MEDIUM: 'warn',
  HIGH: 'danger',
  CRITICAL: 'crit',
  UNKNOWN: 'muted',
};

export function MistralAnalysis({ transactionId }: MistralAnalysisProps) {
  const { phase, data, error, startAnalysis, reset } = useExplanation(transactionId);

  if (!transactionId) {
    return (
      <section className="card mistral-card">
        <h2>Agent IA Mistral</h2>
        <p className="empty-state">
          Sélectionne une transaction pour lancer une analyse approfondie.
        </p>
      </section>
    );
  }

  const result = data?.result;

  return (
    <section className="card mistral-card">
      <header className="card__header">
        <h2>Agent IA Mistral</h2>
        <span className="muted small">txn {transactionId.slice(0, 8)}…</span>
      </header>

      <div className="mistral-actions">
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => void startAnalysis()}
          disabled={phase === 'starting' || phase === 'polling'}
        >
          {phase === 'idle' || phase === 'failed' ? 'Lancer l\'analyse' : 'Analyse en cours…'}
        </button>
        {(phase === 'completed' || phase === 'failed') && (
          <button type="button" className="btn btn--ghost" onClick={reset}>
            Réinitialiser
          </button>
        )}
      </div>

      {phase === 'starting' && <LoadingSpinner label="Envoi de la requête…" inline />}
      {phase === 'polling' && <LoadingSpinner label="L'agent réfléchit (jusqu'à 2 min)…" inline />}
      {error && phase === 'failed' && <p className="error">{error}</p>}

      {result && phase === 'completed' && <AnalysisReport result={result} />}
    </section>
  );
}

function AnalysisReport({ result }: { result: FraudAnalysisResult }) {
  const tone = RISK_TONES[result.risk_level];
  return (
    <div className="analysis-report">
      <div className="analysis-report__head">
        <span className={`badge badge--${tone}`}>{result.risk_level}</span>
        <span className="risk-score">
          Score : <strong>{(result.risk_score * 100).toFixed(0)}%</strong>
        </span>
        <span className="muted small">
          Confiance : {(result.confidence * 100).toFixed(0)}%
        </span>
      </div>

      <div className="analysis-report__reco">
        <span className="muted small">Recommandation</span>
        <strong>{RECOMMENDATION_LABELS[result.recommendation]}</strong>
      </div>

      <p className="analysis-report__text">{result.analysis}</p>

      <div className="factors">
        <div>
          <h4>Facteurs à risque</h4>
          {result.factors.high_risk.length === 0 ? (
            <p className="muted small">Aucun</p>
          ) : (
            <ul>{result.factors.high_risk.map((f) => <li key={f}>{f}</li>)}</ul>
          )}
        </div>
        <div>
          <h4>Facteurs atténuants</h4>
          {result.factors.low_risk.length === 0 ? (
            <p className="muted small">Aucun</p>
          ) : (
            <ul>{result.factors.low_risk.map((f) => <li key={f}>{f}</li>)}</ul>
          )}
        </div>
      </div>
    </div>
  );
}
