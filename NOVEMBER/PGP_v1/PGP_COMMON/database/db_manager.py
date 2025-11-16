#!/usr/bin/env python
"""
Base Database Manager for PGP_v1 Services.
Provides common database connection and utility methods shared across all PGP_v1 microservices.
"""
from datetime import datetime
from typing import Optional
from google.cloud.sql.connector import Connector


class BaseDatabaseManager:
    """
    Base class for database operations across all PGP_v1 services.

    This class provides common methods for:
    - Creating database connections using Cloud SQL Connector
    - Getting current timestamps and datestamps
    - Connection pooling and management

    Service-specific query methods remain in subclasses.
    """

    def __init__(self, instance_connection_name: str, db_name: str, db_user: str, db_password: str, service_name: str):
        """
        Initialize the BaseDatabaseManager.

        Args:
            instance_connection_name: Cloud SQL instance connection name
            db_name: Database name
            db_user: Database user
            db_password: Database password
            service_name: Name of the service (for logging)
        """
        self.instance_connection_name = instance_connection_name
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.service_name = service_name
        self.connector = Connector()

        print(f"🗄️ [DATABASE] DatabaseManager initialized for {service_name}")
        print(f"📊 [DATABASE] Instance: {instance_connection_name}")
        print(f"📊 [DATABASE] Database: {db_name}")

    def get_connection(self):
        """
        Create and return a database connection using Cloud SQL Connector.

        This method is 100% identical across all PGP_v1 services.

        Returns:
            Database connection object or None if failed
        """
        try:
            connection = self.connector.connect(
                self.instance_connection_name,
                "pg8000",
                user=self.db_user,
                password=self.db_password,
                db=self.db_name
            )
            print(f"🔗 [DATABASE] Connection established successfully")
            return connection

        except Exception as e:
            print(f"❌ [DATABASE] Connection failed: {e}")
            return None

    def get_current_timestamp(self) -> str:
        """
        Get current time in PostgreSQL time format.

        This method is 100% identical across all services.

        Returns:
            String representation of current time (e.g., '22:55:30')
        """
        now = datetime.now()
        return now.strftime('%H:%M:%S')

    def get_current_datestamp(self) -> str:
        """
        Get current date in PostgreSQL date format.

        This method is 100% identical across all services.

        Returns:
            String representation of current date (e.g., '2025-06-20')
        """
        now = datetime.now()
        return now.strftime('%Y-%m-%d')

    def execute_query(self, query: str, params: tuple, fetch_one: bool = False, fetch_all: bool = False) -> Optional[any]:
        """
        Execute a database query with automatic connection management.

        Args:
            query: SQL query string
            params: Query parameters tuple
            fetch_one: If True, return single row
            fetch_all: If True, return all rows

        Returns:
            Query result or None if failed
        """
        conn = None
        cur = None
        try:
            conn = self.get_connection()
            if not conn:
                print(f"❌ [DATABASE] Could not establish connection")
                return None

            cur = conn.cursor()
            cur.execute(query, params)

            if fetch_one:
                result = cur.fetchone()
                return result
            elif fetch_all:
                result = cur.fetchall()
                return result
            else:
                # For INSERT/UPDATE/DELETE operations
                conn.commit()
                rows_affected = cur.rowcount
                print(f"✅ [DATABASE] Query executed, {rows_affected} row(s) affected")
                return rows_affected

        except Exception as e:
            if conn:
                try:
                    conn.rollback()
                    print(f"🔄 [DATABASE] Transaction rolled back")
                except Exception:
                    pass
            print(f"❌ [DATABASE] Error executing query: {e}")
            return None

        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                print(f"🔌 [DATABASE] Connection closed")

    def close_connector(self):
        """
        Close the Cloud SQL Connector.

        Call this when shutting down the service.
        """
        try:
            self.connector.close()
            print(f"🔌 [DATABASE] Connector closed")
        except Exception as e:
            print(f"❌ [DATABASE] Error closing connector: {e}")
