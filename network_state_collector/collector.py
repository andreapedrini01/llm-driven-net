"""
NetworkStateCollector - Classe principale del sistema

Integra tutti i componenti per la raccolta, elaborazione e salvataggio
dei dati di stato della rete per l'integrazione con modelli LLM.
"""

import time
import logging
import threading
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path

from .models.config import CollectorConfig
from .models.core import NetworkSnapshot, TopologyData, MetricsData, SwitchInfo
from .models.health import SystemHealth, HealthCheck, HealthStatus, ComponentType
from .configuration_manager import ConfigurationManager
from .ryu_connector import RyuConnector
from .data_processor import DataProcessor
from .data_validator import DataValidator
from .llm_integrator import LLMIntegrator
from .json_serializer import JSONSerializer
from .filesystem_manager import FileSystemManager, FileSystemConfig
from .error_manager import ErrorManager, ErrorCategory, ErrorSeverity
from .logging_manager import LoggingManager
from .performance_monitor import PerformanceMonitor, PerformanceTimer


class NetworkStateCollector:
    """
    Classe principale del Network State Collector
    
    Integra tutti i componenti per:
    - Raccolta dati dal controller Ryu
    - Elaborazione e validazione dati
    - Conversione per integrazione LLM
    - Salvataggio su file system
    - Gestione errori e logging
    """
    
    def __init__(self, config_path: Optional[str] = None, environment: str = "development"):
        """
        Inizializza il Network State Collector
        
        Args:
            config_path: Path del file di configurazione
            environment: Ambiente di esecuzione
        """
        # Inizializza logging manager per primo
        self.logging_manager = LoggingManager()
        self.logger = logging.getLogger(__name__)
        
        # Carica configurazione
        self.config_manager = ConfigurationManager()
        self.config = self._load_configuration(config_path, environment)
        
        # Inizializza componenti
        self.error_manager = ErrorManager()
        self.ryu_connector = RyuConnector(
            ryu_config=self.config.ryu,
            retry_config=self.config.retry
        )
        self.data_processor = DataProcessor()
        self.data_validator = DataValidator()
        self.llm_integrator = LLMIntegrator()
        self.json_serializer = JSONSerializer(
            pretty_print=self.config.output.pretty_print
        )
        # Crea configurazione filesystem
        fs_config = FileSystemConfig(
            base_output_dir=self.config.output.directory,
            llm_output_dir="history",
            history_dir=self.config.output.history_directory,
            max_history_files=self.config.output.max_history_files,
            enable_compression=self.config.output.compress_old_files
        )
        self.filesystem_manager = FileSystemManager(fs_config)
        
        # Performance monitoring
        self.performance_monitor = PerformanceMonitor(history_size=1000)
        
        # Stato interno
        self._is_collecting = False
        self._collection_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._last_snapshot: Optional[NetworkSnapshot] = None
        self._last_topology_hash: Optional[str] = None
        self._collection_stats = {
            "total_snapshots": 0,
            "successful_snapshots": 0,
            "failed_snapshots": 0,
            "last_collection_time": None,
            "average_collection_time": 0.0
        }
        
        self.logger.info("NetworkStateCollector initialized successfully")
    
    def collect_snapshot(self) -> Optional[NetworkSnapshot]:
        """
        Raccoglie un singolo snapshot dello stato della rete
        
        Returns:
            NetworkSnapshot: Snapshot raccolto o None in caso di errore
        """
        with PerformanceTimer(self.performance_monitor, "collect_snapshot"):
            start_time = time.time()
            
            try:
                self.logger.info("Starting network state collection...")
                
                # 1. Raccolta dati dal controller Ryu
                with PerformanceTimer(self.performance_monitor, "collect_raw_data"):
                    switches, links, port_stats = self._collect_raw_data()
                
                if not switches:
                    self.logger.warning("No switches found, skipping snapshot")
                    return None
                
                # 2. Elaborazione dati
                with PerformanceTimer(self.performance_monitor, "process_data"):
                    topology_data = self.data_processor.process_topology(switches, links)
                    metrics_data = self.data_processor.process_metrics(port_stats)
                
                # 3. Creazione snapshot temporaneo per validazione
                timestamp = time.time()
                temp_snapshot = NetworkSnapshot(
                    timestamp=timestamp,
                    topology=topology_data,
                    metrics=metrics_data,
                    metadata={
                        "collection_time": time.time() - start_time,
                        "environment": self.config.environment,
                        "version": self.config.version,
                        "switches_count": len(switches),
                        "links_count": len(links),
                        "ports_count": sum(len(stats) for stats in port_stats.values())
                    }
                )
                
                # 4. Validazione dati
                if self.config.collection.validate_data:
                    with PerformanceTimer(self.performance_monitor, "validate_data"):
                        validation_result = self.data_validator.validate_network_snapshot(temp_snapshot)
                    
                    if not validation_result.is_valid:
                        self.logger.error("Data validation failed, skipping snapshot")
                        self._collection_stats["failed_snapshots"] += 1
                        return None
                
                # 5. Usa lo snapshot già creato
                snapshot = temp_snapshot
                
                # 6. Conversione per LLM
                with PerformanceTimer(self.performance_monitor, "format_for_llm"):
                    llm_data = self.llm_integrator.format_for_llm(snapshot)
                
                # 7. Serializzazione e salvataggio
                with PerformanceTimer(self.performance_monitor, "save_snapshot"):
                    self._save_snapshot(snapshot, llm_data)
                
                # 8. Aggiornamento statistiche
                collection_time = time.time() - start_time
                self._update_collection_stats(collection_time, success=True)
                self._last_snapshot = snapshot
                
                self.logger.info(f"Network snapshot collected successfully in {collection_time:.2f}s")
                return snapshot
                
            except Exception as e:
                collection_time = time.time() - start_time
                self._update_collection_stats(collection_time, success=False)
                
                self.error_manager.handle_error(
                    e,
                    ErrorCategory.PROCESSING,
                    ErrorSeverity.HIGH,
                    "NetworkStateCollector",
                    {"operation": "collect_snapshot", "collection_time": collection_time}
                )
                
                self.logger.error(f"Failed to collect network snapshot: {e}")
                return None
    
    def start_continuous_collection(self, interval: Optional[float] = None) -> None:
        """
        Avvia la raccolta continua dei dati
        
        Args:
            interval: Intervallo di raccolta in secondi (usa configurazione se None)
        """
        if self._is_collecting:
            self.logger.warning("Continuous collection already running")
            return
        
        collection_interval = interval or self.config.collection.interval
        self.logger.info(f"Starting continuous collection with interval {collection_interval}s")
        
        self._is_collecting = True
        self._stop_event.clear()
        
        self._collection_thread = threading.Thread(
            target=self._collection_loop,
            args=(collection_interval,),
            daemon=True,
            name="NetworkStateCollector"
        )
        self._collection_thread.start()
    
    def stop_collection(self) -> None:
        """Ferma la raccolta continua dei dati"""
        if not self._is_collecting:
            self.logger.warning("Continuous collection not running")
            return
        
        self.logger.info("Stopping continuous collection...")
        self._is_collecting = False
        self._stop_event.set()
        
        if self._collection_thread and self._collection_thread.is_alive():
            self._collection_thread.join(timeout=10.0)
            if self._collection_thread.is_alive():
                self.logger.warning("Collection thread did not stop gracefully")
        
        self.logger.info("Continuous collection stopped")
    
    def get_health_status(self) -> SystemHealth:
        """
        Restituisce lo stato di salute del collector
        
        Returns:
            SystemHealth: Stato di salute del sistema
        """
        # Verifica salute dei componenti
        ryu_healthy = self.ryu_connector.is_healthy()
        filesystem_healthy = self.filesystem_manager.get_storage_stats()["available_space"] > 100 * 1024 * 1024  # 100MB
        
        # Crea health checks per i componenti
        system_health = SystemHealth(overall_status=HealthStatus.HEALTHY)
        
        # Health check Ryu Connector
        ryu_status = HealthStatus.HEALTHY if ryu_healthy else HealthStatus.UNHEALTHY
        ryu_check = HealthCheck(
            component=ComponentType.RYU_CONNECTOR,
            status=ryu_status,
            message="Ryu connector is healthy" if ryu_healthy else "Ryu connector is unhealthy",
            details={"is_healthy": ryu_healthy}
        )
        system_health.add_component_check(ryu_check)
        
        # Health check File System
        fs_status = HealthStatus.HEALTHY if filesystem_healthy else HealthStatus.DEGRADED
        fs_check = HealthCheck(
            component=ComponentType.FILE_SYSTEM,
            status=fs_status,
            message="File system is healthy" if filesystem_healthy else "File system has low space",
            details={
                "available_space": self.filesystem_manager.get_storage_stats()["available_space"],
                "is_healthy": filesystem_healthy
            }
        )
        system_health.add_component_check(fs_check)
        
        # Aggiungi dettagli aggiuntivi
        system_health.last_update = time.time()
        
        return system_health
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """
        Restituisce le statistiche di raccolta
        
        Returns:
            Dict: Statistiche di raccolta
        """
        stats = self._collection_stats.copy()
        stats["is_collecting"] = self._is_collecting
        stats["last_snapshot"] = self._last_snapshot.timestamp if self._last_snapshot else None
        return stats
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """
        Restituisce le metriche di performance dettagliate
        
        Returns:
            Dict: Metriche di performance
        """
        return self.performance_monitor.get_all_stats()
    
    def print_performance_summary(self) -> None:
        """Stampa un riepilogo delle performance"""
        self.performance_monitor.print_summary()

    def reload_configuration(self) -> bool:
        """
        Ricarica la configurazione se modificata
        
        Returns:
            bool: True se la configurazione è stata ricaricata
        """
        try:
            reloaded = self.config_manager.reload_config()
            if reloaded:
                self.config = self.config_manager.get_current_config()
                self.logger.info("Configuration reloaded successfully")
            return reloaded
        except Exception as e:
            self.logger.error(f"Failed to reload configuration: {e}")
            return False
    
    def _load_configuration(self, config_path: Optional[str], environment: str) -> CollectorConfig:
        """Carica la configurazione"""
        try:
            return self.config_manager.load_config(config_path, environment)
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            # Usa configurazione di default in caso di errore
            return CollectorConfig()
    
    def _collect_raw_data(self) -> tuple:
        """Raccoglie i dati grezzi dal controller Ryu"""
        switches = []
        links = []
        port_stats = {}
        
        try:
            # Raccolta switches
            switches = self.ryu_connector.get_switches()
            self.logger.debug(f"Collected {len(switches)} switches")
            
            # Raccolta links
            links = self.ryu_connector.get_links()
            self.logger.debug(f"Collected {len(links)} links")
            
            # Raccolta statistiche porte
            if self.config.collection.parallel_collection:
                port_stats = self._collect_port_stats_parallel(switches)
            else:
                port_stats = self._collect_port_stats_sequential(switches)
            
            total_ports = sum(len(stats) for stats in port_stats.values())
            self.logger.debug(f"Collected statistics for {total_ports} ports")
            
        except Exception as e:
            self.logger.error(f"Error collecting raw data: {e}")
            # Re-raise l'eccezione per contarla come fallimento
            raise
        
        return switches, links, port_stats
    
    def _collect_port_stats_sequential(self, switches: List[SwitchInfo]) -> Dict[str, List[Dict[str, Any]]]:
        """Raccoglie statistiche porte in modo sequenziale"""
        port_stats = {}
        
        for switch in switches:
            dpid = switch.dpid
            try:
                stats = self.ryu_connector.get_port_stats(dpid)
                if stats:
                    port_stats[dpid] = stats
            except Exception as e:
                self.logger.warning(f"Failed to get port stats for switch {dpid}: {e}")
                # Continua con gli altri switch
        
        return port_stats
    
    def _collect_port_stats_parallel(self, switches: List[SwitchInfo]) -> Dict[str, List[Dict[str, Any]]]:
        """Raccoglie statistiche porte in parallelo"""
        import concurrent.futures
        
        port_stats = {}
        
        # Se non ci sono switch, ritorna dizionario vuoto
        if not switches:
            return port_stats
        
        max_workers = min(self.config.collection.max_workers, len(switches))
        
        def collect_switch_stats(switch):
            dpid = switch.dpid
            try:
                stats = self.ryu_connector.get_port_stats(dpid)
                return dpid, stats
            except Exception as e:
                self.logger.warning(f"Failed to get port stats for switch {dpid}: {e}")
                return dpid, []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_switch = {executor.submit(collect_switch_stats, switch): switch for switch in switches}
            
            for future in concurrent.futures.as_completed(future_to_switch):
                try:
                    dpid, stats = future.result()
                    if stats:
                        port_stats[dpid] = stats
                except Exception as e:
                    switch = future_to_switch[future]
                    dpid = switch.dpid
                    self.logger.warning(f"Exception collecting stats for switch {dpid}: {e}")
        
        return port_stats
    
    def _save_snapshot(self, snapshot: NetworkSnapshot, llm_data) -> None:
        """Salva lo snapshot su file system"""
        try:
            # Serializza snapshot completo
            snapshot_json = self.json_serializer.serialize_network_snapshot(snapshot)
            
            # Salva file principale
            main_file = self.filesystem_manager.save_network_context(
                snapshot_json,
                timestamp=snapshot.timestamp
            )
            
            # Salva file latest
            latest_file = self.filesystem_manager.save_latest_context(snapshot_json)
            
            # Salva dati LLM (passa l'oggetto LLMNetworkData, non JSON)
            llm_file = self.filesystem_manager.save_llm_data(llm_data)
            
            self.logger.debug(f"Snapshot saved to: {main_file}, {latest_file}, {llm_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save snapshot: {e}")
            raise
    
    def _collection_loop(self, interval: float) -> None:
        """Loop principale per la raccolta continua"""
        self.logger.info(f"Collection loop started with interval {interval}s")
        
        while self._is_collecting and not self._stop_event.is_set():
            try:
                # Raccoglie snapshot
                snapshot = self.collect_snapshot()
                
                # Verifica cambiamenti topologia se richiesto
                if snapshot and self.config.collection.detect_topology_changes:
                    self._check_topology_changes(snapshot)
                
            except Exception as e:
                self.logger.error(f"Error in collection loop: {e}")
            
            # Attende prossima iterazione
            if self._stop_event.wait(interval):
                break  # Stop event è stato settato
        
        self.logger.info("Collection loop ended")
    
    def _check_topology_changes(self, snapshot: NetworkSnapshot) -> None:
        """Verifica cambiamenti nella topologia"""
        try:
            # Calcola hash della topologia corrente
            topology_hash = self._calculate_topology_hash(snapshot.topology)
            
            # Confronta con hash precedente
            if self._last_topology_hash and topology_hash != self._last_topology_hash:
                self.logger.info("Topology change detected, triggering immediate collection")
                # Potrebbe triggerare azioni aggiuntive qui
            
            self._last_topology_hash = topology_hash
            
        except Exception as e:
            self.logger.warning(f"Error checking topology changes: {e}")
    
    def _calculate_topology_hash(self, topology: TopologyData) -> str:
        """Calcola hash della topologia per rilevare cambiamenti"""
        import hashlib
        
        # Crea stringa rappresentativa della topologia
        switches_str = ",".join(sorted(switch["dpid"] for switch in topology.switches))
        links_str = ",".join(sorted(f"{link['src']}-{link['dst']}" for link in topology.links))
        topology_str = f"switches:{switches_str}|links:{links_str}"
        
        return hashlib.md5(topology_str.encode()).hexdigest()
    
    def _update_collection_stats(self, collection_time: float, success: bool) -> None:
        """Aggiorna le statistiche di raccolta"""
        self._collection_stats["total_snapshots"] += 1
        self._collection_stats["last_collection_time"] = time.time()
        
        if success:
            self._collection_stats["successful_snapshots"] += 1
            
            # Calcola tempo medio di raccolta solo per i successi
            total_successful = self._collection_stats["successful_snapshots"]
            current_avg = self._collection_stats["average_collection_time"]
            self._collection_stats["average_collection_time"] = (
                (current_avg * (total_successful - 1) + collection_time) / total_successful
            )
        else:
            self._collection_stats["failed_snapshots"] += 1
    
    def __enter__(self):
        """Context manager entry"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self._is_collecting:
            self.stop_collection()
        
        # Cleanup risorse se necessario
        self.logger.info("NetworkStateCollector context exited")