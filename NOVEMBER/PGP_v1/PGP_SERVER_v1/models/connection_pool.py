#!/usr/bin/env python
"""
Database connection pooling for Cloud SQL.
Uses SQLAlchemy with Cloud SQL Connector for optimal performance.
"""
import logging
from google.cloud.sql.connector import Connector
import sqlalchemy
from sqlalchemy import create_engine, pool, text
from sqlalchemy.orm import sessionmaker
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class ConnectionPool:
    """
    Connection pool manager for Cloud SQL PostgreSQL.

    Features:
    - Cloud SQL Connector integration
    - SQLAlchemy engine with QueuePool
    - Automatic connection recycling
    - Connection health checks
    - Thread-safe operations

    Architecture:
    - Uses Cloud SQL Python Connector (not direct connection)
    - QueuePool maintains pool of connections
    - Pre-ping ensures connections are alive before use
    - Automatic connection recycling after 30 minutes
    """

    def __init__(self, config: dict):
        """
        Initialize connection pool.

        Args:
            config: Database configuration
                {
                    'instance_connection_name': 'project:region:instance',
                    'database': 'database_name',
                    'user': 'username',
                    'password': 'password',
                    'pool_size': 5,           # Optional, default: 5
                    'max_overflow': 10,       # Optional, default: 10
                    'pool_timeout': 30,       # Optional, default: 30s
                    'pool_recycle': 1800      # Optional, default: 1800s (30 min)
                }
        """
        self.config = config
        self.connector = None
        self.engine = None
        self.SessionLocal = None

        self._initialize_pool()

    def _get_conn(self):
        """
        Get database connection using Cloud SQL Connector.

        This function is called by SQLAlchemy when it needs a new connection.
        Uses Cloud SQL Connector to create connection via Unix socket.

        Returns:
            Database connection object (pg8000 connection)
        """
        conn = self.connector.connect(
            self.config['instance_connection_name'],
            "pg8000",
            user=self.config['user'],
            password=self.config['password'],
            db=self.config['database']
        )
        return conn

    def _initialize_pool(self):
        """
        Initialize SQLAlchemy engine with connection pool.

        Creates:
        - Cloud SQL Connector instance
        - SQLAlchemy engine with QueuePool
        - SessionLocal factory for ORM sessions
        """
        try:
            # Initialize Cloud SQL connector
            self.connector = Connector()

            logger.info("🔌 [DB_POOL] Initializing Cloud SQL connector...")

            # Create SQLAlchemy engine with connection pool
            self.engine = create_engine(
                "postgresql+pg8000://",
                creator=self._get_conn,
                poolclass=pool.QueuePool,
                pool_size=self.config.get('pool_size', 5),
                max_overflow=self.config.get('max_overflow', 10),
                pool_timeout=self.config.get('pool_timeout', 30),
                pool_recycle=self.config.get('pool_recycle', 1800),  # 30 minutes
                pool_pre_ping=True,  # Health check before using connection
                echo=False  # Set to True for SQL query logging
            )

            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            logger.info("✅ [DB_POOL] Connection pool initialized")
            logger.info(f"   Instance: {self.config['instance_connection_name']}")
            logger.info(f"   Database: {self.config['database']}")
            logger.info(f"   Pool size: {self.config.get('pool_size', 5)}")
            logger.info(f"   Max overflow: {self.config.get('max_overflow', 10)}")
            logger.info(f"   Pool timeout: {self.config.get('pool_timeout', 30)}s")
            logger.info(f"   Pool recycle: {self.config.get('pool_recycle', 1800)}s")

        except Exception as e:
            logger.error(f"❌ [DB_POOL] Failed to initialize pool: {e}", exc_info=True)
            raise

    def get_session(self):
        """
        Get database session from pool.

        Usage:
            with connection_pool.get_session() as session:
                result = session.execute(text("SELECT * FROM users"))
                session.commit()

        Returns:
            SQLAlchemy session from pool
        """
        return self.SessionLocal()

    def execute_query(self, query: str, params: Optional[dict] = None):
        """
        Execute raw SQL query with connection from pool.

        Args:
            query: SQL query string
            params: Query parameters (optional)

        Returns:
            Query result

        Example:
            result = pool.execute_query(
                "SELECT * FROM users WHERE id = :user_id",
                {'user_id': 123}
            )
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            conn.commit()
            return result

    def health_check(self) -> bool:
        """
        Check database connection health.

        Attempts to execute a simple query to verify connectivity.

        Returns:
            True if healthy, False otherwise
        """
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✅ [DB_POOL] Health check passed")
            return True
        except Exception as e:
            logger.error(f"❌ [DB_POOL] Health check failed: {e}")
            return False

    def get_pool_status(self) -> Dict[str, Any]:
        """
        Get current pool status and statistics.

        Returns:
            Dictionary with pool status information
        """
        if not self.engine:
            return {'status': 'not_initialized'}

        pool_obj = self.engine.pool

        return {
            'status': 'healthy',
            'size': pool_obj.size(),
            'checked_in': pool_obj.checkedin(),
            'checked_out': pool_obj.checkedout(),
            'overflow': pool_obj.overflow(),
            'total_connections': pool_obj.size() + pool_obj.overflow()
        }

    def close(self):
        """
        Close connection pool and connector.

        Should be called on application shutdown to clean up resources.
        """
        try:
            if self.engine:
                self.engine.dispose()
                logger.info("✅ [DB_POOL] Engine disposed")

            if self.connector:
                self.connector.close()
                logger.info("✅ [DB_POOL] Connector closed")

        except Exception as e:
            logger.error(f"❌ [DB_POOL] Error closing pool: {e}", exc_info=True)


def init_connection_pool(config: dict) -> ConnectionPool:
    """
    Factory function to initialize connection pool.

    Args:
        config: Database configuration
            {
                'instance_connection_name': 'project:region:instance',
                'database': 'database_name',
                'user': 'username',
                'password': 'password',
                'pool_size': 5,
                'max_overflow': 10,
                'pool_timeout': 30,
                'pool_recycle': 1800
            }

    Returns:
        ConnectionPool instance

    Example:
        config = {
            'instance_connection_name': 'telepay-459221:us-central1:telepaypsql',
            'database': 'telepaydb',
            'user': 'postgres',
            'password': 'secret',
            'pool_size': 5,
            'max_overflow': 10
        }
        pool = init_connection_pool(config)
    """
    return ConnectionPool(config)
