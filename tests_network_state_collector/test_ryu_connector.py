"""
Test per RyuConnector

Include test unitari e property-based test per validare
la connessione al controller Ryu, gestione errori e retry logic.
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
import requests
from hypothesis import given, strategies as st, assume

from network_state_collector.ryu_connector import (
    RyuConnector, RyuConnectionError, RyuTimeoutError, RyuDataError
)
from llm_integration_module.models.config import RyuConfig, RetryConfig
from llm_integration_module.models.core import SwitchInfo, LinkInfo, PortMetrics
from llm_integration_module.models.health import HealthStatus, ComponentType, HealthCheck


# Strategies per Hypothesis
@st.composite
def ryu_config_strategy(draw):
    """Genera RyuConfig validi per i test"""
    host = draw(st.text(min_size=1, max_size=50).filter(lambda x: '/' not in x and ':' not in x))
    port = draw(st.integers(min_value=1, max_value=65535))
    timeout = draw(st.floats(min_value=1.0, max_value=300.0))
    
    return RyuConfig(
        host=host,
        port=port,
        timeout=timeout,
        use_https=draw(st.booleans()),
        verify_ssl=draw(st.booleans())
    )


@st.composite
def retry_config_strategy(draw):
    """Genera RetryConfig validi per i test"""
    max_attempts = draw(st.integers(min_value=1, max_value=10))
    initial_delay = draw(st.floats(min_value=0.1, max_value=5.0))
    max_delay = draw(st.floats(min_value=initial_delay, max_value=60.0))
    backoff_factor = draw(st.floats(min_value=1.0, max_value=5.0))
    
    return RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        backoff_factor=backoff_factor,
        jitter=draw(st.booleans())
    )


@st.composite
def switch_response_strategy(draw):
    """Genera risposte valide per l'API switches"""
    num_switches = draw(st.integers(min_value=0, max_value=10))
    switches = []
    
    for i in range(num_switches):
        dpid = draw(st.integers(min_value=1, max_value=0xFFFFFFFFFFFFFFFF))
        switches.append({"dpid": dpid})
    
    return switches


@st.composite
def port_response_strategy(draw):
    """Genera risposte valide per l'API port stats"""
    dpid = draw(st.integers(min_value=1, max_value=0xFFFFFFFFFFFFFFFF))
    dpid_str = str(dpid)
    
    # Genera almeno 1 porta per evitare casi edge con liste vuote
    num_ports = draw(st.integers(min_value=1, max_value=48))
    ports = []
    
    for i in range(num_ports):
        port_no = draw(st.integers(min_value=1, max_value=65535))
        ports.append({
            "port_no": port_no,
            "rx_packets": draw(st.integers(min_value=0, max_value=10**12)),
            "tx_packets": draw(st.integers(min_value=0, max_value=10**12)),
            "rx_bytes": draw(st.integers(min_value=0, max_value=10**15)),
            "tx_bytes": draw(st.integers(min_value=0, max_value=10**15)),
            "rx_errors": draw(st.integers(min_value=0, max_value=10**6)),
            "tx_errors": draw(st.integers(min_value=0, max_value=10**6)),
            "rx_dropped": draw(st.integers(min_value=0, max_value=10**6)),
            "tx_dropped": draw(st.integers(min_value=0, max_value=10**6))
        })
    
    return {dpid_str: ports}


@st.composite
def links_response_strategy(draw):
    """Genera risposte valide per l'API topology links"""
    num_links = draw(st.integers(min_value=0, max_value=20))
    links = []
    
    for i in range(num_links):
        src_dpid = draw(st.integers(min_value=1, max_value=0xFFFFFFFFFFFFFFFF))
        dst_dpid = draw(st.integers(min_value=1, max_value=0xFFFFFFFFFFFFFFFF))
        src_port = draw(st.integers(min_value=1, max_value=65535))
        dst_port = draw(st.integers(min_value=1, max_value=65535))
        
        links.append({
            "src": {"dpid": src_dpid, "port_no": src_port},
            "dst": {"dpid": dst_dpid, "port_no": dst_port}
        })
    
    return links


class TestRyuConnector:
    """Test per la classe RyuConnector"""
    
    @pytest.fixture
    def ryu_config(self):
        """Fixture per configurazione Ryu di test"""
        return RyuConfig(
            host="localhost",
            port=8080,
            timeout=5.0
        )
    
    @pytest.fixture
    def retry_config(self):
        """Fixture per configurazione retry di test"""
        return RetryConfig(
            max_attempts=3,
            initial_delay=0.1,
            max_delay=1.0,
            backoff_factor=2.0
        )
    
    @pytest.fixture
    def connector(self, ryu_config, retry_config):
        """Fixture per RyuConnector di test"""
        return RyuConnector(ryu_config, retry_config)
    
    def test_initialization(self, connector, ryu_config):
        """Test inizializzazione del connettore"""
        assert connector.ryu_config == ryu_config
        assert connector.session is not None
        assert connector._connection_stats['total_requests'] == 0
    
    def test_base_url_construction(self, ryu_config):
        """Test costruzione URL base"""
        assert ryu_config.base_url == "http://localhost:8080"
        
        ryu_config.use_https = True
        assert ryu_config.base_url == "https://localhost:8080"
        
        ryu_config.base_path = "/api/v1"
        assert ryu_config.base_url == "https://localhost:8080/api/v1"
    
    @patch('requests.Session.get')
    def test_successful_request(self, mock_get, connector):
        """Test richiesta HTTP di successo"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        mock_get.return_value = mock_response
        
        result = connector._make_request('/test')
        
        assert result == {"test": "data"}
        assert connector._connection_stats['successful_requests'] == 1
        assert connector._connection_stats['failed_requests'] == 0
    
    @patch('requests.Session.get')
    def test_connection_error_with_retry(self, mock_get, connector):
        """Test gestione errore di connessione con retry"""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        with pytest.raises(RyuConnectionError):
            connector._make_request('/test')
        
        # Verifica che siano stati fatti i tentativi di retry
        assert mock_get.call_count == connector.retry_config.max_attempts
        assert connector._connection_stats['failed_requests'] == 1
        assert connector._connection_stats['retry_attempts'] > 0
    
    @patch('requests.Session.get')
    def test_timeout_error_with_retry(self, mock_get, connector):
        """Test gestione timeout con retry"""
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        with pytest.raises(RyuTimeoutError):
            connector._make_request('/test')
        
        assert mock_get.call_count == connector.retry_config.max_attempts
        assert connector._connection_stats['failed_requests'] == 1
    
    @patch('requests.Session.get')
    def test_http_error_no_retry_for_client_errors(self, mock_get, connector):
        """Test che errori 4xx non causino retry"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.text = "Not Found"
        mock_get.return_value = mock_response
        
        with pytest.raises(RyuConnectionError):
            connector._make_request('/test')
        
        # Verifica che non ci siano stati retry per errore 404
        assert mock_get.call_count == 1
    
    @patch('requests.Session.get')
    def test_http_error_with_retry_for_server_errors(self, mock_get, connector):
        """Test che errori 5xx causino retry"""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_get.return_value = mock_response
        
        with pytest.raises(RyuConnectionError):
            connector._make_request('/test')
        
        # Verifica che ci siano stati retry per errore 500
        assert mock_get.call_count == connector.retry_config.max_attempts
    
    @patch('requests.Session.get')
    def test_invalid_json_response(self, mock_get, connector):
        """Test gestione risposta JSON malformata"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_get.return_value = mock_response
        
        with pytest.raises(RyuDataError):
            connector._make_request('/test')
    
    @patch('network_state_collector.ryu_connector.RyuConnector._make_request')
    @patch('network_state_collector.ryu_connector.RyuConnector._get_switch_ports')
    def test_get_switches_success(self, mock_get_ports, mock_request, connector):
        """Test recupero switches con successo"""
        # Mock della risposta switches
        switches_data = [
            {"dpid": 1},
            {"dpid": 2}
        ]
        mock_request.return_value = switches_data
        mock_get_ports.return_value = [1, 2, 3, 4]
        
        switches = connector.get_switches()
        
        assert len(switches) == 2
        assert all(isinstance(switch, SwitchInfo) for switch in switches)
        assert switches[0].dpid == "0000000000000001"
        assert switches[1].dpid == "0000000000000002"
        mock_request.assert_called_once_with('/stats/switches')
    
    @patch('network_state_collector.ryu_connector.RyuConnector._make_request')
    def test_get_switches_invalid_response(self, mock_request, connector):
        """Test gestione risposta switches malformata"""
        mock_request.return_value = "invalid response"
        
        with pytest.raises(RyuDataError):
            connector.get_switches()
    
    @patch('network_state_collector.ryu_connector.RyuConnector._make_request')
    def test_get_links_success(self, mock_request, connector):
        """Test recupero links con successo"""
        links_data = [
            {
                "src": {"dpid": 1, "port_no": 1},
                "dst": {"dpid": 2, "port_no": 2}
            },
            {
                "src": {"dpid": 2, "port_no": 1},
                "dst": {"dpid": 3, "port_no": 1}
            }
        ]
        mock_request.return_value = links_data
        
        links = connector.get_links()
        
        assert len(links) == 2
        assert all(isinstance(link, LinkInfo) for link in links)
        assert links[0].src_dpid == "0000000000000001"
        assert links[0].dst_dpid == "0000000000000002"
        mock_request.assert_called_once_with('/v1.0/topology/links')
    
    @patch('network_state_collector.ryu_connector.RyuConnector._make_request')
    def test_get_port_stats_success(self, mock_request, connector):
        """Test recupero statistiche porte con successo"""
        dpid = "1"
        port_stats_data = {
            "1": [
                {
                    "port_no": 1,
                    "rx_packets": 1000,
                    "tx_packets": 800,
                    "rx_bytes": 64000,
                    "tx_bytes": 51200,
                    "rx_errors": 0,
                    "tx_errors": 0,
                    "rx_dropped": 0,
                    "tx_dropped": 0
                },
                {
                    "port_no": "LOCAL",  # Dovrebbe essere esclusa
                    "rx_packets": 100,
                    "tx_packets": 100,
                    "rx_bytes": 6400,
                    "tx_bytes": 6400,
                    "rx_errors": 0,
                    "tx_errors": 0
                }
            ]
        }
        mock_request.return_value = port_stats_data
        
        port_stats = connector.get_port_stats(dpid)
        
        assert len(port_stats) == 1  # LOCAL port esclusa
        assert isinstance(port_stats[0], PortMetrics)
        assert port_stats[0].port_no == 1
        assert port_stats[0].rx_packets == 1000
        mock_request.assert_called_once_with('/stats/port/1')
    
    @patch('network_state_collector.ryu_connector.RyuConnector._make_request')
    def test_get_port_stats_excludes_local_ports(self, mock_request, connector):
        """Test che le porte LOCAL vengano escluse"""
        dpid = "1"
        port_stats_data = {
            "1": [
                {
                    "port_no": "LOCAL",
                    "rx_packets": 100,
                    "tx_packets": 100,
                    "rx_bytes": 6400,
                    "tx_bytes": 6400,
                    "rx_errors": 0,
                    "tx_errors": 0
                }
            ]
        }
        mock_request.return_value = port_stats_data
        
        port_stats = connector.get_port_stats(dpid)
        
        assert len(port_stats) == 0  # Tutte le porte LOCAL escluse
    
    @patch('requests.Session.get')
    def test_is_healthy_success(self, mock_get, connector):
        """Test health check con successo"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response
        
        assert connector.is_healthy() is True
        
        # Verifica che lo stato di salute sia aggiornato
        health_status = connector.get_health_status()
        assert health_status.status == HealthStatus.HEALTHY
        assert health_status.component == ComponentType.RYU_CONNECTOR
        assert "healthy" in health_status.message.lower()
    
    @patch('requests.Session.get')
    def test_is_healthy_failure(self, mock_get, connector):
        """Test health check con fallimento"""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        assert connector.is_healthy() is False
        
        # Verifica che lo stato di salute sia aggiornato
        health_status = connector.get_health_status()
        assert health_status.status == HealthStatus.UNHEALTHY
        assert health_status.component == ComponentType.RYU_CONNECTOR
        assert "unhealthy" in health_status.message.lower()
    
    def test_get_health_status_detailed(self, connector):
        """Test stato di salute dettagliato"""
        health_status = connector.get_health_status()
        
        assert isinstance(health_status, HealthCheck)
        assert health_status.component == ComponentType.RYU_CONNECTOR
        assert health_status.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED, HealthStatus.UNHEALTHY, HealthStatus.UNKNOWN]
        assert 'connection_health' in health_status.details
        assert 'connection_stats' in health_status.details
        assert 'uptime_seconds' in health_status.details
    
    def test_connection_stats(self, connector):
        """Test statistiche di connessione"""
        stats = connector.get_connection_stats()
        
        assert 'total_requests' in stats
        assert 'successful_requests' in stats
        assert 'failed_requests' in stats
        assert 'success_rate' in stats
        assert 'failure_rate' in stats
        assert 'health_status' in stats
        assert 'is_reachable' in stats
        assert 'response_time_ms' in stats
        assert 'consecutive_failures' in stats
        assert 'uptime_seconds' in stats
        
        # Test reset stats
        connector.reset_stats()
        stats = connector.get_connection_stats()
        assert stats['total_requests'] == 0
        assert stats['consecutive_failures'] == 0
    
    def test_backoff_calculation(self, connector):
        """Test calcolo backoff esponenziale"""
        # Mock time.sleep per evitare attese reali
        with patch('time.sleep') as mock_sleep:
            connector._wait_with_backoff(0)
            connector._wait_with_backoff(1)
            connector._wait_with_backoff(2)
        
        # Verifica che sleep sia stato chiamato con valori crescenti
        assert mock_sleep.call_count == 3
        calls = [call[0][0] for call in mock_sleep.call_args_list]
        
        # I valori dovrebbero essere crescenti (con possibile jitter)
        # Verifica almeno che il secondo sia >= del primo
        assert calls[1] >= calls[0] * 0.5  # Considera il jitter
    
    def test_close_session(self, connector):
        """Test chiusura sessione"""
        session_mock = Mock()
        connector.session = session_mock
        
        connector.close()
        
        session_mock.close.assert_called_once()
    
    @patch('requests.Session.get')
    def test_structured_logging_on_success(self, mock_get, connector):
        """Test logging strutturato per richieste riuscite"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"test": "data"}
        mock_get.return_value = mock_response
        
        # Mock structured logger
        connector.logger.structured = Mock()
        
        result = connector._make_request('/test')
        
        assert result == {"test": "data"}
        # Verifica che il logging strutturato sia stato chiamato
        if hasattr(connector.logger, 'structured'):
            connector.logger.structured.assert_called()
    
    @patch('requests.Session.get')
    def test_structured_logging_on_error(self, mock_get, connector):
        """Test logging strutturato per errori"""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        # Mock structured logger
        connector.logger.structured = Mock()
        
        with pytest.raises(RyuConnectionError):
            connector._make_request('/test')
        
        # Verifica che il logging strutturato sia stato chiamato per l'errore
        if hasattr(connector.logger, 'structured'):
            assert connector.logger.structured.call_count >= 1
    
    @patch('requests.Session.get')
    def test_health_degradation_detection(self, mock_get, connector):
        """Test rilevamento degradazione della salute"""
        # Simula fallimenti consecutivi seguiti da successo
        mock_get.side_effect = [
            requests.exceptions.ConnectionError("Error 1"),
            requests.exceptions.ConnectionError("Error 2"),
            requests.exceptions.ConnectionError("Error 3"),
            requests.exceptions.ConnectionError("Error 4"),
            Mock(status_code=200, json=lambda: [])  # Successo finale
        ]
        
        # Esegui diversi health check per accumulare fallimenti
        for _ in range(4):
            connector.is_healthy()
        
        # L'ultimo dovrebbe avere successo ma il sistema potrebbe essere ancora degradato
        result = connector.is_healthy()
        assert result is True  # L'ultimo check dovrebbe avere successo
        
        health_status = connector.get_health_status()
        # Dopo 4 fallimenti consecutivi, anche se l'ultimo ha successo,
        # il sistema potrebbe ancora essere considerato degradato o sano
        assert health_status.status in [HealthStatus.HEALTHY, HealthStatus.DEGRADED]
    
    @patch('requests.Session.get')
    def test_connection_health_tracking(self, mock_get, connector):
        """Test tracciamento della salute della connessione"""
        # Verifica stato iniziale
        stats = connector.get_connection_stats()
        assert stats['consecutive_failures'] == 0
        assert stats['is_reachable'] is False
        
        # Simula una richiesta riuscita
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_get.return_value = mock_response
        
        result = connector.is_healthy()
        assert result is True
        
        stats = connector.get_connection_stats()
        assert stats['is_reachable'] is True
        assert stats['consecutive_failures'] == 0


class TestRyuConnectorPropertyBased:
    """Test basati su proprietà per RyuConnector"""
    
    @given(ryu_config_strategy(), retry_config_strategy())
    @pytest.mark.property
    def test_connector_initialization_property(self, ryu_config, retry_config):
        """
        Feature: network-state-collector, Property 3: Resilienza agli Errori di Connessione
        
        **Valida: Requisiti 1.4, 5.1, 5.2**
        
        Per qualsiasi configurazione valida, il connettore dovrebbe inizializzarsi
        correttamente e mantenere le configurazioni fornite.
        """
        connector = RyuConnector(ryu_config, retry_config)
        
        assert connector.ryu_config == ryu_config
        assert connector.retry_config == retry_config
        assert connector.session is not None
        assert connector._connection_stats['total_requests'] == 0
        
        # Cleanup
        connector.close()
    
    @given(switch_response_strategy())
    @pytest.mark.property
    def test_switches_parsing_property(self, switches_data):
        """
        Feature: network-state-collector, Property 1: Raccolta Completa della Topologia
        
        **Valida: Requisiti 1.1, 1.2**
        
        Per qualsiasi risposta valida dell'API switches, tutti gli switch dovrebbero
        essere parsati correttamente con DPID formattati.
        """
        ryu_config = RyuConfig()
        retry_config = RetryConfig()
        connector = RyuConnector(ryu_config, retry_config)
        
        with patch.object(connector, '_make_request') as mock_request:
            with patch.object(connector, '_get_switch_ports', return_value=[1, 2, 3]):
                mock_request.return_value = switches_data
                
                switches = connector.get_switches()
                
                # Verifica che tutti gli switch siano stati processati
                expected_count = len([s for s in switches_data if s.get('dpid') is not None])
                assert len(switches) == expected_count
                
                # Verifica formattazione DPID
                for switch in switches:
                    assert isinstance(switch, SwitchInfo)
                    assert len(switch.dpid) == 16
                    assert all(c in "0123456789abcdef" for c in switch.dpid)
        
        connector.close()
    
    @given(links_response_strategy())
    @pytest.mark.property
    def test_links_parsing_property(self, links_data):
        """
        Feature: network-state-collector, Property 1: Raccolta Completa della Topologia
        
        **Valida: Requisiti 1.1, 1.2**
        
        Per qualsiasi risposta valida dell'API links, tutti i link dovrebbero
        essere parsati correttamente con DPID formattati.
        """
        ryu_config = RyuConfig()
        retry_config = RetryConfig()
        connector = RyuConnector(ryu_config, retry_config)
        
        with patch.object(connector, '_make_request') as mock_request:
            mock_request.return_value = links_data
            
            links = connector.get_links()
            
            # Verifica che tutti i link validi siano stati processati
            expected_count = len([
                l for l in links_data 
                if l.get('src', {}).get('dpid') is not None and 
                   l.get('dst', {}).get('dpid') is not None
            ])
            assert len(links) == expected_count
            
            # Verifica formattazione DPID
            for link in links:
                assert isinstance(link, LinkInfo)
                assert len(link.src_dpid) == 16
                assert len(link.dst_dpid) == 16
                assert all(c in "0123456789abcdef" for c in link.src_dpid)
                assert all(c in "0123456789abcdef" for c in link.dst_dpid)
        
        connector.close()
    
    @given(port_response_strategy())
    @pytest.mark.property
    def test_port_stats_parsing_property(self, port_stats_data):
        """
        Feature: network-state-collector, Property 5: Raccolta Completa Metriche Porte

        **Valida: Requisiti 2.1, 2.2**

        Per qualsiasi risposta valida dell'API port stats, tutte le metriche dovrebbero
        essere raccolte correttamente escludendo le porte LOCAL.
        """
        ryu_config = RyuConfig()
        retry_config = RetryConfig()
        connector = RyuConnector(ryu_config, retry_config)

        # Il dpid nella risposta è la chiave del dizionario
        dpid_in_response = list(port_stats_data.keys())[0]

        # Conta le porte non-LOCAL nella risposta originale
        original_ports = port_stats_data[dpid_in_response]
        expected_count = len([
            p for p in original_ports 
            if p.get('port_no') != 'LOCAL' and p.get('port_no') is not None
        ])

        # Il codice converte il dpid, quindi dobbiamo assicurarci che il mock
        # restituisca i dati con la chiave corretta dopo la conversione
        # Se dpid ha lunghezza > 2, viene interpretato come hex e convertito in decimale
        if len(dpid_in_response) > 2:
            # Converte da hex a decimale
            dpid_converted = str(int(dpid_in_response, 16))
        else:
            dpid_converted = dpid_in_response
        
        # Crea la risposta mock con la chiave convertita
        mock_response = {dpid_converted: original_ports}

        with patch.object(connector, '_make_request') as mock_request:
            mock_request.return_value = mock_response

            port_stats = connector.get_port_stats(dpid_in_response)

            assert len(port_stats) == expected_count

            # Verifica che tutte le metriche richieste siano presenti
            for port_metric in port_stats:
                assert isinstance(port_metric, PortMetrics)
                assert port_metric.port_no != 'LOCAL'
                assert isinstance(port_metric.rx_packets, int)
                assert isinstance(port_metric.tx_packets, int)
                assert isinstance(port_metric.rx_bytes, int)
                assert isinstance(port_metric.tx_bytes, int)
                assert isinstance(port_metric.rx_errors, int)
                assert isinstance(port_metric.tx_errors, int)

        connector.close()

    
    @given(st.integers(min_value=0, max_value=5))
    @pytest.mark.property
    def test_retry_attempts_property(self, max_attempts):
        """
        Feature: network-state-collector, Property 3: Resilienza agli Errori di Connessione
        
        **Valida: Requisiti 1.4, 5.1, 5.2**
        
        Per qualsiasi numero di tentativi configurato, il connettore dovrebbe
        rispettare il limite e implementare backoff esponenziale.
        """
        assume(max_attempts >= 1)  # Almeno un tentativo
        
        ryu_config = RyuConfig()
        retry_config = RetryConfig(max_attempts=max_attempts, initial_delay=0.01)  # Delay molto piccolo
        connector = RyuConnector(ryu_config, retry_config)
        
        with patch('requests.Session.get') as mock_get:
            with patch('time.sleep'):  # Mock sleep per evitare attese reali
                mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
                
                with pytest.raises(RyuConnectionError):
                    connector._make_request('/test')
                
                # Verifica che il numero di tentativi sia rispettato
                assert mock_get.call_count == max_attempts
        
        connector.close()
    
    @given(st.floats(min_value=0.1, max_value=10.0))
    @pytest.mark.property
    def test_timeout_configuration_property(self, timeout):
        """
        Feature: network-state-collector, Property 3: Resilienza agli Errori di Connessione
        
        **Valida: Requisiti 1.4, 5.1, 5.2**
        
        Per qualsiasi timeout configurato, le richieste dovrebbero rispettare
        il limite di tempo specificato.
        """
        ryu_config = RyuConfig(timeout=timeout)
        retry_config = RetryConfig(max_attempts=1)  # Un solo tentativo per test veloce
        connector = RyuConnector(ryu_config, retry_config)
        
        with patch('requests.Session.get') as mock_get:
            mock_get.return_value.status_code = 200
            mock_get.return_value.json.return_value = {}
            
            connector._make_request('/test')
            
            # Verifica che il timeout sia stato passato alla richiesta
            mock_get.assert_called_once()
            call_kwargs = mock_get.call_args[1]
            assert call_kwargs['timeout'] == timeout
        
        connector.close()