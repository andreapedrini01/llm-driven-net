"""
Test per FileSystemManager

Test per gestione file system, directory configurabili e storico dati.
"""

import os
import json
import shutil
import tempfile
import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from network_state_collector.filesystem_manager import (
    FileSystemManager, 
    FileSystemConfig, 
    FileSystemError
)
from src.models.core import (
    NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, PortMetrics
)
from src.models.llm import LLMNetworkData, AnomalyIndicator


class TestFileSystemConfig:
    """Test per FileSystemConfig"""
    
    def test_default_values(self):
        """Test valori di default della configurazione"""
        config = FileSystemConfig()
        
        assert config.base_output_dir == "data"
        assert config.llm_output_dir == "llm_output"
        assert config.history_dir == "history"
        assert config.archive_dir == "archive"
        assert config.max_history_files == 100
        assert config.max_file_age_days == 30
        assert config.enable_compression is False
        assert config.file_permissions == 0o644
        assert config.dir_permissions == 0o755
    
    def test_custom_values(self):
        """Test configurazione personalizzata"""
        config = FileSystemConfig(
            base_output_dir="/custom/path",
            llm_output_dir="custom_llm",
            history_dir="custom_history",
            max_history_files=50,
            max_file_age_days=15,
            enable_compression=True,
            file_permissions=0o600,
            dir_permissions=0o700
        )
        
        assert config.base_output_dir == "/custom/path"
        assert config.llm_output_dir == "custom_llm"
        assert config.history_dir == "custom_history"
        assert config.max_history_files == 50
        assert config.max_file_age_days == 15
        assert config.enable_compression is True
        assert config.file_permissions == 0o600
        assert config.dir_permissions == 0o700


class TestFileSystemManager:
    """Test per FileSystemManager"""
    
    def setup_method(self):
        """Setup per ogni test"""
        self.temp_dir = tempfile.mkdtemp()
        self.config = FileSystemConfig(
            base_output_dir=self.temp_dir,
            max_history_files=5,
            max_file_age_days=7
        )
        self.fs_manager = FileSystemManager(self.config)
        
        # Crea dati di test
        self.test_snapshot = self._create_test_snapshot()
        self.test_llm_data = self._create_test_llm_data()
    
    def teardown_method(self):
        """Cleanup dopo ogni test"""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def _create_test_snapshot(self) -> NetworkSnapshot:
        """Crea NetworkSnapshot di test"""
        switches = [
            SwitchInfo(dpid="0000000000000001", active=True, ports=[1, 2]),
            SwitchInfo(dpid="0000000000000002", active=True, ports=[1, 2])
        ]
        
        links = [
            LinkInfo(
                src_dpid="0000000000000001",
                dst_dpid="0000000000000002",
                src_port=2,
                dst_port=1,
                active=True
            )
        ]
        
        topology = TopologyData(
            switches=switches,
            links=links,
            graph_representation={"nodes": 2, "edges": 1}
        )
        
        port_stats = {
            "0000000000000001": [
                PortMetrics(
                    port_no=1,
                    rx_packets=1000,
                    tx_packets=800,
                    rx_bytes=64000,
                    tx_bytes=51200,
                    rx_errors=0,
                    tx_errors=0,
                    rx_dropped=0,
                    tx_dropped=0
                )
            ]
        }
        
        metrics = MetricsData(
            port_statistics=port_stats,
            aggregated_metrics={},
            quality_indicators=None
        )
        
        return NetworkSnapshot(
            timestamp=1640995200.0,
            topology=topology,
            metrics=metrics,
            derived_metrics=None,
            metadata={"version": "1.0"}
        )
    
    def _create_test_llm_data(self) -> LLMNetworkData:
        """Crea LLMNetworkData di test"""
        return LLMNetworkData(
            network_context={
                "topology": {
                    "nodes": ["0000000000000001", "0000000000000002"],
                    "edges": [{"src": "0000000000000001", "dst": "0000000000000002"}]
                },
                "performance": {
                    "utilization_vectors": [[0.1, 0.01], [0.2, 0.02]],
                    "error_rates": [0.01, 0.02]
                }
            },
            performance_vectors=[[0.1, 0.01, 100.0], [0.2, 0.02, 200.0]],
            topology_embedding={
                "adjacency_matrix": [[0, 1], [1, 0]],
                "node_degrees": [1, 1]
            },
            temporal_features={
                "timestamp": 1640995200.0,
                "hour_of_day": 12,
                "is_weekend": False
            },
            anomaly_indicators=[
                AnomalyIndicator(
                    type="test_anomaly",
                    severity=0.5,
                    description="Test anomaly",
                    affected_components=["test"],
                    timestamp=1640995200.0,
                    confidence=0.9
                )
            ]
        )
    
    def test_initialization_default_config(self):
        """Test inizializzazione con configurazione default"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileSystemConfig(base_output_dir=temp_dir)
            fs_manager = FileSystemManager(config)
            
            assert fs_manager.config == config
            assert isinstance(fs_manager.serializer, type(fs_manager.serializer))
            
            # Verifica che le directory siano state create
            base_path = Path(temp_dir)
            assert (base_path / "llm_output").exists()
            assert (base_path / "history").exists()
            assert (base_path / "archive").exists()
    
    def test_initialization_no_config(self):
        """Test inizializzazione senza configurazione"""
        fs_manager = FileSystemManager()
        
        assert isinstance(fs_manager.config, FileSystemConfig)
        assert fs_manager.config.base_output_dir == "data"
    
    def test_save_network_snapshot_default_filename(self):
        """Test salvataggio NetworkSnapshot con nome file automatico"""
        file_path = self.fs_manager.save_network_snapshot(self.test_snapshot)
        
        # Verifica che il file sia stato creato
        assert file_path.exists()
        assert file_path.suffix == ".json"
        assert "network_snapshot_" in file_path.name
        
        # Verifica che sia nella directory history
        assert file_path.parent.name == "history"
        
        # Verifica contenuto
        with open(file_path, 'r') as f:
            data = json.load(f)
        assert "timestamp" in data
        assert "topology" in data
        assert "metrics" in data
    
    def test_save_network_snapshot_custom_filename(self):
        """Test salvataggio NetworkSnapshot con nome file personalizzato"""
        custom_filename = "custom_snapshot.json"
        file_path = self.fs_manager.save_network_snapshot(
            self.test_snapshot, 
            filename=custom_filename
        )
        
        assert file_path.name == custom_filename
        assert file_path.exists()
    
    def test_save_llm_data_default_filename(self):
        """Test salvataggio LLMNetworkData con nome file automatico"""
        file_path = self.fs_manager.save_llm_data(self.test_llm_data)
        
        # Verifica che il file sia stato creato
        assert file_path.exists()
        assert file_path.suffix == ".json"
        assert "network_context_" in file_path.name
        
        # Verifica che sia nella directory llm_output
        assert file_path.parent.name == "llm_output"
        
        # Verifica che sia stato creato anche il file latest
        latest_path = file_path.parent / "network_context_latest.json"
        assert latest_path.exists()
    
    def test_save_llm_data_custom_filename(self):
        """Test salvataggio LLMNetworkData con nome file personalizzato"""
        custom_filename = "custom_llm.json"
        file_path = self.fs_manager.save_llm_data(
            self.test_llm_data, 
            filename=custom_filename
        )
        
        assert file_path.name == custom_filename
        assert file_path.exists()
    
    def test_save_llm_data_no_latest(self):
        """Test salvataggio LLMNetworkData senza file latest"""
        file_path = self.fs_manager.save_llm_data(
            self.test_llm_data, 
            as_latest=False
        )
        
        assert file_path.exists()
        
        # Verifica che il file latest non sia stato creato
        latest_path = file_path.parent / "network_context_latest.json"
        assert not latest_path.exists()
    
    def test_load_network_snapshot(self):
        """Test caricamento NetworkSnapshot"""
        # Salva prima
        saved_path = self.fs_manager.save_network_snapshot(self.test_snapshot)
        
        # Carica
        loaded_snapshot = self.fs_manager.load_network_snapshot(saved_path.name)
        
        assert isinstance(loaded_snapshot, NetworkSnapshot)
        assert loaded_snapshot.timestamp == self.test_snapshot.timestamp
    
    def test_load_network_snapshot_not_found(self):
        """Test caricamento NetworkSnapshot inesistente"""
        with pytest.raises(FileSystemError):
            self.fs_manager.load_network_snapshot("nonexistent.json")
    
    def test_load_llm_data_default(self):
        """Test caricamento LLMNetworkData (latest)"""
        # Salva prima
        self.fs_manager.save_llm_data(self.test_llm_data)
        
        # Carica latest
        loaded_llm = self.fs_manager.load_llm_data()
        
        assert isinstance(loaded_llm, LLMNetworkData)
        assert loaded_llm.network_context == self.test_llm_data.network_context
    
    def test_load_llm_data_specific_file(self):
        """Test caricamento LLMNetworkData specifico"""
        # Salva prima
        saved_path = self.fs_manager.save_llm_data(self.test_llm_data)
        
        # Carica file specifico
        loaded_llm = self.fs_manager.load_llm_data(saved_path.name)
        
        assert isinstance(loaded_llm, LLMNetworkData)
        assert loaded_llm.network_context == self.test_llm_data.network_context
    
    def test_load_llm_data_not_found(self):
        """Test caricamento LLMNetworkData inesistente"""
        with pytest.raises(FileSystemError):
            self.fs_manager.load_llm_data("nonexistent.json")
    
    def test_list_history_files(self):
        """Test listing file di history"""
        # Salva alcuni file
        for i in range(3):
            snapshot = self.test_snapshot
            snapshot.timestamp = 1640995200.0 + i * 3600  # Ogni ora
            self.fs_manager.save_network_snapshot(snapshot)
        
        # Lista file
        files = self.fs_manager.list_history_files()
        
        assert len(files) == 3
        assert all(f.suffix == ".json" for f in files)
        assert all("network_snapshot_" in f.name for f in files)
        
        # Verifica ordinamento (più recenti prima)
        mtimes = [f.stat().st_mtime for f in files]
        assert mtimes == sorted(mtimes, reverse=True)
    
    def test_list_history_files_with_limit(self):
        """Test listing file di history con limite"""
        # Salva alcuni file
        for i in range(5):
            snapshot = self.test_snapshot
            snapshot.timestamp = 1640995200.0 + i * 3600
            self.fs_manager.save_network_snapshot(snapshot)
        
        # Lista con limite
        files = self.fs_manager.list_history_files(limit=3)
        
        assert len(files) == 3
    
    def test_list_llm_files(self):
        """Test listing file LLM"""
        # Salva alcuni file
        for i in range(3):
            llm_data = self.test_llm_data
            llm_data.temporal_features['timestamp'] = 1640995200.0 + i * 3600
            self.fs_manager.save_llm_data(llm_data, as_latest=(i == 2))
        
        # Lista file
        files = self.fs_manager.list_llm_files()
        
        # Dovrebbe includere i 3 file + latest
        assert len(files) >= 3
        assert any("network_context_latest.json" in f.name for f in files)
    
    def test_cleanup_old_files_dry_run(self):
        """Test pulizia file vecchi (dry run)"""
        # Crea file vecchi
        old_time = datetime.now() - timedelta(days=10)
        
        for i in range(3):
            file_path = self.fs_manager._get_history_path() / f"old_file_{i}.json"
            file_path.write_text('{"test": "data"}')
            # Imposta timestamp vecchio
            os.utime(file_path, (old_time.timestamp(), old_time.timestamp()))
        
        # Dry run cleanup
        stats = self.fs_manager.cleanup_old_files(dry_run=True)
        
        assert stats['files_removed'] == 0  # Dry run non rimuove
        assert stats['bytes_freed'] > 0
        
        # Verifica che i file esistano ancora
        files = self.fs_manager.list_history_files()
        assert len(files) == 3
    
    def test_cleanup_old_files_actual(self):
        """Test pulizia file vecchi (effettiva)"""
        # Crea file vecchi
        old_time = datetime.now() - timedelta(days=10)
        
        for i in range(3):
            file_path = self.fs_manager._get_history_path() / f"old_file_{i}.json"
            file_path.write_text('{"test": "data"}')
            os.utime(file_path, (old_time.timestamp(), old_time.timestamp()))
        
        # Cleanup effettivo
        stats = self.fs_manager.cleanup_old_files(dry_run=False)
        
        assert stats['files_removed'] > 0
        assert stats['bytes_freed'] > 0
    
    def test_cleanup_old_files_with_compression(self):
        """Test pulizia file vecchi con compressione"""
        # Configura compressione
        self.fs_manager.config.enable_compression = True
        
        # Crea file vecchi
        old_time = datetime.now() - timedelta(days=10)
        
        for i in range(3):
            file_path = self.fs_manager._get_history_path() / f"old_file_{i}.json"
            file_path.write_text('{"test": "data"}')
            os.utime(file_path, (old_time.timestamp(), old_time.timestamp()))
        
        # Cleanup con archiviazione
        stats = self.fs_manager.cleanup_old_files(dry_run=False)
        
        assert stats['files_archived'] > 0
        
        # Verifica che i file siano stati spostati in archive
        archive_files = list(self.fs_manager._get_archive_path().glob("*.json"))
        assert len(archive_files) > 0
    
    def test_get_storage_stats(self):
        """Test statistiche storage"""
        # Salva alcuni file
        self.fs_manager.save_network_snapshot(self.test_snapshot)
        self.fs_manager.save_llm_data(self.test_llm_data)
        
        stats = self.fs_manager.get_storage_stats()
        
        assert 'base_dir' in stats
        assert 'total_files' in stats
        assert 'total_size_bytes' in stats
        assert 'total_size_mb' in stats
        assert 'total_size_gb' in stats
        assert 'directories' in stats
        
        assert stats['total_files'] > 0
        assert stats['total_size_bytes'] > 0
        
        # Verifica directory stats
        assert 'llm_output' in stats['directories']
        assert 'history' in stats['directories']
    
    def test_create_backup(self):
        """Test creazione backup"""
        # Salva alcuni file
        self.fs_manager.save_network_snapshot(self.test_snapshot)
        self.fs_manager.save_llm_data(self.test_llm_data)
        
        # Crea backup
        backup_path = self.fs_manager.create_backup("test_backup")
        
        assert backup_path.exists()
        assert backup_path.name == "test_backup"
        
        # Verifica contenuto backup
        assert (backup_path / "llm_output").exists()
        assert (backup_path / "history").exists()
        assert (backup_path / "backup_metadata.json").exists()
        
        # Verifica metadata
        with open(backup_path / "backup_metadata.json", 'r') as f:
            metadata = json.load(f)
        
        assert 'created_at' in metadata
        assert 'config' in metadata
        assert 'stats' in metadata
    
    def test_create_backup_default_name(self):
        """Test creazione backup con nome automatico"""
        backup_path = self.fs_manager.create_backup()
        
        assert backup_path.exists()
        assert backup_path.name.startswith("backup_")
    
    def test_generate_snapshot_filename(self):
        """Test generazione nome file snapshot"""
        timestamp = 1640995200.0  # 2022-01-01 00:00:00 UTC
        filename = self.fs_manager._generate_snapshot_filename(timestamp)
        
        assert filename.startswith("network_snapshot_")
        assert filename.endswith(".json")
        assert "20220101" in filename
    
    def test_generate_llm_filename(self):
        """Test generazione nome file LLM"""
        timestamp = 1640995200.0  # 2022-01-01 00:00:00 UTC
        filename = self.fs_manager._generate_llm_filename(timestamp)
        
        assert filename.startswith("network_context_")
        assert filename.endswith(".json")
        assert "20220101" in filename
    
    def test_find_file_in_multiple_directories(self):
        """Test ricerca file in multiple directory"""
        # Salva file in history
        history_file = self.fs_manager._get_history_path() / "test_file.json"
        history_file.write_text('{"test": "history"}')
        
        # Salva file in llm_output
        llm_file = self.fs_manager._get_llm_output_path() / "test_llm.json"
        llm_file.write_text('{"test": "llm"}')
        
        # Trova file
        found_history = self.fs_manager._find_file("test_file.json")
        found_llm = self.fs_manager._find_file("test_llm.json")
        found_none = self.fs_manager._find_file("nonexistent.json")
        
        assert found_history == history_file
        assert found_llm == llm_file
        assert found_none is None
    
    def test_get_directory_stats(self):
        """Test statistiche directory"""
        # Crea alcuni file
        test_dir = Path(self.temp_dir) / "test_stats"
        test_dir.mkdir()
        
        for i in range(3):
            file_path = test_dir / f"file_{i}.json"
            file_path.write_text(f'{{"test": "data_{i}"}}')
        
        stats = self.fs_manager._get_directory_stats(test_dir)
        
        assert stats['file_count'] == 3
        assert stats['total_size'] > 0
        assert stats['latest_file'] is not None
        assert stats['oldest_file'] is not None
        assert stats['path'] == str(test_dir)
    
    def test_get_directory_stats_empty(self):
        """Test statistiche directory vuota"""
        empty_dir = Path(self.temp_dir) / "empty"
        empty_dir.mkdir()
        
        stats = self.fs_manager._get_directory_stats(empty_dir)
        
        assert stats['file_count'] == 0
        assert stats['total_size'] == 0
        assert stats['latest_file'] is None
        assert stats['oldest_file'] is None
    
    def test_get_directory_stats_nonexistent(self):
        """Test statistiche directory inesistente"""
        nonexistent_dir = Path(self.temp_dir) / "nonexistent"
        
        stats = self.fs_manager._get_directory_stats(nonexistent_dir)
        
        assert stats['file_count'] == 0
        assert stats['total_size'] == 0
    
    @patch('network_state_collector.filesystem_manager.os.chmod')
    def test_set_file_permissions(self, mock_chmod):
        """Test impostazione permessi file"""
        test_file = Path(self.temp_dir) / "test.json"
        test_file.write_text('{"test": "data"}')
        
        self.fs_manager._set_file_permissions(test_file)
        
        mock_chmod.assert_called_once_with(test_file, self.config.file_permissions)
    
    def test_archive_file(self):
        """Test archiviazione file"""
        # Crea file da archiviare
        source_file = self.fs_manager._get_history_path() / "to_archive.json"
        source_file.write_text('{"test": "archive"}')
        
        # Archivia
        self.fs_manager._archive_file(source_file)
        
        # Verifica che il file sia stato spostato
        assert not source_file.exists()
        
        archived_file = self.fs_manager._get_archive_path() / "to_archive.json"
        assert archived_file.exists()
        
        # Verifica contenuto
        assert archived_file.read_text() == '{"test": "archive"}'
    
    def test_error_handling_save_network_snapshot(self):
        """Test gestione errori durante salvataggio NetworkSnapshot"""
        # Mock serializer per causare errore
        with patch.object(self.fs_manager.serializer, 'save_to_file', 
                         side_effect=Exception("Save error")):
            with pytest.raises(FileSystemError):
                self.fs_manager.save_network_snapshot(self.test_snapshot)
    
    def test_error_handling_save_llm_data(self):
        """Test gestione errori durante salvataggio LLMNetworkData"""
        # Mock serializer per causare errore
        with patch.object(self.fs_manager.serializer, 'save_to_file', 
                         side_effect=Exception("Serialization error")):
            with pytest.raises(FileSystemError):
                self.fs_manager.save_llm_data(self.test_llm_data)
    
    def test_error_handling_load_network_snapshot(self):
        """Test gestione errori durante caricamento NetworkSnapshot"""
        # Crea file con JSON non valido
        invalid_file = self.fs_manager._get_history_path() / "invalid.json"
        invalid_file.write_text("invalid json")
        
        with pytest.raises(FileSystemError):
            self.fs_manager.load_network_snapshot("invalid.json")
    
    def test_error_handling_cleanup_old_files(self):
        """Test gestione errori durante pulizia file"""
        # Crea file vecchio
        old_time = datetime.now() - timedelta(days=10)
        file_path = self.fs_manager._get_history_path() / "old_file.json"
        file_path.write_text('{"test": "data"}')
        os.utime(file_path, (old_time.timestamp(), old_time.timestamp()))
        
        # Mock Path.unlink per causare errore durante cleanup
        with patch('pathlib.Path.unlink', side_effect=PermissionError("Permission denied")):
            # Cleanup dovrebbe gestire l'errore
            stats = self.fs_manager.cleanup_old_files(dry_run=False)
            
            assert stats['errors'] > 0


class TestFileSystemManagerIntegration:
    """Test di integrazione per FileSystemManager"""
    
    def test_full_workflow(self):
        """Test workflow completo"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileSystemConfig(base_output_dir=temp_dir)
            fs_manager = FileSystemManager(config)
            
            # Crea dati di test
            snapshot = NetworkSnapshot(
                timestamp=datetime.now().timestamp(),
                topology=TopologyData(switches=[], links=[], graph_representation={}),
                metrics=MetricsData(port_statistics={}, aggregated_metrics={}, quality_indicators=None),
                derived_metrics=None,
                metadata={"test": True}
            )
            
            llm_data = LLMNetworkData(
                network_context={"test": "context"},
                performance_vectors=[[1.0, 2.0]],
                topology_embedding={"test": "embedding"},
                temporal_features={"timestamp": datetime.now().timestamp()},
                anomaly_indicators=[]
            )
            
            # Salva dati
            snapshot_path = fs_manager.save_network_snapshot(snapshot)
            llm_path = fs_manager.save_llm_data(llm_data)
            
            # Verifica salvataggio
            assert snapshot_path.exists()
            assert llm_path.exists()
            
            # Carica dati
            loaded_snapshot = fs_manager.load_network_snapshot(snapshot_path.name)
            loaded_llm = fs_manager.load_llm_data(llm_path.name)
            
            # Verifica caricamento
            assert loaded_snapshot.timestamp == snapshot.timestamp
            assert loaded_llm.network_context == llm_data.network_context
            
            # Ottieni statistiche
            stats = fs_manager.get_storage_stats()
            assert stats['total_files'] >= 2
            
            # Crea backup
            backup_path = fs_manager.create_backup()
            assert backup_path.exists()
            
            # Lista file
            history_files = fs_manager.list_history_files()
            llm_files = fs_manager.list_llm_files()
            
            assert len(history_files) >= 1
            assert len(llm_files) >= 1
    
    def test_concurrent_access_simulation(self):
        """Test simulazione accesso concorrente"""
        with tempfile.TemporaryDirectory() as temp_dir:
            config = FileSystemConfig(base_output_dir=temp_dir)
            fs_manager = FileSystemManager(config)
            
            # Simula salvataggio concorrente
            snapshots = []
            for i in range(5):
                snapshot = NetworkSnapshot(
                    timestamp=datetime.now().timestamp() + i,
                    topology=TopologyData(switches=[], links=[], graph_representation={}),
                    metrics=MetricsData(port_statistics={}, aggregated_metrics={}, quality_indicators=None),
                    derived_metrics=None,
                    metadata={"id": i}
                )
                snapshots.append(snapshot)
            
            # Salva tutti gli snapshot
            saved_paths = []
            for snapshot in snapshots:
                path = fs_manager.save_network_snapshot(snapshot)
                saved_paths.append(path)
            
            # Verifica che tutti siano stati salvati
            assert len(saved_paths) == 5
            assert all(path.exists() for path in saved_paths)
            
            # Verifica che possano essere caricati
            for i, path in enumerate(saved_paths):
                loaded = fs_manager.load_network_snapshot(path.name)
                assert loaded.metadata["id"] == i