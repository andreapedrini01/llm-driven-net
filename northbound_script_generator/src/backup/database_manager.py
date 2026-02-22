"""Database manager for PostgreSQL operations."""

import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional
from sqlalchemy import create_engine, text, MetaData, Table, Column, String, DateTime, Integer, Boolean, Text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from .models import DatabaseConfig

logger = logging.getLogger(__name__)

Base = declarative_base()


class BackupRecord(Base):
    """SQLAlchemy model for backup records."""
    __tablename__ = 'backup_records'
    
    backup_id = Column(String(255), primary_key=True)
    backup_type = Column(String(50), nullable=False)
    status = Column(String(50), nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False, default=0)
    compressed_size = Column(Integer, nullable=False, default=0)
    is_encrypted = Column(Boolean, nullable=False, default=False)
    checksum = Column(String(255), nullable=False)
    database_name = Column(String(255), nullable=False)
    metadata_json = Column(Text, nullable=True)


class DatabaseManager:
    """Manages PostgreSQL database operations for backup system."""
    
    def __init__(self, config: DatabaseConfig):
        """Initialize database manager.
        
        Args:
            config: Database configuration
        """
        self.config = config
        self.engine = None
        self.SessionLocal = None
        self._setup_database()
    
    def _setup_database(self):
        """Setup database connection and tables."""
        try:
            # Create engine with connection pooling
            self.engine = create_engine(
                self.config.connection_url,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=3600,
                echo=False
            )
            
            # Create session factory
            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )
            
            # Create tables if they don't exist
            Base.metadata.create_all(bind=self.engine)
            
            logger.info("Database manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to setup database: {e}")
            raise
    
    def test_connection(self) -> bool:
        """Test database connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                return result.fetchone()[0] == 1
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False
    
    def get_database_info(self) -> Dict[str, Any]:
        """Get database information.
        
        Returns:
            Dictionary with database information
        """
        try:
            with self.engine.connect() as conn:
                # Get database version
                version_result = conn.execute(text("SELECT version()"))
                version = version_result.fetchone()[0]
                
                # Get database size
                size_query = text("""
                    SELECT pg_size_pretty(pg_database_size(current_database())) as size,
                           pg_database_size(current_database()) as size_bytes
                """)
                size_result = conn.execute(size_query)
                size_info = size_result.fetchone()
                
                # Get table count
                table_count_query = text("""
                    SELECT count(*) FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                table_count_result = conn.execute(table_count_query)
                table_count = table_count_result.fetchone()[0]
                
                return {
                    'version': version,
                    'size_pretty': size_info[0],
                    'size_bytes': size_info[1],
                    'table_count': table_count,
                    'database_name': self.config.database,
                    'host': self.config.host,
                    'port': self.config.port
                }
                
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {}
    
    def create_backup_record(self, backup_info: Dict[str, Any]) -> bool:
        """Create a backup record in the database.
        
        Args:
            backup_info: Backup information dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session = self.SessionLocal()
            try:
                record = BackupRecord(
                    backup_id=backup_info['backup_id'],
                    backup_type=backup_info['backup_type'],
                    status=backup_info['status'],
                    created_at=backup_info.get('created_at', datetime.utcnow()),
                    completed_at=backup_info.get('completed_at'),
                    file_path=backup_info['file_path'],
                    file_size=backup_info.get('file_size', 0),
                    compressed_size=backup_info.get('compressed_size', 0),
                    is_encrypted=backup_info.get('is_encrypted', False),
                    checksum=backup_info['checksum'],
                    database_name=backup_info['database_name'],
                    metadata_json=backup_info.get('metadata_json')
                )
                
                session.add(record)
                session.commit()
                logger.info(f"Created backup record: {backup_info['backup_id']}")
                return True
                
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to create backup record: {e}")
                return False
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Database session error: {e}")
            return False
    
    def update_backup_record(self, backup_id: str, updates: Dict[str, Any]) -> bool:
        """Update a backup record.
        
        Args:
            backup_id: Backup identifier
            updates: Dictionary of fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session = self.SessionLocal()
            try:
                record = session.query(BackupRecord).filter(
                    BackupRecord.backup_id == backup_id
                ).first()
                
                if not record:
                    logger.warning(f"Backup record not found: {backup_id}")
                    return False
                
                for key, value in updates.items():
                    if hasattr(record, key):
                        setattr(record, key, value)
                
                session.commit()
                logger.info(f"Updated backup record: {backup_id}")
                return True
                
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to update backup record: {e}")
                return False
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Database session error: {e}")
            return False
    
    def get_backup_record(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """Get a backup record by ID.
        
        Args:
            backup_id: Backup identifier
            
        Returns:
            Backup record dictionary or None if not found
        """
        try:
            session = self.SessionLocal()
            try:
                record = session.query(BackupRecord).filter(
                    BackupRecord.backup_id == backup_id
                ).first()
                
                if not record:
                    return None
                
                return {
                    'backup_id': record.backup_id,
                    'backup_type': record.backup_type,
                    'status': record.status,
                    'created_at': record.created_at,
                    'completed_at': record.completed_at,
                    'file_path': record.file_path,
                    'file_size': record.file_size,
                    'compressed_size': record.compressed_size,
                    'is_encrypted': record.is_encrypted,
                    'checksum': record.checksum,
                    'database_name': record.database_name,
                    'metadata_json': record.metadata_json
                }
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Failed to get backup record: {e}")
            return None
    
    def list_backup_records(self, limit: int = 100, offset: int = 0) -> list:
        """List backup records.
        
        Args:
            limit: Maximum number of records to return
            offset: Number of records to skip
            
        Returns:
            List of backup record dictionaries
        """
        try:
            session = self.SessionLocal()
            try:
                records = session.query(BackupRecord).order_by(
                    BackupRecord.created_at.desc()
                ).limit(limit).offset(offset).all()
                
                return [
                    {
                        'backup_id': record.backup_id,
                        'backup_type': record.backup_type,
                        'status': record.status,
                        'created_at': record.created_at,
                        'completed_at': record.completed_at,
                        'file_path': record.file_path,
                        'file_size': record.file_size,
                        'compressed_size': record.compressed_size,
                        'is_encrypted': record.is_encrypted,
                        'checksum': record.checksum,
                        'database_name': record.database_name,
                        'metadata_json': record.metadata_json
                    }
                    for record in records
                ]
                
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Failed to list backup records: {e}")
            return []
    
    def delete_backup_record(self, backup_id: str) -> bool:
        """Delete a backup record.
        
        Args:
            backup_id: Backup identifier
            
        Returns:
            True if successful, False otherwise
        """
        try:
            session = self.SessionLocal()
            try:
                record = session.query(BackupRecord).filter(
                    BackupRecord.backup_id == backup_id
                ).first()
                
                if not record:
                    logger.warning(f"Backup record not found: {backup_id}")
                    return False
                
                session.delete(record)
                session.commit()
                logger.info(f"Deleted backup record: {backup_id}")
                return True
                
            except Exception as e:
                session.rollback()
                logger.error(f"Failed to delete backup record: {e}")
                return False
            finally:
                session.close()
                
        except Exception as e:
            logger.error(f"Database session error: {e}")
            return False
    
    def close(self):
        """Close database connections."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connections closed")