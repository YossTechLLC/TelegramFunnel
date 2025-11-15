#!/usr/bin/env python
"""
💾 Database Connection Manager for GCRegisterAPI-10-26
Handles PostgreSQL connection pooling via Cloud SQL Connector
"""
import pg8000
from google.cloud.sql.connector import Connector
from contextlib import contextmanager
from config_manager import config_manager


class DatabaseManager:
    """Manages database connections using Cloud SQL Connector"""

    def __init__(self):
        self.config = config_manager.get_config()
        self.connector = Connector()
        print("💾 DatabaseManager initialized")

    def get_connection(self):
        """
        Create a database connection using Cloud SQL Connector

        Returns:
            pg8000 connection object
        """
        try:
            conn = self.connector.connect(
                self.config['cloud_sql_connection_name'],
                "pg8000",
                user=self.config['database_user'],
                password=self.config['database_password'],
                db=self.config['database_name']
            )
            return conn
        except Exception as e:
            print(f"❌ Database connection error: {e}")
            raise

    @contextmanager
    def get_db(self):
        """
        Context manager for database connections

        Usage:
            with db_manager.get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT ...")
        """
        conn = None
        try:
            conn = self.get_connection()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"❌ Database transaction error: {e}")
            raise
        finally:
            if conn:
                conn.close()


# Global database manager instance
db_manager = DatabaseManager()
