"""
Test per i modelli dati del Network State Collector

Include test unitari e property-based test per validare
la correttezza delle strutture dati e della serializzazione.
"""

import pytest
import json
import time
from hypothesis import given, strategies as st
from llm_integration_module.models.core import (
    NetworkSnapshot, TopologyData, MetricsData,
    SwitchInfo, LinkInfo, PortMetrics, AggregatedMetrics,
    SnapshotMetadata, DerivedMetrics
)


# Strategies per Hypothesis
@st.composite
def dpid_strategy(draw):
    """Genera DPID validi per i test"""
    # Genera un numero intero e lo formatta come DPID
    dpid_int = draw(st.integers(min_value=1, max_value=0xFFFFFFFFFFFFFFFF))
    return f"{dpid_int:016x}"


@st.composite
def switch_info_strategy(draw):
    """Genera SwitchInfo validi per i test"""
    dpid = draw(dpid_strategy())
    ports = draw(st.lists(st.integers(min_value=1, max_value=65535), min_size=1, max_size=48))
    active = draw(st.booleans())
    return SwitchInfo(dpid=dpid, ports=ports, active=active)


@st.composite
def link_info_strategy(draw):
    """Genera LinkInfo validi per i test"""
    src_dpid = draw(dpid_strategy())
    dst_dpid = draw(dpid_strategy())
    src_port = draw(st.integers(min_value=1, max_value=65535))
    dst_port = draw(st.integers(min_value=1, max_value=65535))
    active = draw(st.booleans())
    return LinkInfo(
        src_dpid=src_dpid,
        dst_dpid=dst_dpid,
        src_port=src_port,
        dst_port=dst_port,
        active=active
    )


@st.composite
def topology_data_strategy(draw):
    """Genera TopologyData validi per i test"""
    switches = draw(st.lists(switch_info_strategy(), min_size=1, max_size=10))
    links = draw(st.lists(link_info_strategy(), min_size=0, max_size=20))
    graph_repr = draw(st.dictionaries(st.text(), st.text(), max_size=5))
    return TopologyData(switches=switches, links=links, graph_representation=graph_repr)


@st.composite
def port_metrics_strategy(draw):
    """Genera PortMetrics validi per i test"""
    port_no = draw(st.integers(min_value=1, max_value=65535))
    rx_packets = draw(st.integers(min_value=0, max_value=10**12))
    tx_packets = draw(st.integers(min_value=0, max_value=10**12))
    rx_bytes = draw(st.integers(min_value=0, max_value=10**15))
    tx_bytes = draw(st.integers(min_value=0, max_value=10**15))
    rx_errors = draw(st.integers(min_value=0, max_value=10**6))
    tx_errors = draw(st.integers(min_value=0, max_value=10**6))
    rx_dropped = draw(st.integers(min_value=0, max_value=10**6))
    tx_dropped = draw(st.integers(min_value=0, max_value=10**6))
    
    return PortMetrics(
        port_no=port_no,
        rx_packets=rx_packets,
        tx_packets=tx_packets,
        rx_bytes=rx_bytes,
        tx_bytes=tx_bytes,
        rx_errors=rx_errors,
        tx_errors=tx_errors,
        rx_dropped=rx_dropped,
        tx_dropped=tx_dropped
    )


@st.composite
def metrics_data_strategy(draw):
    """Genera MetricsData validi per i test"""
    # Genera statistiche delle porte per alcuni switch
    num_switches = draw(st.integers(min_value=1, max_value=5))
    port_statistics = {}
    
    for i in range(num_switches):
        dpid = f"{i+1:016x}"
        num_ports = draw(st.integers(min_value=1, max_value=8))
        ports = draw(st.lists(port_metrics_strategy(), min_size=num_ports, max_size=num_ports))
        port_statistics[dpid] = ports
    
    return MetricsData(port_statistics=port_statistics)


@st.composite
def derived_metrics_strategy(draw):
    """Genera DerivedMetrics validi per i test"""
    return DerivedMetrics(
        network_utilization=draw(st.floats(min_value=0.0, max_value=1.0)),
        congestion_level=draw(st.floats(min_value=0.0, max_value=1.0)),
        error_rate=draw(st.floats(min_value=0.0, max_value=1.0)),
        topology_stability=draw(st.floats(min_value=0.0, max_value=1.0)),
        performance_score=draw(st.floats(min_value=0.0, max_value=1.0))
    )


@st.composite
def snapshot_metadata_strategy(draw):
    """Genera SnapshotMetadata validi per i test"""
    return SnapshotMetadata(
        collection_duration_ms=draw(st.floats(min_value=1.0, max_value=10000.0)),
        switches_count=draw(st.integers(min_value=1, max_value=100)),
        links_count=draw(st.integers(min_value=0, max_value=500)),
        total_ports=draw(st.integers(min_value=1, max_value=1000)),
        data_quality_score=draw(st.floats(min_value=0.0, max_value=1.0)),
        errors_encountered=draw(st.lists(st.text(), max_size=5))
    )


@st.composite
def network_snapshot_strategy(draw):
    """Genera NetworkSnapshot validi per i test"""
    # Usa un timestamp fisso per evitare flaky tests
    base_time = 1640995200.0  # 2022-01-01 00:00:00 UTC
    timestamp = draw(st.floats(min_value=base_time - 86400, max_value=base_time + 86400))
    topology = draw(topology_data_strategy())
    metrics = draw(metrics_data_strategy())
    derived_metrics = draw(st.one_of(st.none(), derived_metrics_strategy()))
    metadata = draw(st.one_of(st.none(), snapshot_metadata_strategy()))
    
    return NetworkSnapshot(
        timestamp=timestamp,
        topology=topology,
        metrics=metrics,
        derived_metrics=derived_metrics,
        metadata=metadata
    )


class TestSwitchInfo:
    """Test per la classe SwitchInfo"""
    
    def test_dpid_formatting_from_int(self):
        """Test formattazione DPID da intero"""
        switch = SwitchInfo(dpid=1, ports=[1, 2, 3])
        assert switch.dpid == "0000000000000001"
    
    def test_dpid_formatting_from_hex_string(self):
        """Test formattazione DPID da stringa esadecimale"""
        switch = SwitchInfo(dpid="0x1", ports=[1, 2, 3])
        assert switch.dpid == "0000000000000001"
    
    def test_dpid_formatting_from_clean_hex(self):
        """Test formattazione DPID da hex pulito"""
        switch = SwitchInfo(dpid="1", ports=[1, 2, 3])
        assert switch.dpid == "0000000000000001"
    
    @given(st.integers(min_value=1, max_value=0xFFFFFFFFFFFFFFFF))
    def test_dpid_formatting_property(self, dpid_int):
        """Property test: DPID dovrebbe sempre essere formattato a 16 caratteri"""
        switch = SwitchInfo(dpid=dpid_int, ports=[1])
        assert len(switch.dpid) == 16
        assert all(c in "0123456789abcdef" for c in switch.dpid)


class TestLinkInfo:
    """Test per la classe LinkInfo"""
    
    def test_link_dpid_formatting(self):
        """Test formattazione DPID nei link"""
        link = LinkInfo(src_dpid=1, dst_dpid=2, src_port=1, dst_port=2)
        assert link.src_dpid == "0000000000000001"
        assert link.dst_dpid == "0000000000000002"


class TestPortMetrics:
    """Test per la classe PortMetrics"""
    
    def test_utilization_calculation(self):
        """Test calcolo utilizzo porta"""
        port = PortMetrics(
            port_no=1,
            rx_packets=100,
            tx_packets=100,
            rx_bytes=1000,
            tx_bytes=1000,
            rx_errors=0,
            tx_errors=0
        )
        
        # Con capacità 1Gbps, 2000 bytes = 16000 bits
        utilization = port.calculate_utilization(1000000000)
        expected = (2000 * 8) / 1000000000
        assert abs(utilization - expected) < 0.0001
    
    def test_error_rate_calculation(self):
        """Test calcolo tasso di errore"""
        port = PortMetrics(
            port_no=1,
            rx_packets=100,
            tx_packets=100,
            rx_bytes=1000,
            tx_bytes=1000,
            rx_errors=5,
            tx_errors=5
        )
        
        error_rate = port.calculate_error_rate()
        expected = 10 / 200  # 10 errori su 200 pacchetti totali
        assert abs(error_rate - expected) < 0.0001
    
    def test_congestion_detection(self):
        """Test rilevamento congestione"""
        port = PortMetrics(
            port_no=1,
            rx_packets=100,
            tx_packets=100,
            rx_bytes=900000000,  # 900MB
            tx_bytes=100000000,  # 100MB
            rx_errors=0,
            tx_errors=0
        )
        
        # Con 1GB di dati e capacità 1Gbps, utilizzo = 8Gbps/1Gbps = 8 (capped a 1.0)
        # Dovrebbe essere congestionato (> 0.8)
        assert port.is_congested(threshold=0.8)


class TestTopologyData:
    """Test per la classe TopologyData"""
    
    def test_to_dict_conversion(self):
        """Test conversione in dizionario"""
        switch = SwitchInfo(dpid="0000000000000001", ports=[1, 2])
        link = LinkInfo(
            src_dpid="0000000000000001",
            dst_dpid="0000000000000002",
            src_port=1,
            dst_port=2
        )
        topology = TopologyData(switches=[switch], links=[link])
        
        data = topology.to_dict()
        assert "switches" in data
        assert "links" in data
        assert len(data["switches"]) == 1
        assert len(data["links"]) == 1
    
    def test_from_dict_conversion(self):
        """Test creazione da dizionario"""
        data = {
            "switches": [{
                "dpid": "0000000000000001",
                "ports": [1, 2],
                "active": True
            }],
            "links": [{
                "src_dpid": "0000000000000001",
                "dst_dpid": "0000000000000002",
                "src_port": 1,
                "dst_port": 2,
                "active": True
            }],
            "graph_representation": {}
        }
        
        topology = TopologyData.from_dict(data)
        assert len(topology.switches) == 1
        assert len(topology.links) == 1
        assert topology.switches[0].dpid == "0000000000000001"


class TestMetricsData:
    """Test per la classe MetricsData"""
    
    def test_to_dict_conversion(self):
        """Test conversione in dizionario"""
        port = PortMetrics(
            port_no=1,
            rx_packets=100,
            tx_packets=100,
            rx_bytes=1000,
            tx_bytes=1000,
            rx_errors=0,
            tx_errors=0
        )
        metrics = MetricsData(port_statistics={"0000000000000001": [port]})
        
        data = metrics.to_dict()
        assert "port_statistics" in data
        assert "0000000000000001" in data["port_statistics"]


class TestNetworkSnapshot:
    """Test per la classe NetworkSnapshot"""
    
    def test_json_serialization(self):
        """Test serializzazione JSON"""
        switch = SwitchInfo(dpid="0000000000000001", ports=[1])
        topology = TopologyData(switches=[switch], links=[])
        port = PortMetrics(
            port_no=1, rx_packets=100, tx_packets=100,
            rx_bytes=1000, tx_bytes=1000, rx_errors=0, tx_errors=0
        )
        metrics = MetricsData(port_statistics={"0000000000000001": [port]})
        
        snapshot = NetworkSnapshot(
            timestamp=time.time(),
            topology=topology,
            metrics=metrics
        )
        
        json_str = snapshot.to_json()
        assert isinstance(json_str, str)
        
        # Verifica che sia JSON valido
        parsed = json.loads(json_str)
        assert "timestamp" in parsed
        assert "topology" in parsed
        assert "metrics" in parsed
    
    @given(network_snapshot_strategy())
    @pytest.mark.property
    def test_round_trip_serialization(self, snapshot):
        """
        Feature: network-state-collector, Property 22: Round-trip Serializzazione
        
        **Valida: Requisiti 8.4**
        
        Per qualsiasi oggetto Network_State valido, il parsing seguito dalla 
        serializzazione seguito dal parsing dovrebbe produrre un oggetto equivalente.
        """
        # Serializza in JSON
        json_str = snapshot.to_json()
        
        # Deserializza da JSON
        parsed_snapshot = NetworkSnapshot.from_json(json_str)
        
        # Serializza di nuovo
        json_str_2 = parsed_snapshot.to_json()
        
        # Deserializza di nuovo
        parsed_snapshot_2 = NetworkSnapshot.from_json(json_str_2)
        
        # Verifica che i dati siano equivalenti
        assert parsed_snapshot.timestamp == snapshot.timestamp
        assert len(parsed_snapshot.topology.switches) == len(snapshot.topology.switches)
        assert len(parsed_snapshot.topology.links) == len(snapshot.topology.links)
        assert len(parsed_snapshot.metrics.port_statistics) == len(snapshot.metrics.port_statistics)
        
        # Verifica round-trip completo
        assert parsed_snapshot_2.timestamp == snapshot.timestamp
        assert len(parsed_snapshot_2.topology.switches) == len(snapshot.topology.switches)
    
    @given(topology_data_strategy())
    @pytest.mark.property
    def test_topology_round_trip(self, topology):
        """Property test per round-trip di TopologyData"""
        data_dict = topology.to_dict()
        restored_topology = TopologyData.from_dict(data_dict)
        
        assert len(restored_topology.switches) == len(topology.switches)
        assert len(restored_topology.links) == len(topology.links)
        
        # Verifica DPID formattazione
        for orig_switch, restored_switch in zip(topology.switches, restored_topology.switches):
            assert restored_switch.dpid == orig_switch.dpid
            assert len(restored_switch.dpid) == 16
    
    @given(metrics_data_strategy())
    @pytest.mark.property
    def test_metrics_round_trip(self, metrics):
        """Property test per round-trip di MetricsData"""
        data_dict = metrics.to_dict()
        restored_metrics = MetricsData.from_dict(data_dict)
        
        assert len(restored_metrics.port_statistics) == len(metrics.port_statistics)
        
        for dpid in metrics.port_statistics:
            assert dpid in restored_metrics.port_statistics
            orig_ports = metrics.port_statistics[dpid]
            restored_ports = restored_metrics.port_statistics[dpid]
            assert len(restored_ports) == len(orig_ports)