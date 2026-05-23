import {
  PolarAngleAxis,
  RadialBar,
  RadialBarChart,
  ResponsiveContainer,
} from 'recharts';
import type { AccountRiskProfile } from '../types';

interface RiskProfileProps {
  profile: AccountRiskProfile;
}

function riskBucket(score: number): 'low' | 'med' | 'high' | 'crit' {
  if (score >= 0.85) return 'crit';
  if (score >= 0.6) return 'high';
  if (score >= 0.3) return 'med';
  return 'low';
}

const BUCKET_LABELS: Record<ReturnType<typeof riskBucket>, string> = {
  low: 'Faible',
  med: 'Modéré',
  high: 'Élevé',
  crit: 'Critique',
};

const BUCKET_COLORS: Record<ReturnType<typeof riskBucket>, string> = {
  low: 'var(--c-ok)',
  med: 'var(--c-warn)',
  high: 'var(--c-fraud)',
  crit: 'var(--c-fraud)',
};

export function RiskProfile({ profile }: RiskProfileProps) {
  const rp = profile.risk_profile;
  const bucket = riskBucket(rp.historical_risk_score);
  const chartData = [{ name: 'risk', value: rp.historical_risk_score * 100, fill: BUCKET_COLORS[bucket] }];

  return (
    <section className="card risk-card">
      <header className="card__header">
        <div>
          <h2>Profil de risque</h2>
          <p className="muted small">{profile.holder_name} · {profile.account_id.slice(0, 8)}…</p>
        </div>
        <span className={`badge badge--${rp.is_high_risk ? 'fraud' : 'ok'}`}>
          {rp.is_high_risk ? 'À HAUT RISQUE' : 'OK'}
        </span>
      </header>

      <div className="risk-grid">
        <div className="risk-gauge">
          <ResponsiveContainer width="100%" height={180}>
            <RadialBarChart
              cx="50%"
              cy="50%"
              innerRadius="65%"
              outerRadius="100%"
              barSize={18}
              startAngle={90}
              endAngle={-270}
              data={chartData}
            >
              <PolarAngleAxis type="number" domain={[0, 100]} tick={false} />
              <RadialBar background dataKey="value" cornerRadius={9} />
            </RadialBarChart>
          </ResponsiveContainer>
          <div className="risk-gauge__value">
            <strong>{(rp.historical_risk_score * 100).toFixed(0)}%</strong>
            <span className="muted small">{BUCKET_LABELS[bucket]}</span>
          </div>
        </div>

        <dl className="risk-metrics">
          <div>
            <dt>Transactions</dt>
            <dd>{rp.transaction_count.toLocaleString('fr-FR')}</dd>
          </div>
          <div>
            <dt>Fraudes détectées</dt>
            <dd className={rp.fraud_count > 0 ? 'danger' : ''}>
              {rp.fraud_count.toLocaleString('fr-FR')}
            </dd>
          </div>
          <div>
            <dt>Taux de fraude</dt>
            <dd>{(rp.fraud_rate * 100).toFixed(2)}%</dd>
          </div>
          <div>
            <dt>Dernière maj</dt>
            <dd className="small">{new Date(rp.last_updated).toLocaleString('fr-FR')}</dd>
          </div>
        </dl>
      </div>
    </section>
  );
}
