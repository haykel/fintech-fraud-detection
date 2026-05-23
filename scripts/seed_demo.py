"""scripts/seed_demo.py — peuple Postgres avec un compte démo + transactions.

Idempotent : tous les UUIDs sont stables, les saves utilisent `session.merge` côté
repositories, donc relancer le script met juste à jour les enregistrements.

Usage :
    .venv/bin/python scripts/seed_demo.py

Pré-requis : Postgres up via docker-compose (port 5432 exposé).
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

# Permet d'exécuter le script depuis n'importe où.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from domain.account import Account, AccountStatus  # noqa: E402
from domain.transaction import Money, Transaction, TransactionStatus  # noqa: E402
from infrastructure.postgres.repositories import (  # noqa: E402
    PostgresAccountRepository,
    PostgresTransactionRepository,
    init_db,
)


DEMO_ACCOUNT_ID = "11111111-1111-1111-1111-111111111111"

# UUIDs stables pour rendre le seed idempotent (merge = upsert).
TXN_SPECS = [
    # (uuid, offset_days, amount, ccy, merchant, category, country, is_fraud, score, reason)
    ("aaaaaaaa-0001-0001-0001-000000000001",  0,    45.00, "EUR", "Boulangerie du Coin",     "food",           "FR", False, 0.05, None),
    ("aaaaaaaa-0002-0002-0002-000000000002", -1,  1200.50, "EUR", "Apple Store",             "electronics",    "FR", False, 0.12, None),
    ("aaaaaaaa-0003-0003-0003-000000000003", -2,    89.90, "EUR", "Netflix",                 "subscription",   "NL", False, 0.08, None),
    ("aaaaaaaa-0004-0004-0004-000000000004", -3,   320.00, "EUR", "Carrefour Drive",         "groceries",      "FR", False, 0.10, None),
    ("aaaaaaaa-0005-0005-0005-000000000005", -3,  8500.00, "EUR", "Crypto Vault Anonymous",  "crypto",         "KP", True,  0.92, "rule_geolocation, rule_unusual_merchant"),
    ("aaaaaaaa-0006-0006-0006-000000000006", -5, 25000.00, "EUR", "Western Express Wire",    "money_transfer", "IR", True,  0.96, "rule_high_amount, rule_unusual_merchant, rule_geolocation"),
]


def _mask_db_url(url: str) -> str:
    """Cache le mot de passe dans une URL postgresql://user:pass@host..."""
    if "://" not in url or "@" not in url:
        return url
    proto, rest = url.split("://", 1)
    creds, host = rest.split("@", 1)
    if ":" in creds:
        user, _ = creds.split(":", 1)
        return f"{proto}://{user}:***@{host}"
    return url


async def seed() -> None:
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/fintech_db",
    )
    print(f"→ DB cible : {_mask_db_url(db_url)}")
    print("→ init_db (create tables si absentes)…")
    await init_db()

    account_repo = PostgresAccountRepository()
    txn_repo = PostgresTransactionRepository()

    account = Account(
        id=DEMO_ACCOUNT_ID,
        holder_name="Alice Demo",
        email="alice.demo@example.com",
        status=AccountStatus.ACTIVE,
    )
    print(f"→ Sauvegarde du compte {DEMO_ACCOUNT_ID} (Alice Demo)…")
    await account_repo.save(account)

    now = datetime.utcnow()
    fraud_count = 0
    risk_scores: list[float] = []

    print(f"→ Insertion de {len(TXN_SPECS)} transactions…")
    for spec in TXN_SPECS:
        uid, offset, amount, ccy, merchant, category, country, is_fraud, score, reason = spec
        ts = now + timedelta(days=offset)
        txn = Transaction(
            id=uid,
            account_id=DEMO_ACCOUNT_ID,
            amount=Money(Decimal(str(amount)), ccy),
            merchant_id=f"m-{abs(hash(merchant)) % 10000:04d}",
            merchant_name=merchant,
            merchant_category=category,
            merchant_country=country,
            transaction_country=country,
            timestamp=ts,
            status=TransactionStatus.APPROVED,
        )
        if is_fraud and reason is not None:
            txn.mark_as_fraudulent(risk_score=score, reason=reason)
            fraud_count += 1
        risk_scores.append(score)
        await txn_repo.save(txn)
        marker = "🚨" if is_fraud else "✓ "
        print(
            f"  {marker} {ts:%Y-%m-%d} {amount:>9.2f} {ccy}  "
            f"{merchant[:30]:<30} ({country})  risk={score:.2f}"
        )

    avg = sum(risk_scores) / len(risk_scores)
    account.update_risk_profile(
        historical_risk_score=avg,
        transaction_count=len(TXN_SPECS),
        fraud_count=fraud_count,
    )
    await account_repo.save(account)

    print()
    print("✓ Seed terminé.")
    print(f"  Compte         : {DEMO_ACCOUNT_ID}")
    print(f"  Transactions   : {len(TXN_SPECS)} (dont {fraud_count} fraudes)")
    print(f"  Score moyen    : {avg:.2f}")
    print()
    print("Ouvre maintenant le dashboard :")
    print(f"  http://localhost:3000/?account={DEMO_ACCOUNT_ID}")


if __name__ == "__main__":
    asyncio.run(seed())
