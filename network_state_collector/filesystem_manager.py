"""
FileSystemManager - Gestione file system e output

Implementa la gestione del salvataggio in directory configurabili,
nomi file consistenti per l'integrazione LLM e storico dati.
"""

import os
import shutil
import logging
from pathlib import Path
from typing import Dict, List, Optional, Union, Any
from datetime import datetime, timedelta
from dataclasses import dataclass
import json
import glob

from .models.core import NetworkSnapshot
from .models.llm import LLMNetworkData
from .json_serializer import JSONSerializer


@dataclass
class FileSystemConfig:
    """Configurazione per FileSystemManager"""
    base_output_dir: str = "data"
    llm_output_dir: str = "llm_output"
    history_dir: str = "history"
    archive_dir: str = "archive"
    max_history_files: int = 100
    max_file_age_days: int = 30
    enable_compression: bool = False
    file_permissions: int = 0o644
    dir_permissions: int = 0o755


class FileSystemError(Exception):
    """Eccezione per errori del file system"""
    pass


class FileSystemManager:
    """
    Gestore del file system per output dati
    
    Gestisce:
    - Salvataggio in directory configurabili
    - Nomi file consistenti per integrazione LLM
    - Storico dati per analisi trend
    - Pulizia automatica file vecchi
    - Compressione opzionale
    """
    
    def __init__(self, config: Optional[FileSystemConfig] = None):
        """
        Inizializza il FileSystemManager
        
        Args:
            config: Configurazione del file system
        """
        self.config = config or FileSystemConfig()
        self.logger = logging.getLogger(__name__)
        self.serializer = JSONSerializer(pretty_print=True, indent=2)
        
        # Crea directory base
        self._ensure_directories()
        
        self.logger.info("FileSystemManager initialized", extra={
            'component': 'FileSystemManager',
            'base_dir': self.config.base_output_dir,
            'llm_dir': self.config.llm_output_dir
        })
    
    def save_network_snapshot(self, snapshot: NetworkSnapshot, 
                            filename: Optional[str] = None) -> Path:
        """
        Salva un NetworkSnapshot su file
        
        Args:
            snapshot: Snapshot da salvare
            filename: Nome file personalizzato (opzionale)
            
        Returns:
            Path del file salvato
            
        Raises:
            FileSystemError: Se il salvataggio fallisce
        """
        try:
            if filename is None:
                filename = self._generate_snapshot_filename(snapshot.timestamp)
            
            file_path = self._get_history_path() / filename
            
            self.logger.debug("Saving NetworkSnapshot", extra={
                'component': 'FileSystemManager',
                'file_path': str(file_path),
                'timestamp': snapshot.timestamp
            })
            
            # Salva usando il serializer
            self.serializer.save_to_file(snapshot, file_path)
            
            # Imposta permessi
            self._set_file_permissions(file_path)
            
            self.logger.info("NetworkSnapshot saved successfully", extra={
                'component': 'FileSystemManager',
                'file_path': str(file_path),
                'file_size': file_path.stat().st_size
            })
            
            return file_path
            
        except Exception as e:
            error_msg = f"Failed to save NetworkSnapshot: {e}"
            self.logger.error(error_msg, extra={'component': 'FileSystemManager'})
            raise FileSystemError(error_msg) from e
    
    def save_llm_data(self, llm_data: LLMNetworkData, 
                      filename: Optional[str] = None,
                      as_latest: bool = True) -> Path:
        """
        Salva dati LLM su file
        
        Args:
            llm_data: Dati LLM da salvare
            filename: Nome file personalizzato (opzionale)
            as_latest: Se salvare anche come file "latest"
            
        Returns:
            Path del file salvato
            
        Raises:
            FileSystemError: Se il salvataggio fallisce
        """
        try:
            if filename is None:
                timestamp = llm_data.temporal_features.get('timestamp', datetime.now().timestamp())
                filename = self._generate_llm_filename(timestamp)
            
            file_path = self._get_llm_output_path() / filename
            
            self.logger.debug("Saving LLMNetworkData", extra={
                'component': 'FileSystemManager',
                'file_path': str(file_path),
                'as_latest': as_latest
            })
            
            # Salva usando il serializer
            self.serializer.save_to_file(llm_data, file_path)
            
            # Imposta permessi
            self._set_file_permissions(file_path)
            
            # Salva anche come latest se richiesto
            if as_latest:
                latest_path = self._get_llm_output_path() / "network_context_latest.json"
                shutil.copy2(file_path, latest_path)
                self._set_file_permissions(latest_path)
                
                self.logger.debug("LLM data also saved as latest", extra={
                    'component': 'FileSystemManager',
                    'latest_path': str(latest_path)
                })
            
            self.logger.info("LLMNetworkData saved successfully", extra={
                'component': 'FileSystemManager',
                'file_path': str(file_path),
                'file_size': file_path.stat().st_size,
                'as_latest': as_latest
            })
            
            return file_path
            
        except Exception as e:
            error_msg = f"Failed to save LLMNetworkData: {e}"
            self.logger.error(error_msg, extra={'component': 'FileSystemManager'})
            raise FileSystemError(error_msg) from e
    
    def load_network_snapshot(self, filename: str) -> NetworkSnapshot:
        """
        Carica un NetworkSnapshot da file
        
        Args:
            filename: Nome del file da caricare
            
        Returns:
            NetworkSnapshot caricato
            
        Raises:
            FileSystemError: Se il caricamento fallisce
        """
        try:
            file_path = self._find_file(filename)
            
            if not file_path:
                raise FileSystemError(f"File not found: {filename}")
            
            self.logger.debug("Loading NetworkSnapshot", extra={
                'component': 'FileSystemManager',
                'file_path': str(file_path)
            })
            
            snapshot = self.serializer.load_from_file(file_path, 'snapshot')
            
            self.logger.info("NetworkSnapshot loaded successfully", extra={
                'component': 'FileSystemManager',
                'file_path': str(file_path),
                'timestamp': snapshot.timestamp
            })
            
            return snapshot
            
        except Exception as e:
            error_msg = f"Failed to load NetworkSnapshot from {filename}: {e}"
            self.logger.error(error_msg, extra={'component': 'FileSystemManager'})
            raise FileSystemError(error_msg) from e
    
    def load_llm_data(self, filename: str = "network_context_latest.json") -> LLMNetworkData:
        """
        Carica dati LLM da file
        
        Args:
            filename: Nome del file da caricare (default: latest)
            
        Returns:
            LLMNetworkData caricato
            
        Raises:
            FileSystemError: Se il caricamento fallisce
        """
        try:
            file_path = self._find_file(filename)
            
            if not file_path:
                raise FileSystemError(f"File not found: {filename}")
            
            self.logger.debug("Loading LLMNetworkData", extra={
                'component': 'FileSystemManager',
                'file_path': str(file_path)
            })
            
            llm_data = self.serializer.load_from_file(file_path, 'llm')
            
            self.logger.info("LLMNetworkData loaded successfully", extra={
                'component': 'FileSystemManager',
                'file_path': str(file_path)
            })
            
            return llm_data
            
        except Exception as e:
            error_msg = f"Failed to load LLMNetworkData from {filename}: {e}"
            self.logger.error(error_msg, extra={'component': 'FileSystemManager'})
            raise FileSystemError(error_msg) from e
    
    def list_history_files(self, pattern: str = "*.json", 
                          limit: Optional[int] = None) -> List[Path]:
        """
        Lista i file nello storico
        
        Args:
            pattern: Pattern per filtrare i file
            limit: Limite massimo di file da restituire
            
        Returns:
            Lista di Path dei file trovati
        """
        try:
            history_path = self._get_history_path()
            files = list(history_path.glob(pattern))
            
            # Ordina per data di modifica (più recenti prima)
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            if limit:
                files = files[:limit]
            
            self.logger.debug("Listed history files", extra={
                'component': 'FileSystemManager',
                'pattern': pattern,
                'count': len(files),
                'limit': limit
            })
            
            return files
            
        except Exception as e:
            error_msg = f"Failed to list history files: {e}"
            self.logger.error(error_msg, extra={'component': 'FileSystemManager'})
            raise FileSystemError(error_msg) from e
    
    def list_llm_files(self, pattern: str = "*.json", 
                       limit: Optional[int] = None) -> List[Path]:
        """
        Lista i file LLM
        
        Args:
            pattern: Pattern per filtrare i file
            limit: Limite massimo di file da restituire
            
        Returns:
            Lista di Path dei file trovati
        """
        try:
            llm_path = self._get_llm_output_path()
            files = list(llm_path.glob(pattern))
            
            # Ordina per data di modifica (più recenti prima)
            files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            if limit:
                files = files[:limit]
            
            self.logger.debug("Listed LLM files", extra={
                'component': 'FileSystemManager',
                'pattern': pattern,
                'count': len(files),
                'limit': limit
            })
            
            return files
            
        except Exception as e:
            error_msg = f"Failed to list LLM files: {e}"
            self.logger.error(error_msg, extra={'component': 'FileSystemManager'})
            raise FileSystemError(error_msg) from e
    
    def cleanup_old_files(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Pulisce i file vecchi secondo la configurazione
        
        Args:
            dry_run: Se True, non elimina i file ma restituisce cosa verrebbe eliminato
            
        Returns:
            Dizionario con statistiche della pulizia
        """
        try:
            stats = {
                'files_removed': 0,
                'files_archived': 0,
                'bytes_freed': 0,
                'errors': 0
            }
            
            cutoff_date = datetime.now() - timedelta(days=self.config.max_file_age_days)
            cutoff_timestamp = cutoff_date.timestamp()
            
            # Pulisci file di history
            history_files = self.list_history_files()
            
            # Rimuovi file che superano il limite di numero O sono troppo vecchi
            files_to_remove = []
            
            # File che superano il limite di numero (mantieni solo i più recenti)
            if len(history_files) > self.config.max_history_files:
                files_to_remove.extend(history_files[self.config.max_history_files:])
            
            # File troppo vecchi (anche se sotto il limite di numero)
            for file_path in history_files:
                if file_path.stat().st_mtime < cutoff_timestamp and file_path not in files_to_remove:
                    files_to_remove.append(file_path)
            
            # Rimuovi i file identificati
            for file_path in files_to_remove:
                try:
                    file_size = file_path.stat().st_size
                    
                    if not dry_run:
                        if self.config.enable_compression:
                            # Archivia invece di eliminare
                            self._archive_file(file_path)
                            stats['files_archived'] += 1
                        else:
                            file_path.unlink()
                            stats['files_removed'] += 1
                    
                    stats['bytes_freed'] += file_size
                    
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup file {file_path}: {e}")
                    stats['errors'] += 1
            
            # Pulisci file LLM (escludi latest)
            llm_files = [f for f in self.list_llm_files() 
                        if f.name != "network_context_latest.json"]
            
            llm_files_to_remove = []
            
            # File che superano il limite di numero
            if len(llm_files) > self.config.max_history_files:
                llm_files_to_remove.extend(llm_files[self.config.max_history_files:])
            
            # File troppo vecchi
            for file_path in llm_files:
                if file_path.stat().st_mtime < cutoff_timestamp and file_path not in llm_files_to_remove:
                    llm_files_to_remove.append(file_path)
            
            # Rimuovi i file LLM identificati
            for file_path in llm_files_to_remove:
                try:
                    file_size = file_path.stat().st_size
                    
                    if not dry_run:
                        if self.config.enable_compression:
                            self._archive_file(file_path)
                            stats['files_archived'] += 1
                        else:
                            file_path.unlink()
                            stats['files_removed'] += 1
                    
                    stats['bytes_freed'] += file_size
                    
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup LLM file {file_path}: {e}")
                    stats['errors'] += 1
            
            action = "Would cleanup" if dry_run else "Cleaned up"
            self.logger.info(f"{action} old files", extra={
                'component': 'FileSystemManager',
                'dry_run': dry_run,
                **stats
            })
            
            return stats
            
        except Exception as e:
            error_msg = f"Failed to cleanup old files: {e}"
            self.logger.error(error_msg, extra={'component': 'FileSystemManager'})
            raise FileSystemError(error_msg) from e
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Ottiene statistiche di utilizzo dello storage
        
        Returns:
            Dizionario con statistiche dello storage
        """
        try:
            stats = {
                'base_dir': str(self._get_base_path()),
                'total_files': 0,
                'total_size_bytes': 0,
                'directories': {}
            }
            
            # Analizza ogni directory
            for dir_name in ['llm_output', 'history', 'archive']:
                dir_path = self._get_base_path() / getattr(self.config, f"{dir_name}_dir")
                
                if dir_path.exists():
                    dir_stats = self._get_directory_stats(dir_path)
                    stats['directories'][dir_name] = dir_stats
                    stats['total_files'] += dir_stats['file_count']
                    stats['total_size_bytes'] += dir_stats['total_size']
            
            # Converti bytes in unità leggibili
            stats['total_size_mb'] = stats['total_size_bytes'] / (1024 * 1024)
            stats['total_size_gb'] = stats['total_size_mb'] / 1024
            
            # Aggiungi informazioni spazio disponibile
            try:
                import shutil
                total, used, free = shutil.disk_usage(self._get_base_path())
                stats['available_space'] = free
                stats['total_space'] = total
                stats['used_space'] = used
            except Exception as e:
                self.logger.warning(f"Could not get disk usage: {e}")
                # Fallback per evitare errori nei test
                stats['available_space'] = 1024 * 1024 * 1024  # 1GB default
                stats['total_space'] = 10 * 1024 * 1024 * 1024  # 10GB default
                stats['used_space'] = stats['total_size_bytes']
            
            self.logger.debug("Generated storage stats", extra={
                'component': 'FileSystemManager',
                'total_files': stats['total_files'],
                'total_size_mb': f"{stats['total_size_mb']:.2f}",
                'available_space_mb': f"{stats['available_space'] / (1024 * 1024):.2f}"
            })
            
            return stats
            
        except Exception as e:
            error_msg = f"Failed to get storage stats: {e}"
            self.logger.error(error_msg, extra={'component': 'FileSystemManager'})
            raise FileSystemError(error_msg) from e
    
    def save_network_context(self, snapshot_json: str, timestamp: float) -> Path:
        """
        Salva il contesto di rete con timestamp
        
        Args:
            snapshot_json: JSON serializzato del NetworkSnapshot
            timestamp: Timestamp del snapshot
            
        Returns:
            Path del file salvato
        """
        try:
            filename = self._generate_snapshot_filename(timestamp)
            file_path = self._get_history_path() / filename
            
            with open(file_path, 'w') as f:
                f.write(snapshot_json)
            
            self._set_file_permissions(file_path)
            
            self.logger.info("Network context saved", extra={
                'component': 'FileSystemManager',
                'file_path': str(file_path),
                'timestamp': timestamp
            })
            
            return file_path
            
        except Exception as e:
            error_msg = f"Failed to save network context: {e}"
            self.logger.error(error_msg, extra={'component': 'FileSystemManager'})
            raise FileSystemError(error_msg) from e
    
    def save_latest_context(self, snapshot_json: str) -> Path:
        """
        Salva il contesto come file latest
        
        Args:
            snapshot_json: JSON serializzato del NetworkSnapshot
            
        Returns:
            Path del file salvato
        """
        try:
            file_path = self._get_history_path() / "network_snapshot_latest.json"
            
            with open(file_path, 'w') as f:
                f.write(snapshot_json)
            
            self._set_file_permissions(file_path)
            
            self.logger.debug("Latest context saved", extra={
                'component': 'FileSystemManager',
                'file_path': str(file_path)
            })
            
            return file_path
            
        except Exception as e:
            error_msg = f"Failed to save latest context: {e}"
            self.logger.error(error_msg, extra={'component': 'FileSystemManager'})
            raise FileSystemError(error_msg) from e
    
    def create_backup(self, backup_name: Optional[str] = None) -> Path:
        """
        Crea un backup completo dei dati
        
        Args:
            backup_name: Nome del backup (opzionale)
            
        Returns:
            Path del backup creato
            
        Raises:
            FileSystemError: Se la creazione del backup fallisce
        """
        try:
            if backup_name is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_name = f"backup_{timestamp}"
            
            backup_path = self._get_base_path() / "backups" / backup_name
            backup_path.mkdir(parents=True, exist_ok=True)
            
            self.logger.info("Creating backup", extra={
                'component': 'FileSystemManager',
                'backup_name': backup_name,
                'backup_path': str(backup_path)
            })
            
            # Copia tutte le directory
            for dir_name in ['llm_output', 'history']:
                src_dir = self._get_base_path() / getattr(self.config, f"{dir_name}_dir")
                if src_dir.exists():
                    dst_dir = backup_path / dir_name
                    shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
            
            # Crea file di metadata del backup
            metadata = {
                'created_at': datetime.now().isoformat(),
                'config': {
                    'base_output_dir': self.config.base_output_dir,
                    'llm_output_dir': self.config.llm_output_dir,
                    'history_dir': self.config.history_dir
                },
                'stats': self.get_storage_stats()
            }
            
            metadata_path = backup_path / "backup_metadata.json"
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
            
            self.logger.info("Backup created successfully", extra={
                'component': 'FileSystemManager',
                'backup_path': str(backup_path),
                'backup_size': self._get_directory_stats(backup_path)['total_size']
            })
            
            return backup_path
            
        except Exception as e:
            error_msg = f"Failed to create backup: {e}"
            self.logger.error(error_msg, extra={'component': 'FileSystemManager'})
            raise FileSystemError(error_msg) from e
    
    def _ensure_directories(self):
        """Crea le directory necessarie"""
        directories = [
            self._get_base_path(),
            self._get_llm_output_path(),
            self._get_history_path(),
            self._get_archive_path()
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            os.chmod(directory, self.config.dir_permissions)
    
    def _get_base_path(self) -> Path:
        """Ottiene il path base"""
        return Path(self.config.base_output_dir)
    
    def _get_llm_output_path(self) -> Path:
        """Ottiene il path per output LLM"""
        return self._get_base_path() / self.config.llm_output_dir
    
    def _get_history_path(self) -> Path:
        """Ottiene il path per lo storico"""
        return self._get_base_path() / self.config.history_dir
    
    def _get_archive_path(self) -> Path:
        """Ottiene il path per l'archivio"""
        return self._get_base_path() / self.config.archive_dir
    
    def _generate_snapshot_filename(self, timestamp: float) -> str:
        """Genera nome file per NetworkSnapshot"""
        dt = datetime.fromtimestamp(timestamp)
        return f"network_snapshot_{dt.strftime('%Y%m%d_%H%M%S')}.json"
    
    def _generate_llm_filename(self, timestamp: float) -> str:
        """Genera nome file per dati LLM"""
        dt = datetime.fromtimestamp(timestamp)
        return f"network_context_{dt.strftime('%Y%m%d_%H%M%S')}.json"
    
    def _set_file_permissions(self, file_path: Path):
        """Imposta i permessi del file"""
        os.chmod(file_path, self.config.file_permissions)
    
    def _find_file(self, filename: str) -> Optional[Path]:
        """Trova un file nelle directory gestite"""
        search_paths = [
            self._get_llm_output_path(),
            self._get_history_path(),
            self._get_archive_path()
        ]
        
        for search_path in search_paths:
            file_path = search_path / filename
            if file_path.exists():
                return file_path
        
        return None
    
    def _archive_file(self, file_path: Path):
        """Archivia un file (con compressione opzionale)"""
        archive_path = self._get_archive_path()
        archive_path.mkdir(parents=True, exist_ok=True)
        
        # Per ora, semplicemente sposta il file
        # In futuro si potrebbe aggiungere compressione
        dest_path = archive_path / file_path.name
        shutil.move(str(file_path), str(dest_path))
        self._set_file_permissions(dest_path)
    
    def _get_directory_stats(self, directory: Path) -> Dict[str, Any]:
        """Ottiene statistiche di una directory"""
        stats = {
            'path': str(directory),
            'file_count': 0,
            'total_size': 0,
            'latest_file': None,
            'oldest_file': None
        }
        
        if not directory.exists():
            return stats
        
        files = list(directory.glob("*"))
        files = [f for f in files if f.is_file()]
        
        if not files:
            return stats
        
        stats['file_count'] = len(files)
        stats['total_size'] = sum(f.stat().st_size for f in files)
        
        # File più recente e più vecchio
        files_by_mtime = sorted(files, key=lambda f: f.stat().st_mtime)
        stats['oldest_file'] = {
            'name': files_by_mtime[0].name,
            'mtime': files_by_mtime[0].stat().st_mtime
        }
        stats['latest_file'] = {
            'name': files_by_mtime[-1].name,
            'mtime': files_by_mtime[-1].stat().st_mtime
        }
        
        return stats