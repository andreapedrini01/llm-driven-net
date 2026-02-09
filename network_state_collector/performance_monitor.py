"""
Performance Monitor - Monitoraggio prestazioni del collector

Traccia metriche di performance per ottimizzazione e debugging.
"""

import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque


@dataclass
class PerformanceMetrics:
    """Metriche di performance per una singola operazione"""
    operation: str
    duration_ms: float
    timestamp: float
    success: bool
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class PerformanceMonitor:
    """
    Monitora le prestazioni del collector
    
    Traccia:
    - Tempi di esecuzione operazioni
    - Throughput (snapshot/secondo)
    - Latenza media/min/max
    - Errori e retry
    - Utilizzo risorse
    """
    
    def __init__(self, history_size: int = 1000):
        """
        Inizializza il monitor
        
        Args:
            history_size: Numero di metriche da mantenere in memoria
        """
        self.logger = logging.getLogger(__name__)
        self.history_size = history_size
        
        # Metriche per operazione
        self._metrics: Dict[str, deque] = {}
        
        # Statistiche aggregate
        self._stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "start_time": time.time()
        }
        
        self.logger.info("PerformanceMonitor initialized")
    
    def record_operation(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        error_message: Optional[str] = None,
        **metadata
    ) -> None:
        """
        Registra una metrica di performance
        
        Args:
            operation: Nome dell'operazione
            duration_ms: Durata in millisecondi
            success: Se l'operazione è riuscita
            error_message: Messaggio di errore (se fallita)
            **metadata: Metadati aggiuntivi
        """
        metric = PerformanceMetrics(
            operation=operation,
            duration_ms=duration_ms,
            timestamp=time.time(),
            success=success,
            error_message=error_message,
            metadata=metadata
        )
        
        # Aggiungi alla history
        if operation not in self._metrics:
            self._metrics[operation] = deque(maxlen=self.history_size)
        
        self._metrics[operation].append(metric)
        
        # Aggiorna statistiche
        self._stats["total_operations"] += 1
        if success:
            self._stats["successful_operations"] += 1
        else:
            self._stats["failed_operations"] += 1
    
    def get_operation_stats(self, operation: str) -> Dict[str, Any]:
        """
        Ottiene statistiche per una specifica operazione
        
        Args:
            operation: Nome dell'operazione
            
        Returns:
            Dizionario con statistiche
        """
        if operation not in self._metrics or not self._metrics[operation]:
            return {
                "operation": operation,
                "count": 0,
                "avg_duration_ms": 0.0,
                "min_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "success_rate": 0.0
            }
        
        metrics = list(self._metrics[operation])
        durations = [m.duration_ms for m in metrics]
        successes = sum(1 for m in metrics if m.success)
        
        return {
            "operation": operation,
            "count": len(metrics),
            "avg_duration_ms": sum(durations) / len(durations),
            "min_duration_ms": min(durations),
            "max_duration_ms": max(durations),
            "p50_duration_ms": self._percentile(durations, 50),
            "p95_duration_ms": self._percentile(durations, 95),
            "p99_duration_ms": self._percentile(durations, 99),
            "success_rate": (successes / len(metrics)) * 100,
            "total_successes": successes,
            "total_failures": len(metrics) - successes
        }
    
    def get_all_stats(self) -> Dict[str, Any]:
        """
        Ottiene tutte le statistiche aggregate
        
        Returns:
            Dizionario con tutte le statistiche
        """
        uptime_seconds = time.time() - self._stats["start_time"]
        
        operations_stats = {}
        for operation in self._metrics.keys():
            operations_stats[operation] = self.get_operation_stats(operation)
        
        return {
            "uptime_seconds": uptime_seconds,
            "uptime_formatted": self._format_duration(uptime_seconds),
            "total_operations": self._stats["total_operations"],
            "successful_operations": self._stats["successful_operations"],
            "failed_operations": self._stats["failed_operations"],
            "success_rate": (
                (self._stats["successful_operations"] / self._stats["total_operations"]) * 100
                if self._stats["total_operations"] > 0 else 0.0
            ),
            "operations_per_second": (
                self._stats["total_operations"] / uptime_seconds
                if uptime_seconds > 0 else 0.0
            ),
            "operations": operations_stats
        }
    
    def get_recent_metrics(
        self,
        operation: Optional[str] = None,
        limit: int = 10
    ) -> List[PerformanceMetrics]:
        """
        Ottiene le metriche più recenti
        
        Args:
            operation: Filtra per operazione (None = tutte)
            limit: Numero massimo di metriche
            
        Returns:
            Lista di metriche
        """
        if operation:
            if operation not in self._metrics:
                return []
            return list(self._metrics[operation])[-limit:]
        
        # Tutte le operazioni
        all_metrics = []
        for metrics in self._metrics.values():
            all_metrics.extend(metrics)
        
        # Ordina per timestamp e prendi le più recenti
        all_metrics.sort(key=lambda m: m.timestamp, reverse=True)
        return all_metrics[:limit]
    
    def get_slow_operations(
        self,
        threshold_ms: float = 1000.0,
        limit: int = 10
    ) -> List[PerformanceMetrics]:
        """
        Ottiene le operazioni più lente
        
        Args:
            threshold_ms: Soglia in millisecondi
            limit: Numero massimo di risultati
            
        Returns:
            Lista di operazioni lente
        """
        slow_ops = []
        
        for metrics in self._metrics.values():
            for metric in metrics:
                if metric.duration_ms >= threshold_ms:
                    slow_ops.append(metric)
        
        # Ordina per durata decrescente
        slow_ops.sort(key=lambda m: m.duration_ms, reverse=True)
        return slow_ops[:limit]
    
    def reset_stats(self) -> None:
        """Reset di tutte le statistiche"""
        self._metrics.clear()
        self._stats = {
            "total_operations": 0,
            "successful_operations": 0,
            "failed_operations": 0,
            "start_time": time.time()
        }
        self.logger.info("Performance stats reset")
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calcola il percentile di una lista di valori"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index]
    
    def _format_duration(self, seconds: float) -> str:
        """Formatta una durata in formato leggibile"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    def print_summary(self) -> None:
        """Stampa un riepilogo delle metriche"""
        stats = self.get_all_stats()
        
        print("\n" + "="*60)
        print("  Performance Monitor Summary")
        print("="*60)
        print(f"\nUptime: {stats['uptime_formatted']}")
        print(f"Total Operations: {stats['total_operations']}")
        print(f"Success Rate: {stats['success_rate']:.1f}%")
        print(f"Operations/sec: {stats['operations_per_second']:.2f}")
        
        print("\nPer-Operation Stats:")
        print("-" * 60)
        
        for op_name, op_stats in stats['operations'].items():
            print(f"\n{op_name}:")
            print(f"  Count: {op_stats['count']}")
            print(f"  Avg: {op_stats['avg_duration_ms']:.2f}ms")
            print(f"  Min: {op_stats['min_duration_ms']:.2f}ms")
            print(f"  Max: {op_stats['max_duration_ms']:.2f}ms")
            print(f"  P95: {op_stats['p95_duration_ms']:.2f}ms")
            print(f"  Success Rate: {op_stats['success_rate']:.1f}%")
        
        print("\n" + "="*60 + "\n")


class PerformanceTimer:
    """Context manager per misurare il tempo di esecuzione"""
    
    def __init__(
        self,
        monitor: PerformanceMonitor,
        operation: str,
        **metadata
    ):
        """
        Inizializza il timer
        
        Args:
            monitor: PerformanceMonitor da usare
            operation: Nome dell'operazione
            **metadata: Metadati aggiuntivi
        """
        self.monitor = monitor
        self.operation = operation
        self.metadata = metadata
        self.start_time = None
        self.success = True
        self.error_message = None
    
    def __enter__(self):
        """Avvia il timer"""
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ferma il timer e registra la metrica"""
        duration_ms = (time.time() - self.start_time) * 1000
        
        if exc_type is not None:
            self.success = False
            self.error_message = str(exc_val)
        
        self.monitor.record_operation(
            operation=self.operation,
            duration_ms=duration_ms,
            success=self.success,
            error_message=self.error_message,
            **self.metadata
        )
        
        # Non sopprimere l'eccezione
        return False
    
    def mark_failed(self, error_message: str) -> None:
        """Marca l'operazione come fallita"""
        self.success = False
        self.error_message = error_message
