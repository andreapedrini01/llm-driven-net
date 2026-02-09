"""
RyuConnector - Connettore per il controller Ryu

Implementa la connessione HTTP al controller Ryu con gestione robusta degli errori,
retry logic con backoff esponenziale e timeout configurabili.
"""

import time
import random
import logging
import json
from typing import List, Dict, Any, Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models.config import RyuConfig, RetryConfig
from .models.core import SwitchInfo, LinkInfo, PortMetrics
from .models.health import (
    HealthStatus, ComponentType, HealthCheck, ConnectionHealth, 
    StructuredLogEntry
)


class RyuConnectionError(Exception):
    """Eccezione per errori di connessione al controller Ryu"""
    pass


class RyuTimeoutError(RyuConnectionError):
    """Eccezione per timeout nelle richieste al controller Ryu"""
    pass


class RyuDataError(Exception):
    """Eccezione per dati malformati ricevuti dal controller Ryu"""
    pass


class RyuConnector:
    """
    Connettore per il controller Ryu con gestione errori robusta
    
    Implementa i metodi base per le chiamate API al controller Ryu:
    - get_switches(): Recupera la lista degli switch attivi
    - get_links(): Recupera i link di topologia
    - get_port_stats(): Recupera le statistiche delle porte
    
    Include gestione timeout, retry con backoff esponenziale e logging strutturato.
    """
    
    def __init__(self, ryu_config: RyuConfig, retry_config: RetryConfig):
        """
        Inizializza il connettore Ryu
        
        Args:
            ryu_config: Configurazione per la connessione Ryu
            retry_config: Configurazione per la logica di retry
        """
        self.ryu_config = ryu_config
        self.retry_config = retry_config
        self.logger = logging.getLogger(__name__)
        
        # Inizializza la sessione HTTP con retry automatico
        self.session = requests.Session()
        self._setup_session()
        
        # Statistiche di connessione
        self._connection_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retry_attempts': 0,
            'last_error': None,
            'last_success': None
        }
        
        # Health monitoring
        self._connection_health = ConnectionHealth(
            is_reachable=False,
            response_time_ms=0.0,
            consecutive_failures=0,
            success_rate=0.0
        )
        self._start_time = time.time()
        
        self.logger.info(f"RyuConnector initialized for {ryu_config.base_url}")
        self._log_structured_event("initialization", "RyuConnector initialized successfully")
    
    def _setup_session(self) -> None:
        """Configura la sessione HTTP con retry automatico"""
        # Configura retry strategy per la sessione
        retry_strategy = Retry(
            total=self.retry_config.max_attempts,
            backoff_factor=self.retry_config.backoff_factor,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Configura headers comuni
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'NetworkStateCollector/1.0'
        })
        
        # Configura SSL se necessario
        if not self.ryu_config.verify_ssl:
            self.session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Esegue una richiesta HTTP con retry e gestione errori
        
        Args:
            endpoint: Endpoint API relativo (es. '/stats/switches')
            params: Parametri query opzionali
            
        Returns:
            Risposta JSON parsata
            
        Raises:
            RyuConnectionError: Per errori di connessione
            RyuTimeoutError: Per timeout
            RyuDataError: Per dati malformati
        """
        url = f"{self.ryu_config.base_url}{endpoint}"
        self._connection_stats['total_requests'] += 1
        start_time = time.time()
        
        for attempt in range(self.retry_config.max_attempts):
            try:
                self.logger.debug(f"Making request to {url} (attempt {attempt + 1})")
                
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.ryu_config.timeout
                )
                
                response_time_ms = (time.time() - start_time) * 1000
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                        self._connection_stats['successful_requests'] += 1
                        self._connection_stats['last_success'] = time.time()
                        
                        # Aggiorna health status
                        self._connection_health.is_reachable = True
                        self._connection_health.response_time_ms = response_time_ms
                        self._connection_health.last_successful_request = time.time()
                        self._connection_health.consecutive_failures = 0
                        self._update_success_rate()
                        
                        self.logger.debug(f"Successful request to {endpoint}")
                        self._log_structured_success(endpoint, response_time_ms)
                        return data
                    except ValueError as e:
                        error_msg = f"Invalid JSON response from {endpoint}: {e}"
                        self.logger.error(error_msg)
                        self._log_structured_error(endpoint, "json_parse_error", attempt + 1, str(e), 
                                                 response_time_ms=response_time_ms, status_code=response.status_code)
                        raise RyuDataError(error_msg) from e
                
                else:
                    error_msg = f"HTTP {response.status_code} from {endpoint}: {response.text}"
                    self.logger.warning(error_msg)
                    
                    self._log_structured_error(endpoint, "http_error", attempt + 1, error_msg,
                                             response_time_ms=response_time_ms, status_code=response.status_code)
                    
                    # Per alcuni status code, non fare retry
                    if response.status_code in [400, 401, 403, 404]:
                        self._update_connection_failure()
                        raise RyuConnectionError(error_msg)
                    
                    # Per altri status code, continua con retry
                    if attempt < self.retry_config.max_attempts - 1:
                        self._wait_with_backoff(attempt)
                        continue
                    else:
                        self._update_connection_failure()
                        raise RyuConnectionError(error_msg)
            
            except requests.exceptions.Timeout as e:
                response_time_ms = (time.time() - start_time) * 1000
                error_msg = f"Timeout connecting to {endpoint} after {self.ryu_config.timeout}s"
                self.logger.warning(error_msg)
                
                self._log_structured_error(endpoint, "timeout", attempt + 1, error_msg,
                                         response_time_ms=response_time_ms)
                
                if attempt < self.retry_config.max_attempts - 1:
                    self._wait_with_backoff(attempt)
                    continue
                else:
                    self._connection_stats['failed_requests'] += 1
                    self._connection_stats['last_error'] = time.time()
                    self._update_connection_failure()
                    raise RyuTimeoutError(error_msg) from e
            
            except requests.exceptions.ConnectionError as e:
                response_time_ms = (time.time() - start_time) * 1000
                error_msg = f"Connection error to {endpoint}: {e}"
                self.logger.warning(error_msg)
                
                self._log_structured_error(endpoint, "connection_error", attempt + 1, error_msg,
                                         response_time_ms=response_time_ms)
                
                if attempt < self.retry_config.max_attempts - 1:
                    self._wait_with_backoff(attempt)
                    continue
                else:
                    self._connection_stats['failed_requests'] += 1
                    self._connection_stats['last_error'] = time.time()
                    self._update_connection_failure()
                    raise RyuConnectionError(error_msg) from e
            
            except RyuDataError:
                # Re-raise RyuDataError without wrapping
                self._update_connection_failure()
                raise
            except Exception as e:
                response_time_ms = (time.time() - start_time) * 1000
                error_msg = f"Unexpected error connecting to {endpoint}: {e}"
                self.logger.error(error_msg)
                
                self._log_structured_error(endpoint, "unexpected_error", attempt + 1, error_msg,
                                         response_time_ms=response_time_ms)
                
                self._connection_stats['failed_requests'] += 1
                self._connection_stats['last_error'] = time.time()
                self._update_connection_failure()
                raise RyuConnectionError(error_msg) from e
        
        # Questo non dovrebbe mai essere raggiunto
        self._update_connection_failure()
        raise RyuConnectionError(f"Max retry attempts exceeded for {endpoint}")
    
    def _wait_with_backoff(self, attempt: int) -> None:
        """
        Implementa il backoff esponenziale con jitter
        
        Args:
            attempt: Numero del tentativo corrente (0-based)
        """
        delay = min(
            self.retry_config.initial_delay * (self.retry_config.backoff_factor ** attempt),
            self.retry_config.max_delay
        )
        
        # Aggiungi jitter se configurato
        if self.retry_config.jitter:
            delay *= (0.5 + random.random() * 0.5)  # Jitter tra 50% e 100% del delay
        
        self._connection_stats['retry_attempts'] += 1
        self.logger.info(f"Waiting {delay:.2f}s before retry (attempt {attempt + 1})")
        time.sleep(delay)
    
    def get_switches(self) -> List[SwitchInfo]:
        """
        Recupera la lista degli switch attivi dal controller Ryu
        
        Returns:
            Lista di SwitchInfo con DPID formattati e porte
            
        Raises:
            RyuConnectionError: Per errori di connessione
            RyuDataError: Per dati malformati
        """
        self.logger.debug("Fetching switches from Ryu controller")
        
        try:
            # Recupera la lista degli switch
            switches_data = self._make_request('/stats/switches')
            
            if not isinstance(switches_data, list):
                raise RyuDataError(f"Expected list of switches, got {type(switches_data)}")
            
            switches = []
            for switch_data in switches_data:
                try:
                    dpid = switch_data.get('dpid')
                    if dpid is None:
                        self.logger.warning("Switch without DPID found, skipping")
                        continue
                    
                    # Recupera le porte per questo switch
                    ports = self._get_switch_ports(dpid)
                    
                    switch_info = SwitchInfo(
                        dpid=dpid,
                        ports=ports,
                        active=True
                    )
                    switches.append(switch_info)
                    
                except Exception as e:
                    self.logger.error(f"Error processing switch data {switch_data}: {e}")
                    continue
            
            self.logger.info(f"Retrieved {len(switches)} switches")
            return switches
            
        except (RyuConnectionError, RyuTimeoutError, RyuDataError):
            raise
        except Exception as e:
            error_msg = f"Unexpected error getting switches: {e}"
            self.logger.error(error_msg)
            raise RyuConnectionError(error_msg) from e
    
    def _get_switch_ports(self, dpid: str) -> List[int]:
        """
        Recupera le porte per uno switch specifico
        
        Args:
            dpid: DPID dello switch
            
        Returns:
            Lista dei numeri di porta
        """
        try:
            # Formatta il DPID per la richiesta
            if isinstance(dpid, int):
                dpid_param = str(dpid)
            else:
                dpid_param = str(dpid)
            
            ports_data = self._make_request(f'/stats/port/{dpid_param}')
            
            if not isinstance(ports_data, dict) or dpid_param not in ports_data:
                self.logger.warning(f"No port data found for switch {dpid}")
                return []
            
            ports = []
            for port_data in ports_data[dpid_param]:
                port_no = port_data.get('port_no')
                if port_no is not None and port_no != 'LOCAL':
                    try:
                        ports.append(int(port_no))
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid port number {port_no} for switch {dpid}")
                        continue
            
            return sorted(ports)
            
        except Exception as e:
            self.logger.warning(f"Error getting ports for switch {dpid}: {e}")
            return []
    
    def get_links(self) -> List[LinkInfo]:
        """
        Recupera i link di topologia dal controller Ryu
        
        Returns:
            Lista di LinkInfo con DPID formattati e informazioni porte
            
        Raises:
            RyuConnectionError: Per errori di connessione
            RyuDataError: Per dati malformati
        """
        self.logger.debug("Fetching topology links from Ryu controller")
        
        try:
            links_data = self._make_request('/v1.0/topology/links')
            
            if not isinstance(links_data, list):
                raise RyuDataError(f"Expected list of links, got {type(links_data)}")
            
            links = []
            for link_data in links_data:
                try:
                    src = link_data.get('src', {})
                    dst = link_data.get('dst', {})
                    
                    src_dpid = src.get('dpid')
                    dst_dpid = dst.get('dpid')
                    src_port = src.get('port_no')
                    dst_port = dst.get('port_no')
                    
                    if None in [src_dpid, dst_dpid, src_port, dst_port]:
                        self.logger.warning(f"Incomplete link data: {link_data}")
                        continue
                    
                    link_info = LinkInfo(
                        src_dpid=src_dpid,
                        dst_dpid=dst_dpid,
                        src_port=int(src_port),
                        dst_port=int(dst_port),
                        active=True
                    )
                    links.append(link_info)
                    
                except Exception as e:
                    self.logger.error(f"Error processing link data {link_data}: {e}")
                    continue
            
            self.logger.info(f"Retrieved {len(links)} topology links")
            return links
            
        except (RyuConnectionError, RyuTimeoutError, RyuDataError):
            raise
        except Exception as e:
            error_msg = f"Unexpected error getting links: {e}"
            self.logger.error(error_msg)
            raise RyuConnectionError(error_msg) from e
    
    def get_port_stats(self, dpid: str) -> List[PortMetrics]:
        """
        Recupera le statistiche delle porte per uno switch specifico
        
        Args:
            dpid: DPID dello switch (può essere int o str)
            
        Returns:
            Lista di PortMetrics per le porte dello switch (esclude porte LOCAL)
            
        Raises:
            RyuConnectionError: Per errori di connessione
            RyuDataError: Per dati malformati
        """
        self.logger.debug(f"Fetching port statistics for switch {dpid}")
        
        try:
            # Formatta il DPID per la richiesta
            if isinstance(dpid, int):
                dpid_param = str(dpid)
            else:
                dpid_param = str(dpid)
            
            stats_data = self._make_request(f'/stats/port/{dpid_param}')
            
            if not isinstance(stats_data, dict) or dpid_param not in stats_data:
                raise RyuDataError(f"No port statistics found for switch {dpid}")
            
            port_stats = []
            for port_data in stats_data[dpid_param]:
                try:
                    port_no = port_data.get('port_no')
                    
                    # Escludi le porte LOCAL come richiesto dai requisiti
                    if port_no == 'LOCAL' or port_no is None:
                        continue
                    
                    # Converte port_no in intero
                    try:
                        port_no_int = int(port_no)
                    except (ValueError, TypeError):
                        self.logger.warning(f"Invalid port number {port_no} for switch {dpid}")
                        continue
                    
                    # Estrai le metriche richieste
                    port_metrics = PortMetrics(
                        port_no=port_no_int,
                        rx_packets=int(port_data.get('rx_packets', 0)),
                        tx_packets=int(port_data.get('tx_packets', 0)),
                        rx_bytes=int(port_data.get('rx_bytes', 0)),
                        tx_bytes=int(port_data.get('tx_bytes', 0)),
                        rx_errors=int(port_data.get('rx_errors', 0)),
                        tx_errors=int(port_data.get('tx_errors', 0)),
                        rx_dropped=int(port_data.get('rx_dropped', 0)),
                        tx_dropped=int(port_data.get('tx_dropped', 0))
                    )
                    port_stats.append(port_metrics)
                    
                except Exception as e:
                    self.logger.error(f"Error processing port data {port_data}: {e}")
                    continue
            
            self.logger.debug(f"Retrieved statistics for {len(port_stats)} ports on switch {dpid}")
            return port_stats
            
        except (RyuConnectionError, RyuTimeoutError, RyuDataError):
            raise
        except Exception as e:
            error_msg = f"Unexpected error getting port stats for switch {dpid}: {e}"
            self.logger.error(error_msg)
            raise RyuConnectionError(error_msg) from e
    
    def is_healthy(self) -> bool:
        """
        Verifica se la connessione al controller Ryu è sana
        
        Returns:
            True se la connessione è operativa, False altrimenti
        """
        try:
            start_time = time.time()
            # Prova una richiesta semplice per verificare la connessione
            # Usa direttamente la sessione per evitare di alterare le statistiche principali
            response = self.session.get(
                f"{self.ryu_config.base_url}/stats/switches",
                timeout=self.ryu_config.timeout
            )
            response_time_ms = (time.time() - start_time) * 1000
            
            if response.status_code == 200:
                # Aggiorna health status
                self._connection_health.is_reachable = True
                self._connection_health.response_time_ms = response_time_ms
                self._connection_health.last_successful_request = time.time()
                self._connection_health.consecutive_failures = 0
                
                self._log_structured_event("health_check_success", 
                                         f"Health check passed in {response_time_ms:.2f}ms")
                return True
            else:
                raise RyuConnectionError(f"HTTP {response.status_code}: {response.text}")
                
        except Exception as e:
            self._connection_health.is_reachable = False
            self._connection_health.last_error = str(e)
            self._connection_health.consecutive_failures += 1
            
            self.logger.warning(f"Health check failed: {e}")
            self._log_structured_event("health_check_failure", f"Health check failed: {e}")
            return False
    
    def get_health_status(self) -> HealthCheck:
        """
        Restituisce lo stato di salute dettagliato del connettore
        
        Returns:
            HealthCheck con stato dettagliato
        """
        # Aggiorna le statistiche
        self._update_success_rate()
        
        status = self._connection_health.status
        
        if status == HealthStatus.HEALTHY:
            message = "Connection is healthy"
        elif status == HealthStatus.DEGRADED:
            message = f"Connection is degraded: {self._get_degradation_reason()}"
        else:
            message = f"Connection is unhealthy: {self._connection_health.last_error or 'Unknown error'}"
        
        return HealthCheck(
            component=ComponentType.RYU_CONNECTOR,
            status=status,
            message=message,
            details={
                "connection_health": self._connection_health.to_dict(),
                "connection_stats": self.get_connection_stats(),
                "uptime_seconds": time.time() - self._start_time
            }
        )
    
    def _get_degradation_reason(self) -> str:
        """Determina la ragione della degradazione"""
        reasons = []
        
        if self._connection_health.consecutive_failures > 3:
            reasons.append(f"{self._connection_health.consecutive_failures} consecutive failures")
        
        if self._connection_health.success_rate < 0.5 and self._connection_health.success_rate > 0:
            reasons.append(f"low success rate ({self._connection_health.success_rate:.2%})")
        
        if self._connection_health.response_time_ms > 5000:
            reasons.append(f"high response time ({self._connection_health.response_time_ms:.0f}ms)")
        
        return ", ".join(reasons) if reasons else "unknown"
    
    def _update_connection_failure(self) -> None:
        """Aggiorna i contatori per un fallimento di connessione"""
        self._connection_health.is_reachable = False
        self._connection_health.consecutive_failures += 1
        self._connection_health.last_error = "Connection failed"
        self._update_success_rate()
    
    def _update_success_rate(self) -> None:
        """Aggiorna il tasso di successo delle connessioni"""
        total = self._connection_stats['total_requests']
        if total > 0:
            self._connection_health.success_rate = self._connection_stats['successful_requests'] / total
        else:
            self._connection_health.success_rate = 0.0
    
    def _log_structured_event(self, event_type: str, message: str, **kwargs) -> None:
        """Log di un evento strutturato"""
        log_entry = StructuredLogEntry(
            timestamp=time.time(),
            level="INFO",
            component="ryu_connector",
            event_type=event_type,
            message=message,
            context=kwargs
        )
        
        # Log sia in formato tradizionale che strutturato
        self.logger.info(message)
        if hasattr(self.logger, 'structured'):
            self.logger.structured(log_entry.to_json())
    
    def _log_structured_success(self, endpoint: str, response_time_ms: float) -> None:
        """Log strutturato per connessioni riuscite"""
        log_entry = StructuredLogEntry.create_connection_success(
            message=f"Successful request to {endpoint}",
            endpoint=endpoint,
            response_time_ms=response_time_ms,
            base_url=self.ryu_config.base_url
        )
        
        if hasattr(self.logger, 'structured'):
            self.logger.structured(log_entry.to_json())
    
    def _log_structured_error(self, endpoint: str, error_type: str, attempt: int, 
                            error_message: str, **kwargs) -> None:
        """Log strutturato per errori di connessione"""
        log_entry = StructuredLogEntry.create_connection_error(
            message=error_message,
            endpoint=endpoint,
            error_type=error_type,
            attempt=attempt,
            max_attempts=self.retry_config.max_attempts,
            base_url=self.ryu_config.base_url,
            **kwargs
        )
        
        if hasattr(self.logger, 'structured'):
            self.logger.structured(log_entry.to_json())
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Restituisce le statistiche di connessione
        
        Returns:
            Dizionario con statistiche di connessione
        """
        stats = self._connection_stats.copy()
        
        # Calcola metriche derivate
        total = stats['total_requests']
        if total > 0:
            stats['success_rate'] = stats['successful_requests'] / total
            stats['failure_rate'] = stats['failed_requests'] / total
        else:
            stats['success_rate'] = 0.0
            stats['failure_rate'] = 0.0
        
        # Aggiungi informazioni di salute
        stats['health_status'] = self._connection_health.status.value
        stats['is_reachable'] = self._connection_health.is_reachable
        stats['response_time_ms'] = self._connection_health.response_time_ms
        stats['consecutive_failures'] = self._connection_health.consecutive_failures
        stats['uptime_seconds'] = time.time() - self._start_time
        
        return stats
    
    def reset_stats(self) -> None:
        """Resetta le statistiche di connessione"""
        self._connection_stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'retry_attempts': 0,
            'last_error': None,
            'last_success': None
        }
        
        # Reset health status
        self._connection_health = ConnectionHealth(
            is_reachable=False,
            response_time_ms=0.0,
            consecutive_failures=0,
            success_rate=0.0
        )
        
        self.logger.info("Connection statistics and health status reset")
        self._log_structured_event("stats_reset", "Connection statistics and health status reset")
    
    def close(self) -> None:
        """Chiude la sessione HTTP"""
        if self.session:
            self.session.close()
            uptime = time.time() - self._start_time
            self.logger.info(f"RyuConnector session closed after {uptime:.2f}s uptime")
            self._log_structured_event("shutdown", f"RyuConnector session closed", 
                                     uptime_seconds=uptime)