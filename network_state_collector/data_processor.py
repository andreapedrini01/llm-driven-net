"""
DataProcessor - Elaborazione e trasformazione dati di rete

Implementa l'elaborazione dei dati grezzi ricevuti dal RyuConnector
convertendoli in strutture dati standardizzate per l'integrazione LLM.
"""

import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from src.models.core import (
    TopologyData, SwitchInfo, LinkInfo, MetricsData, PortMetrics, 
    AggregatedMetrics, DerivedMetrics
)
from src.models.health import QualityMetrics


class DataProcessingError(Exception):
    """Eccezione per errori nell'elaborazione dati"""
    pass


class DataProcessor:
    """
    Processore per l'elaborazione e trasformazione dati di rete
    
    Converte i dati grezzi ricevuti dal RyuConnector in strutture dati
    standardizzate (TopologyData, MetricsData) con formattazione consistente
    dei DPID e validazione dei dati.
    """
    
    def __init__(self):
        """Inizializza il processore dati"""
        self.logger = logging.getLogger(__name__)
        self._processing_stats = {
            'topology_processed': 0,
            'metrics_processed': 0,
            'errors_encountered': 0,
            'last_processing_time': 0.0
        }
        
        self.logger.info("DataProcessor initialized")
    
    def process_topology(self, switches: List[SwitchInfo], links: List[LinkInfo]) -> TopologyData:
        """
        Converte dati grezzi di topologia in TopologyData strutturata
        
        Implementa:
        - Formattazione consistente DPID (esadecimale a 16 cifre)
        - Validazione completezza dati switch e link
        - Creazione rappresentazione grafica della topologia
        - Gestione errori con continuazione operativa
        
        Args:
            switches: Lista di SwitchInfo dal RyuConnector
            links: Lista di LinkInfo dal RyuConnector
            
        Returns:
            TopologyData con dati formattati e validati
            
        Raises:
            DataProcessingError: Per errori critici nell'elaborazione
            
        Valida: Requisiti 1.3, 2.1
        """
        start_time = time.time()
        self.logger.debug(f"Processing topology data: {len(switches)} switches, {len(links)} links")
        
        try:
            # Processa e valida gli switch
            processed_switches = self._process_switches(switches)
            
            # Processa e valida i link
            processed_links = self._process_links(links, processed_switches)
            
            # Crea rappresentazione grafica della topologia
            graph_representation = self._create_graph_representation(processed_switches, processed_links)
            
            # Crea l'oggetto TopologyData
            topology_data = TopologyData(
                switches=processed_switches,
                links=processed_links,
                graph_representation=graph_representation
            )
            
            # Aggiorna statistiche
            processing_time = time.time() - start_time
            self._processing_stats['topology_processed'] += 1
            self._processing_stats['last_processing_time'] = processing_time
            
            self.logger.info(
                f"Topology processing completed: {len(processed_switches)} switches, "
                f"{len(processed_links)} links in {processing_time:.3f}s"
            )
            
            return topology_data
            
        except Exception as e:
            self._processing_stats['errors_encountered'] += 1
            error_msg = f"Error processing topology data: {e}"
            self.logger.error(error_msg)
            raise DataProcessingError(error_msg) from e
    
    def _process_switches(self, switches: List[SwitchInfo]) -> List[SwitchInfo]:
        """
        Processa e valida i dati degli switch
        
        Args:
            switches: Lista di switch grezzi
            
        Returns:
            Lista di switch processati con DPID formattati
        """
        processed_switches = []
        
        for switch in switches:
            try:
                # Il DPID viene già formattato nel __post_init__ di SwitchInfo
                # ma verifichiamo che sia corretto
                formatted_dpid = self._format_dpid(switch.dpid)
                
                # Valida che le porte siano valide
                valid_ports = self._validate_ports(switch.ports)
                
                processed_switch = SwitchInfo(
                    dpid=formatted_dpid,
                    ports=valid_ports,
                    active=switch.active
                )
                
                processed_switches.append(processed_switch)
                self.logger.debug(f"Processed switch {formatted_dpid} with {len(valid_ports)} ports")
                
            except Exception as e:
                self.logger.warning(f"Error processing switch {switch}: {e}")
                # Continua con gli altri switch come richiesto dai requisiti
                continue
        
        if not processed_switches:
            raise DataProcessingError("No valid switches found in topology data")
        
        return processed_switches
    
    def _process_links(self, links: List[LinkInfo], switches: List[SwitchInfo]) -> List[LinkInfo]:
        """
        Processa e valida i dati dei link
        
        Args:
            links: Lista di link grezzi
            switches: Lista di switch processati per validazione
            
        Returns:
            Lista di link processati con DPID formattati
        """
        processed_links = []
        switch_dpids = {switch.dpid for switch in switches}
        
        for link in links:
            try:
                # Formatta i DPID dei link
                src_dpid = self._format_dpid(link.src_dpid)
                dst_dpid = self._format_dpid(link.dst_dpid)
                
                # Valida che i DPID esistano negli switch
                if src_dpid not in switch_dpids:
                    self.logger.warning(f"Link source DPID {src_dpid} not found in switches")
                    continue
                
                if dst_dpid not in switch_dpids:
                    self.logger.warning(f"Link destination DPID {dst_dpid} not found in switches")
                    continue
                
                # Valida le porte
                if not isinstance(link.src_port, int) or link.src_port < 0:
                    self.logger.warning(f"Invalid source port {link.src_port} for link {src_dpid}->{dst_dpid}")
                    continue
                
                if not isinstance(link.dst_port, int) or link.dst_port < 0:
                    self.logger.warning(f"Invalid destination port {link.dst_port} for link {src_dpid}->{dst_dpid}")
                    continue
                
                processed_link = LinkInfo(
                    src_dpid=src_dpid,
                    dst_dpid=dst_dpid,
                    src_port=link.src_port,
                    dst_port=link.dst_port,
                    active=link.active
                )
                
                processed_links.append(processed_link)
                self.logger.debug(f"Processed link {src_dpid}:{link.src_port} -> {dst_dpid}:{link.dst_port}")
                
            except Exception as e:
                self.logger.warning(f"Error processing link {link}: {e}")
                # Continua con gli altri link come richiesto dai requisiti
                continue
        
        return processed_links
    
    def _format_dpid(self, dpid: Any) -> str:
        """
        Formatta un DPID in formato esadecimale consistente a 16 cifre
        
        Implementa il requisito 1.3: "IL Sistema DEVE convertire tutti i DPID 
        in formato esadecimale a 16 cifre per consistenza"
        
        Args:
            dpid: DPID in qualsiasi formato (int, str, hex)
            
        Returns:
            DPID formattato come stringa esadecimale a 16 cifre (es: "0000000000000001")
            
        Raises:
            ValueError: Se il DPID non può essere convertito
        """
        try:
            if isinstance(dpid, int):
                # Converte direttamente da intero
                return f"{dpid:016x}"
            
            elif isinstance(dpid, str):
                # Rimuovi prefissi comuni e separatori
                dpid_clean = dpid.replace("0x", "").replace(":", "").replace("-", "").strip()
                
                # Converte da stringa esadecimale a intero e poi formatta
                dpid_int = int(dpid_clean, 16)
                return f"{dpid_int:016x}"
            
            else:
                # Prova a convertire in stringa e poi processare
                return self._format_dpid(str(dpid))
                
        except (ValueError, TypeError) as e:
            raise ValueError(f"Cannot format DPID '{dpid}': {e}") from e
    
    def _validate_ports(self, ports: List[int]) -> List[int]:
        """
        Valida e filtra la lista delle porte
        
        Args:
            ports: Lista di numeri di porta
            
        Returns:
            Lista di porte valide (numeri interi positivi), senza duplicati
        """
        valid_ports = set()  # Usa set per evitare duplicati
        
        for port in ports:
            try:
                # Verifica che sia già un intero o convertibile senza perdita di precisione
                if isinstance(port, int):
                    port_int = port
                elif isinstance(port, float) and port.is_integer():
                    port_int = int(port)
                else:
                    port_int = int(port)
                    # Verifica che la conversione non abbia cambiato il valore
                    if float(port_int) != float(port):
                        self.logger.warning(f"Invalid port number format (precision loss): {port}")
                        continue
                
                if port_int >= 0:  # Accetta porta 0 se presente
                    valid_ports.add(port_int)
                else:
                    self.logger.warning(f"Invalid negative port number: {port}")
            except (ValueError, TypeError):
                self.logger.warning(f"Invalid port number format: {port}")
                continue
        
        return sorted(list(valid_ports))
    
    def _create_graph_representation(self, switches: List[SwitchInfo], 
                                   links: List[LinkInfo]) -> Dict[str, Any]:
        """
        Crea una rappresentazione grafica della topologia per l'analisi LLM
        
        Args:
            switches: Lista di switch processati
            links: Lista di link processati
            
        Returns:
            Dizionario con rappresentazione grafica della topologia
        """
        # Crea lista dei nodi (switch)
        nodes = []
        for switch in switches:
            nodes.append({
                "id": switch.dpid,
                "type": "switch",
                "ports": switch.ports,
                "port_count": len(switch.ports),
                "active": switch.active
            })
        
        # Crea lista degli archi (link)
        edges = []
        for link in links:
            edges.append({
                "source": link.src_dpid,
                "target": link.dst_dpid,
                "source_port": link.src_port,
                "target_port": link.dst_port,
                "active": link.active,
                "bidirectional": self._is_bidirectional_link(link, links)
            })
        
        # Calcola metriche della topologia
        topology_metrics = self._calculate_topology_metrics(nodes, edges)
        
        return {
            "nodes": nodes,
            "edges": edges,
            "metrics": topology_metrics,
            "adjacency_matrix": self._create_adjacency_matrix(switches, links),
            "connectivity_info": self._analyze_connectivity(switches, links)
        }
    
    def _is_bidirectional_link(self, link: LinkInfo, all_links: List[LinkInfo]) -> bool:
        """
        Verifica se un link è bidirezionale
        
        Args:
            link: Link da verificare
            all_links: Tutti i link della topologia
            
        Returns:
            True se esiste il link inverso
        """
        for other_link in all_links:
            if (other_link.src_dpid == link.dst_dpid and 
                other_link.dst_dpid == link.src_dpid and
                other_link.src_port == link.dst_port and
                other_link.dst_port == link.src_port):
                return True
        return False
    
    def _calculate_topology_metrics(self, nodes: List[Dict[str, Any]], 
                                  edges: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calcola metriche della topologia per l'analisi LLM
        
        Args:
            nodes: Lista dei nodi
            edges: Lista degli archi
            
        Returns:
            Dizionario con metriche della topologia
        """
        total_nodes = len(nodes)
        total_edges = len(edges)
        active_nodes = sum(1 for node in nodes if node["active"])
        active_edges = sum(1 for edge in edges if edge["active"])
        
        # Calcola il grado medio dei nodi
        node_degrees = {}
        for edge in edges:
            src = edge["source"]
            dst = edge["target"]
            node_degrees[src] = node_degrees.get(src, 0) + 1
            node_degrees[dst] = node_degrees.get(dst, 0) + 1
        
        avg_degree = sum(node_degrees.values()) / len(node_degrees) if node_degrees else 0
        
        return {
            "total_nodes": total_nodes,
            "total_edges": total_edges,
            "active_nodes": active_nodes,
            "active_edges": active_edges,
            "average_node_degree": avg_degree,
            "density": (2 * total_edges) / (total_nodes * (total_nodes - 1)) if total_nodes > 1 else 0,
            "node_degrees": node_degrees
        }
    
    def _create_adjacency_matrix(self, switches: List[SwitchInfo], 
                               links: List[LinkInfo]) -> Dict[str, Dict[str, bool]]:
        """
        Crea la matrice di adiacenza della topologia
        
        Args:
            switches: Lista degli switch
            links: Lista dei link
            
        Returns:
            Matrice di adiacenza come dizionario annidato
        """
        # Inizializza la matrice
        adjacency = {}
        for switch in switches:
            adjacency[switch.dpid] = {}
            for other_switch in switches:
                adjacency[switch.dpid][other_switch.dpid] = False
        
        # Popola la matrice con i link
        for link in links:
            if link.active:
                adjacency[link.src_dpid][link.dst_dpid] = True
        
        return adjacency
    
    def _analyze_connectivity(self, switches: List[SwitchInfo], 
                            links: List[LinkInfo]) -> Dict[str, Any]:
        """
        Analizza la connettività della topologia
        
        Args:
            switches: Lista degli switch
            links: Lista dei link
            
        Returns:
            Informazioni sulla connettività
        """
        # Conta switch isolati (senza link)
        connected_switches = set()
        for link in links:
            if link.active:
                connected_switches.add(link.src_dpid)
                connected_switches.add(link.dst_dpid)
        
        isolated_switches = []
        for switch in switches:
            if switch.dpid not in connected_switches:
                isolated_switches.append(switch.dpid)
        
        return {
            "connected_switches": len(connected_switches),
            "isolated_switches": len(isolated_switches),
            "isolated_switch_list": isolated_switches,
            "connectivity_ratio": len(connected_switches) / len(switches) if switches else 0
        }
    
    def process_metrics(self, port_stats: Dict[str, List[PortMetrics]]) -> MetricsData:
        """
        Elabora le statistiche delle porte in MetricsData strutturata
        
        Implementa:
        - Filtraggio porte LOCAL (doppio controllo oltre al RyuConnector)
        - Validazione completezza dati per ogni porta
        - Formattazione consistente DPID
        - Calcolo metriche aggregate per switch
        - Gestione errori con continuazione operativa
        
        Args:
            port_stats: Dizionario dpid -> lista di PortMetrics
            
        Returns:
            MetricsData con statistiche elaborate e metriche aggregate
            
        Raises:
            DataProcessingError: Per errori critici nell'elaborazione
            
        Valida: Requisiti 2.2, 2.3, 6.3
        """
        start_time = time.time()
        self.logger.debug(f"Processing metrics for {len(port_stats)} switches")
        
        try:
            # Filtra e valida le statistiche delle porte
            filtered_port_stats = self._filter_and_validate_port_stats(port_stats)
            
            # Formatta i DPID nelle chiavi
            formatted_port_stats = {}
            for dpid, metrics in filtered_port_stats.items():
                formatted_dpid = self._format_dpid(dpid)
                formatted_port_stats[formatted_dpid] = metrics
            
            # Calcola metriche aggregate per ogni switch
            aggregated_metrics = {}
            for dpid, metrics in formatted_port_stats.items():
                aggregated = self._calculate_aggregated_metrics(dpid, metrics)
                aggregated_metrics[dpid] = aggregated
            
            # Calcola metriche di qualità dei dati
            quality_metrics = self._calculate_quality_metrics(formatted_port_stats, aggregated_metrics)
            
            # Crea oggetto MetricsData
            metrics_data = MetricsData(
                port_statistics=formatted_port_stats,
                aggregated_metrics=aggregated_metrics,
                quality_indicators=quality_metrics
            )
            
            # Aggiorna statistiche
            processing_time = time.time() - start_time
            self._processing_stats['metrics_processed'] += 1
            self._processing_stats['last_processing_time'] = processing_time
            
            self.logger.info(f"Metrics processing completed in {processing_time:.3f}s")
            return metrics_data
            
        except Exception as e:
            self._processing_stats['errors_encountered'] += 1
            error_msg = f"Error processing metrics data: {e}"
            self.logger.error(error_msg)
            raise DataProcessingError(error_msg) from e
    
    def _calculate_aggregated_metrics(self, dpid: str, 
                                    port_metrics: List[PortMetrics]) -> AggregatedMetrics:
        """
        Calcola metriche aggregate per uno switch
        
        Args:
            dpid: DPID dello switch
            port_metrics: Lista delle metriche delle porte
            
        Returns:
            AggregatedMetrics per lo switch
        """
        if not port_metrics:
            return AggregatedMetrics(
                dpid=dpid,
                total_rx_packets=0,
                total_tx_packets=0,
                total_rx_bytes=0,
                total_tx_bytes=0,
                total_errors=0,
                average_utilization=0.0,
                congested_ports=0
            )
        
        # Somma le metriche di tutte le porte
        total_rx_packets = sum(port.rx_packets for port in port_metrics)
        total_tx_packets = sum(port.tx_packets for port in port_metrics)
        total_rx_bytes = sum(port.rx_bytes for port in port_metrics)
        total_tx_bytes = sum(port.tx_bytes for port in port_metrics)
        total_errors = sum(port.rx_errors + port.tx_errors for port in port_metrics)
        
        # Calcola utilizzo medio e porte congestionate
        utilizations = [port.calculate_utilization() for port in port_metrics]
        average_utilization = sum(utilizations) / len(utilizations)
        congested_ports = sum(1 for port in port_metrics if port.is_congested())
        
        return AggregatedMetrics(
            dpid=dpid,
            total_rx_packets=total_rx_packets,
            total_tx_packets=total_tx_packets,
            total_rx_bytes=total_rx_bytes,
            total_tx_bytes=total_tx_bytes,
            total_errors=total_errors,
            average_utilization=average_utilization,
            congested_ports=congested_ports
        )
    
    def calculate_derived_metrics(self, metrics: MetricsData) -> DerivedMetrics:
        """
        Calcola metriche derivate dai dati di prestazioni
        
        Args:
            metrics: MetricsData con statistiche delle porte
            
        Returns:
            DerivedMetrics con metriche calcolate
        """
        try:
            # Calcola utilizzo medio della rete
            all_utilizations = []
            for switch_metrics in metrics.aggregated_metrics.values():
                all_utilizations.append(switch_metrics.average_utilization)
            
            network_utilization = sum(all_utilizations) / len(all_utilizations) if all_utilizations else 0.0
            
            # Calcola livello di congestione
            total_ports = sum(len(ports) for ports in metrics.port_statistics.values())
            total_congested = sum(switch_metrics.congested_ports 
                                for switch_metrics in metrics.aggregated_metrics.values())
            congestion_level = total_congested / total_ports if total_ports > 0 else 0.0
            
            # Calcola tasso di errore medio
            total_packets = sum(switch_metrics.total_rx_packets + switch_metrics.total_tx_packets
                              for switch_metrics in metrics.aggregated_metrics.values())
            total_errors = sum(switch_metrics.total_errors 
                             for switch_metrics in metrics.aggregated_metrics.values())
            error_rate = total_errors / total_packets if total_packets > 0 else 0.0
            
            # Calcola stabilità topologia (placeholder - richiede dati storici)
            topology_stability = 1.0  # Assumiamo topologia stabile per ora
            
            # Calcola punteggio prestazioni complessivo
            performance_score = self._calculate_performance_score(
                network_utilization, congestion_level, error_rate, topology_stability
            )
            
            return DerivedMetrics(
                network_utilization=network_utilization,
                congestion_level=congestion_level,
                error_rate=error_rate,
                topology_stability=topology_stability,
                performance_score=performance_score
            )
            
        except Exception as e:
            error_msg = f"Error calculating derived metrics: {e}"
            self.logger.error(error_msg)
            raise DataProcessingError(error_msg) from e
    
    def _calculate_performance_score(self, utilization: float, congestion: float, 
                                   error_rate: float, stability: float) -> float:
        """
        Calcola un punteggio di prestazioni complessivo (0.0 - 1.0)
        
        Args:
            utilization: Utilizzo medio della rete (0.0 - 1.0)
            congestion: Livello di congestione (0.0 - 1.0)
            error_rate: Tasso di errore (0.0 - 1.0)
            stability: Stabilità topologia (0.0 - 1.0)
            
        Returns:
            Punteggio prestazioni (1.0 = ottimo, 0.0 = pessimo)
        """
        # Pesi per i diversi fattori
        weights = {
            'utilization': 0.3,    # Utilizzo moderato è buono
            'congestion': 0.3,     # Bassa congestione è buona
            'error_rate': 0.3,     # Bassi errori sono buoni
            'stability': 0.1       # Alta stabilità è buona
        }
        
        # Normalizza i valori (più alto = migliore)
        normalized_utilization = 1.0 - abs(utilization - 0.5) * 2  # Ottimale intorno a 50%
        normalized_congestion = 1.0 - congestion  # Meno congestione = meglio
        normalized_error_rate = 1.0 - min(error_rate, 1.0)  # Meno errori = meglio
        normalized_stability = stability  # Più stabilità = meglio
        
        # Calcola punteggio pesato
        score = (
            normalized_utilization * weights['utilization'] +
            normalized_congestion * weights['congestion'] +
            normalized_error_rate * weights['error_rate'] +
            normalized_stability * weights['stability']
        )
        
        return max(0.0, min(1.0, score))  # Clamp tra 0.0 e 1.0
    
    def _filter_and_validate_port_stats(self, port_stats: Dict[str, List[PortMetrics]]) -> Dict[str, List[PortMetrics]]:
        """
        Filtra e valida le statistiche delle porte
        
        Implementa:
        - Filtraggio porte LOCAL (doppio controllo)
        - Validazione completezza dati
        - Rimozione porte con dati inconsistenti
        
        Args:
            port_stats: Statistiche grezze delle porte
            
        Returns:
            Statistiche filtrate e validate
            
        Valida: Requisiti 2.2, 2.3
        """
        filtered_stats = {}
        
        for dpid, metrics_list in port_stats.items():
            valid_metrics = []
            
            for port_metric in metrics_list:
                try:
                    # Filtra porte LOCAL (doppio controllo oltre al RyuConnector)
                    if self._is_local_port(port_metric.port_no):
                        self.logger.debug(f"Filtering LOCAL port {port_metric.port_no} for switch {dpid}")
                        continue
                    
                    # Valida completezza dati
                    if not self._validate_port_metric_completeness(port_metric):
                        self.logger.warning(f"Incomplete data for port {port_metric.port_no} on switch {dpid}")
                        continue
                    
                    # Valida consistenza dati
                    if not self._validate_port_metric_consistency(port_metric):
                        self.logger.warning(f"Inconsistent data for port {port_metric.port_no} on switch {dpid}")
                        continue
                    
                    valid_metrics.append(port_metric)
                    
                except Exception as e:
                    self.logger.error(f"Error validating port metric {port_metric}: {e}")
                    continue
            
            if valid_metrics:
                filtered_stats[dpid] = valid_metrics
                self.logger.debug(f"Switch {dpid}: {len(valid_metrics)} valid ports out of {len(metrics_list)}")
            else:
                self.logger.warning(f"No valid port metrics found for switch {dpid}")
        
        return filtered_stats
    
    def _is_local_port(self, port_no: int) -> bool:
        """
        Verifica se una porta è una porta LOCAL
        
        Le porte LOCAL del controller Ryu hanno tipicamente:
        - port_no = 0xfffffffe (4294967294) per OFPP_LOCAL
        - Oppure sono identificate come 'LOCAL' (già filtrate dal RyuConnector)
        
        Args:
            port_no: Numero della porta
            
        Returns:
            True se è una porta LOCAL
        """
        # Costanti OpenFlow per porte speciali
        OFPP_LOCAL = 0xfffffffe  # 4294967294
        OFPP_CONTROLLER = 0xfffffffd  # 4294967293
        OFPP_ALL = 0xfffffffc  # 4294967292
        OFPP_FLOOD = 0xfffffffb  # 4294967291
        
        # Verifica se è una porta speciale OpenFlow
        special_ports = {OFPP_LOCAL, OFPP_CONTROLLER, OFPP_ALL, OFPP_FLOOD}
        
        return port_no in special_ports
    
    def _validate_port_metric_completeness(self, port_metric: PortMetrics) -> bool:
        """
        Valida che una metrica di porta abbia tutti i dati necessari
        
        Args:
            port_metric: Metrica da validare
            
        Returns:
            True se i dati sono completi
            
        Valida: Requisito 2.3
        """
        # Verifica che tutti i campi richiesti siano presenti e non negativi
        required_fields = [
            'port_no', 'rx_packets', 'tx_packets', 
            'rx_bytes', 'tx_bytes', 'rx_errors', 'tx_errors'
        ]
        
        for field in required_fields:
            value = getattr(port_metric, field, None)
            if value is None:
                return False
            
            # I contatori devono essere non negativi
            if field != 'port_no' and value < 0:
                return False
        
        # Verifica che il numero di porta sia valido
        if not isinstance(port_metric.port_no, int) or port_metric.port_no < 0:
            return False
        
        return True
    
    def _validate_port_metric_consistency(self, port_metric: PortMetrics) -> bool:
        """
        Valida la consistenza dei dati di una metrica di porta
        
        Args:
            port_metric: Metrica da validare
            
        Returns:
            True se i dati sono consistenti
        """
        # Verifica che i bytes siano coerenti con i pacchetti
        # (un pacchetto dovrebbe avere almeno qualche byte)
        if port_metric.rx_packets > 0 and port_metric.rx_bytes == 0:
            return False
        
        if port_metric.tx_packets > 0 and port_metric.tx_bytes == 0:
            return False
        
        # Verifica che gli errori non superino i pacchetti totali
        if port_metric.rx_errors > port_metric.rx_packets:
            return False
        
        if port_metric.tx_errors > port_metric.tx_packets:
            return False
        
        # Verifica che i dropped non superino i pacchetti totali
        if hasattr(port_metric, 'rx_dropped') and port_metric.rx_dropped > port_metric.rx_packets:
            return False
        
        if hasattr(port_metric, 'tx_dropped') and port_metric.tx_dropped > port_metric.tx_packets:
            return False
        
        return True
    
    def _calculate_quality_metrics(self, port_stats: Dict[str, List[PortMetrics]], 
                                 aggregated_metrics: Dict[str, AggregatedMetrics]) -> 'QualityMetrics':
        """
        Calcola metriche di qualità dei dati raccolti
        
        Args:
            port_stats: Statistiche delle porte
            aggregated_metrics: Metriche aggregate
            
        Returns:
            QualityMetrics con punteggi di qualità
        """
        from src.models.health import QualityMetrics
        
        issues_detected = []
        
        # Calcola completezza (percentuale di switch con dati)
        total_switches = len(port_stats)
        switches_with_data = sum(1 for metrics in port_stats.values() if metrics)
        completeness_score = switches_with_data / total_switches if total_switches > 0 else 0.0
        
        if completeness_score < 1.0:
            missing_switches = total_switches - switches_with_data
            issues_detected.append(f"{missing_switches} switches without port data")
        
        # Calcola consistenza (percentuale di porte con dati validi)
        total_ports = sum(len(metrics) for metrics in port_stats.values())
        valid_ports = total_ports  # Già filtrate nella validazione
        consistency_score = 1.0  # Se siamo arrivati qui, i dati sono consistenti
        
        # Calcola tempestività (assumiamo che i dati siano recenti)
        timeliness_score = 1.0  # Placeholder - richiederebbe timestamp dei dati
        
        # Calcola accuratezza basata su metriche derivate ragionevoli
        accuracy_score = 1.0
        for dpid, metrics in aggregated_metrics.items():
            # Verifica che le metriche siano in range ragionevoli
            if metrics.average_utilization > 1.0:
                accuracy_score *= 0.9
                issues_detected.append(f"Switch {dpid} has utilization > 100%")
            
            # Verifica tasso di errore ragionevole
            total_packets = metrics.total_rx_packets + metrics.total_tx_packets
            if total_packets > 0:
                error_rate = metrics.total_errors / total_packets
                if error_rate > 0.1:  # Più del 10% di errori è sospetto
                    accuracy_score *= 0.8
                    issues_detected.append(f"Switch {dpid} has high error rate: {error_rate:.2%}")
        
        return QualityMetrics(
            completeness_score=completeness_score,
            consistency_score=consistency_score,
            timeliness_score=timeliness_score,
            accuracy_score=accuracy_score,
            overall_score=0.0,  # Calcolato automaticamente in __post_init__
            issues_detected=issues_detected
        )
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """
        Restituisce statistiche di elaborazione
        
        Returns:
            Dizionario con statistiche del processore
        """
        return self._processing_stats.copy()
    
    def reset_stats(self) -> None:
        """Resetta le statistiche di elaborazione"""
        self._processing_stats = {
            'topology_processed': 0,
            'metrics_processed': 0,
            'errors_encountered': 0,
            'last_processing_time': 0.0
        }
        self.logger.info("Processing statistics reset")