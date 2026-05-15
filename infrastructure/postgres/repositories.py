from typing import Optional, List
from domain.transaction import Transaction
from domain.account import Account


class PostgresTransactionRepository:
    """
    Repository adapter pour les Transactions en PostgreSQL
    
    En développement réel, utiliser une librairie ORM comme SQLAlchemy
    """
    
    def __init__(self):
        # Connection pool à initialiser
        self.db = None
    
    async def find_by_id(self, transaction_id: str) -> Optional[Transaction]:
        """Finds a transaction by ID"""
        # TODO: Implémenter avec sqlalchemy
        return None
    
    async def find_by_account_id(self, account_id: str) -> List[Transaction]:
        """Finds all transactions for an account"""
        # TODO: Implémenter avec sqlalchemy
        return []
    
    async def save(self, transaction: Transaction) -> None:
        """Saves a transaction"""
        # TODO: Implémenter avec sqlalchemy
        pass


class PostgresAccountRepository:
    """
    Repository adapter pour les Accounts en PostgreSQL
    """
    
    def __init__(self):
        # Connection pool à initialiser
        self.db = None
    
    async def find_by_id(self, account_id: str) -> Optional[Account]:
        """Finds an account by ID"""
        # TODO: Implémenter avec sqlalchemy
        return None
    
    async def save(self, account: Account) -> None:
        """Saves an account"""
        # TODO: Implémenter avec sqlalchemy
        pass