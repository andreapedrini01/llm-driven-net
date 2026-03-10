"""Main backup service implementation."""

import asyncio
import gzip
import hashlib
import json
import logging
import os
import shutil
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from cryptography.fernet import Fernet

from .models import (
    BackupType, BackupStatus, BackupInfo, BackupResult, RestoreResult,
    BackupConfig, BackupFilters, BackupSchedule, VerificationResult,
    CleanupResult, DatabaseConfig, BackupMetrics
)
from .database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class BackupService:
    """Main backup and recovery service."""
    
    def __init__(self, config: BackupConfig, db_config: DatabaseConfig):
        """Initialize backup service.
        
        Args:
            config: Backup configuration
            db_config: Database configuration
        """
        self.config = config
        self.db_config = db_config
        self.db_manager = DatabaseManager(db_config)
        
        # Setup backup directory
        self.backup_dir = Path(config.backup_directory)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup encryption if enabled
        self.cipher = None
        if config.encryption_enabled:
            self._setup_encryption()
        
        # Verify pg_dump availability
        self._verify_pg_tools()
        
        logger.info("Backup service initialized")
    
    def _setup_encryption(self):
        """Setup encryption for backups."""
        try:
            if self.config.encryption_key:
                # Use provided key
                key = self.config.encryption_key.encode()
                if len(key) != 44:  # Fernet key should be 44 bytes when base64 encoded
                    # Generate key from provided string
                    key = hashlib.sha256(key).digest()
                    key = Fernet.generate_key()
            else:
                # Generate new key
                key = Fernet.generate_key()
                logger.warning("No encryption key provided, generated new key")
            
            self.cipher = Fernet(key)
            logger.info("Encryption setup completed")
            
        except Exception as e:
            logger.error(f"Failed to setup encryption: {e}")
            raise
    
    def _verify_pg_tools(self):
        """Verify PostgreSQL tools are available."""
        try:
            # Check pg_dump
            result = subprocess.run(
                [self.config.pg_dump_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError(f"pg_dump not found or not working: {result.stderr}")
            
            # Check psql
            result = subprocess.run(
                [self.config.psql_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                raise RuntimeError(f"psql not found or not working: {result.stderr}")
            
            logger.info("PostgreSQL tools verified successfully")
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("Timeout verifying PostgreSQL tools")
        except Exception as e:
            logger.error(f"Failed to verify PostgreSQL tools: {e}")
            raise
    
    def create_backup(self, backup_type: BackupType = BackupType.FULL) -> BackupResult:
        """Create a database backup.
        
        Args:
            backup_type: Type of backup to create
            
        Returns:
            BackupResult with operation details
        """
        backup_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        logger.info(f"Starting backup {backup_id} (type: {backup_type})")
        
        try:
            # Create backup record
            backup_info = {
                'backup_id': backup_id,
                'backup_type': backup_type.value,
                'status': BackupStatus.RUNNING.value,
                'created_at': start_time,
                'file_path': '',
                'checksum': '',
                'database_name': self.db_config.database
            }
            
            if not self.db_manager.create_backup_record(backup_info):
                raise RuntimeError("Failed to create backup record")
            
            # Generate backup file path
            timestamp = start_time.strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{self.db_config.database}_{backup_type.value}_{timestamp}.sql"
            backup_path = self.backup_dir / backup_filename
            
            # Create the backup using pg_dump
            dump_result = self._create_pg_dump(backup_path, backup_type)
            
            if not dump_result['success']:
                raise RuntimeError(f"pg_dump failed: {dump_result['error']}")
            
            # Get file size before compression/encryption
            original_size = backup_path.stat().st_size
            
            # Compress backup if enabled
            compressed_size = original_size
            if self.config.compression_enabled:
                compressed_path = self._compress_backup(backup_path)
                backup_path = compressed_path
                compressed_size = backup_path.stat().st_size
            
            # Encrypt backup if enabled
            if self.config.encryption_enabled and self.cipher:
                encrypted_path = self._encrypt_backup(backup_path)
                backup_path = encrypted_path
            
            # Calculate checksum
            checksum = self._calculate_checksum(backup_path)
            
            # Update backup record
            completion_time = datetime.utcnow()
            duration = (completion_time - start_time).total_seconds()
            
            updates = {
                'status': BackupStatus.COMPLETED.value,
                'completed_at': completion_time,
                'file_path': str(backup_path),
                'file_size': original_size,
                'compressed_size': compressed_size,
                'is_encrypted': self.config.encryption_enabled,
                'checksum': checksum
            }
            
            if not self.db_manager.update_backup_record(backup_id, updates):
                logger.warning(f"Failed to update backup record: {backup_id}")
            
            # Create BackupInfo object
            backup_info_obj = BackupInfo(
                backup_id=backup_id,
                backup_type=backup_type,
                status=BackupStatus.COMPLETED,
                created_at=start_time,
                completed_at=completion_time,
                file_path=str(backup_path),
                file_size=original_size,
                compressed_size=compressed_size,
                is_encrypted=self.config.encryption_enabled,
                checksum=checksum,
                database_name=self.db_config.database,
                metadata={
                    'pg_dump_version': dump_result.get('version', ''),
                    'compression_ratio': compressed_size / original_size if original_size > 0 else 1.0
                }
            )
            
            logger.info(f"Backup {backup_id} completed successfully in {duration:.2f}s")
            
            return BackupResult(
                backup_id=backup_id,
                status=BackupStatus.COMPLETED,
                message=f"Backup completed successfully",
                backup_info=backup_info_obj,
                duration_seconds=duration
            )
            
        except Exception as e:
            # Update backup record as failed
            self.db_manager.update_backup_record(backup_id, {
                'status': BackupStatus.FAILED.value,
                'completed_at': datetime.utcnow()
            })
            
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            logger.error(f"Backup {backup_id} failed: {error_msg}")
            
            return BackupResult(
                backup_id=backup_id,
                status=BackupStatus.FAILED,
                message=f"Backup failed: {error_msg}",
                error_details=error_msg,
                duration_seconds=duration
            )
    
    def _create_pg_dump(self, backup_path: Path, backup_type: BackupType) -> Dict[str, Any]:
        """Create PostgreSQL dump.
        
        Args:
            backup_path: Path for backup file
            backup_type: Type of backup
            
        Returns:
            Dictionary with success status and details
        """
        try:
            # Build pg_dump command
            cmd = [
                self.config.pg_dump_path,
                "--host", self.db_config.host,
                "--port", str(self.db_config.port),
                "--username", self.db_config.username,
                "--dbname", self.db_config.database,
                "--no-password",
                "--verbose",
                "--file", str(backup_path)
            ]
            
            # Add backup type specific options
            if backup_type == BackupType.FULL:
                cmd.extend(["--clean", "--create", "--if-exists"])
            elif backup_type == BackupType.INCREMENTAL:
                # For incremental, we'll do data-only dump
                # In a real implementation, you'd track changes
                cmd.extend(["--data-only"])
            
            # Set environment for password
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_config.password
            
            # Execute pg_dump
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': result.stderr or "pg_dump failed with no error message"
                }
            
            # Get pg_dump version
            version_result = subprocess.run(
                [self.config.pg_dump_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            return {
                'success': True,
                'version': version_result.stdout.strip() if version_result.returncode == 0 else '',
                'output': result.stderr  # pg_dump outputs to stderr
            }
            
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'pg_dump timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _compress_backup(self, backup_path: Path) -> Path:
        """Compress backup file.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            Path to compressed file
        """
        compressed_path = backup_path.with_suffix(backup_path.suffix + '.gz')
        
        with open(backup_path, 'rb') as f_in:
            with gzip.open(compressed_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Remove original file
        backup_path.unlink()
        
        logger.info(f"Compressed backup: {compressed_path}")
        return compressed_path
    
    def _encrypt_backup(self, backup_path: Path) -> Path:
        """Encrypt backup file.
        
        Args:
            backup_path: Path to backup file
            
        Returns:
            Path to encrypted file
        """
        encrypted_path = backup_path.with_suffix(backup_path.suffix + '.enc')
        
        with open(backup_path, 'rb') as f_in:
            data = f_in.read()
            encrypted_data = self.cipher.encrypt(data)
            
            with open(encrypted_path, 'wb') as f_out:
                f_out.write(encrypted_data)
        
        # Remove original file
        backup_path.unlink()
        
        logger.info(f"Encrypted backup: {encrypted_path}")
        return encrypted_path
    
    def _calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of file.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hexadecimal checksum string
        """
        sha256_hash = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()
    
    def restore_backup(self, backup_id: str) -> RestoreResult:
        """Restore from backup.
        
        Args:
            backup_id: Backup identifier
            
        Returns:
            RestoreResult with operation details
        """
        restore_id = str(uuid.uuid4())
        start_time = datetime.utcnow()
        
        logger.info(f"Starting restore {restore_id} from backup {backup_id}")
        
        try:
            # Get backup record
            backup_record = self.db_manager.get_backup_record(backup_id)
            if not backup_record:
                raise RuntimeError(f"Backup not found: {backup_id}")
            
            backup_path = Path(backup_record['file_path'])
            if not backup_path.exists():
                raise RuntimeError(f"Backup file not found: {backup_path}")
            
            # Verify backup integrity
            verification = self.verify_backup(backup_id)
            if not verification.is_valid:
                raise RuntimeError(f"Backup verification failed: {verification.error_details}")
            
            # Prepare backup file for restore
            restore_file = self._prepare_backup_for_restore(backup_path, backup_record)
            
            try:
                # Perform restore
                restore_result = self._perform_restore(restore_file)
                
                if not restore_result['success']:
                    raise RuntimeError(f"Restore failed: {restore_result['error']}")
                
                duration = (datetime.utcnow() - start_time).total_seconds()
                
                logger.info(f"Restore {restore_id} completed successfully in {duration:.2f}s")
                
                return RestoreResult(
                    restore_id=restore_id,
                    backup_id=backup_id,
                    status="completed",
                    message="Restore completed successfully",
                    restored_at=datetime.utcnow(),
                    duration_seconds=duration
                )
                
            finally:
                # Clean up temporary restore file if it's different from original
                if restore_file != backup_path and restore_file.exists():
                    restore_file.unlink()
            
        except Exception as e:
            duration = (datetime.utcnow() - start_time).total_seconds()
            error_msg = str(e)
            
            logger.error(f"Restore {restore_id} failed: {error_msg}")
            
            return RestoreResult(
                restore_id=restore_id,
                backup_id=backup_id,
                status="failed",
                message=f"Restore failed: {error_msg}",
                restored_at=datetime.utcnow(),
                duration_seconds=duration,
                error_details=error_msg
            )
    
    def _prepare_backup_for_restore(self, backup_path: Path, backup_record: Dict[str, Any]) -> Path:
        """Prepare backup file for restore (decrypt/decompress if needed).
        
        Args:
            backup_path: Path to backup file
            backup_record: Backup record from database
            
        Returns:
            Path to prepared backup file
        """
        current_path = backup_path
        
        # Decrypt if encrypted
        if backup_record['is_encrypted'] and self.cipher:
            decrypted_path = backup_path.with_suffix('.decrypted')
            
            with open(current_path, 'rb') as f_in:
                encrypted_data = f_in.read()
                decrypted_data = self.cipher.decrypt(encrypted_data)
                
                with open(decrypted_path, 'wb') as f_out:
                    f_out.write(decrypted_data)
            
            current_path = decrypted_path
        
        # Decompress if compressed
        if str(backup_path).endswith('.gz'):
            decompressed_path = current_path.with_suffix('')
            
            with gzip.open(current_path, 'rb') as f_in:
                with open(decompressed_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            
            # Remove decrypted file if it was temporary
            if current_path != backup_path:
                current_path.unlink()
            
            current_path = decompressed_path
        
        return current_path
    
    def _perform_restore(self, backup_file: Path) -> Dict[str, Any]:
        """Perform database restore using psql.
        
        Args:
            backup_file: Path to prepared backup file
            
        Returns:
            Dictionary with success status and details
        """
        try:
            # Build psql command
            cmd = [
                self.config.psql_path,
                "--host", self.db_config.host,
                "--port", str(self.db_config.port),
                "--username", self.db_config.username,
                "--dbname", self.db_config.database,
                "--no-password",
                "--file", str(backup_file)
            ]
            
            # Set environment for password
            env = os.environ.copy()
            env['PGPASSWORD'] = self.db_config.password
            
            # Execute psql
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=3600  # 1 hour timeout
            )
            
            if result.returncode != 0:
                return {
                    'success': False,
                    'error': result.stderr or "psql failed with no error message"
                }
            
            return {
                'success': True,
                'output': result.stdout
            }
            
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'psql timeout'}
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def verify_backup(self, backup_id: str) -> VerificationResult:
        """Verify backup integrity.
        
        Args:
            backup_id: Backup identifier
            
        Returns:
            VerificationResult with verification details
        """
        logger.info(f"Verifying backup {backup_id}")
        
        try:
            # Get backup record
            backup_record = self.db_manager.get_backup_record(backup_id)
            if not backup_record:
                return VerificationResult(
                    backup_id=backup_id,
                    is_valid=False,
                    checksum_match=False,
                    file_exists=False,
                    file_readable=False,
                    size_match=False,
                    verification_time=datetime.utcnow(),
                    error_details="Backup record not found"
                )
            
            backup_path = Path(backup_record['file_path'])
            
            # Check if file exists
            file_exists = backup_path.exists()
            if not file_exists:
                return VerificationResult(
                    backup_id=backup_id,
                    is_valid=False,
                    checksum_match=False,
                    file_exists=False,
                    file_readable=False,
                    size_match=False,
                    verification_time=datetime.utcnow(),
                    error_details="Backup file not found"
                )
            
            # Check if file is readable
            file_readable = os.access(backup_path, os.R_OK)
            
            # Check file size
            actual_size = backup_path.stat().st_size
            expected_size = backup_record['compressed_size'] or backup_record['file_size']
            size_match = actual_size == expected_size
            
            # Verify checksum
            checksum_match = False
            if file_readable:
                try:
                    actual_checksum = self._calculate_checksum(backup_path)
                    expected_checksum = backup_record['checksum']
                    checksum_match = actual_checksum == expected_checksum
                except Exception as e:
                    logger.error(f"Failed to calculate checksum: {e}")
            
            is_valid = file_exists and file_readable and size_match and checksum_match
            
            return VerificationResult(
                backup_id=backup_id,
                is_valid=is_valid,
                checksum_match=checksum_match,
                file_exists=file_exists,
                file_readable=file_readable,
                size_match=size_match,
                verification_time=datetime.utcnow(),
                error_details=None if is_valid else "One or more verification checks failed"
            )
            
        except Exception as e:
            logger.error(f"Backup verification failed: {e}")
            return VerificationResult(
                backup_id=backup_id,
                is_valid=False,
                checksum_match=False,
                file_exists=False,
                file_readable=False,
                size_match=False,
                verification_time=datetime.utcnow(),
                error_details=str(e)
            )
    
    def list_backups(self, filters: Optional[BackupFilters] = None) -> List[BackupInfo]:
        """List available backups.
        
        Args:
            filters: Optional filters for backup listing
            
        Returns:
            List of BackupInfo objects
        """
        try:
            records = self.db_manager.list_backup_records()
            backups = []
            
            for record in records:
                # Apply filters if provided
                if filters:
                    if filters.backup_type and record['backup_type'] != filters.backup_type.value:
                        continue
                    if filters.status and record['status'] != filters.status.value:
                        continue
                    if filters.created_after and record['created_at'] < filters.created_after:
                        continue
                    if filters.created_before and record['created_at'] > filters.created_before:
                        continue
                    if filters.database_name and record['database_name'] != filters.database_name:
                        continue
                
                backup_info = BackupInfo(
                    backup_id=record['backup_id'],
                    backup_type=BackupType(record['backup_type']),
                    status=BackupStatus(record['status']),
                    created_at=record['created_at'],
                    completed_at=record['completed_at'],
                    file_path=record['file_path'],
                    file_size=record['file_size'],
                    compressed_size=record['compressed_size'],
                    is_encrypted=record['is_encrypted'],
                    checksum=record['checksum'],
                    database_name=record['database_name'],
                    metadata=json.loads(record['metadata_json']) if record['metadata_json'] else {}
                )
                backups.append(backup_info)
            
            return backups
            
        except Exception as e:
            logger.error(f"Failed to list backups: {e}")
            return []
    
    def cleanup_old_backups(self) -> CleanupResult:
        """Clean up old backups based on retention policy.
        
        Returns:
            CleanupResult with cleanup details
        """
        cleanup_id = str(uuid.uuid4())
        cleanup_time = datetime.utcnow()
        cutoff_date = cleanup_time - timedelta(days=self.config.retention_days)
        
        logger.info(f"Starting backup cleanup {cleanup_id}, removing backups older than {cutoff_date}")
        
        try:
            # Get old backups
            filters = BackupFilters(created_before=cutoff_date)
            old_backups = self.list_backups(filters)
            
            deleted_backups = []
            freed_space = 0
            
            for backup in old_backups:
                try:
                    # Delete backup file
                    backup_path = Path(backup.file_path)
                    if backup_path.exists():
                        file_size = backup_path.stat().st_size
                        backup_path.unlink()
                        freed_space += file_size
                        logger.info(f"Deleted backup file: {backup_path}")
                    
                    # Delete backup record
                    if self.db_manager.delete_backup_record(backup.backup_id):
                        deleted_backups.append(backup.backup_id)
                        logger.info(f"Deleted backup record: {backup.backup_id}")
                    
                except Exception as e:
                    logger.error(f"Failed to delete backup {backup.backup_id}: {e}")
            
            logger.info(f"Cleanup {cleanup_id} completed: deleted {len(deleted_backups)} backups, freed {freed_space} bytes")
            
            return CleanupResult(
                cleanup_id=cleanup_id,
                deleted_backups=deleted_backups,
                freed_space_bytes=freed_space,
                cleanup_time=cleanup_time
            )
            
        except Exception as e:
            logger.error(f"Backup cleanup failed: {e}")
            return CleanupResult(
                cleanup_id=cleanup_id,
                deleted_backups=[],
                freed_space_bytes=0,
                cleanup_time=cleanup_time,
                error_details=str(e)
            )
    
    def get_backup_metrics(self) -> BackupMetrics:
        """Get backup system metrics.
        
        Returns:
            BackupMetrics with system statistics
        """
        try:
            all_backups = self.list_backups()
            
            total_backups = len(all_backups)
            successful_backups = len([b for b in all_backups if b.status == BackupStatus.COMPLETED])
            failed_backups = len([b for b in all_backups if b.status == BackupStatus.FAILED])
            
            total_size = sum(b.compressed_size or b.file_size for b in all_backups)
            
            # Calculate average backup time for completed backups
            completed_backups = [b for b in all_backups if b.status == BackupStatus.COMPLETED and b.completed_at]
            avg_backup_time = 0.0
            if completed_backups:
                total_time = sum(
                    (b.completed_at - b.created_at).total_seconds() 
                    for b in completed_backups
                )
                avg_backup_time = total_time / len(completed_backups)
            
            # Get last backup time
            last_backup_time = None
            if all_backups:
                last_backup_time = max(b.created_at for b in all_backups)
            
            # Calculate retention compliance
            cutoff_date = datetime.utcnow() - timedelta(days=self.config.retention_days)
            within_retention = len([b for b in all_backups if b.created_at >= cutoff_date])
            retention_compliance = (within_retention / total_backups * 100) if total_backups > 0 else 100.0
            
            return BackupMetrics(
                total_backups=total_backups,
                successful_backups=successful_backups,
                failed_backups=failed_backups,
                total_size_bytes=total_size,
                average_backup_time_seconds=avg_backup_time,
                last_backup_time=last_backup_time,
                next_scheduled_backup=None,  # Would be calculated from schedule
                retention_compliance=retention_compliance
            )
            
        except Exception as e:
            logger.error(f"Failed to get backup metrics: {e}")
            return BackupMetrics(
                total_backups=0,
                successful_backups=0,
                failed_backups=0,
                total_size_bytes=0,
                average_backup_time_seconds=0.0,
                retention_compliance=0.0
            )
    
    def close(self):
        """Close backup service and cleanup resources."""
        if self.db_manager:
            self.db_manager.close()
        logger.info("Backup service closed")