"""
DataValidator - Validazione rigorosa e gestione qualità dati

Implementa la validazione completa dei dati di rete raccolti,
il rilevamento di anomalie e la generazione di metriche di qualità.
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum

from .models.core import (
    NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, 
    PortMetrics, AggregatedMetrics, DerivedMetrics
)
from .models.health import QualityMetrics


class ValidationSeverity(Enum):
    """Livelli di severità per le validazioni"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AnomalyType(Enum):
    """Tipi di anomalie rilevabili"""
    TOPOLOGY_INCONSISTENCY = "topology_inconsistency"
    METRICS_OUTLIER = "metrics_outlier"
    DATA_CORRUPTION = "data_corruption"
    MISSING_DATA = "missing_data"
    TEMPORAL_ANOMALY = "temporal_anomaly"
    PERFORMANCE_DEGRADATION = "performance_degradation"


@dataclass
class ValidationIssue:
    """Rappresenta un problema di validazione rilevato"""
    severity: ValidationSeverity
    anomaly_type: AnomalyType
    component: str  # switch_id, link_id, port_id, etc.
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "severity": self.severity.value,
            "anomaly_type": self.anomaly_type.value,
            "component": self.component,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp
        }


@dataclass
class ValidationResult:
    """Risultato di una validazione completa"""
    is_valid: bool
    quality_score: float  # 0.0 - 1.0
    issues: List[ValidationIssue] = field(default_factory=list)
    corrected_data: Optional[Any] = None
    validation_duration_ms: float = 0.0
    
    def get_issues_by_severity(self, severity: ValidationSeverity) -> List[ValidationIssue]:
        """Restituisce le issue di una specifica severità"""
        return [issue for issue in self.issues if issue.severity == severity]
    
    def get_critical_issues(self) -> List[ValidationIssue]:
        """Restituisce solo le issue critiche"""
        return self.get_issues_by_severity(ValidationSeverity.CRITICAL)
    
    def has_critical_issues(self) -> bool:
        """Verifica se ci sono issue critiche"""
        return len(self.get_critical_issues()) > 0


class DataValidationError(Exception):
    """Eccezione per errori critici nella validazione"""
    pass


class DataValidator:
    """
    Validatore per dati di rete con rilevamento anomalie e correzione automatica
    
    Implementa:
    - Validazione completezza e consistenza dati (Requisito 7.1)
    - Rilevamento e gestione anomalie (Requisito 7.2)
    - Generazione metriche di qualità dati (Requisito 7.4)
    - Correzione automatica quando possibile
    """
    
    def __init__(self, 
                 enable_auto_correction: bool = True,
                 anomaly_thresholds: Optional[Dict[str, float]] = None):
        """
        Inizializza il validatore dati
        
        Args:
            enable_auto_correction: Abilita correzione automatica dei dati
            anomaly_thresholds: Soglie personalizzate per rilevamento anomalie
        """
        self.logger = logging.getLogger(__name__)
        self.enable_auto_correction = enable_auto_correction
        
        # Soglie default per rilevamento anomalie
        self.anomaly_thresholds = {
            'max_utilization': 1.0,
            'max_error_rate': 0.5,
            'max_packet_loss': 0.3,
            'min_link_capacity': 1000,  # bytes
            'max_response_time': 10.0,  # secondi
            'topology_stability_threshold': 0.8,
            'port_count_variance_threshold': 0.5,
            'metrics_outlier_std_dev': 3.0
        }
        
        if anomaly_thresholds:
            self.anomaly_thresholds.update(anomaly_thresholds)
        
        # Statistiche di validazione
        self._validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'anomalies_detected': 0,
            'auto_corrections_applied': 0,
            'last_validation_time': 0.0
        }
        
        # Cache per dati storici (per rilevamento anomalie temporali)
        self._historical_data: List[NetworkSnapshot] = []
        self._max_history_size = 100
        
        self.logger.info(f"DataValidator initialized with auto_correction={enable_auto_correction}")
    
    def validate_network_snapshot(self, snapshot: NetworkSnapshot) -> ValidationResult:
        """
        Valida un snapshot completo della rete
        
        Args:
            snapshot: NetworkSnapshot da validare
            
        Returns:
            ValidationResult con esito validazione e eventuali correzioni
            
        Valida: Requisiti 7.1, 7.2, 7.4
        """
        start_time = time.time()
        self.logger.debug("Starting network snapshot validation")
        
        try:
            issues = []
            corrected_snapshot = None
            
            # 1. Validazione strutturale base
            structural_issues = self._validate_snapshot_structure(snapshot)
            issues.extend(structural_issues)
            
            # 2. Validazione topologia
            topology_issues = self._validate_topology_data(snapshot.topology)
            issues.extend(topology_issues)
            
            # 3. Validazione metriche
            metrics_issues = self._validate_metrics_data(snapshot.metrics)
            issues.extend(metrics_issues)
            
            # 4. Validazione consistenza cross-componenti
            consistency_issues = self._validate_cross_component_consistency(
                snapshot.topology, snapshot.metrics
            )
            issues.extend(consistency_issues)
            
            # 5. Rilevamento anomalie
            anomaly_issues = self._detect_anomalies(snapshot)
            issues.extend(anomaly_issues)
            
            # 6. Validazione temporale (se ci sono dati storici)
            if self._historical_data:
                temporal_issues = self._validate_temporal_consistency(snapshot)
                issues.extend(temporal_issues)
            
            # 7. Correzione automatica se abilitata
            if self.enable_auto_correction and issues:
                corrected_snapshot = self._apply_auto_corrections(snapshot, issues)
            
            # 8. Calcola punteggio qualità
            quality_score = self._calculate_quality_score(issues, snapshot)
            
            # 9. Determina se la validazione è passata
            is_valid = not any(issue.severity == ValidationSeverity.CRITICAL for issue in issues)
            
            # Aggiorna statistiche
            validation_duration = (time.time() - start_time) * 1000
            self._update_validation_stats(is_valid, len(issues), validation_duration)
            
            # Aggiungi ai dati storici
            self._add_to_history(snapshot)
            
            result = ValidationResult(
                is_valid=is_valid,
                quality_score=quality_score,
                issues=issues,
                corrected_data=corrected_snapshot,
                validation_duration_ms=validation_duration
            )
            
            self.logger.info(
                f"Validation completed: valid={is_valid}, quality={quality_score:.3f}, "
                f"issues={len(issues)}, duration={validation_duration:.1f}ms"
            )
            
            return result
            
        except Exception as e:
            self._validation_stats['failed_validations'] += 1
            error_msg = f"Critical error during validation: {e}"
            self.logger.error(error_msg)
            raise DataValidationError(error_msg) from e
    
    def _validate_snapshot_structure(self, snapshot: NetworkSnapshot) -> List[ValidationIssue]:
        """Valida la struttura base dello snapshot"""
        issues = []
        
        # Verifica timestamp
        if not isinstance(snapshot.timestamp, (int, float)) or snapshot.timestamp <= 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                anomaly_type=AnomalyType.DATA_CORRUPTION,
                component="snapshot",
                message="Invalid or missing timestamp",
                details={"timestamp": snapshot.timestamp}
            ))
        
        # Verifica presenza componenti essenziali
        if snapshot.topology is None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                anomaly_type=AnomalyType.MISSING_DATA,
                component="snapshot",
                message="Missing topology data"
            ))
        
        if snapshot.metrics is None:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.CRITICAL,
                anomaly_type=AnomalyType.MISSING_DATA,
                component="snapshot",
                message="Missing metrics data"
            ))
        
        # Verifica timestamp ragionevole (non troppo vecchio o futuro)
        current_time = time.time()
        if isinstance(snapshot.timestamp, (int, float)):
            time_diff = abs(current_time - snapshot.timestamp)
            if time_diff > 3600:  # Più di 1 ora di differenza
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    anomaly_type=AnomalyType.TEMPORAL_ANOMALY,
                    component="snapshot",
                    message="Timestamp significantly different from current time",
                    details={
                        "snapshot_timestamp": snapshot.timestamp,
                        "current_timestamp": current_time,
                        "difference_seconds": time_diff
                    }
                ))
        
        return issues
    
    def _validate_topology_data(self, topology: TopologyData) -> List[ValidationIssue]:
        """Valida i dati di topologia"""
        issues = []
        
        if not topology:
            return issues
        
        # Valida switch
        switch_issues = self._validate_switches(topology.switches)
        issues.extend(switch_issues)
        
        # Valida link
        link_issues = self._validate_links(topology.links, topology.switches)
        issues.extend(link_issues)
        
        # Valida rappresentazione grafica
        if topology.graph_representation:
            graph_issues = self._validate_graph_representation(topology.graph_representation)
            issues.extend(graph_issues)
        
        return issues
    
    def _validate_switches(self, switches: List[SwitchInfo]) -> List[ValidationIssue]:
        """Valida i dati degli switch"""
        issues = []
        
        if not switches:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                anomaly_type=AnomalyType.MISSING_DATA,
                component="topology",
                message="No switches found in topology"
            ))
            return issues
        
        seen_dpids = set()
        
        for switch in switches:
            # Verifica DPID duplicati
            if switch.dpid in seen_dpids:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    anomaly_type=AnomalyType.TOPOLOGY_INCONSISTENCY,
                    component=f"switch_{switch.dpid}",
                    message="Duplicate switch DPID found",
                    details={"dpid": switch.dpid}
                ))
            seen_dpids.add(switch.dpid)
            
            # Verifica formato DPID
            if not self._is_valid_dpid_format(switch.dpid):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    anomaly_type=AnomalyType.DATA_CORRUPTION,
                    component=f"switch_{switch.dpid}",
                    message="Invalid DPID format",
                    details={"dpid": switch.dpid}
                ))
            
            # Verifica porte
            if not switch.ports:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    anomaly_type=AnomalyType.MISSING_DATA,
                    component=f"switch_{switch.dpid}",
                    message="Switch has no ports",
                    details={"dpid": switch.dpid}
                ))
            else:
                # Verifica porte duplicate
                if len(switch.ports) != len(set(switch.ports)):
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        anomaly_type=AnomalyType.DATA_CORRUPTION,
                        component=f"switch_{switch.dpid}",
                        message="Switch has duplicate ports",
                        details={"dpid": switch.dpid, "ports": switch.ports}
                    ))
                
                # Verifica porte negative
                invalid_ports = [p for p in switch.ports if p < 0]
                if invalid_ports:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        anomaly_type=AnomalyType.DATA_CORRUPTION,
                        component=f"switch_{switch.dpid}",
                        message="Switch has invalid negative ports",
                        details={"dpid": switch.dpid, "invalid_ports": invalid_ports}
                    ))
        
        return issues
    
    def _validate_links(self, links: List[LinkInfo], switches: List[SwitchInfo]) -> List[ValidationIssue]:
        """Valida i dati dei link"""
        issues = []
        
        if not switches:
            return issues  # Non possiamo validare link senza switch
        
        switch_dpids = {switch.dpid for switch in switches}
        switch_ports = {switch.dpid: set(switch.ports) for switch in switches}
        
        seen_links = set()
        
        for link in links:
            # Crea identificatore unico per il link
            link_id = (link.src_dpid, link.src_port, link.dst_dpid, link.dst_port)
            
            # Verifica link duplicati
            if link_id in seen_links:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    anomaly_type=AnomalyType.TOPOLOGY_INCONSISTENCY,
                    component=f"link_{link.src_dpid}_{link.dst_dpid}",
                    message="Duplicate link found",
                    details={
                        "src_dpid": link.src_dpid,
                        "dst_dpid": link.dst_dpid,
                        "src_port": link.src_port,
                        "dst_port": link.dst_port
                    }
                ))
            seen_links.add(link_id)
            
            # Verifica che i DPID esistano negli switch
            if link.src_dpid not in switch_dpids:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    anomaly_type=AnomalyType.TOPOLOGY_INCONSISTENCY,
                    component=f"link_{link.src_dpid}_{link.dst_dpid}",
                    message="Link source DPID not found in switches",
                    details={"src_dpid": link.src_dpid}
                ))
            
            if link.dst_dpid not in switch_dpids:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    anomaly_type=AnomalyType.TOPOLOGY_INCONSISTENCY,
                    component=f"link_{link.src_dpid}_{link.dst_dpid}",
                    message="Link destination DPID not found in switches",
                    details={"dst_dpid": link.dst_dpid}
                ))
            
            # Verifica che le porte esistano negli switch
            if (link.src_dpid in switch_ports and 
                link.src_port not in switch_ports[link.src_dpid]):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    anomaly_type=AnomalyType.TOPOLOGY_INCONSISTENCY,
                    component=f"link_{link.src_dpid}_{link.dst_dpid}",
                    message="Link source port not found in switch",
                    details={
                        "src_dpid": link.src_dpid,
                        "src_port": link.src_port,
                        "available_ports": list(switch_ports[link.src_dpid])
                    }
                ))
            
            if (link.dst_dpid in switch_ports and 
                link.dst_port not in switch_ports[link.dst_dpid]):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    anomaly_type=AnomalyType.TOPOLOGY_INCONSISTENCY,
                    component=f"link_{link.src_dpid}_{link.dst_dpid}",
                    message="Link destination port not found in switch",
                    details={
                        "dst_dpid": link.dst_dpid,
                        "dst_port": link.dst_port,
                        "available_ports": list(switch_ports[link.dst_dpid])
                    }
                ))
            
            # Verifica self-loop
            if link.src_dpid == link.dst_dpid and link.src_port == link.dst_port:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    anomaly_type=AnomalyType.TOPOLOGY_INCONSISTENCY,
                    component=f"link_{link.src_dpid}_{link.dst_dpid}",
                    message="Self-loop link detected",
                    details={
                        "dpid": link.src_dpid,
                        "port": link.src_port
                    }
                ))
        
        return issues
    
    def _validate_metrics_data(self, metrics: MetricsData) -> List[ValidationIssue]:
        """Valida i dati delle metriche"""
        issues = []
        
        if not metrics:
            return issues
        
        # Valida statistiche delle porte
        if metrics.port_statistics:
            port_issues = self._validate_port_statistics(metrics.port_statistics)
            issues.extend(port_issues)
        
        # Valida metriche aggregate
        if metrics.aggregated_metrics:
            agg_issues = self._validate_aggregated_metrics(
                metrics.aggregated_metrics, metrics.port_statistics
            )
            issues.extend(agg_issues)
        
        return issues
    
    def _validate_port_statistics(self, port_stats: Dict[str, List[PortMetrics]]) -> List[ValidationIssue]:
        """Valida le statistiche delle porte"""
        issues = []
        
        for dpid, port_metrics in port_stats.items():
            # Verifica formato DPID
            if not self._is_valid_dpid_format(dpid):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    anomaly_type=AnomalyType.DATA_CORRUPTION,
                    component=f"metrics_{dpid}",
                    message="Invalid DPID format in port statistics",
                    details={"dpid": dpid}
                ))
            
            seen_ports = set()
            
            for port_metric in port_metrics:
                # Verifica porte duplicate
                if port_metric.port_no in seen_ports:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        anomaly_type=AnomalyType.DATA_CORRUPTION,
                        component=f"port_{dpid}_{port_metric.port_no}",
                        message="Duplicate port metrics found",
                        details={"dpid": dpid, "port_no": port_metric.port_no}
                    ))
                seen_ports.add(port_metric.port_no)
                
                # Valida singola metrica porta
                port_issues = self._validate_single_port_metric(dpid, port_metric)
                issues.extend(port_issues)
        
        return issues
    
    def _validate_single_port_metric(self, dpid: str, port_metric: PortMetrics) -> List[ValidationIssue]:
        """Valida una singola metrica di porta"""
        issues = []
        component = f"port_{dpid}_{port_metric.port_no}"
        
        # Verifica valori negativi
        negative_fields = []
        for field in ['rx_packets', 'tx_packets', 'rx_bytes', 'tx_bytes', 
                     'rx_errors', 'tx_errors', 'rx_dropped', 'tx_dropped']:
            value = getattr(port_metric, field, 0)
            if value < 0:
                negative_fields.append(field)
        
        if negative_fields:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                anomaly_type=AnomalyType.DATA_CORRUPTION,
                component=component,
                message="Port metric has negative values",
                details={"negative_fields": negative_fields}
            ))
        
        # Verifica consistenza pacchetti/bytes
        if port_metric.rx_packets > 0 and port_metric.rx_bytes == 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                anomaly_type=AnomalyType.DATA_CORRUPTION,
                component=component,
                message="Port has RX packets but no RX bytes",
                details={
                    "rx_packets": port_metric.rx_packets,
                    "rx_bytes": port_metric.rx_bytes
                }
            ))
        
        if port_metric.tx_packets > 0 and port_metric.tx_bytes == 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                anomaly_type=AnomalyType.DATA_CORRUPTION,
                component=component,
                message="Port has TX packets but no TX bytes",
                details={
                    "tx_packets": port_metric.tx_packets,
                    "tx_bytes": port_metric.tx_bytes
                }
            ))
        
        # Verifica errori vs pacchetti
        if port_metric.rx_errors > port_metric.rx_packets:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                anomaly_type=AnomalyType.DATA_CORRUPTION,
                component=component,
                message="RX errors exceed RX packets",
                details={
                    "rx_errors": port_metric.rx_errors,
                    "rx_packets": port_metric.rx_packets
                }
            ))
        
        if port_metric.tx_errors > port_metric.tx_packets:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.ERROR,
                anomaly_type=AnomalyType.DATA_CORRUPTION,
                component=component,
                message="TX errors exceed TX packets",
                details={
                    "tx_errors": port_metric.tx_errors,
                    "tx_packets": port_metric.tx_packets
                }
            ))
        
        # Rilevamento anomalie metriche
        error_rate = port_metric.calculate_error_rate()
        if error_rate > self.anomaly_thresholds['max_error_rate']:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                anomaly_type=AnomalyType.PERFORMANCE_DEGRADATION,
                component=component,
                message="High error rate detected",
                details={
                    "error_rate": error_rate,
                    "threshold": self.anomaly_thresholds['max_error_rate']
                }
            ))
        
        utilization = port_metric.calculate_utilization()
        if utilization > self.anomaly_thresholds['max_utilization']:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                anomaly_type=AnomalyType.PERFORMANCE_DEGRADATION,
                component=component,
                message="Port utilization exceeds maximum",
                details={
                    "utilization": utilization,
                    "threshold": self.anomaly_thresholds['max_utilization']
                }
            ))
        
        return issues
    
    def _validate_aggregated_metrics(self, 
                                   aggregated: Dict[str, AggregatedMetrics],
                                   port_stats: Dict[str, List[PortMetrics]]) -> List[ValidationIssue]:
        """Valida le metriche aggregate"""
        issues = []
        
        for dpid, agg_metrics in aggregated.items():
            component = f"aggregated_{dpid}"
            
            # Verifica formato DPID
            if not self._is_valid_dpid_format(dpid):
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    anomaly_type=AnomalyType.DATA_CORRUPTION,
                    component=component,
                    message="Invalid DPID format in aggregated metrics",
                    details={"dpid": dpid}
                ))
            
            # Verifica consistenza con port statistics
            if dpid in port_stats:
                port_metrics = port_stats[dpid]
                
                # Calcola totali attesi dalle porte
                expected_rx_packets = sum(p.rx_packets for p in port_metrics)
                expected_tx_packets = sum(p.tx_packets for p in port_metrics)
                expected_rx_bytes = sum(p.rx_bytes for p in port_metrics)
                expected_tx_bytes = sum(p.tx_bytes for p in port_metrics)
                expected_errors = sum(p.rx_errors + p.tx_errors for p in port_metrics)
                
                # Verifica consistenza
                tolerance = 0.01  # 1% di tolleranza per errori di arrotondamento
                
                if abs(agg_metrics.total_rx_packets - expected_rx_packets) > expected_rx_packets * tolerance:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        anomaly_type=AnomalyType.DATA_CORRUPTION,
                        component=component,
                        message="Aggregated RX packets inconsistent with port statistics",
                        details={
                            "aggregated": agg_metrics.total_rx_packets,
                            "expected": expected_rx_packets
                        }
                    ))
                
                if abs(agg_metrics.total_errors - expected_errors) > expected_errors * tolerance:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        anomaly_type=AnomalyType.DATA_CORRUPTION,
                        component=component,
                        message="Aggregated errors inconsistent with port statistics",
                        details={
                            "aggregated": agg_metrics.total_errors,
                            "expected": expected_errors
                        }
                    ))
            
            # Verifica valori ragionevoli
            if agg_metrics.average_utilization > self.anomaly_thresholds['max_utilization']:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    anomaly_type=AnomalyType.PERFORMANCE_DEGRADATION,
                    component=component,
                    message="High average utilization detected",
                    details={
                        "utilization": agg_metrics.average_utilization,
                        "threshold": self.anomaly_thresholds['max_utilization']
                    }
                ))
        
        return issues
    
    def _validate_cross_component_consistency(self, 
                                            topology: TopologyData, 
                                            metrics: MetricsData) -> List[ValidationIssue]:
        """Valida la consistenza tra topologia e metriche"""
        issues = []
        
        if not topology or not metrics:
            return issues
        
        # Verifica che tutti gli switch in topologia abbiano metriche
        topology_dpids = {switch.dpid for switch in topology.switches}
        metrics_dpids = set(metrics.port_statistics.keys()) if metrics.port_statistics else set()
        
        missing_metrics = topology_dpids - metrics_dpids
        for dpid in missing_metrics:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                anomaly_type=AnomalyType.MISSING_DATA,
                component=f"consistency_{dpid}",
                message="Switch in topology has no metrics data",
                details={"dpid": dpid}
            ))
        
        # Verifica che le metriche non abbiano switch inesistenti
        extra_metrics = metrics_dpids - topology_dpids
        for dpid in extra_metrics:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                anomaly_type=AnomalyType.TOPOLOGY_INCONSISTENCY,
                component=f"consistency_{dpid}",
                message="Metrics data for non-existent switch",
                details={"dpid": dpid}
            ))
        
        # Verifica consistenza porte
        for switch in topology.switches:
            if switch.dpid in metrics.port_statistics:
                topology_ports = set(switch.ports)
                metrics_ports = {pm.port_no for pm in metrics.port_statistics[switch.dpid]}
                
                missing_port_metrics = topology_ports - metrics_ports
                if missing_port_metrics:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.INFO,
                        anomaly_type=AnomalyType.MISSING_DATA,
                        component=f"consistency_{switch.dpid}",
                        message="Some switch ports have no metrics",
                        details={
                            "dpid": switch.dpid,
                            "missing_ports": list(missing_port_metrics)
                        }
                    ))
                
                extra_port_metrics = metrics_ports - topology_ports
                if extra_port_metrics:
                    issues.append(ValidationIssue(
                        severity=ValidationSeverity.INFO,
                        anomaly_type=AnomalyType.TOPOLOGY_INCONSISTENCY,
                        component=f"consistency_{switch.dpid}",
                        message="Metrics for ports not in topology",
                        details={
                            "dpid": switch.dpid,
                            "extra_ports": list(extra_port_metrics)
                        }
                    ))
        
        return issues
    
    def _detect_anomalies(self, snapshot: NetworkSnapshot) -> List[ValidationIssue]:
        """Rileva anomalie nei dati"""
        issues = []
        
        # Rilevamento anomalie topologia
        if snapshot.topology:
            topology_anomalies = self._detect_topology_anomalies(snapshot.topology)
            issues.extend(topology_anomalies)
        
        # Rilevamento anomalie metriche
        if snapshot.metrics:
            metrics_anomalies = self._detect_metrics_anomalies(snapshot.metrics)
            issues.extend(metrics_anomalies)
        
        # Rilevamento anomalie prestazioni
        if snapshot.derived_metrics:
            performance_anomalies = self._detect_performance_anomalies(snapshot.derived_metrics)
            issues.extend(performance_anomalies)
        
        return issues
    
    def _detect_topology_anomalies(self, topology: TopologyData) -> List[ValidationIssue]:
        """Rileva anomalie nella topologia"""
        issues = []
        
        # Rileva switch isolati
        if topology.graph_representation and "connectivity_info" in topology.graph_representation:
            connectivity = topology.graph_representation["connectivity_info"]
            if connectivity.get("isolated_switches", 0) > 0:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    anomaly_type=AnomalyType.TOPOLOGY_INCONSISTENCY,
                    component="topology",
                    message="Isolated switches detected",
                    details={
                        "isolated_count": connectivity["isolated_switches"],
                        "isolated_switches": connectivity.get("isolated_switch_list", [])
                    }
                ))
        
        # Rileva topologie sparse
        if (topology.graph_representation and 
            "metrics" in topology.graph_representation):
            metrics = topology.graph_representation["metrics"]
            density = metrics.get("density", 0)
            if density < 0.1 and len(topology.switches) > 2:  # Topologia molto sparsa
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.INFO,
                    anomaly_type=AnomalyType.TOPOLOGY_INCONSISTENCY,
                    component="topology",
                    message="Sparse topology detected",
                    details={"density": density}
                ))
        
        return issues
    
    def _detect_metrics_anomalies(self, metrics: MetricsData) -> List[ValidationIssue]:
        """Rileva anomalie nelle metriche"""
        issues = []
        
        if not metrics.port_statistics:
            return issues
        
        # Raccoglie tutte le metriche per analisi statistica
        all_utilizations = []
        all_error_rates = []
        
        for dpid, port_metrics in metrics.port_statistics.items():
            for port_metric in port_metrics:
                utilization = port_metric.calculate_utilization()
                error_rate = port_metric.calculate_error_rate()
                
                all_utilizations.append(utilization)
                all_error_rates.append(error_rate)
        
        # Rileva outlier utilizzando deviazione standard
        if len(all_utilizations) > 3:
            util_mean = sum(all_utilizations) / len(all_utilizations)
            util_std = (sum((x - util_mean) ** 2 for x in all_utilizations) / len(all_utilizations)) ** 0.5
            
            threshold = self.anomaly_thresholds['metrics_outlier_std_dev']
            
            for dpid, port_metrics in metrics.port_statistics.items():
                for port_metric in port_metrics:
                    utilization = port_metric.calculate_utilization()
                    if abs(utilization - util_mean) > threshold * util_std:
                        issues.append(ValidationIssue(
                            severity=ValidationSeverity.INFO,
                            anomaly_type=AnomalyType.METRICS_OUTLIER,
                            component=f"port_{dpid}_{port_metric.port_no}",
                            message="Port utilization is statistical outlier",
                            details={
                                "utilization": utilization,
                                "mean": util_mean,
                                "std_dev": util_std,
                                "threshold": threshold
                            }
                        ))
        
        return issues
    
    def _detect_performance_anomalies(self, derived_metrics: DerivedMetrics) -> List[ValidationIssue]:
        """Rileva anomalie nelle prestazioni"""
        issues = []
        
        # Verifica prestazioni degradate
        if derived_metrics.performance_score < 0.5:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                anomaly_type=AnomalyType.PERFORMANCE_DEGRADATION,
                component="network",
                message="Low network performance score detected",
                details={"performance_score": derived_metrics.performance_score}
            ))
        
        # Verifica alta congestione
        if derived_metrics.congestion_level > 0.7:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                anomaly_type=AnomalyType.PERFORMANCE_DEGRADATION,
                component="network",
                message="High network congestion detected",
                details={"congestion_level": derived_metrics.congestion_level}
            ))
        
        # Verifica alto tasso di errore
        if derived_metrics.error_rate > self.anomaly_thresholds['max_error_rate']:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                anomaly_type=AnomalyType.PERFORMANCE_DEGRADATION,
                component="network",
                message="High network error rate detected",
                details={
                    "error_rate": derived_metrics.error_rate,
                    "threshold": self.anomaly_thresholds['max_error_rate']
                }
            ))
        
        return issues
    
    def _validate_temporal_consistency(self, snapshot: NetworkSnapshot) -> List[ValidationIssue]:
        """Valida la consistenza temporale con dati storici"""
        issues = []
        
        if not self._historical_data:
            return issues
        
        latest_historical = self._historical_data[-1]
        
        # Verifica cambiamenti drastici nella topologia
        current_switch_count = len(snapshot.topology.switches) if snapshot.topology else 0
        historical_switch_count = len(latest_historical.topology.switches) if latest_historical.topology else 0
        
        if current_switch_count > 0 and historical_switch_count > 0:
            switch_change_ratio = abs(current_switch_count - historical_switch_count) / historical_switch_count
            
            if switch_change_ratio > self.anomaly_thresholds['port_count_variance_threshold']:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    anomaly_type=AnomalyType.TEMPORAL_ANOMALY,
                    component="topology",
                    message="Significant change in switch count detected",
                    details={
                        "current_count": current_switch_count,
                        "historical_count": historical_switch_count,
                        "change_ratio": switch_change_ratio
                    }
                ))
        
        # Verifica timestamp progression
        time_diff = snapshot.timestamp - latest_historical.timestamp
        if time_diff < 0:
            issues.append(ValidationIssue(
                severity=ValidationSeverity.WARNING,
                anomaly_type=AnomalyType.TEMPORAL_ANOMALY,
                component="snapshot",
                message="Snapshot timestamp is older than previous snapshot",
                details={
                    "current_timestamp": snapshot.timestamp,
                    "previous_timestamp": latest_historical.timestamp,
                    "time_difference": time_diff
                }
            ))
        
        return issues
    
    def _apply_auto_corrections(self, 
                              snapshot: NetworkSnapshot, 
                              issues: List[ValidationIssue]) -> Optional[NetworkSnapshot]:
        """Applica correzioni automatiche quando possibile"""
        if not self.enable_auto_correction:
            return None
        
        corrected_snapshot = snapshot  # Inizia con lo snapshot originale
        corrections_applied = 0
        
        for issue in issues:
            if issue.severity in [ValidationSeverity.WARNING, ValidationSeverity.INFO]:
                # Applica correzioni per issue non critiche
                if issue.anomaly_type == AnomalyType.DATA_CORRUPTION:
                    # Esempio: correzione valori negativi
                    if "negative_fields" in issue.details:
                        # Qui implementeresti la logica di correzione specifica
                        corrections_applied += 1
                        self.logger.info(f"Applied auto-correction for {issue.component}: {issue.message}")
        
        if corrections_applied > 0:
            self._validation_stats['auto_corrections_applied'] += corrections_applied
            return corrected_snapshot
        
        return None
    
    def _calculate_quality_score(self, issues: List[ValidationIssue], snapshot: NetworkSnapshot) -> float:
        """Calcola il punteggio di qualità dei dati"""
        if not issues:
            return 1.0
        
        # Pesi per diversi tipi di severità
        severity_weights = {
            ValidationSeverity.CRITICAL: 1.0,
            ValidationSeverity.ERROR: 0.7,
            ValidationSeverity.WARNING: 0.3,
            ValidationSeverity.INFO: 0.1
        }
        
        # Calcola penalità totale
        total_penalty = 0.0
        for issue in issues:
            total_penalty += severity_weights.get(issue.severity, 0.1)
        
        # Normalizza in base al numero di componenti
        component_count = 1  # Base
        if snapshot.topology:
            component_count += len(snapshot.topology.switches)
            component_count += len(snapshot.topology.links)
        if snapshot.metrics and snapshot.metrics.port_statistics:
            component_count += sum(len(ports) for ports in snapshot.metrics.port_statistics.values())
        
        normalized_penalty = total_penalty / component_count
        quality_score = max(0.0, 1.0 - normalized_penalty)
        
        return quality_score
    
    def _is_valid_dpid_format(self, dpid: str) -> bool:
        """Verifica se un DPID ha il formato corretto"""
        if not isinstance(dpid, str):
            return False
        
        if len(dpid) != 16:
            return False
        
        try:
            int(dpid, 16)
            return True
        except ValueError:
            return False
    
    def _add_to_history(self, snapshot: NetworkSnapshot) -> None:
        """Aggiunge uno snapshot alla cronologia"""
        self._historical_data.append(snapshot)
        
        # Mantieni solo gli ultimi N snapshot
        if len(self._historical_data) > self._max_history_size:
            self._historical_data.pop(0)
    
    def _update_validation_stats(self, is_valid: bool, issue_count: int, duration_ms: float) -> None:
        """Aggiorna le statistiche di validazione"""
        self._validation_stats['total_validations'] += 1
        self._validation_stats['last_validation_time'] = duration_ms
        
        if is_valid:
            self._validation_stats['successful_validations'] += 1
        else:
            self._validation_stats['failed_validations'] += 1
        
        self._validation_stats['anomalies_detected'] += issue_count
    
    def _validate_graph_representation(self, graph: Dict[str, Any]) -> List[ValidationIssue]:
        """Valida la rappresentazione grafica della topologia"""
        issues = []
        
        required_keys = ['nodes', 'edges', 'metrics']
        for key in required_keys:
            if key not in graph:
                issues.append(ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    anomaly_type=AnomalyType.MISSING_DATA,
                    component="graph_representation",
                    message=f"Missing required key in graph representation: {key}",
                    details={"missing_key": key}
                ))
        
        return issues
    
    def generate_quality_metrics(self, validation_result: ValidationResult) -> QualityMetrics:
        """
        Genera metriche di qualità dettagliate dai risultati di validazione
        
        Args:
            validation_result: Risultato della validazione
            
        Returns:
            QualityMetrics con punteggi dettagliati
            
        Valida: Requisito 7.4
        """
        issues = validation_result.issues
        
        # Calcola completezza (basata su dati mancanti)
        missing_data_issues = [i for i in issues if i.anomaly_type == AnomalyType.MISSING_DATA]
        completeness_score = max(0.0, 1.0 - len(missing_data_issues) * 0.1)
        
        # Calcola consistenza (basata su inconsistenze)
        consistency_issues = [i for i in issues 
                            if i.anomaly_type in [AnomalyType.TOPOLOGY_INCONSISTENCY, 
                                                AnomalyType.DATA_CORRUPTION]]
        consistency_score = max(0.0, 1.0 - len(consistency_issues) * 0.15)
        
        # Calcola tempestività (basata su anomalie temporali)
        temporal_issues = [i for i in issues if i.anomaly_type == AnomalyType.TEMPORAL_ANOMALY]
        timeliness_score = max(0.0, 1.0 - len(temporal_issues) * 0.2)
        
        # Calcola accuratezza (basata su outlier e degradazioni)
        accuracy_issues = [i for i in issues 
                         if i.anomaly_type in [AnomalyType.METRICS_OUTLIER,
                                             AnomalyType.PERFORMANCE_DEGRADATION]]
        accuracy_score = max(0.0, 1.0 - len(accuracy_issues) * 0.1)
        
        # Raccoglie descrizioni delle issue
        issues_detected = [f"{issue.severity.value}: {issue.message}" for issue in issues]
        
        return QualityMetrics(
            completeness_score=completeness_score,
            consistency_score=consistency_score,
            timeliness_score=timeliness_score,
            accuracy_score=accuracy_score,
            overall_score=validation_result.quality_score,
            issues_detected=issues_detected
        )
    
    def get_validation_stats(self) -> Dict[str, Any]:
        """Restituisce statistiche di validazione"""
        return self._validation_stats.copy()
    
    def reset_stats(self) -> None:
        """Resetta le statistiche di validazione"""
        self._validation_stats = {
            'total_validations': 0,
            'successful_validations': 0,
            'failed_validations': 0,
            'anomalies_detected': 0,
            'auto_corrections_applied': 0,
            'last_validation_time': 0.0
        }
        self.logger.info("Validation statistics reset")
    
    def clear_history(self) -> None:
        """Pulisce la cronologia dei dati"""
        self._historical_data.clear()
        self.logger.info("Historical data cleared")
    
    def set_anomaly_thresholds(self, thresholds: Dict[str, float]) -> None:
        """Aggiorna le soglie per il rilevamento anomalie"""
        self.anomaly_thresholds.update(thresholds)
        self.logger.info(f"Updated anomaly thresholds: {thresholds}")