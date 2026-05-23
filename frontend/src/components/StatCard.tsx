import type { ReactNode } from 'react';

interface StatCardProps {
  title: string;
  value: ReactNode;
  icon?: ReactNode;
  trend?: number;
  tone?: 'neutral' | 'positive' | 'negative';
}

export function StatCard({ title, value, icon, trend, tone = 'neutral' }: StatCardProps) {
  return (
    <article className={`stat-card stat-card--${tone}`}>
      <header className="stat-card__header">
        {icon && <span className="stat-card__icon" aria-hidden="true">{icon}</span>}
        <h3 className="stat-card__title">{title}</h3>
      </header>
      <div className="stat-card__value">{value}</div>
      {typeof trend === 'number' && (
        <span className={`stat-card__trend stat-card__trend--${trend >= 0 ? 'up' : 'down'}`}>
          {trend >= 0 ? '▲' : '▼'} {Math.abs(trend).toFixed(1)}%
        </span>
      )}
    </article>
  );
}
