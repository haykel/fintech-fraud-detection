import { useEffect, useState } from 'react';
import { Dashboard } from './components/Dashboard';
import { ErrorBoundary } from './components/ErrorBoundary';

const DEFAULT_ACCOUNT_ID = import.meta.env.VITE_DEFAULT_ACCOUNT_ID ?? '';

function readAccountFromUrl(): string {
  if (typeof window === 'undefined') return DEFAULT_ACCOUNT_ID;
  const params = new URLSearchParams(window.location.search);
  return params.get('account') ?? DEFAULT_ACCOUNT_ID;
}

export function App() {
  const [accountId, setAccountId] = useState<string>(readAccountFromUrl());
  const [draft, setDraft] = useState<string>(accountId);

  // Keep the URL ?account= param in sync so links are shareable.
  useEffect(() => {
    if (!accountId) return;
    const url = new URL(window.location.href);
    if (url.searchParams.get('account') !== accountId) {
      url.searchParams.set('account', accountId);
      window.history.replaceState({}, '', url);
    }
  }, [accountId]);

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <span className="app__logo" aria-hidden="true">🛡️</span>
          <div>
            <h1>Fraud Detection</h1>
            <p className="muted small">
              Tableau de bord analyste · {new Date().toLocaleDateString('fr-FR', {
                weekday: 'long',
                year: 'numeric',
                month: 'long',
                day: 'numeric',
              })}
            </p>
          </div>
        </div>

        <form
          className="app__account-form"
          onSubmit={(e) => {
            e.preventDefault();
            setAccountId(draft.trim());
          }}
        >
          <label htmlFor="account-input" className="visually-hidden">
            Identifiant de compte
          </label>
          <input
            id="account-input"
            type="text"
            placeholder="UUID du compte"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
          <button type="submit" className="btn btn--primary" disabled={!draft.trim()}>
            Charger
          </button>
        </form>
      </header>

      <main className="app__main">
        <ErrorBoundary>
          <Dashboard accountId={accountId} />
        </ErrorBoundary>
      </main>

      <footer className="app__footer">
        <span className="muted small">
          FinTech Fraud Detection · API {import.meta.env.VITE_API_URL || '/api (proxy)'}
        </span>
      </footer>
    </div>
  );
}
