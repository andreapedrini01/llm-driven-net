"""
LLMIntegrator - Integrazione con modelli LLM

Implementa la conversione dei dati di rete in formato ottimizzato per
l'integrazione con i modelli di linguaggio del team.
"""

import time
import logging
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import asdict

from .models.core import NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo
from .models.llm import LLMNetworkData, AnomalyIndicator, ContextEmbedding
from .models.health import QualityMetrics
from .data_validator import ValidationResult


class LLMIntegrationError(Exception):
    """Eccezione per errori nell'integrazione LLM"""
    pass


class LLMIntegrator:
    """
    Integratore per modelli LLM
    
    Converte i dati di rete in formato ottimizzato per l'analisi LLM:
    - Formattazione del contesto di rete
    - Creazione di vettori di performance
    - Generazione di embedding topologici
    - Rilevamento di indicatori di anomalia
    """
    
    def __init__(self, enable_anomaly_detection: bool = True):
        """
        Inizializza l'LLMIntegrator
        
        Args:
            enable_anomaly_detection: Se abilitare il rilevamento anomalie
        """
        self.logger = logging.getLogger(__name__)
        self.enable_anomaly_detection = enable_anomaly_detection
        
        # Soglie per rilevamento anomalie
        self.anomaly_thresholds = {
            'high_utilization': 0.8,
            'high_error_rate': 0.01,
            'packet_loss': 0.005,
            'congestion_threshold': 0.9
        }
        
        # Cache per embedding topologici
        self._topology_cache: Dict[str, Dict[str, Any]] = {}
        
        self.logger.info("LLMIntegrator initialized", extra={
            'component': 'LLMIntegrator',
            'anomaly_detection': enable_anomaly_detection
        })
    
    def format_for_llm(self, snapshot: NetworkSnapshot) -> LLMNetworkData:
        """
        Converte un NetworkSnapshot in formato LLMNetworkData
        
        Args:
            snapshot: Snapshot della rete da convertire
            
        Returns:
            Dati formattati per l'integrazione LLM
            
        Raises:
            LLMIntegrationError: Se la conversione fallisce
        """
        try:
            self.logger.debug("Starting LLM format conversion", extra={
                'component': 'LLMIntegrator',
                'timestamp': snapshot.timestamp
            })
            
            # Crea contesto di rete
            network_context = self._create_network_context(snapshot)
            
            # Genera vettori di performance
            performance_vectors = self._create_performance_vectors(snapshot.metrics)
            
            # Crea embedding topologico
            topology_embedding = self._create_topology_embedding(snapshot.topology)
            
            # Genera features temporali
            temporal_features = self._create_temporal_features(snapshot)
            
            # Rileva anomalie se abilitato
            anomaly_indicators = []
            if self.enable_anomaly_detection:
                anomaly_indicators = self._detect_anomalies(snapshot)
            
            llm_data = LLMNetworkData(
                network_context=network_context,
                performance_vectors=performance_vectors,
                topology_embedding=topology_embedding,
                temporal_features=temporal_features,
                anomaly_indicators=anomaly_indicators
            )
            
            self.logger.info("LLM format conversion completed", extra={
                'component': 'LLMIntegrator',
                'nodes_count': len(network_context.get('topology', {}).get('nodes', [])),
                'edges_count': len(network_context.get('topology', {}).get('edges', [])),
                'performance_vectors_count': len(performance_vectors),
                'anomalies_count': len(anomaly_indicators)
            })
            
            return llm_data
            
        except Exception as e:
            error_msg = f"Failed to format data for LLM: {e}"
            self.logger.error(error_msg, extra={'component': 'LLMIntegrator'})
            raise LLMIntegrationError(error_msg) from e
    
    def create_context_embedding(self, data: LLMNetworkData) -> ContextEmbedding:
        """
        Crea embedding del contesto per l'analisi LLM
        
        Args:
            data: Dati LLM da cui creare l'embedding
            
        Returns:
            Embedding del contesto
        """
        try:
            # Embedding topologico (rappresentazione grafica)
            topology_embedding = self._compute_topology_embedding(data.topology_embedding)
            
            # Embedding delle performance (vettori numerici)
            performance_embedding = self._compute_performance_embedding(data.performance_vectors)
            
            # Embedding temporale (features temporali)
            temporal_embedding = self._compute_temporal_embedding(data.temporal_features)
            
            # Dimensione dell'embedding (somma delle dimensioni)
            dimension = (
                len(topology_embedding.get('features', [])) +
                len(performance_embedding.get('features', [])) +
                len(temporal_embedding.get('features', []))
            )
            
            return ContextEmbedding(
                topology_embedding=topology_embedding,
                performance_embedding=performance_embedding,
                temporal_embedding=temporal_embedding,
                dimension=dimension
            )
            
        except Exception as e:
            error_msg = f"Failed to create context embedding: {e}"
            self.logger.error(error_msg, extra={'component': 'LLMIntegrator'})
            raise LLMIntegrationError(error_msg) from e
    
    def validate_llm_schema(self, data: LLMNetworkData) -> ValidationResult:
        """
        Valida che i dati LLM rispettino lo schema richiesto
        
        Args:
            data: Dati LLM da validare
            
        Returns:
            Risultato della validazione
        """
        issues = []
        
        # Valida network_context
        if not isinstance(data.network_context, dict):
            issues.append("network_context must be a dictionary")
        else:
            if 'topology' not in data.network_context:
                issues.append("network_context missing 'topology' section")
            if 'performance' not in data.network_context:
                issues.append("network_context missing 'performance' section")
        
        # Valida performance_vectors
        if not isinstance(data.performance_vectors, list):
            issues.append("performance_vectors must be a list")
        elif data.performance_vectors:
            if not all(isinstance(v, list) for v in data.performance_vectors):
                issues.append("performance_vectors must contain lists of numbers")
        
        # Valida topology_embedding
        if not isinstance(data.topology_embedding, dict):
            issues.append("topology_embedding must be a dictionary")
        
        # Valida temporal_features
        if not isinstance(data.temporal_features, dict):
            issues.append("temporal_features must be a dictionary")
        
        # Valida anomaly_indicators
        if not isinstance(data.anomaly_indicators, list):
            issues.append("anomaly_indicators must be a list")
        elif data.anomaly_indicators:
            for i, indicator in enumerate(data.anomaly_indicators):
                if not isinstance(indicator, AnomalyIndicator):
                    issues.append(f"anomaly_indicators[{i}] must be AnomalyIndicator instance")
        
        is_valid = len(issues) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            quality_score=1.0 if is_valid else max(0.0, 1.0 - len(issues) * 0.1)
        )
    
    def _create_network_context(self, snapshot: NetworkSnapshot) -> Dict[str, Any]:
        """Crea il contesto di rete per LLM"""
        topology_data = snapshot.topology
        metrics_data = snapshot.metrics
        
        # Nodi (switch) con DPID formattati
        nodes = [switch.dpid for switch in topology_data.switches]
        
        # Archi (link) con informazioni porte
        edges = []
        for link in topology_data.links:
            edges.append({
                "src": link.src_dpid,
                "dst": link.dst_dpid,
                "port_out": link.src_port,
                "port_in": link.dst_port,
                "active": link.active
            })
        
        # Dati di performance aggregati
        performance_data = self._aggregate_performance_data(metrics_data)
        
        return {
            "topology": {
                "nodes": nodes,
                "edges": edges,
                "node_count": len(nodes),
                "edge_count": len(edges)
            },
            "performance": performance_data,
            "metadata": {
                "timestamp": snapshot.timestamp,
                "collection_time": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(snapshot.timestamp))
            }
        }
    
    def _create_performance_vectors(self, metrics: MetricsData) -> List[List[float]]:
        """Crea vettori di performance per l'analisi LLM"""
        vectors = []
        
        for dpid, port_metrics_list in metrics.port_statistics.items():
            for port_metric in port_metrics_list:
                # Vettore per ogni porta: [utilizzo, errori, throughput]
                utilization = port_metric.calculate_utilization() * 100  # Percentuale
                error_rate = port_metric.calculate_error_rate()
                throughput_mb = float(port_metric.rx_bytes + port_metric.tx_bytes) / 1024 / 1024  # MB
                
                vector = [utilization, error_rate, throughput_mb]
                vectors.append(vector)
        
        return vectors
    
    def _create_topology_embedding(self, topology: TopologyData) -> Dict[str, Any]:
        """Crea embedding topologico per l'analisi grafica"""
        # Crea matrice di adiacenza
        nodes = [switch.dpid for switch in topology.switches]
        node_to_index = {node: i for i, node in enumerate(nodes)}
        
        adjacency_matrix = [[0] * len(nodes) for _ in range(len(nodes))]
        
        for link in topology.links:
            if link.src_dpid in node_to_index and link.dst_dpid in node_to_index:
                src_idx = node_to_index[link.src_dpid]
                dst_idx = node_to_index[link.dst_dpid]
                adjacency_matrix[src_idx][dst_idx] = 1
                adjacency_matrix[dst_idx][src_idx] = 1  # Grafo non diretto
        
        # Calcola metriche topologiche
        node_degrees = [sum(row) for row in adjacency_matrix]
        avg_degree = sum(node_degrees) / len(node_degrees) if node_degrees else 0
        
        return {
            "adjacency_matrix": adjacency_matrix,
            "node_degrees": node_degrees,
            "average_degree": avg_degree,
            "node_count": len(nodes),
            "edge_count": len(topology.links),
            "density": len(topology.links) / (len(nodes) * (len(nodes) - 1) / 2) if len(nodes) > 1 else 0
        }
    
    def _create_temporal_features(self, snapshot: NetworkSnapshot) -> Dict[str, Any]:
        """Crea features temporali per l'analisi LLM"""
        timestamp = snapshot.timestamp
        dt = time.localtime(timestamp)
        
        return {
            "timestamp": timestamp,
            "hour_of_day": dt.tm_hour,
            "day_of_week": dt.tm_wday,
            "day_of_month": dt.tm_mday,
            "month": dt.tm_mon,
            "is_weekend": dt.tm_wday >= 5,
            "is_business_hours": 9 <= dt.tm_hour <= 17,
            "time_features": {
                "hour_sin": np.sin(2 * np.pi * dt.tm_hour / 24),
                "hour_cos": np.cos(2 * np.pi * dt.tm_hour / 24),
                "day_sin": np.sin(2 * np.pi * dt.tm_wday / 7),
                "day_cos": np.cos(2 * np.pi * dt.tm_wday / 7)
            }
        }
    
    def _detect_anomalies(self, snapshot: NetworkSnapshot) -> List[AnomalyIndicator]:
        """Rileva anomalie nei dati di rete"""
        anomalies = []
        
        # Analizza metriche delle porte
        for dpid, port_metrics_list in snapshot.metrics.port_statistics.items():
            for port_metric in port_metrics_list:
                utilization = port_metric.calculate_utilization()
                error_rate = port_metric.calculate_error_rate()
                
                # Alta utilizzazione
                if utilization > self.anomaly_thresholds['high_utilization']:
                    anomalies.append(AnomalyIndicator(
                        type="high_utilization",
                        severity=min(1.0, utilization),
                        description=f"High utilization on port {port_metric.port_no}: {utilization*100:.1f}%",
                        affected_components=[f"{dpid}:{port_metric.port_no}"],
                        timestamp=snapshot.timestamp,
                        confidence=0.9
                    ))
                
                # Alto tasso di errori
                if error_rate > self.anomaly_thresholds['high_error_rate']:
                    anomalies.append(AnomalyIndicator(
                        type="high_error_rate",
                        severity=min(1.0, error_rate * 100),
                        description=f"High error rate on port {port_metric.port_no}: {error_rate:.3f}",
                        affected_components=[f"{dpid}:{port_metric.port_no}"],
                        timestamp=snapshot.timestamp,
                        confidence=0.95
                    ))
        
        # Analizza topologia per switch isolati
        active_switches = [s.dpid for s in snapshot.topology.switches if s.active]
        connected_switches = set()
        
        for link in snapshot.topology.links:
            if link.active:
                connected_switches.add(link.src_dpid)
                connected_switches.add(link.dst_dpid)
        
        isolated_switches = set(active_switches) - connected_switches
        
        for switch_dpid in isolated_switches:
            anomalies.append(AnomalyIndicator(
                type="isolated_switch",
                severity=0.8,
                description=f"Switch {switch_dpid} appears to be isolated",
                affected_components=[switch_dpid],
                timestamp=snapshot.timestamp,
                confidence=0.85
            ))
        
        return anomalies
    
    def _aggregate_performance_data(self, metrics: MetricsData) -> Dict[str, Any]:
        """Aggrega i dati di performance per il contesto LLM"""
        total_ports = 0
        total_utilization = 0.0
        total_errors = 0
        total_throughput = 0.0
        
        utilization_vectors = []
        error_rates = []
        congestion_indicators = []
        
        for dpid, port_metrics_list in metrics.port_statistics.items():
            for port_metric in port_metrics_list:
                utilization = port_metric.calculate_utilization()
                error_rate = port_metric.calculate_error_rate()
                
                total_ports += 1
                total_utilization += utilization * 100  # Percentuale
                total_errors += port_metric.rx_errors + port_metric.tx_errors
                total_throughput += port_metric.rx_bytes + port_metric.tx_bytes
                
                utilization_vectors.append([utilization, error_rate])
                error_rates.append(error_rate)
                congestion_indicators.append(
                    utilization > self.anomaly_thresholds['congestion_threshold']
                )
        
        return {
            "utilization_vectors": utilization_vectors,
            "error_rates": error_rates,
            "congestion_indicators": congestion_indicators,
            "aggregated_metrics": {
                "average_utilization": total_utilization / total_ports if total_ports > 0 else 0.0,
                "total_errors": total_errors,
                "total_throughput_mb": total_throughput / 1024 / 1024,
                "active_ports": total_ports
            }
        }
    
    def _compute_topology_embedding(self, topology_data: Dict[str, Any]) -> Dict[str, Any]:
        """Calcola embedding topologico avanzato"""
        adjacency_matrix = topology_data.get('adjacency_matrix', [])
        
        if not adjacency_matrix:
            return {"features": [], "dimension": 0}
        
        # Features topologiche
        features = [
            topology_data.get('average_degree', 0),
            topology_data.get('density', 0),
            topology_data.get('node_count', 0),
            topology_data.get('edge_count', 0)
        ]
        
        return {
            "features": features,
            "dimension": len(features),
            "type": "topology_structural"
        }
    
    def _compute_performance_embedding(self, performance_vectors: List[List[float]]) -> Dict[str, Any]:
        """Calcola embedding delle performance"""
        if not performance_vectors:
            return {"features": [], "dimension": 0}
        
        # Statistiche aggregate sui vettori di performance
        flattened = [val for vector in performance_vectors for val in vector]
        
        if not flattened:
            return {"features": [], "dimension": 0}
        
        features = [
            np.mean(flattened),
            np.std(flattened),
            np.min(flattened),
            np.max(flattened),
            len(performance_vectors)
        ]
        
        return {
            "features": features,
            "dimension": len(features),
            "type": "performance_statistical"
        }
    
    def _compute_temporal_embedding(self, temporal_features: Dict[str, Any]) -> Dict[str, Any]:
        """Calcola embedding temporale"""
        time_features = temporal_features.get('time_features', {})
        
        features = [
            temporal_features.get('hour_of_day', 0) / 24.0,  # Normalizzato
            temporal_features.get('day_of_week', 0) / 7.0,   # Normalizzato
            1.0 if temporal_features.get('is_weekend', False) else 0.0,
            1.0 if temporal_features.get('is_business_hours', False) else 0.0,
            time_features.get('hour_sin', 0.0),
            time_features.get('hour_cos', 0.0),
            time_features.get('day_sin', 0.0),
            time_features.get('day_cos', 0.0)
        ]
        
        return {
            "features": features,
            "dimension": len(features),
            "type": "temporal_cyclical"
        }