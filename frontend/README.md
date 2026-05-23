# FinTech Fraud Dashboard

Dashboard React + TypeScript pour la plateforme FinTech Fraud Detection.

Stack : Vite, React 18, TypeScript (strict), Axios, Recharts.

## Lancement local

```bash
cd frontend
npm install
npm run dev
# Ouvre http://localhost:3000
```

Le serveur Vite proxifie automatiquement `/api/*` vers `http://localhost:8000`
(le backend FastAPI), donc le frontend et l'API partagent une origine en dev —
pas de soucis de CORS à régler.

Assure-toi d'avoir lancé le backend dans un autre terminal :

```bash
.venv/bin/uvicorn interfaces.api.main:app --reload --port 8000
```

## Configuration

Copie `.env.example` en `.env.local` (gitignoré) et ajuste :

| Variable | Défaut | Rôle |
|---|---|---|
| `VITE_API_URL` | vide (proxy `/api`) | URL absolue du backend si tu ne veux pas du proxy Vite |
| `VITE_DEFAULT_ACCOUNT_ID` | vide | UUID du compte pré-chargé au démarrage |

L'identifiant de compte peut aussi être passé via le query param `?account=<uuid>`
ou saisi dans la barre du header.

## Scripts

| Commande | Description |
|---|---|
| `npm run dev` | Serveur de développement sur :3000 avec HMR |
| `npm run build` | Vérif TypeScript + build prod dans `dist/` |
| `npm run preview` | Sert le build prod localement |
| `npm run typecheck` | Vérif TS sans build |

## Architecture

```
src/
├── components/
│   ├── Dashboard.tsx        # Page principale
│   ├── StatCard.tsx         # Tuile de KPI
│   ├── TransactionList.tsx  # Tableau des transactions cliquables
│   ├── RiskProfile.tsx      # Profil de risque + jauge radiale
│   ├── AlertsPanel.tsx      # Liste des alertes fraude (dérivées)
│   ├── MistralAnalysis.tsx  # Pilote l'agent IA (POST analyze + poll)
│   ├── LoadingSpinner.tsx
│   └── ErrorBoundary.tsx
├── hooks/
│   ├── useTransactions.ts
│   ├── useRiskProfile.ts
│   ├── useFraudAlerts.ts    # Dérive depuis /transactions?is_fraud=true
│   └── useExplanation.ts    # POST /analyze puis polling /explanation
├── services/
│   └── api.ts               # Client axios + retry exponentiel + ApiError
├── types/index.ts           # Types alignés sur les routes FastAPI
├── styles/App.css           # CSS pur, design tokens via variables
├── App.tsx                  # Shell + sélecteur de compte
└── main.tsx
```

## Endpoints consommés

| Méthode | URL | Hook |
|---|---|---|
| `GET` | `/health` | `api.health()` |
| `GET` | `/api/transactions/{id}` | `api.getTransaction()` |
| `GET` | `/api/accounts/{id}/transactions` | `useTransactions` |
| `GET` | `/api/accounts/{id}/risk-profile` | `useRiskProfile` |
| `GET` | `/api/accounts/{id}/transactions?is_fraud=true` | `useFraudAlerts` |
| `POST` | `/api/transactions/{id}/analyze` | `useExplanation.startAnalysis` |
| `GET` | `/api/transactions/{id}/explanation` | `useExplanation` (polling 2s) |

## Notes

- **Pas de framework UI** (Tailwind/MUI/Bootstrap). CSS pur, design tokens
  via variables CSS dans `:root`. Palette : `--c-ok` vert `#0F6E56`,
  `--c-fraud` rouge `#E24B4A`.
- **Strict TypeScript** : `noUncheckedIndexedAccess`, `noUnusedLocals`, etc.
- **Retry HTTP** : 2 retries (exponentiel 500ms → 1s) sur GET/HEAD pour les
  codes 408/429/5xx et les erreurs réseau.
- **Polling Mistral** : intervalle 2s, timeout dur 2 min (l'agent renvoie
  généralement en 3-15s en cloud, beaucoup plus lent en local Ollama).
