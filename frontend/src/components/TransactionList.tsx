import type { Transaction } from '../types';

interface TransactionListProps {
  transactions: Transaction[];
  onSelect?: (transaction: Transaction) => void;
  selectedId?: string | null;
}

const STATUS_LABELS: Record<Transaction['status'], string> = {
  PENDING: 'En attente',
  APPROVED: 'Approuvée',
  REJECTED: 'Rejetée',
  BLOCKED: 'Bloquée',
};

function formatAmount(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat('fr-FR', { style: 'currency', currency }).format(amount);
  } catch {
    return `${amount.toFixed(2)} ${currency}`;
  }
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('fr-FR', { dateStyle: 'short', timeStyle: 'short' });
}

export function TransactionList({ transactions, onSelect, selectedId }: TransactionListProps) {
  if (transactions.length === 0) {
    return <p className="empty-state">Aucune transaction à afficher.</p>;
  }

  return (
    <div className="table-wrap">
      <table className="txn-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Marchand</th>
            <th className="num">Montant</th>
            <th>Statut</th>
            <th className="num">Risque</th>
            <th>Fraude</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((t) => {
            const isSelected = selectedId === t.id;
            return (
              <tr
                key={t.id}
                className={`${isSelected ? 'selected ' : ''}${onSelect ? 'clickable' : ''}`}
                onClick={() => onSelect?.(t)}
              >
                <td>{formatDate(t.timestamp)}</td>
                <td>{t.merchant_name ?? <span className="muted">{t.merchant_id}</span>}</td>
                <td className="num">{formatAmount(t.amount, t.currency)}</td>
                <td>
                  <span className={`badge badge--${t.status.toLowerCase()}`}>
                    {STATUS_LABELS[t.status]}
                  </span>
                </td>
                <td className="num">
                  <span className={`risk-pill risk-pill--${riskBucket(t.risk_score)}`}>
                    {(t.risk_score * 100).toFixed(0)}%
                  </span>
                </td>
                <td>{t.is_fraud ? <span className="badge badge--fraud">FRAUDE</span> : '—'}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function riskBucket(score: number): 'low' | 'med' | 'high' | 'crit' {
  if (score >= 0.85) return 'crit';
  if (score >= 0.6) return 'high';
  if (score >= 0.3) return 'med';
  return 'low';
}
