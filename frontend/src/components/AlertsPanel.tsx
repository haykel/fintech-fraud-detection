import type { FraudAlert } from '../types';

interface AlertsPanelProps {
  alerts: FraudAlert[];
  onSelect?: (alert: FraudAlert) => void;
}

const PRIORITY_LABELS: Record<FraudAlert['priority'], string> = {
  HIGH: 'Élevée',
  MEDIUM: 'Modérée',
  LOW: 'Faible',
};

function formatAmount(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat('fr-FR', { style: 'currency', currency }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
}

export function AlertsPanel({ alerts, onSelect }: AlertsPanelProps) {
  if (alerts.length === 0) {
    return (
      <section className="card alerts-card">
        <header className="card__header">
          <h2>Alertes fraude</h2>
          <span className="badge badge--ok">Aucune</span>
        </header>
        <p className="empty-state">Aucune transaction frauduleuse pour ce compte.</p>
      </section>
    );
  }

  return (
    <section className="card alerts-card">
      <header className="card__header">
        <h2>Alertes fraude</h2>
        <span className="badge badge--fraud">{alerts.length}</span>
      </header>
      <ul className="alert-list">
        {alerts.map((a) => (
          <li
            key={a.transaction_id}
            className={onSelect ? 'alert-item clickable' : 'alert-item'}
            onClick={() => onSelect?.(a)}
          >
            <div className="alert-item__top">
              <span className={`badge badge--priority-${a.priority.toLowerCase()}`}>
                {PRIORITY_LABELS[a.priority]}
              </span>
              <strong>{formatAmount(a.amount, a.currency)}</strong>
            </div>
            <div className="alert-item__merchant">{a.merchant_name ?? 'Marchand inconnu'}</div>
            <div className="muted small">{a.reason ?? 'Sans détail'}</div>
            <div className="muted small">{new Date(a.timestamp).toLocaleString('fr-FR')}</div>
          </li>
        ))}
      </ul>
    </section>
  );
}
