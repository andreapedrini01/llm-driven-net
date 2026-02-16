"""
Test di integrazione per DataProcessor con RyuConnector

Verifica che il DataProcessor possa elaborare correttamente i dati
provenienti dal RyuConnector.
"""

import pytest
from unittest.mock import Mock, patch
from network_state_collector.data_processor import DataProcessor
from src.models.core import SwitchInfo, LinkInfo, PortMetrics


class TestDataProcessorIntegration:
    """Test di integrazione per DataProcessor"""
    
    def setup_method(self):
        """Setup per ogni test"""
        self.processor = DataProcessor()
    
    def test_process_topology_from_ryu_data(self):
        """Test elaborazione topologia con dati simulati da Ryu"""
        # Simula dati che potrebbero arrivare dal RyuConnector
        switches = [
            SwitchInfo(dpid=1, ports=[1, 2, 3], active=True),
            SwitchInfo(dpid=2, ports=[1, 2], active=True),
            SwitchInfo(dpid=0xABCDEF123456, ports=[1, 2, 3, 4], active=True)
        ]
        
        links = [
            LinkInfo(src_dpid=1, dst_dpid=2, src_port=1, dst_port=1, active=True),
            LinkInfo(src_dpid=2, dst_dpid=1, src_port=1, dst_port=1, active=True),
            LinkInfo(src_dpid=1, dst_dpid=0xABCDEF123456, src_port=2, dst_port=1, active=True)
        ]
        
        # Processa i dati
        result = self.processor.process_topology(switches, links)
        
        # Verifica risultati
        assert len(result.switches) == 3
        assert len(result.links) == 3
        
        # Verifica formattazione DPID
        expected_dpids = {
            "0000000000000001",
            "0000000000000002", 
            "0000abcdef123456"
        }
        actual_dpids = {switch.dpid for switch in result.switches}
        assert actual_dpids == expected_dpids
        
        # Verifica link formattati
        for link in result.links:
            assert len(link.src_dpid) == 16
            assert len(link.dst_dpid) == 16
            assert link.src_dpid in expected_dpids
            assert link.dst_dpid in expected_dpids
        
        # Verifica rappresentazione grafica
        graph = result.graph_representation
        assert len(graph["nodes"]) == 3
        assert len(graph["edges"]) == 3
        
        # Verifica metriche topologia
        metrics = graph["metrics"]
        assert metrics["total_nodes"] == 3
        assert metrics["total_edges"] == 3
        assert metrics["active_nodes"] == 3
        assert metrics["active_edges"] == 3
        
        # Verifica connettività
        connectivity = graph["connectivity_info"]
        assert connectivity["connected_switches"] == 3
        assert connectivity["isolated_switches"] == 0
        assert connectivity["connectivity_ratio"] == 1.0
    
    def test_process_metrics_from_ryu_data(self):
        """Test elaborazione metriche con dati simulati da Ryu"""
        # Simula dati di metriche che potrebbero arrivare dal RyuConnector
        port_stats = {
            "1": [
                PortMetrics(port_no=1, rx_packets=1000, tx_packets=800, 
                           rx_bytes=64000, tx_bytes=51200, rx_errors=0, tx_errors=0),
                PortMetrics(port_no=2, rx_packets=500, tx_packets=600,
                           rx_bytes=32000, tx_bytes=38400, rx_errors=1, tx_errors=0)
            ],
            "0xABCDEF123456": [
                PortMetrics(port_no=1, rx_packets=2000, tx_packets=1800,
                           rx_bytes=128000, tx_bytes=115200, rx_errors=0, tx_errors=2)
            ]
        }
        
        # Processa le metriche
        result = self.processor.process_metrics(port_stats)
        
        # Verifica risultati
        assert len(result.port_statistics) == 2
        assert len(result.aggregated_metrics) == 2
        
        # Verifica formattazione DPID nelle chiavi
        expected_dpids = {"0000000000000001", "0000abcdef123456"}
        assert set(result.port_statistics.keys()) == expected_dpids
        assert set(result.aggregated_metrics.keys()) == expected_dpids
        
        # Verifica metriche aggregate
        switch1_metrics = result.aggregated_metrics["0000000000000001"]
        assert switch1_metrics.total_rx_packets == 1500  # 1000 + 500
        assert switch1_metrics.total_tx_packets == 1400  # 800 + 600
        assert switch1_metrics.total_errors == 1  # 0 + 1 + 0 + 0
        
        switch2_metrics = result.aggregated_metrics["0000abcdef123456"]
        assert switch2_metrics.total_rx_packets == 2000
        assert switch2_metrics.total_tx_packets == 1800
        assert switch2_metrics.total_errors == 2  # 0 + 2
    
    def test_calculate_derived_metrics(self):
        """Test calcolo metriche derivate"""
        # Crea dati di metriche di test
        port_stats = {
            "0000000000000001": [
                PortMetrics(port_no=1, rx_packets=1000, tx_packets=800,
                           rx_bytes=64000, tx_bytes=51200, rx_errors=0, tx_errors=0),
                PortMetrics(port_no=2, rx_packets=500, tx_packets=600,
                           rx_bytes=32000, tx_bytes=38400, rx_errors=1, tx_errors=0)
            ]
        }
        
        metrics_data = self.processor.process_metrics(port_stats)
        
        # Calcola metriche derivate
        derived = self.processor.calculate_derived_metrics(metrics_data)
        
        # Verifica che le metriche derivate siano calcolate
        assert 0.0 <= derived.network_utilization <= 1.0
        assert 0.0 <= derived.congestion_level <= 1.0
        assert 0.0 <= derived.error_rate <= 1.0
        assert 0.0 <= derived.topology_stability <= 1.0
        assert 0.0 <= derived.performance_score <= 1.0
        
        # Verifica che il tasso di errore sia corretto
        # Total packets: 1000 + 800 + 500 + 600 = 2900
        # Total errors: 0 + 0 + 1 + 0 = 1
        # Error rate: 1/2900 ≈ 0.000345
        expected_error_rate = 1 / 2900
        assert abs(derived.error_rate - expected_error_rate) < 0.001
    
    def test_end_to_end_processing(self):
        """Test elaborazione end-to-end completa"""
        # Simula un flusso completo di elaborazione dati
        
        # 1. Dati di topologia
        switches = [
            SwitchInfo(dpid="0x1", ports=[1, 2], active=True),
            SwitchInfo(dpid="0x2", ports=[1, 2], active=True)
        ]
        
        links = [
            LinkInfo(src_dpid="0x1", dst_dpid="0x2", src_port=1, dst_port=1, active=True),
            LinkInfo(src_dpid="0x2", dst_dpid="0x1", src_port=1, dst_port=1, active=True)
        ]
        
        # 2. Dati di metriche
        port_stats = {
            "0x1": [
                PortMetrics(port_no=1, rx_packets=1000, tx_packets=800,
                           rx_bytes=64000, tx_bytes=51200, rx_errors=0, tx_errors=0),
                PortMetrics(port_no=2, rx_packets=200, tx_packets=150,
                           rx_bytes=12800, tx_bytes=9600, rx_errors=0, tx_errors=0)
            ],
            "0x2": [
                PortMetrics(port_no=1, rx_packets=800, tx_packets=1000,
                           rx_bytes=51200, tx_bytes=64000, rx_errors=0, tx_errors=0),
                PortMetrics(port_no=2, rx_packets=100, tx_packets=120,
                           rx_bytes=6400, tx_bytes=7680, rx_errors=0, tx_errors=0)
            ]
        }
        
        # 3. Elabora topologia
        topology_data = self.processor.process_topology(switches, links)
        
        # 4. Elabora metriche
        metrics_data = self.processor.process_metrics(port_stats)
        
        # 5. Calcola metriche derivate
        derived_metrics = self.processor.calculate_derived_metrics(metrics_data)
        
        # 6. Verifica risultati finali
        assert len(topology_data.switches) == 2
        assert len(topology_data.links) == 2
        assert len(metrics_data.port_statistics) == 2
        assert len(metrics_data.aggregated_metrics) == 2
        
        # Verifica coerenza DPID tra topologia e metriche
        topology_dpids = {switch.dpid for switch in topology_data.switches}
        metrics_dpids = set(metrics_data.port_statistics.keys())
        assert topology_dpids == metrics_dpids
        
        # Verifica che le metriche derivate siano ragionevoli
        assert derived_metrics.error_rate == 0.0  # Nessun errore nei dati di test
        assert derived_metrics.topology_stability == 1.0  # Topologia stabile
        assert derived_metrics.performance_score > 0.0  # Qualche performance
        
        # Verifica statistiche del processore
        stats = self.processor.get_processing_stats()
        assert stats['topology_processed'] == 1
        assert stats['metrics_processed'] == 1
        assert stats['errors_encountered'] == 0
        assert stats['last_processing_time'] > 0
    
    def test_error_handling_during_processing(self):
        """Test gestione errori durante l'elaborazione"""
        # Test con dati che potrebbero causare errori
        
        # Switch con porte invalide
        switches = [
            SwitchInfo(dpid="1", ports=[1, -1, "invalid", 2.5, 3], active=True)
        ]
        
        # Processa - dovrebbe gestire gli errori gracefully
        result = self.processor.process_topology(switches, [])
        
        # Verifica che il processing sia riuscito nonostante gli errori
        assert len(result.switches) == 1
        # Le porte invalide dovrebbero essere filtrate
        assert result.switches[0].ports == [1, 3]  # Solo le porte valide
        
        # Verifica che le statistiche riflettano il processing
        stats = self.processor.get_processing_stats()
        assert stats['topology_processed'] > 0