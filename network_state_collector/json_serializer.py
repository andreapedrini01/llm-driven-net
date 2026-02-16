"""
JSONSerializer - Serializzazione e deserializzazione JSON

Implementa serializzazione/deserializzazione consistente con pretty printing
per i dati di rete e l'integrazione LLM.
"""

import json
import logging
from typing import Dict, Any, Optional, Union
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path

from src.models.core import NetworkSnapshot, TopologyData, MetricsData
from src.models.llm import LLMNetworkData, AnomalyIndicator, ContextEmbedding
from .data_validator import ValidationResult


class JSONSerializationError(Exception):
    """Eccezione per errori di serializzazione JSON"""
    pass


class JSONDeserializationError(Exception):
    """Eccezione per errori di deserializzazione JSON"""
    pass


class JSONSerializer:
    """
    Serializzatore JSON per dati di rete
    
    Fornisce serializzazione/deserializzazione consistente con:
    - Pretty printing configurabile per leggibilità
    - Gestione di dataclass e tipi complessi
    - Validazione dei dati serializzati
    - Supporto per diversi formati di output
    """
    
    def __init__(self, 
                 pretty_print: bool = True,
                 indent: int = 2,
                 ensure_ascii: bool = False,
                 sort_keys: bool = True):
        """
        Inizializza il JSONSerializer
        
        Args:
            pretty_print: Se abilitare la formattazione pretty print
            indent: Numero di spazi per l'indentazione
            ensure_ascii: Se forzare caratteri ASCII
            sort_keys: Se ordinare le chiavi alfabeticamente
        """
        self.logger = logging.getLogger(__name__)
        self.pretty_print = pretty_print
        self.indent = indent if pretty_print else None
        self.ensure_ascii = ensure_ascii
        self.sort_keys = sort_keys
        
        self.logger.info("JSONSerializer initialized", extra={
            'component': 'JSONSerializer',
            'pretty_print': pretty_print,
            'indent': indent
        })
    
    def serialize_network_snapshot(self, snapshot: NetworkSnapshot) -> str:
        """
        Serializza un NetworkSnapshot in JSON
        
        Args:
            snapshot: Snapshot da serializzare
            
        Returns:
            Stringa JSON formattata
            
        Raises:
            JSONSerializationError: Se la serializzazione fallisce
        """
        try:
            self.logger.debug("Serializing NetworkSnapshot", extra={
                'component': 'JSONSerializer',
                'timestamp': snapshot.timestamp
            })
            
            # Converte in dizionario serializzabile
            data = self._convert_to_serializable(snapshot)
            
            # Serializza con le opzioni configurate
            json_str = json.dumps(
                data,
                indent=self.indent,
                ensure_ascii=self.ensure_ascii,
                sort_keys=self.sort_keys,
                default=self._json_default
            )
            
            self.logger.debug("NetworkSnapshot serialization completed", extra={
                'component': 'JSONSerializer',
                'json_length': len(json_str)
            })
            
            return json_str
            
        except Exception as e:
            error_msg = f"Failed to serialize NetworkSnapshot: {e}"
            self.logger.error(error_msg, extra={'component': 'JSONSerializer'})
            raise JSONSerializationError(error_msg) from e
    
    def serialize_llm_data(self, llm_data: LLMNetworkData) -> str:
        """
        Serializza dati LLM in JSON
        
        Args:
            llm_data: Dati LLM da serializzare
            
        Returns:
            Stringa JSON formattata
            
        Raises:
            JSONSerializationError: Se la serializzazione fallisce
        """
        try:
            self.logger.debug("Serializing LLMNetworkData", extra={
                'component': 'JSONSerializer'
            })
            
            # Converte in dizionario serializzabile
            data = self._convert_to_serializable(llm_data)
            
            # Serializza con le opzioni configurate
            json_str = json.dumps(
                data,
                indent=self.indent,
                ensure_ascii=self.ensure_ascii,
                sort_keys=self.sort_keys,
                default=self._json_default
            )
            
            self.logger.debug("LLMNetworkData serialization completed", extra={
                'component': 'JSONSerializer',
                'json_length': len(json_str)
            })
            
            return json_str
            
        except Exception as e:
            error_msg = f"Failed to serialize LLMNetworkData: {e}"
            self.logger.error(error_msg, extra={'component': 'JSONSerializer'})
            raise JSONSerializationError(error_msg) from e
    
    def deserialize_network_snapshot(self, json_str: str) -> NetworkSnapshot:
        """
        Deserializza JSON in NetworkSnapshot
        
        Args:
            json_str: Stringa JSON da deserializzare
            
        Returns:
            NetworkSnapshot deserializzato
            
        Raises:
            JSONDeserializationError: Se la deserializzazione fallisce
        """
        try:
            self.logger.debug("Deserializing NetworkSnapshot", extra={
                'component': 'JSONSerializer',
                'json_length': len(json_str)
            })
            
            # Parse JSON
            data = json.loads(json_str)
            
            # Converte in NetworkSnapshot
            snapshot = self._convert_from_dict_to_snapshot(data)
            
            self.logger.debug("NetworkSnapshot deserialization completed", extra={
                'component': 'JSONSerializer',
                'timestamp': snapshot.timestamp
            })
            
            return snapshot
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON format: {e}"
            self.logger.error(error_msg, extra={'component': 'JSONSerializer'})
            raise JSONDeserializationError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to deserialize NetworkSnapshot: {e}"
            self.logger.error(error_msg, extra={'component': 'JSONSerializer'})
            raise JSONDeserializationError(error_msg) from e
    
    def deserialize_llm_data(self, json_str: str) -> LLMNetworkData:
        """
        Deserializza JSON in LLMNetworkData
        
        Args:
            json_str: Stringa JSON da deserializzare
            
        Returns:
            LLMNetworkData deserializzato
            
        Raises:
            JSONDeserializationError: Se la deserializzazione fallisce
        """
        try:
            self.logger.debug("Deserializing LLMNetworkData", extra={
                'component': 'JSONSerializer',
                'json_length': len(json_str)
            })
            
            # Parse JSON
            data = json.loads(json_str)
            
            # Converte in LLMNetworkData
            llm_data = self._convert_from_dict_to_llm_data(data)
            
            self.logger.debug("LLMNetworkData deserialization completed", extra={
                'component': 'JSONSerializer'
            })
            
            return llm_data
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON format: {e}"
            self.logger.error(error_msg, extra={'component': 'JSONSerializer'})
            raise JSONDeserializationError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to deserialize LLMNetworkData: {e}"
            self.logger.error(error_msg, extra={'component': 'JSONSerializer'})
            raise JSONDeserializationError(error_msg) from e
    
    def save_to_file(self, data: Union[NetworkSnapshot, LLMNetworkData], 
                     file_path: Union[str, Path]) -> None:
        """
        Salva dati serializzati in file
        
        Args:
            data: Dati da salvare
            file_path: Percorso del file di destinazione
            
        Raises:
            JSONSerializationError: Se il salvataggio fallisce
        """
        try:
            file_path = Path(file_path)
            
            # Crea directory se non esiste
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Serializza i dati
            if isinstance(data, NetworkSnapshot):
                json_str = self.serialize_network_snapshot(data)
            elif isinstance(data, LLMNetworkData):
                json_str = self.serialize_llm_data(data)
            else:
                raise JSONSerializationError(f"Unsupported data type: {type(data)}")
            
            # Salva nel file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(json_str)
            
            self.logger.info("Data saved to file", extra={
                'component': 'JSONSerializer',
                'file_path': str(file_path),
                'file_size': len(json_str)
            })
            
        except Exception as e:
            error_msg = f"Failed to save data to file {file_path}: {e}"
            self.logger.error(error_msg, extra={'component': 'JSONSerializer'})
            raise JSONSerializationError(error_msg) from e
    
    def load_from_file(self, file_path: Union[str, Path], 
                       data_type: str = 'auto') -> Union[NetworkSnapshot, LLMNetworkData]:
        """
        Carica dati da file JSON
        
        Args:
            file_path: Percorso del file da caricare
            data_type: Tipo di dati ('snapshot', 'llm', 'auto')
            
        Returns:
            Dati deserializzati
            
        Raises:
            JSONDeserializationError: Se il caricamento fallisce
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                raise JSONDeserializationError(f"File not found: {file_path}")
            
            # Legge il file
            with open(file_path, 'r', encoding='utf-8') as f:
                json_str = f.read()
            
            # Determina il tipo di dati se auto
            if data_type == 'auto':
                data_type = self._detect_data_type(json_str)
            
            # Deserializza in base al tipo
            if data_type == 'snapshot':
                data = self.deserialize_network_snapshot(json_str)
            elif data_type == 'llm':
                data = self.deserialize_llm_data(json_str)
            else:
                raise JSONDeserializationError(f"Unknown data type: {data_type}")
            
            self.logger.info("Data loaded from file", extra={
                'component': 'JSONSerializer',
                'file_path': str(file_path),
                'data_type': data_type
            })
            
            return data
            
        except Exception as e:
            error_msg = f"Failed to load data from file {file_path}: {e}"
            self.logger.error(error_msg, extra={'component': 'JSONSerializer'})
            raise JSONDeserializationError(error_msg) from e
    
    def pretty_format(self, json_str: str) -> str:
        """
        Applica pretty formatting a una stringa JSON
        
        Args:
            json_str: Stringa JSON da formattare
            
        Returns:
            Stringa JSON formattata
            
        Raises:
            JSONSerializationError: Se la formattazione fallisce
        """
        try:
            # Parse e ri-serializza con pretty print
            data = json.loads(json_str)
            return json.dumps(
                data,
                indent=self.indent,
                ensure_ascii=self.ensure_ascii,
                sort_keys=self.sort_keys
            )
        except Exception as e:
            error_msg = f"Failed to pretty format JSON: {e}"
            self.logger.error(error_msg, extra={'component': 'JSONSerializer'})
            raise JSONSerializationError(error_msg) from e
    
    def validate_json_format(self, json_str: str) -> ValidationResult:
        """
        Valida il formato JSON
        
        Args:
            json_str: Stringa JSON da validare
            
        Returns:
            Risultato della validazione
        """
        issues = []
        
        try:
            # Tenta il parsing
            json.loads(json_str)
            
            # Verifica se è pretty formatted (se richiesto)
            if self.pretty_print:
                try:
                    pretty_formatted = self.pretty_format(json_str)
                    if json_str.strip() != pretty_formatted.strip():
                        issues.append("JSON is not pretty formatted")
                except:
                    issues.append("JSON cannot be pretty formatted")
            
        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON format: {e}")
        except Exception as e:
            issues.append(f"JSON validation error: {e}")
        
        is_valid = len(issues) == 0
        
        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            quality_score=1.0 if is_valid else 0.0
        )
    
    def _convert_to_serializable(self, obj: Any) -> Any:
        """Converte oggetti in formato serializzabile"""
        if is_dataclass(obj):
            return asdict(obj)
        elif isinstance(obj, dict):
            return {k: self._convert_to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._convert_to_serializable(item) for item in obj]
        else:
            return obj
    
    def _json_default(self, obj: Any) -> Any:
        """Handler per oggetti non serializzabili di default"""
        if hasattr(obj, 'isoformat'):  # datetime objects
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return obj.__dict__
        else:
            return str(obj)
    
    def _convert_from_dict_to_snapshot(self, data: Dict[str, Any]) -> NetworkSnapshot:
        """Converte dizionario in NetworkSnapshot"""
        # Implementazione semplificata - in un sistema reale
        # dovrebbe ricostruire completamente gli oggetti
        from src.models.core import NetworkSnapshot, TopologyData, MetricsData
        
        # Per ora, crea oggetti vuoti con i dati base
        # In una implementazione completa, dovrebbe ricostruire
        # tutti gli oggetti nested correttamente
        
        topology = TopologyData(switches=[], links=[], graph_representation={})
        metrics = MetricsData(port_statistics={}, aggregated_metrics={}, quality_indicators=None)
        
        return NetworkSnapshot(
            timestamp=data.get('timestamp', 0.0),
            topology=topology,
            metrics=metrics,
            derived_metrics=None,
            metadata=data.get('metadata', {})
        )
    
    def _convert_from_dict_to_llm_data(self, data: Dict[str, Any]) -> LLMNetworkData:
        """Converte dizionario in LLMNetworkData"""
        return LLMNetworkData(
            network_context=data.get('network_context', {}),
            performance_vectors=data.get('performance_vectors', []),
            topology_embedding=data.get('topology_embedding', {}),
            temporal_features=data.get('temporal_features', {}),
            anomaly_indicators=[]  # Semplificato per ora
        )
    
    def _detect_data_type(self, json_str: str) -> str:
        """Rileva automaticamente il tipo di dati dal JSON"""
        try:
            data = json.loads(json_str)
            
            # Controlla per campi caratteristici di LLMNetworkData
            if 'network_context' in data and 'performance_vectors' in data:
                return 'llm'
            # Controlla per campi caratteristici di NetworkSnapshot
            elif 'topology' in data and 'metrics' in data:
                return 'snapshot'
            else:
                # Default a snapshot se non chiaro
                return 'snapshot'
                
        except:
            return 'snapshot'  # Default fallback