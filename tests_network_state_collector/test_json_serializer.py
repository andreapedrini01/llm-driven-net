"""
Test per JSONSerializer

Test per serializzazione/deserializzazione JSON con pretty printing.
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from network_state_collector.json_serializer import (
    JSONSerializer, 
    JSONSerializationError, 
    JSONDeserializationError
)
from src.models.core import (
    NetworkSnapshot, TopologyData, MetricsData, SwitchInfo, LinkInfo, PortMetrics
)
from src.models.llm import LLMNetworkData, AnomalyIndicator
from network_state_collector.data_validator import ValidationResult


class TestJSONSerializer:
    """Test per JSONSerializer"""
    
    def setup_method(self):
        """Setup per ogni test"""
        self.serializer = JSONSerializer(pretty_print=True, indent=2)
        self.serializer_compact = JSONSerializer(pretty_print=False)
        
        # Crea dati di test
        self.test_snapshot = self._create_test_snapshot()
        self.test_llm_data = self._create_test_llm_data()
    
    def _create_test_snapshot(self) -> NetworkSnapshot:
        """Crea NetworkSnapshot di test"""
        switches = [
            SwitchInfo(dpid="0000000000000001", active=True, ports=[1, 2]),
            SwitchInfo(dpid="0000000000000002", active=True, ports=[1, 2])
        ]
        
        links = [
            LinkInfo(
                src_dpid="0000000000000001",
                dst_dpid="0000000000000002",
                src_port=2,
                dst_port=1,
                active=True
            )
        ]
        
        topology = TopologyData(
            switches=switches,
            links=links,
            graph_representation={"nodes": 2, "edges": 1}
        )
        
        port_stats = {
            "0000000000000001": [
                PortMetrics(
                    port_no=1,
                    rx_packets=1000,
                    tx_packets=800,
                    rx_bytes=64000,
                    tx_bytes=51200,
                    rx_errors=0,
                    tx_errors=0,
                    rx_dropped=0,
                    tx_dropped=0
                )
            ]
        }
        
        metrics = MetricsData(
            port_statistics=port_stats,
            aggregated_metrics={},
            quality_indicators=None
        )
        
        return NetworkSnapshot(
            timestamp=1640995200.0,
            topology=topology,
            metrics=metrics,
            derived_metrics=None,
            metadata={"version": "1.0"}
        )
    
    def _create_test_llm_data(self) -> LLMNetworkData:
        """Crea LLMNetworkData di test"""
        return LLMNetworkData(
            network_context={
                "topology": {
                    "nodes": ["0000000000000001", "0000000000000002"],
                    "edges": [{"src": "0000000000000001", "dst": "0000000000000002"}]
                },
                "performance": {
                    "utilization_vectors": [[0.1, 0.01], [0.2, 0.02]],
                    "error_rates": [0.01, 0.02]
                }
            },
            performance_vectors=[[0.1, 0.01, 100.0], [0.2, 0.02, 200.0]],
            topology_embedding={
                "adjacency_matrix": [[0, 1], [1, 0]],
                "node_degrees": [1, 1]
            },
            temporal_features={
                "timestamp": 1640995200.0,
                "hour_of_day": 12,
                "is_weekend": False
            },
            anomaly_indicators=[
                AnomalyIndicator(
                    type="test_anomaly",
                    severity=0.5,
                    description="Test anomaly",
                    affected_components=["test"],
                    timestamp=1640995200.0,
                    confidence=0.9
                )
            ]
        )
    
    def test_init_default_settings(self):
        """Test inizializzazione con impostazioni default"""
        serializer = JSONSerializer()
        
        assert serializer.pretty_print is True
        assert serializer.indent == 2
        assert serializer.ensure_ascii is False
        assert serializer.sort_keys is True
    
    def test_init_custom_settings(self):
        """Test inizializzazione con impostazioni personalizzate"""
        serializer = JSONSerializer(
            pretty_print=False,
            indent=4,
            ensure_ascii=True,
            sort_keys=False
        )
        
        assert serializer.pretty_print is False
        assert serializer.indent is None  # None quando pretty_print=False
        assert serializer.ensure_ascii is True
        assert serializer.sort_keys is False
    
    def test_serialize_network_snapshot_pretty(self):
        """Test serializzazione NetworkSnapshot con pretty print"""
        json_str = self.serializer.serialize_network_snapshot(self.test_snapshot)
        
        # Verifica che sia JSON valido
        data = json.loads(json_str)
        assert isinstance(data, dict)
        
        # Verifica presenza campi principali
        assert "timestamp" in data
        assert "topology" in data
        assert "metrics" in data
        assert "metadata" in data
        
        # Verifica pretty formatting
        assert "\n" in json_str  # Deve contenere newline
        assert "  " in json_str  # Deve contenere indentazione
    
    def test_serialize_network_snapshot_compact(self):
        """Test serializzazione NetworkSnapshot compatta"""
        json_str = self.serializer_compact.serialize_network_snapshot(self.test_snapshot)
        
        # Verifica che sia JSON valido
        data = json.loads(json_str)
        assert isinstance(data, dict)
        
        # Verifica formato compatto
        assert "\n" not in json_str  # Non deve contenere newline
    
    def test_serialize_llm_data_pretty(self):
        """Test serializzazione LLMNetworkData con pretty print"""
        json_str = self.serializer.serialize_llm_data(self.test_llm_data)
        
        # Verifica che sia JSON valido
        data = json.loads(json_str)
        assert isinstance(data, dict)
        
        # Verifica presenza campi principali
        assert "network_context" in data
        assert "performance_vectors" in data
        assert "topology_embedding" in data
        assert "temporal_features" in data
        assert "anomaly_indicators" in data
        
        # Verifica pretty formatting
        assert "\n" in json_str
        assert "  " in json_str
    
    def test_serialize_llm_data_compact(self):
        """Test serializzazione LLMNetworkData compatta"""
        json_str = self.serializer_compact.serialize_llm_data(self.test_llm_data)
        
        # Verifica che sia JSON valido
        data = json.loads(json_str)
        assert isinstance(data, dict)
        
        # Verifica formato compatto
        assert "\n" not in json_str
    
    def test_deserialize_network_snapshot(self):
        """Test deserializzazione NetworkSnapshot"""
        # Serializza e poi deserializza
        json_str = self.serializer.serialize_network_snapshot(self.test_snapshot)
        deserialized = self.serializer.deserialize_network_snapshot(json_str)
        
        # Verifica che sia un NetworkSnapshot
        assert isinstance(deserialized, NetworkSnapshot)
        assert deserialized.timestamp == self.test_snapshot.timestamp
    
    def test_deserialize_llm_data(self):
        """Test deserializzazione LLMNetworkData"""
        # Serializza e poi deserializza
        json_str = self.serializer.serialize_llm_data(self.test_llm_data)
        deserialized = self.serializer.deserialize_llm_data(json_str)
        
        # Verifica che sia LLMNetworkData
        assert isinstance(deserialized, LLMNetworkData)
        assert deserialized.network_context == self.test_llm_data.network_context
    
    def test_serialize_invalid_data_type(self):
        """Test serializzazione con tipo dati non supportato"""
        with pytest.raises(JSONSerializationError):
            # Passa un oggetto che non è dataclass
            self.serializer.serialize_network_snapshot("invalid")
    
    def test_deserialize_invalid_json(self):
        """Test deserializzazione con JSON non valido"""
        with pytest.raises(JSONDeserializationError):
            self.serializer.deserialize_network_snapshot("invalid json")
    
    def test_deserialize_empty_json(self):
        """Test deserializzazione con JSON vuoto"""
        # Il deserializzatore dovrebbe gestire JSON vuoto senza errore
        # ma creare un oggetto con valori di default
        result = self.serializer.deserialize_network_snapshot("{}")
        assert isinstance(result, NetworkSnapshot)
        assert result.timestamp == 0.0
    
    def test_save_to_file_network_snapshot(self):
        """Test salvataggio NetworkSnapshot su file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_snapshot.json"
            
            self.serializer.save_to_file(self.test_snapshot, file_path)
            
            # Verifica che il file sia stato creato
            assert file_path.exists()
            
            # Verifica contenuto
            with open(file_path, 'r') as f:
                content = f.read()
            
            data = json.loads(content)
            assert "timestamp" in data
            assert "topology" in data
    
    def test_save_to_file_llm_data(self):
        """Test salvataggio LLMNetworkData su file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_llm.json"
            
            self.serializer.save_to_file(self.test_llm_data, file_path)
            
            # Verifica che il file sia stato creato
            assert file_path.exists()
            
            # Verifica contenuto
            with open(file_path, 'r') as f:
                content = f.read()
            
            data = json.loads(content)
            assert "network_context" in data
            assert "performance_vectors" in data
    
    def test_save_to_file_creates_directory(self):
        """Test che save_to_file crei le directory necessarie"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "subdir" / "test.json"
            
            self.serializer.save_to_file(self.test_snapshot, file_path)
            
            # Verifica che directory e file siano stati creati
            assert file_path.parent.exists()
            assert file_path.exists()
    
    def test_save_to_file_unsupported_type(self):
        """Test salvataggio con tipo non supportato"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.json"
            
            with pytest.raises(JSONSerializationError):
                self.serializer.save_to_file("unsupported", file_path)
    
    def test_load_from_file_network_snapshot(self):
        """Test caricamento NetworkSnapshot da file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_snapshot.json"
            
            # Salva prima
            self.serializer.save_to_file(self.test_snapshot, file_path)
            
            # Carica
            loaded = self.serializer.load_from_file(file_path, 'snapshot')
            
            assert isinstance(loaded, NetworkSnapshot)
            assert loaded.timestamp == self.test_snapshot.timestamp
    
    def test_load_from_file_llm_data(self):
        """Test caricamento LLMNetworkData da file"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_llm.json"
            
            # Salva prima
            self.serializer.save_to_file(self.test_llm_data, file_path)
            
            # Carica
            loaded = self.serializer.load_from_file(file_path, 'llm')
            
            assert isinstance(loaded, LLMNetworkData)
            assert loaded.network_context == self.test_llm_data.network_context
    
    def test_load_from_file_auto_detect(self):
        """Test caricamento con rilevamento automatico tipo"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test_llm.json"
            
            # Salva LLMNetworkData
            self.serializer.save_to_file(self.test_llm_data, file_path)
            
            # Carica con auto-detect
            loaded = self.serializer.load_from_file(file_path, 'auto')
            
            assert isinstance(loaded, LLMNetworkData)
    
    def test_load_from_file_not_found(self):
        """Test caricamento file inesistente"""
        with pytest.raises(JSONDeserializationError):
            self.serializer.load_from_file("nonexistent.json")
    
    def test_load_from_file_unknown_type(self):
        """Test caricamento con tipo sconosciuto"""
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.json"
            
            # Crea file vuoto
            with open(file_path, 'w') as f:
                f.write('{}')
            
            with pytest.raises(JSONDeserializationError):
                self.serializer.load_from_file(file_path, 'unknown')
    
    def test_pretty_format_valid_json(self):
        """Test pretty formatting di JSON valido"""
        compact_json = '{"a":1,"b":2}'
        pretty_json = self.serializer.pretty_format(compact_json)
        
        # Verifica che sia formattato
        assert "\n" in pretty_json
        assert "  " in pretty_json
        
        # Verifica che il contenuto sia lo stesso
        assert json.loads(compact_json) == json.loads(pretty_json)
    
    def test_pretty_format_invalid_json(self):
        """Test pretty formatting di JSON non valido"""
        with pytest.raises(JSONSerializationError):
            self.serializer.pretty_format("invalid json")
    
    def test_validate_json_format_valid(self):
        """Test validazione JSON valido"""
        # Usa JSON già pretty formatted per questo test
        valid_json = '{\n  "test": "value"\n}'
        result = self.serializer.validate_json_format(valid_json)
        
        assert result.is_valid is True
        assert len(result.issues) == 0
        assert result.quality_score == 1.0
    
    def test_validate_json_format_invalid(self):
        """Test validazione JSON non valido"""
        invalid_json = '{"test": invalid}'
        result = self.serializer.validate_json_format(invalid_json)
        
        assert result.is_valid is False
        assert len(result.issues) > 0
        assert result.quality_score == 0.0
    
    def test_validate_json_format_not_pretty(self):
        """Test validazione JSON non pretty formatted"""
        compact_json = '{"a":1,"b":2}'
        result = self.serializer.validate_json_format(compact_json)
        
        # Dovrebbe essere valido ma segnalare che non è pretty formatted
        assert result.is_valid is False  # Perché non è pretty formatted
        assert any("not pretty formatted" in issue for issue in result.issues)
    
    def test_detect_data_type_llm(self):
        """Test rilevamento automatico tipo LLM"""
        json_str = '{"network_context": {}, "performance_vectors": []}'
        data_type = self.serializer._detect_data_type(json_str)
        
        assert data_type == 'llm'
    
    def test_detect_data_type_snapshot(self):
        """Test rilevamento automatico tipo snapshot"""
        json_str = '{"topology": {}, "metrics": {}}'
        data_type = self.serializer._detect_data_type(json_str)
        
        assert data_type == 'snapshot'
    
    def test_detect_data_type_unknown(self):
        """Test rilevamento automatico tipo sconosciuto"""
        json_str = '{"unknown": "data"}'
        data_type = self.serializer._detect_data_type(json_str)
        
        assert data_type == 'snapshot'  # Default fallback
    
    def test_detect_data_type_invalid_json(self):
        """Test rilevamento automatico con JSON non valido"""
        data_type = self.serializer._detect_data_type('invalid json')
        
        assert data_type == 'snapshot'  # Default fallback
    
    def test_json_default_datetime(self):
        """Test handler per oggetti datetime"""
        from datetime import datetime
        
        dt = datetime(2024, 1, 1, 12, 0, 0)
        result = self.serializer._json_default(dt)
        
        assert isinstance(result, str)
        assert "2024-01-01T12:00:00" in result
    
    def test_json_default_object_with_dict(self):
        """Test handler per oggetti con __dict__"""
        class TestObj:
            def __init__(self):
                self.value = 42
        
        obj = TestObj()
        result = self.serializer._json_default(obj)
        
        assert result == {"value": 42}
    
    def test_json_default_fallback(self):
        """Test handler fallback per oggetti sconosciuti"""
        result = self.serializer._json_default(42)
        
        assert result == "42"
    
    def test_convert_to_serializable_dataclass(self):
        """Test conversione dataclass in dizionario"""
        from dataclasses import dataclass
        
        @dataclass
        class TestData:
            value: int
        
        obj = TestData(value=42)
        result = self.serializer._convert_to_serializable(obj)
        
        assert result == {"value": 42}
    
    def test_convert_to_serializable_dict(self):
        """Test conversione dizionario nested"""
        data = {"a": {"b": [1, 2, 3]}}
        result = self.serializer._convert_to_serializable(data)
        
        assert result == data
    
    def test_convert_to_serializable_list(self):
        """Test conversione lista"""
        data = [1, 2, {"a": 3}]
        result = self.serializer._convert_to_serializable(data)
        
        assert result == data
    
    def test_convert_to_serializable_primitive(self):
        """Test conversione tipi primitivi"""
        assert self.serializer._convert_to_serializable(42) == 42
        assert self.serializer._convert_to_serializable("test") == "test"
        assert self.serializer._convert_to_serializable(True) is True
    
    @patch('network_state_collector.json_serializer.json.dumps')
    def test_serialize_network_snapshot_json_error(self, mock_dumps):
        """Test gestione errore durante serializzazione"""
        mock_dumps.side_effect = Exception("JSON error")
        
        with pytest.raises(JSONSerializationError):
            self.serializer.serialize_network_snapshot(self.test_snapshot)
    
    @patch('network_state_collector.json_serializer.json.dumps')
    def test_serialize_llm_data_json_error(self, mock_dumps):
        """Test gestione errore durante serializzazione LLM"""
        mock_dumps.side_effect = Exception("JSON error")
        
        with pytest.raises(JSONSerializationError):
            self.serializer.serialize_llm_data(self.test_llm_data)
    
    def test_round_trip_serialization_snapshot(self):
        """Test round-trip serializzazione NetworkSnapshot"""
        # Serializza
        json_str = self.serializer.serialize_network_snapshot(self.test_snapshot)
        
        # Deserializza
        deserialized = self.serializer.deserialize_network_snapshot(json_str)
        
        # Verifica che i dati principali siano preservati
        assert deserialized.timestamp == self.test_snapshot.timestamp
        assert isinstance(deserialized, NetworkSnapshot)
    
    def test_round_trip_serialization_llm(self):
        """Test round-trip serializzazione LLMNetworkData"""
        # Serializza
        json_str = self.serializer.serialize_llm_data(self.test_llm_data)
        
        # Deserializza
        deserialized = self.serializer.deserialize_llm_data(json_str)
        
        # Verifica che i dati principali siano preservati
        assert deserialized.network_context == self.test_llm_data.network_context
        assert isinstance(deserialized, LLMNetworkData)


class TestJSONSerializerIntegration:
    """Test di integrazione per JSONSerializer"""
    
    def test_file_operations_workflow(self):
        """Test workflow completo di operazioni su file"""
        serializer = JSONSerializer(pretty_print=True)
        
        # Crea dati di test
        llm_data = LLMNetworkData(
            network_context={"test": "data"},
            performance_vectors=[[1.0, 2.0]],
            topology_embedding={"nodes": 2},
            temporal_features={"timestamp": 1640995200.0},
            anomaly_indicators=[]
        )
        
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "integration_test.json"
            
            # Salva
            serializer.save_to_file(llm_data, file_path)
            
            # Carica
            loaded = serializer.load_from_file(file_path, 'auto')
            
            # Verifica
            assert isinstance(loaded, LLMNetworkData)
            assert loaded.network_context == llm_data.network_context
            assert loaded.performance_vectors == llm_data.performance_vectors
    
    def test_pretty_print_consistency(self):
        """Test consistenza pretty print tra serializzazioni"""
        serializer = JSONSerializer(pretty_print=True, indent=2, sort_keys=True)
        
        data = {"z": 3, "a": 1, "m": 2}
        
        # Serializza due volte
        json1 = json.dumps(data, indent=2, sort_keys=True)
        json2 = serializer.pretty_format(json.dumps(data))
        
        # Dovrebbero essere identici
        assert json1 == json2
    
    def test_error_handling_chain(self):
        """Test catena di gestione errori"""
        serializer = JSONSerializer()
        
        # Test errore serializzazione -> salvataggio
        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "error_test.json"
            
            with pytest.raises(JSONSerializationError):
                serializer.save_to_file("invalid_data", file_path)
            
            # Il file non dovrebbe essere stato creato
            assert not file_path.exists()