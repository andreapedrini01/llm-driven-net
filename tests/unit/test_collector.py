"""
Test per NetworkStateCollector

Testa la classe principale del sistema che integra tutti i componenti
per la raccolta, elaborazione e salvataggio dei dati di rete.
"""

import pytest
import time
import tempfile
import threading
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from network_state_collector.collector import NetworkStateCollector
from llm_integration_module.models.config import CollectorConfig
from llm_integration_module.models.core import NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, PortMetrics
from llm_integration_module.models.health import SystemHealth


class TestNetworkStateCollector:
    """Test per NetworkStateCollector"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Crea directory temporanea per configurazione"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_config(self, temp_config_dir):
        """Configurazione di esempio per i test"""
        config = CollectorConfig()
        config.output.directory = str(temp_config_dir / "data")
        config.collection.interval = 1.0  # Intervallo breve per test
        config.collection.validate_data = False  # Disabilita validazione per test
        return config
    
    @pytest.fixture
    def mock_components(self):
        """Mock dei componenti del collector"""
        with patch('network_state_collector.collector.ConfigurationManager') as mock_config_manager, \
             patch('network_state_collector.collector.RyuConnector') as mock_ryu, \
             patch('network_state_collector.collector.DataProcessor') as mock_processor, \
             patch('network_state_collector.collector.DataValidator') as mock_validator, \
             patch('network_state_collector.collector.LLMIntegrator') as mock_llm, \
             patch('network_state_collector.collector.JSONSerializer') as mock_serializer, \
             patch('network_state_collector.collector.FileSystemManager') as mock_filesystem, \
             patch('network_state_collector.collector.ErrorManager') as mock_error, \
             patch('network_state_collector.collector.LoggingManager') as mock_logging:
            
            yield {
                'ConfigurationManager': mock_config_manager,
                'RyuConnector': mock_ryu,
                'DataProcessor': mock_processor,
                'DataValidator': mock_validator,
                'LLMIntegrator': mock_llm,
                'JSONSerializer': mock_serializer,
                'FileSystemManager': mock_filesystem,
                'ErrorManager': mock_error,
                'LoggingManager': mock_logging
            }
    
    @pytest.fixture
    def sample_raw_data(self):
        """Dati grezzi di esempio dal controller Ryu"""
        switches = [
            SwitchInfo(dpid="0000000000000001", ports=[1, 2], active=True),
            SwitchInfo(dpid="0000000000000002", ports=[1, 2], active=True)
        ]
        
        links = [
            LinkInfo(src_dpid="0000000000000001", dst_dpid="0000000000000002", 
                    src_port=1, dst_port=1, active=True)
        ]
        
        port_stats = {
            "0000000000000001": [
                PortMetrics(port_no=1, rx_packets=100, tx_packets=200, rx_bytes=1000, tx_bytes=2000, rx_errors=0, tx_errors=0),
                PortMetrics(port_no=2, rx_packets=150, tx_packets=250, rx_bytes=1500, tx_bytes=2500, rx_errors=0, tx_errors=0)
            ],
            "0000000000000002": [
                PortMetrics(port_no=1, rx_packets=300, tx_packets=400, rx_bytes=3000, tx_bytes=4000, rx_errors=0, tx_errors=0)
            ]
        }
        
        return switches, links, port_stats
    
    @pytest.fixture
    def sample_processed_data(self):
        """Dati elaborati di esempio"""
        topology_data = TopologyData(
            switches=[
                {"dpid": "0000000000000001", "ports": [1, 2]},
                {"dpid": "0000000000000002", "ports": [1]}
            ],
            links=[
                {"src": "0000000000000001", "dst": "0000000000000002", "src_port": 1, "dst_port": 1}
            ],
            graph_representation={"nodes": 2, "edges": 1}
        )
        
        metrics_data = MetricsData(
            port_statistics={
                "0000000000000001": [
                    {"port_no": 1, "rx_packets": 100, "tx_packets": 200},
                    {"port_no": 2, "rx_packets": 150, "tx_packets": 250}
                ],
                "0000000000000002": [
                    {"port_no": 1, "rx_packets": 300, "tx_packets": 400}
                ]
            },
            aggregated_metrics={"total_ports": 3, "total_switches": 2},
            quality_indicators={"completeness": 1.0, "consistency": 1.0}
        )
        
        return topology_data, metrics_data
    
    def test_init_with_default_config(self, mock_components):
        """Test inizializzazione con configurazione di default"""
        # Setup mock
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        collector = NetworkStateCollector()
        
        assert collector.config is not None
        assert collector.ryu_connector is not None
        assert collector.data_processor is not None
        assert collector.data_validator is not None
        assert collector.llm_integrator is not None
        assert collector.json_serializer is not None
        assert collector.filesystem_manager is not None
        assert collector.error_manager is not None
        assert collector.logging_manager is not None
        assert not collector._is_collecting
        assert collector._collection_thread is None
    
    def test_init_with_custom_config(self, mock_components, temp_config_dir):
        """Test inizializzazione con configurazione personalizzata"""
        # Crea file di configurazione
        config_file = temp_config_dir / "test.yaml"
        config_file.write_text("environment: test")
        
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        collector = NetworkStateCollector(str(config_file), "test")
        
        mock_config_manager.load_config.assert_called_once_with(str(config_file), "test")
    
    def test_collect_snapshot_success(self, mock_components, sample_raw_data, sample_processed_data):
        """Test raccolta snapshot con successo"""
        switches, links, port_stats = sample_raw_data
        topology_data, metrics_data = sample_processed_data
        
        # Setup mocks
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        mock_ryu = mock_components['RyuConnector'].return_value
        mock_ryu.get_switches.return_value = switches
        mock_ryu.get_links.return_value = links
        mock_ryu.get_port_stats.side_effect = lambda dpid: port_stats.get(dpid, [])
        
        mock_processor = mock_components['DataProcessor'].return_value
        mock_processor.process_topology.return_value = topology_data
        mock_processor.process_metrics.return_value = metrics_data
        
        mock_llm = mock_components['LLMIntegrator'].return_value
        mock_llm.format_for_llm.return_value = {"formatted": "data"}
        
        mock_serializer = mock_components['JSONSerializer'].return_value
        mock_serializer.serialize_network_snapshot.return_value = '{"snapshot": "data"}'
        mock_serializer.serialize_llm_data.return_value = '{"llm": "data"}'
        
        mock_filesystem = mock_components['FileSystemManager'].return_value
        mock_filesystem.save_network_context.return_value = "snapshot.json"
        mock_filesystem.save_latest_context.return_value = "latest.json"
        mock_filesystem.save_llm_data.return_value = "llm.json"
        
        # Test
        collector = NetworkStateCollector()
        snapshot = collector.collect_snapshot()
        
        # Verifiche
        assert snapshot is not None
        assert isinstance(snapshot, NetworkSnapshot)
        assert snapshot.topology == topology_data
        assert snapshot.metrics == metrics_data
        assert collector._collection_stats["successful_snapshots"] == 1
        assert collector._collection_stats["failed_snapshots"] == 0
        assert collector._last_snapshot == snapshot
        
        # Verifica chiamate ai componenti
        mock_ryu.get_switches.assert_called_once()
        mock_ryu.get_links.assert_called_once()
        mock_processor.process_topology.assert_called_once_with(switches, links)
        mock_processor.process_metrics.assert_called_once_with(port_stats)
        mock_llm.format_for_llm.assert_called_once()
        mock_filesystem.save_network_context.assert_called_once()
        mock_filesystem.save_latest_context.assert_called_once()
        mock_filesystem.save_llm_data.assert_called_once()
    
    def test_collect_snapshot_no_switches(self, mock_components):
        """Test raccolta snapshot quando non ci sono switch"""
        # Setup mocks
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        mock_ryu = mock_components['RyuConnector'].return_value
        mock_ryu.get_switches.return_value = []  # Nessuno switch
        
        # Test
        collector = NetworkStateCollector()
        snapshot = collector.collect_snapshot()
        
        # Verifiche
        assert snapshot is None
        assert collector._collection_stats["successful_snapshots"] == 0
        assert collector._collection_stats["failed_snapshots"] == 0  # Non conta come fallimento
    
    def test_collect_snapshot_with_validation_failure(self, mock_components, sample_raw_data, sample_processed_data):
        """Test raccolta snapshot con fallimento validazione"""
        switches, links, port_stats = sample_raw_data
        topology_data, metrics_data = sample_processed_data
        
        # Setup mocks
        config = CollectorConfig()
        config.collection.validate_data = True
        
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = config
        
        mock_ryu = mock_components['RyuConnector'].return_value
        mock_ryu.get_switches.return_value = switches
        mock_ryu.get_links.return_value = links
        mock_ryu.get_port_stats.side_effect = lambda dpid: port_stats.get(dpid, [])
        
        mock_processor = mock_components['DataProcessor'].return_value
        mock_processor.process_topology.return_value = topology_data
        mock_processor.process_metrics.return_value = metrics_data
        
        # Mock validazione fallita
        mock_validator = mock_components['DataValidator'].return_value
        mock_validation_result = Mock()
        mock_validation_result.is_valid = False
        mock_validator.validate_network_snapshot.return_value = mock_validation_result
        
        # Test
        collector = NetworkStateCollector()
        snapshot = collector.collect_snapshot()
        
        # Verifiche
        assert snapshot is None
        assert collector._collection_stats["successful_snapshots"] == 0
        assert collector._collection_stats["failed_snapshots"] == 1
    
    def test_collect_snapshot_with_exception(self, mock_components):
        """Test raccolta snapshot con eccezione"""
        # Setup mocks
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        mock_ryu = mock_components['RyuConnector'].return_value
        mock_ryu.get_switches.side_effect = Exception("Connection error")
        
        # Test
        collector = NetworkStateCollector()
        snapshot = collector.collect_snapshot()
        
        # Verifiche
        assert snapshot is None
        assert collector._collection_stats["successful_snapshots"] == 0
        assert collector._collection_stats["failed_snapshots"] == 1
    
    def test_start_stop_continuous_collection(self, mock_components):
        """Test avvio e stop raccolta continua"""
        # Setup mocks
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        collector = NetworkStateCollector()
        
        # Test avvio
        assert not collector._is_collecting
        collector.start_continuous_collection(0.1)  # Intervallo molto breve
        
        assert collector._is_collecting
        assert collector._collection_thread is not None
        assert collector._collection_thread.is_alive()
        
        # Attende un po' per permettere almeno una iterazione
        time.sleep(0.2)
        
        # Test stop
        collector.stop_collection()
        
        assert not collector._is_collecting
        assert not collector._collection_thread.is_alive()
    
    def test_start_continuous_collection_already_running(self, mock_components):
        """Test avvio raccolta continua quando già in esecuzione"""
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        collector = NetworkStateCollector()
        collector._is_collecting = True  # Simula già in esecuzione
        
        # Non dovrebbe fare nulla
        collector.start_continuous_collection()
        
        assert collector._collection_thread is None
    
    def test_stop_collection_not_running(self, mock_components):
        """Test stop raccolta quando non in esecuzione"""
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        collector = NetworkStateCollector()
        
        # Non dovrebbe causare errori
        collector.stop_collection()
        
        assert not collector._is_collecting
    
    def test_get_health_status_healthy(self, mock_components):
        """Test stato di salute quando tutto è sano"""
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        mock_ryu = mock_components['RyuConnector'].return_value
        mock_ryu.is_healthy.return_value = True
        
        mock_filesystem = mock_components['FileSystemManager'].return_value
        mock_filesystem.get_storage_stats.return_value = {"available_space": 1000 * 1024 * 1024}  # 1GB
        
        collector = NetworkStateCollector()
        health = collector.get_health_status()
        
        assert isinstance(health, SystemHealth)
        assert health.overall_status.value == "healthy"
        assert len(health.components) == 2  # RYU_CONNECTOR and FILE_SYSTEM
    
    def test_get_health_status_degraded(self, mock_components):
        """Test stato di salute degradato"""
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        mock_ryu = mock_components['RyuConnector'].return_value
        mock_ryu.is_healthy.return_value = True
        
        mock_filesystem = mock_components['FileSystemManager'].return_value
        mock_filesystem.get_storage_stats.return_value = {"available_space": 50 * 1024 * 1024}  # 50MB (sotto soglia)
        
        collector = NetworkStateCollector()
        health = collector.get_health_status()
        
        assert health.overall_status.value == "degraded"
    
    def test_get_health_status_unhealthy(self, mock_components):
        """Test stato di salute non sano"""
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        mock_ryu = mock_components['RyuConnector'].return_value
        mock_ryu.is_healthy.return_value = False
        
        mock_filesystem = mock_components['FileSystemManager'].return_value
        mock_filesystem.get_storage_stats.return_value = {"available_space": 50 * 1024 * 1024}  # Poco spazio
        
        collector = NetworkStateCollector()
        health = collector.get_health_status()
        
        assert health.overall_status.value == "unhealthy"
    
    def test_get_collection_stats(self, mock_components):
        """Test ottenimento statistiche raccolta"""
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        collector = NetworkStateCollector()
        
        # Modifica statistiche per test
        collector._collection_stats["total_snapshots"] = 10
        collector._collection_stats["successful_snapshots"] = 8
        collector._collection_stats["failed_snapshots"] = 2
        
        stats = collector.get_collection_stats()
        
        assert stats["total_snapshots"] == 10
        assert stats["successful_snapshots"] == 8
        assert stats["failed_snapshots"] == 2
        assert "is_collecting" in stats
        assert "last_snapshot" in stats
    
    def test_reload_configuration_success(self, mock_components):
        """Test ricaricamento configurazione con successo"""
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        mock_config_manager.reload_config.return_value = True
        mock_config_manager.get_current_config.return_value = CollectorConfig()
        
        collector = NetworkStateCollector()
        result = collector.reload_configuration()
        
        assert result is True
        mock_config_manager.reload_config.assert_called_once()
        mock_config_manager.get_current_config.assert_called_once()
    
    def test_reload_configuration_no_changes(self, mock_components):
        """Test ricaricamento configurazione senza modifiche"""
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        mock_config_manager.reload_config.return_value = False
        
        collector = NetworkStateCollector()
        result = collector.reload_configuration()
        
        assert result is False
        mock_config_manager.reload_config.assert_called_once()
        mock_config_manager.get_current_config.assert_not_called()
    
    def test_reload_configuration_error(self, mock_components):
        """Test ricaricamento configurazione con errore"""
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        mock_config_manager.reload_config.side_effect = Exception("Reload error")
        
        collector = NetworkStateCollector()
        result = collector.reload_configuration()
        
        assert result is False
    
    def test_collect_port_stats_sequential(self, mock_components, sample_raw_data):
        """Test raccolta statistiche porte sequenziale"""
        switches, _, _ = sample_raw_data
        
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        config = CollectorConfig()
        config.collection.parallel_collection = False
        mock_config_manager.load_config.return_value = config
        
        mock_ryu = mock_components['RyuConnector'].return_value
        mock_ryu.get_port_stats.side_effect = [
            [{"port_no": 1, "rx_packets": 100}],  # Switch 1
            [{"port_no": 1, "rx_packets": 200}]   # Switch 2
        ]
        
        collector = NetworkStateCollector()
        result = collector._collect_port_stats_sequential(switches)
        
        assert len(result) == 2
        assert "0000000000000001" in result
        assert "0000000000000002" in result
        assert mock_ryu.get_port_stats.call_count == 2
    
    def test_collect_port_stats_parallel(self, mock_components, sample_raw_data):
        """Test raccolta statistiche porte parallela"""
        switches, _, _ = sample_raw_data
        
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        config = CollectorConfig()
        config.collection.parallel_collection = True
        config.collection.max_workers = 2
        mock_config_manager.load_config.return_value = config
        
        mock_ryu = mock_components['RyuConnector'].return_value
        mock_ryu.get_port_stats.side_effect = [
            [{"port_no": 1, "rx_packets": 100}],  # Switch 1
            [{"port_no": 1, "rx_packets": 200}]   # Switch 2
        ]
        
        collector = NetworkStateCollector()
        result = collector._collect_port_stats_parallel(switches)
        
        assert len(result) == 2
        assert "0000000000000001" in result
        assert "0000000000000002" in result
        assert mock_ryu.get_port_stats.call_count == 2
    
    def test_topology_change_detection(self, mock_components, sample_processed_data):
        """Test rilevamento cambiamenti topologia"""
        topology_data, _ = sample_processed_data
        
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        collector = NetworkStateCollector()
        
        # Prima chiamata - stabilisce hash iniziale
        snapshot1 = NetworkSnapshot(
            timestamp=time.time(),
            topology=topology_data,
            metrics=MetricsData(port_statistics={}, aggregated_metrics={}, quality_indicators={}),
            metadata={}
        )
        collector._check_topology_changes(snapshot1)
        initial_hash = collector._last_topology_hash
        
        # Seconda chiamata con stessa topologia - nessun cambiamento
        collector._check_topology_changes(snapshot1)
        assert collector._last_topology_hash == initial_hash
        
        # Terza chiamata con topologia modificata
        modified_topology = TopologyData(
            switches=[{"dpid": "0000000000000003", "ports": [1]}],  # Switch diverso
            links=[],
            graph_representation={"nodes": 1, "edges": 0}
        )
        snapshot2 = NetworkSnapshot(
            timestamp=time.time(),
            topology=modified_topology,
            metrics=MetricsData(port_statistics={}, aggregated_metrics={}, quality_indicators={}),
            metadata={}
        )
        collector._check_topology_changes(snapshot2)
        assert collector._last_topology_hash != initial_hash
    
    def test_context_manager(self, mock_components):
        """Test utilizzo come context manager"""
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        with NetworkStateCollector() as collector:
            assert collector is not None
            collector._is_collecting = True  # Simula raccolta attiva
        
        # Dovrebbe aver chiamato stop_collection automaticamente
        assert not collector._is_collecting
    
    def test_update_collection_stats(self, mock_components):
        """Test aggiornamento statistiche raccolta"""
        mock_config_manager = mock_components['ConfigurationManager'].return_value
        mock_config_manager.load_config.return_value = CollectorConfig()
        
        collector = NetworkStateCollector()
        
        # Test successo
        collector._update_collection_stats(1.5, success=True)
        
        assert collector._collection_stats["total_snapshots"] == 1
        assert collector._collection_stats["successful_snapshots"] == 1
        assert collector._collection_stats["failed_snapshots"] == 0
        assert collector._collection_stats["average_collection_time"] == 1.5
        
        # Test fallimento
        collector._update_collection_stats(2.0, success=False)
        
        assert collector._collection_stats["total_snapshots"] == 2
        assert collector._collection_stats["successful_snapshots"] == 1
        assert collector._collection_stats["failed_snapshots"] == 1
        assert collector._collection_stats["average_collection_time"] == 1.5  # Non cambia per fallimenti
        
        # Test secondo successo (verifica media)
        collector._update_collection_stats(2.5, success=True)
        
        assert collector._collection_stats["total_snapshots"] == 3
        assert collector._collection_stats["successful_snapshots"] == 2
        assert collector._collection_stats["failed_snapshots"] == 1
        assert collector._collection_stats["average_collection_time"] == 2.0  # (1.5 + 2.5) / 2