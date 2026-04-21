"""
Modelli di configurazione per Network State Collector

Contiene le dataclass per la configurazione del sistema,
inclusi parametri di connessione, retry logic e output.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from pathlib import Path
import json

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    yaml = None  # type: ignore


@dataclass
class RetryConfig:
    """Configurazione per la logica di retry"""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "max_attempts": self.max_attempts,
            "initial_delay": self.initial_delay,
            "max_delay": self.max_delay,
            "backoff_factor": self.backoff_factor,
            "jitter": self.jitter
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RetryConfig':
        """Crea istanza da dizionario"""
        return cls(
            max_attempts=data.get("max_attempts", 3),
            initial_delay=data.get("initial_delay", 1.0),
            max_delay=data.get("max_delay", 60.0),
            backoff_factor=data.get("backoff_factor", 2.0),
            jitter=data.get("jitter", True)
        )


@dataclass
class RyuConfig:
    """Configurazione per la connessione al controller Ryu"""
    host: str = "localhost"
    port: int = 8080
    base_path: str = ""
    timeout: float = 30.0
    use_https: bool = False
    verify_ssl: bool = True
    
    @property
    def base_url(self) -> str:
        """Costruisce l'URL base per le API Ryu"""
        protocol = "https" if self.use_https else "http"
        base = f"{protocol}://{self.host}:{self.port}"
        if self.base_path:
            base += f"/{self.base_path.strip('/')}"
        return base
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "host": self.host,
            "port": self.port,
            "base_path": self.base_path,
            "timeout": self.timeout,
            "use_https": self.use_https,
            "verify_ssl": self.verify_ssl
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RyuConfig':
        """Crea istanza da dizionario"""
        return cls(
            host=data.get("host", "localhost"),
            port=data.get("port", 8080),
            base_path=data.get("base_path", ""),
            timeout=data.get("timeout", 30.0),
            use_https=data.get("use_https", False),
            verify_ssl=data.get("verify_ssl", True)
        )


@dataclass
class OutputConfig:
    """Configurazione per l'output dei dati"""
    directory: str = "data"
    filename_pattern: str = "network_context_{timestamp}.json"
    latest_filename: str = "network_context_latest.json"
    history_directory: str = "network_context_history"
    embeddings_directory: str = "embeddings"
    metadata_directory: str = "metadata"
    pretty_print: bool = True
    compress_old_files: bool = False
    max_history_files: int = 1000
    
    def get_output_path(self) -> Path:
        """Restituisce il path della directory di output"""
        return Path(self.directory)
    
    def get_history_path(self) -> Path:
        """Restituisce il path della directory storico"""
        return self.get_output_path() / self.history_directory
    
    def get_embeddings_path(self) -> Path:
        """Restituisce il path della directory embeddings"""
        return self.get_output_path() / self.embeddings_directory
    
    def get_metadata_path(self) -> Path:
        """Restituisce il path della directory metadata"""
        return self.get_output_path() / self.metadata_directory
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "directory": self.directory,
            "filename_pattern": self.filename_pattern,
            "latest_filename": self.latest_filename,
            "history_directory": self.history_directory,
            "embeddings_directory": self.embeddings_directory,
            "metadata_directory": self.metadata_directory,
            "pretty_print": self.pretty_print,
            "compress_old_files": self.compress_old_files,
            "max_history_files": self.max_history_files
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OutputConfig':
        """Crea istanza da dizionario"""
        return cls(
            directory=data.get("directory", "data"),
            filename_pattern=data.get("filename_pattern", "network_context_{timestamp}.json"),
            latest_filename=data.get("latest_filename", "network_context_latest.json"),
            history_directory=data.get("history_directory", "network_context_history"),
            embeddings_directory=data.get("embeddings_directory", "embeddings"),
            metadata_directory=data.get("metadata_directory", "metadata"),
            pretty_print=data.get("pretty_print", True),
            compress_old_files=data.get("compress_old_files", False),
            max_history_files=data.get("max_history_files", 1000)
        )


@dataclass
class CollectionConfig:
    """Configurazione per la raccolta dati"""
    interval: float = 30.0  # secondi
    continuous_mode: bool = False
    detect_topology_changes: bool = True
    calculate_derived_metrics: bool = True
    validate_data: bool = True
    exclude_local_ports: bool = True
    parallel_collection: bool = True
    max_workers: int = 4
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "interval": self.interval,
            "continuous_mode": self.continuous_mode,
            "detect_topology_changes": self.detect_topology_changes,
            "calculate_derived_metrics": self.calculate_derived_metrics,
            "validate_data": self.validate_data,
            "exclude_local_ports": self.exclude_local_ports,
            "parallel_collection": self.parallel_collection,
            "max_workers": self.max_workers
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CollectionConfig':
        """Crea istanza da dizionario"""
        return cls(
            interval=data.get("interval", 30.0),
            continuous_mode=data.get("continuous_mode", False),
            detect_topology_changes=data.get("detect_topology_changes", True),
            calculate_derived_metrics=data.get("calculate_derived_metrics", True),
            validate_data=data.get("validate_data", True),
            exclude_local_ports=data.get("exclude_local_ports", True),
            parallel_collection=data.get("parallel_collection", True),
            max_workers=data.get("max_workers", 4)
        )


@dataclass
class LoggingConfig:
    """Configurazione per il logging"""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    file_path: Optional[str] = None
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    console_output: bool = True
    structured_logging: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "level": self.level,
            "format": self.format,
            "file_path": self.file_path,
            "max_file_size": self.max_file_size,
            "backup_count": self.backup_count,
            "console_output": self.console_output,
            "structured_logging": self.structured_logging
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LoggingConfig':
        """Crea istanza da dizionario"""
        return cls(
            level=data.get("level", "INFO"),
            format=data.get("format", "%(asctime)s - %(name)s - %(levelname)s - %(message)s"),
            file_path=data.get("file_path"),
            max_file_size=data.get("max_file_size", 10 * 1024 * 1024),
            backup_count=data.get("backup_count", 5),
            console_output=data.get("console_output", True),
            structured_logging=data.get("structured_logging", True)
        )


@dataclass
class CollectorConfig:
    """Configurazione principale del Network State Collector"""
    ryu: RyuConfig = field(default_factory=RyuConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    output: OutputConfig = field(default_factory=OutputConfig)
    collection: CollectionConfig = field(default_factory=CollectionConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    environment: str = "development"
    version: str = "1.0.0"
    
    def to_dict(self) -> Dict[str, Any]:
        """Converte in dizionario per serializzazione"""
        return {
            "ryu": self.ryu.to_dict(),
            "retry": self.retry.to_dict(),
            "output": self.output.to_dict(),
            "collection": self.collection.to_dict(),
            "logging": self.logging.to_dict(),
            "environment": self.environment,
            "version": self.version
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CollectorConfig':
        """Crea istanza da dizionario"""
        return cls(
            ryu=RyuConfig.from_dict(data.get("ryu", {})),
            retry=RetryConfig.from_dict(data.get("retry", {})),
            output=OutputConfig.from_dict(data.get("output", {})),
            collection=CollectionConfig.from_dict(data.get("collection", {})),
            logging=LoggingConfig.from_dict(data.get("logging", {})),
            environment=data.get("environment", "development"),
            version=data.get("version", "1.0.0")
        )
    
    def to_json(self, indent: int = 2) -> str:
        """Serializza in JSON con pretty printing"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'CollectorConfig':
        """Crea istanza da stringa JSON"""
        data = json.loads(json_str)
        return cls.from_dict(data)
    
    def to_yaml(self) -> str:
        """Serializza in YAML"""
        if not HAS_YAML:
            raise ImportError("PyYAML is required for YAML serialization. Install with: pip install pyyaml")
        return yaml.dump(self.to_dict(), default_flow_style=False, allow_unicode=True)
    
    @classmethod
    def from_yaml(cls, yaml_str: str) -> 'CollectorConfig':
        """Crea istanza da stringa YAML"""
        if not HAS_YAML:
            raise ImportError("PyYAML is required for YAML parsing. Install with: pip install pyyaml")
        data = yaml.safe_load(yaml_str)
        return cls.from_dict(data)
    
    @classmethod
    def load_from_file(cls, file_path: str) -> 'CollectorConfig':
        """Carica configurazione da file (JSON o YAML)"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        content = path.read_text(encoding='utf-8')
        
        if path.suffix.lower() in ['.yaml', '.yml']:
            if not HAS_YAML:
                raise ImportError("PyYAML is required for YAML files. Install with: pip install pyyaml")
            return cls.from_yaml(content)
        elif path.suffix.lower() == '.json':
            return cls.from_json(content)
        else:
            # Prova prima YAML (se disponibile), poi JSON
            if HAS_YAML:
                try:
                    return cls.from_yaml(content)
                except Exception:
                    pass
            return cls.from_json(content)
    
    def save_to_file(self, file_path: str, format: str = "auto") -> None:
        """Salva configurazione su file"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        if format == "auto":
            format = "yaml" if path.suffix.lower() in ['.yaml', '.yml'] else "json"
        
        if format == "yaml":
            content = self.to_yaml()
        else:
            content = self.to_json()
        
        path.write_text(content, encoding='utf-8')