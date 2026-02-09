"""
Test per LLMIntegrator - Integrazione con modelli LLM
"""

import pytest
import time
import numpy as np
from unittest.mock import Mock, patch

from network_state_collector.llm_integrator import LLMIntegrator, LLMIntegrationError
from network_state_collector.models.core import (
    NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, PortMetrics
)
from network_state_collector.models.llm import LLMNetworkData, AnomalyIndicator
from network_state_collector.models.health import QualityMetrics


class TestLLMIntegrator:
    """Test per la classe LLMIntegrator"""
    
    def setup_method(self):
        """Setup per ogni test"""
        self.integrator = LLMIntegrator()
        
        # Crea dati di test
        self.test_switches = [
            SwitchInfo(dpid="0000000000000001", ports=[1, 2, 3]),
            SwitchInfo(dpid="0000000000000002", ports=[1, 2])
        ]
        
        self.test_links = [
            LinkInfo(
                src_dpid="0000000000000001",
                dst_dpid="0000000000000002",
                src_port=1,
                dst_port=1
            )
        ]
        
        self.test_port_metrics = {
            "0000000000000001": [
                PortMetrics(
                    port_no=1,
                    rx_packets=1000,
                    tx_packets=900,
                    rx_bytes=1024000,
                    tx_bytes=921600,
                    rx_errors=5,
                    tx_errors=2
                ),
                PortMetrics(
                    port_no=2,
                    rx_packets=2000,
                    tx_packets=1800,
                    rx_bytes=2048000,
                    tx_bytes=1843200,
                    rx_errors=10,
                    tx_errors=8
                )
            ],
            "0000000000000002": [
                PortMetrics(
                    port_no=1,
                    rx_packets=800,
                    tx_packets=750,
                    rx_bytes=819200,
                    tx_bytes=768000,
                    rx_errors=2,
                    tx_errors=1
                )
            ]
        }
        
        self.test_topology = TopologyData(
            switches=self.test_switches,
            links=self.test_links,
            graph_representation={}
        )
        
        self.test_metrics = MetricsData(
            port_statistics=self.test_port_metrics,
            aggregated_metrics={},
            quality_indicators=QualityMetrics(
                completeness_score=1.0,
                consistency_score=1.0,
                timeliness_score=1.0,
                accuracy_score=1.0,
                overall_score=1.0
            )
        )
        
        self.test_snapshot = NetworkSnapshot(
            timestamp=time.time(),
            topology=self.test_topology,
            metrics=self.test_metrics,
            derived_metrics={},
            metadata={}
        )
    
    def test_initialization(self):
        """Test inizializzazione LLMIntegrator"""
        integrator = LLMIntegrator(enable_anomaly_detection=False)
        
        assert integrator.enable_anomaly_detection is False
        assert 'high_utilization' in integrator.anomaly_thresholds
        assert integrator._topology_cache == {}
    
    def test_format_for_llm_basic(self):
        """Test conversione base in formato LLM"""
        llm_data = self.integrator.format_for_llm(self.test_snapshot)
        
        assert isinstance(llm_data, LLMNetworkData)
        assert isinstance(llm_data.network_context, dict)
        assert isinstance(llm_data.performance_vectors, list)
        assert isinstance(llm_data.topology_embedding, dict)
        assert isinstance(llm_data.temporal_features, dict)
        assert isinstance(llm_data.anomaly_indicators, list)
    
    def test_network_context_creation(self):
        """Test creazione contesto di rete"""
        llm_data = self.integrator.format_for_llm(self.test_snapshot)
        context = llm_data.network_context
        
        # Verifica struttura topology
        assert 'topology' in context
        topology = context['topology']
        assert 'nodes' in topology
        assert 'edges' in topology
        assert topology['node_count'] == 2
        assert topology['edge_count'] == 1
        
        # Verifica nodi
        nodes = topology['nodes']
        assert "0000000000000001" in nodes
        assert "0000000000000002" in nodes
        
        # Verifica archi
        edges = topology['edges']
        assert len(edges) == 1
        edge = edges[0]
        assert edge['src'] == "0000000000000001"
        assert edge['dst'] == "0000000000000002"
        assert edge['port_out'] == 1
        assert edge['port_in'] == 1
        
        # Verifica performance
        assert 'performance' in context
        performance = context['performance']
        assert 'utilization_vectors' in performance
        assert 'error_rates' in performance
        assert 'aggregated_metrics' in performance
    
    def test_performance_vectors_creation(self):
        """Test creazione vettori di performance"""
        llm_data = self.integrator.format_for_llm(self.test_snapshot)
        vectors = llm_data.performance_vectors
        
        # Dovremmo avere 3 vettori (2 porte per switch1 + 1 porta per switch2)
        assert len(vectors) == 3
        
        # Ogni vettore dovrebbe avere 3 elementi: [utilizzo, errori, throughput]
        for vector in vectors:
            assert len(vector) == 3
            assert all(isinstance(v, float) for v in vector)
            assert 0 <= vector[0] <= 100  # Utilizzo percentuale
            assert vector[1] >= 0  # Tasso errori
            assert vector[2] >= 0  # Throughput
    
    def test_topology_embedding_creation(self):
        """Test creazione embedding topologico"""
        llm_data = self.integrator.format_for_llm(self.test_snapshot)
        embedding = llm_data.topology_embedding
        
        assert 'adjacency_matrix' in embedding
        assert 'node_degrees' in embedding
        assert 'average_degree' in embedding
        assert 'node_count' in embedding
        assert 'edge_count' in embedding
        assert 'density' in embedding
        
        # Verifica matrice di adiacenza
        adj_matrix = embedding['adjacency_matrix']
        assert len(adj_matrix) == 2  # 2 nodi
        assert len(adj_matrix[0]) == 2
        assert adj_matrix[0][1] == 1  # Connessione tra nodo 0 e 1
        assert adj_matrix[1][0] == 1  # Connessione simmetrica
        
        # Verifica gradi dei nodi
        node_degrees = embedding['node_degrees']
        assert len(node_degrees) == 2
        assert node_degrees[0] == 1  # Nodo 0 ha grado 1
        assert node_degrees[1] == 1  # Nodo 1 ha grado 1
    
    def test_temporal_features_creation(self):
        """Test creazione features temporali"""
        llm_data = self.integrator.format_for_llm(self.test_snapshot)
        temporal = llm_data.temporal_features
        
        assert 'timestamp' in temporal
        assert 'hour_of_day' in temporal
        assert 'day_of_week' in temporal
        assert 'is_weekend' in temporal
        assert 'is_business_hours' in temporal
        assert 'time_features' in temporal
        
        # Verifica time_features ciclici
        time_features = temporal['time_features']
        assert 'hour_sin' in time_features
        assert 'hour_cos' in time_features
        assert 'day_sin' in time_features
        assert 'day_cos' in time_features
        
        # Verifica range valori
        assert 0 <= temporal['hour_of_day'] <= 23
        assert 0 <= temporal['day_of_week'] <= 6
        assert isinstance(temporal['is_weekend'], bool)
        assert isinstance(temporal['is_business_hours'], bool)
    
    def test_anomaly_detection_enabled(self):
        """Test rilevamento anomalie abilitato"""
        # Crea integrator con anomaly detection abilitato
        integrator = LLMIntegrator(enable_anomaly_detection=True)
        
        # Modifica dati per creare anomalie
        high_util_metrics = PortMetrics(
            port_no=1,
            rx_packets=1000,
            tx_packets=900,
            rx_bytes=10240000000,  # 10GB - alta utilizzazione
            tx_bytes=9216000000,   # 9GB
            rx_errors=50,          # Molti errori
            tx_errors=20
        )
        
        anomaly_snapshot = NetworkSnapshot(
            timestamp=time.time(),
            topology=self.test_topology,
            metrics=MetricsData(
                port_statistics={"0000000000000001": [high_util_metrics]},
                aggregated_metrics={},
                quality_indicators=QualityMetrics(1.0, 1.0, 1.0, 1.0, 1.0)
            ),
            derived_metrics={},
            metadata={}
        )
        
        llm_data = integrator.format_for_llm(anomaly_snapshot)
        
        # Dovremmo rilevare anomalie
        assert len(llm_data.anomaly_indicators) > 0
        
        # Verifica tipi di anomalie
        anomaly_types = [a.type for a in llm_data.anomaly_indicators]
        assert "high_utilization" in anomaly_types
        assert "high_error_rate" in anomaly_types
    
    def test_anomaly_detection_disabled(self):
        """Test rilevamento anomalie disabilitato"""
        integrator = LLMIntegrator(enable_anomaly_detection=False)
        
        llm_data = integrator.format_for_llm(self.test_snapshot)
        
        # Non dovremmo avere anomalie
        assert len(llm_data.anomaly_indicators) == 0
    
    def test_isolated_switch_detection(self):
        """Test rilevamento switch isolati"""
        # Crea topologia con switch isolato
        isolated_switches = [
            SwitchInfo(dpid="0000000000000001", ports=[1, 2]),
            SwitchInfo(dpid="0000000000000002", ports=[1, 2]),
            SwitchInfo(dpid="0000000000000003", ports=[1, 2])  # Switch isolato
        ]
        
        # Link solo tra switch 1 e 2
        connected_links = [
            LinkInfo(
                src_dpid="0000000000000001",
                dst_dpid="0000000000000002",
                src_port=1,
                dst_port=1
            )
        ]
        
        isolated_topology = TopologyData(
            switches=isolated_switches,
            links=connected_links,
            graph_representation={}
        )
        
        isolated_snapshot = NetworkSnapshot(
            timestamp=time.time(),
            topology=isolated_topology,
            metrics=self.test_metrics,
            derived_metrics={},
            metadata={}
        )
        
        llm_data = self.integrator.format_for_llm(isolated_snapshot)
        
        # Dovremmo rilevare switch isolato
        isolated_anomalies = [
            a for a in llm_data.anomaly_indicators 
            if a.type == "isolated_switch"
        ]
        assert len(isolated_anomalies) == 1
        assert "0000000000000003" in isolated_anomalies[0].affected_components
    
    def test_create_context_embedding(self):
        """Test creazione embedding del contesto"""
        llm_data = self.integrator.format_for_llm(self.test_snapshot)
        embedding = self.integrator.create_context_embedding(llm_data)
        
        assert hasattr(embedding, 'topology_embedding')
        assert hasattr(embedding, 'performance_embedding')
        assert hasattr(embedding, 'temporal_embedding')
        assert hasattr(embedding, 'dimension')
        
        # Verifica che ogni embedding abbia features
        assert 'features' in embedding.topology_embedding
        assert 'features' in embedding.performance_embedding
        assert 'features' in embedding.temporal_embedding
        
        # Verifica dimensione
        expected_dim = (
            len(embedding.topology_embedding['features']) +
            len(embedding.performance_embedding['features']) +
            len(embedding.temporal_embedding['features'])
        )
        assert embedding.dimension == expected_dim
    
    def test_validate_llm_schema_valid(self):
        """Test validazione schema LLM con dati validi"""
        llm_data = self.integrator.format_for_llm(self.test_snapshot)
        result = self.integrator.validate_llm_schema(llm_data)
        
        assert result.is_valid is True
        assert len(result.issues) == 0
        assert result.quality_score == 1.0
    
    def test_validate_llm_schema_invalid(self):
        """Test validazione schema LLM con dati invalidi"""
        # Crea dati LLM invalidi
        invalid_data = LLMNetworkData(
            network_context="invalid",  # Dovrebbe essere dict
            performance_vectors="invalid",  # Dovrebbe essere list
            topology_embedding="invalid",  # Dovrebbe essere dict
            temporal_features="invalid",  # Dovrebbe essere dict
            anomaly_indicators="invalid"  # Dovrebbe essere list
        )
        
        result = self.integrator.validate_llm_schema(invalid_data)
        
        assert result.is_valid is False
        assert len(result.issues) > 0
        assert result.quality_score < 1.0
        
        # Verifica messaggi di errore specifici
        issues_text = " ".join(result.issues)
        assert "network_context must be a dictionary" in issues_text
        assert "performance_vectors must be a list" in issues_text
        assert "topology_embedding must be a dictionary" in issues_text
        assert "temporal_features must be a dictionary" in issues_text
        assert "anomaly_indicators must be a list" in issues_text
    
    def test_error_handling(self):
        """Test gestione errori"""
        # Crea snapshot con dati invalidi
        invalid_snapshot = NetworkSnapshot(
            timestamp=None,  # Timestamp invalido
            topology=None,   # Topologia invalida
            metrics=None,    # Metriche invalide
            derived_metrics={},
            metadata={}
        )
        
        with pytest.raises(LLMIntegrationError):
            self.integrator.format_for_llm(invalid_snapshot)
    
    def test_performance_aggregation(self):
        """Test aggregazione dati di performance"""
        llm_data = self.integrator.format_for_llm(self.test_snapshot)
        performance = llm_data.network_context['performance']
        
        assert 'aggregated_metrics' in performance
        aggregated = performance['aggregated_metrics']
        
        assert 'average_utilization' in aggregated
        assert 'total_errors' in aggregated
        assert 'total_throughput_mb' in aggregated
        assert 'active_ports' in aggregated
        
        # Verifica valori aggregati
        assert aggregated['active_ports'] == 3  # 3 porte totali
        assert aggregated['average_utilization'] > 0
        assert aggregated['total_errors'] >= 0
        assert aggregated['total_throughput_mb'] >= 0
    
    def test_json_serialization(self):
        """Test serializzazione JSON"""
        llm_data = self.integrator.format_for_llm(self.test_snapshot)
        
        # Test to_dict
        data_dict = llm_data.to_dict()
        assert isinstance(data_dict, dict)
        assert 'network_context' in data_dict
        assert 'performance_vectors' in data_dict
        
        # Test to_json
        json_str = llm_data.to_json()
        assert isinstance(json_str, str)
        assert 'network_context' in json_str
        
        # Test round-trip
        restored_data = LLMNetworkData.from_json(json_str)
        assert restored_data.network_context == llm_data.network_context
        assert restored_data.performance_vectors == llm_data.performance_vectors
    
    def test_anomaly_thresholds_customization(self):
        """Test personalizzazione soglie anomalie"""
        integrator = LLMIntegrator()
        
        # Modifica soglie
        integrator.anomaly_thresholds['high_utilization'] = 0.5  # 50%
        integrator.anomaly_thresholds['high_error_rate'] = 0.005  # 0.5%
        
        # Crea metriche che superano le nuove soglie
        moderate_metrics = PortMetrics(
            port_no=1,
            rx_packets=1000,
            tx_packets=900,
            rx_bytes=5120000000,  # 5GB - supera 50%
            tx_bytes=4608000000,  # 4GB
            rx_errors=8,          # Supera 0.5% error rate
            tx_errors=2
        )
        
        test_snapshot = NetworkSnapshot(
            timestamp=time.time(),
            topology=self.test_topology,
            metrics=MetricsData(
                port_statistics={"0000000000000001": [moderate_metrics]},
                aggregated_metrics={},
                quality_indicators=QualityMetrics(1.0, 1.0, 1.0, 1.0, 1.0)
            ),
            derived_metrics={},
            metadata={}
        )
        
        llm_data = integrator.format_for_llm(test_snapshot)
        
        # Dovremmo rilevare anomalie con le nuove soglie
        assert len(llm_data.anomaly_indicators) > 0
        anomaly_types = [a.type for a in llm_data.anomaly_indicators]
        assert "high_utilization" in anomaly_types
        assert "high_error_rate" in anomaly_types


class TestLLMIntegrationError:
    """Test per la classe LLMIntegrationError"""
    
    def test_exception_creation(self):
        """Test creazione eccezione"""
        error = LLMIntegrationError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)


class TestIntegration:
    """Test di integrazione per LLMIntegrator"""
    
    def test_end_to_end_conversion(self):
        """Test conversione end-to-end completa"""
        integrator = LLMIntegrator(enable_anomaly_detection=True)
        
        # Crea snapshot complesso
        switches = [
            SwitchInfo(dpid=f"000000000000000{i}", ports=[1, 2, 3, 4])
            for i in range(1, 6)  # 5 switch
        ]
        
        links = [
            LinkInfo(f"000000000000000{i}", f"000000000000000{i+1}", 1, 1)
            for i in range(1, 5)  # Topologia lineare
        ]
        
        port_stats = {}
        for i, switch in enumerate(switches):
            port_stats[switch.dpid] = [
                PortMetrics(
                    port_no=j,
                    rx_packets=1000 * (i + 1) * j,
                    tx_packets=900 * (i + 1) * j,
                    rx_bytes=1024000 * (i + 1) * j,
                    tx_bytes=921600 * (i + 1) * j,
                    rx_errors=i * j,
                    tx_errors=i * j // 2
                )
                for j in range(1, 4)  # 3 porte per switch
            ]
        
        complex_snapshot = NetworkSnapshot(
            timestamp=time.time(),
            topology=TopologyData(switches=switches, links=links, graph_representation={}),
            metrics=MetricsData(
                port_statistics=port_stats,
                aggregated_metrics={},
                quality_indicators=QualityMetrics(1.0, 1.0, 1.0, 1.0, 1.0)
            ),
            derived_metrics={},
            metadata={}
        )
        
        # Conversione completa
        llm_data = integrator.format_for_llm(complex_snapshot)
        
        # Verifica risultati
        assert len(llm_data.network_context['topology']['nodes']) == 5
        assert len(llm_data.network_context['topology']['edges']) == 4
        assert len(llm_data.performance_vectors) == 15  # 5 switch * 3 porte
        
        # Verifica embedding
        embedding = integrator.create_context_embedding(llm_data)
        assert embedding.dimension > 0
        
        # Verifica validazione
        validation = integrator.validate_llm_schema(llm_data)
        assert validation.is_valid
        
        # Verifica serializzazione
        json_str = llm_data.to_json()
        restored = LLMNetworkData.from_json(json_str)
        assert len(restored.performance_vectors) == len(llm_data.performance_vectors)