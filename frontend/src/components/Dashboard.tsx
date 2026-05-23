import { useMemo, useState } from 'react';
import { useTransactions } from '../hooks/useTransactions';
import { useRiskProfile } from '../hooks/useRiskProfile';
import { useFraudAlerts } from '../hooks/useFraudAlerts';
import { StatCard } from './StatCard';
import { TransactionList } from './TransactionList';
import { RiskProfile } from './RiskProfile';
import { AlertsPanel } from './AlertsPanel';
import { MistralAnalysis } from './MistralAnalysis';
import { LoadingSpinner } from './LoadingSpinner';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { Transaction } from '../types';

interface DashboardProps {
  accountId: string;
}

interface DailyBucket {
  date: string;
  total: number;
  frauds: number;
}

function bucketByDay(transactions: Transaction[]): DailyBucket[] {
  const map = new Map<string, DailyBucket>();
  for (const t of transactions) {
    const day = t.timestamp.slice(0, 10);
    const bucket = map.get(day) ?? { date: day, total: 0, frauds: 0 };
    bucket.total += 1;
    if (t.is_fraud) bucket.frauds += 1;
    map.set(day, bucket);
  }
  return Array.from(map.values()).sort((a, b) => a.date.localeCompare(b.date));
}

export function Dashboard({ accountId }: DashboardProps) {
  const txns = useTransactions(accountId, { limit: 100 });
  const risk = useRiskProfile(accountId);
  const alerts = useFraudAlerts(accountId);

  const [selectedTransactionId, setSelectedTransactionId] = useState<string | null>(null);

  const transactions = txns.data?.transactions ?? [];
  const buckets = useMemo(() => bucketByDay(transactions), [transactions]);

  const fraudCount = risk.data?.risk_profile.fraud_count ?? 0;
  const txnCount = risk.data?.risk_profile.transaction_count ?? 0;
  const fraudRate = risk.data?.risk_profile.fraud_rate ?? 0;

  if (!accountId) {
    return (
      <p className="empty-state">
        Saisis un identifiant de compte ci-dessus pour démarrer.
      </p>
    );
  }

  return (
    <>
      <section className="stat-grid">
        <StatCard
          title="Transactions totales"
          value={loadingOr(risk.loading, txnCount.toLocaleString('fr-FR'))}
          icon="📊"
        />
        <StatCard
          title="Fraudes détectées"
          value={loadingOr(risk.loading, fraudCount.toLocaleString('fr-FR'))}
          icon="🚨"
          tone={fraudCount > 0 ? 'negative' : 'neutral'}
        />
        <StatCard
          title="Taux de fraude"
          value={loadingOr(risk.loading, `${(fraudRate * 100).toFixed(2)}%`)}
          icon="📈"
          tone={fraudRate > 0.05 ? 'negative' : 'positive'}
        />
      </section>

      <section className="card chart-card">
        <header className="card__header">
          <h2>Tendance fraude (par jour)</h2>
          <span className="muted small">{transactions.length} transactions</span>
        </header>
        {txns.loading ? (
          <LoadingSpinner label="Chargement des transactions…" />
        ) : buckets.length === 0 ? (
          <p className="empty-state">Pas de données à représenter.</p>
        ) : (
          <div style={{ width: '100%', height: 260 }}>
            <ResponsiveContainer>
              <BarChart data={buckets} margin={{ top: 16, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--c-border)" />
                <XAxis dataKey="date" stroke="var(--c-text-muted)" fontSize={12} />
                <YAxis allowDecimals={false} stroke="var(--c-text-muted)" fontSize={12} />
                <Tooltip
                  contentStyle={{
                    background: 'var(--c-surface)',
                    border: '1px solid var(--c-border)',
                    borderRadius: 6,
                  }}
                />
                <Bar dataKey="total" name="Total" fill="var(--c-ok)" radius={[4, 4, 0, 0]} />
                <Bar dataKey="frauds" name="Fraudes" fill="var(--c-fraud)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      <div className="grid-2">
        {risk.loading ? (
          <div className="card"><LoadingSpinner label="Chargement du profil…" /></div>
        ) : risk.error ? (
          <div className="card error">Profil indisponible : {risk.error}</div>
        ) : risk.data ? (
          <RiskProfile profile={risk.data} />
        ) : null}

        <AlertsPanel
          alerts={alerts.data}
          onSelect={(a) => setSelectedTransactionId(a.transaction_id)}
        />
      </div>

      <section className="card">
        <header className="card__header">
          <h2>Historique des transactions</h2>
          <button type="button" className="btn btn--ghost" onClick={() => void txns.refetch()}>
            Rafraîchir
          </button>
        </header>
        {txns.loading ? (
          <LoadingSpinner label="Chargement…" />
        ) : txns.error ? (
          <p className="error">{txns.error}</p>
        ) : (
          <TransactionList
            transactions={transactions}
            selectedId={selectedTransactionId}
            onSelect={(t) => setSelectedTransactionId(t.id)}
          />
        )}
      </section>

      <MistralAnalysis transactionId={selectedTransactionId} />
    </>
  );
}

function loadingOr(loading: boolean, value: string): string {
  return loading ? '…' : value;
}
