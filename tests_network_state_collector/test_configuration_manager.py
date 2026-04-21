"""
Test per ConfigurationManager

Testa il caricamento, validazione e gestione delle configurazioni
per diversi ambienti e scenari.
"""

import pytest
import tempfile
import os
import json
import yaml
from pathlib import Path
from unittest.mock import patch, MagicMock

from network_state_collector.configuration_manager import ConfigurationManager, ValidationResult
from llm_integration_module.models.config import CollectorConfig, RyuConfig, RetryConfig, OutputConfig, CollectionConfig, LoggingConfig
from network_state_collector.error_manager import ErrorManager


class TestConfigurationManager:
    """Test per ConfigurationManager"""
    
    @pytest.fixture
    def temp_config_dir(self):
        """Crea una directory temporanea per i test"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def sample_config_dict(self):
        """Configurazione di esempio per i test"""
        return {
            "environment": "test",
            "version": "1.0.0",
            "ryu": {
                "host": "localhost",
                "port": 8080,
                "base_path": "",
                "timeout": 30.0,
                "use_https": False,
                "verify_ssl": True
            },
            "retry": {
                "max_attempts": 3,
                "initial_delay": 1.0,
                "max_delay": 60.0,
                "backoff_factor": 2.0,
                "jitter": True
            },
            "output": {
                "directory": "test_data",
                "filename_pattern": "network_context_{timestamp}.json",
                "latest_filename": "network_context_latest.json",
                "history_directory": "history",
                "embeddings_directory": "embeddings",
                "metadata_directory": "metadata",
                "pretty_print": True,
                "compress_old_files": False,
                "max_history_files": 100
            },
            "collection": {
                "interval": 30.0,
                "continuous_mode": False,
                "detect_topology_changes": True,
                "calculate_derived_metrics": True,
                "validate_data": True,
                "exclude_local_ports": True,
                "parallel_collection": True,
                "max_workers": 4
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file_path": None,
                "max_file_size": 10485760,
                "backup_count": 5,
                "console_output": True,
                "structured_logging": True
            }
        }
    
    @pytest.fixture
    def config_manager(self, temp_config_dir):
        """Crea un ConfigurationManager per i test"""
        return ConfigurationManager(str(temp_config_dir))
    
    def test_init(self, temp_config_dir):
        """Test inizializzazione ConfigurationManager"""
        manager = ConfigurationManager(str(temp_config_dir))
        
        assert manager.config_dir == temp_config_dir
        assert manager.error_manager is not None
        assert manager._current_config is None
        assert manager._config_file_path is None
        assert manager._last_modified is None
        assert len(manager._config_cache) == 0
    
    def test_load_config_yaml(self, config_manager, temp_config_dir, sample_config_dict):
        """Test caricamento configurazione da file YAML"""
        # Crea file di configurazione YAML
        config_file = temp_config_dir / "test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_dict, f)
        
        # Carica configurazione
        config = config_manager.load_config(str(config_file))
        
        assert isinstance(config, CollectorConfig)
        assert config.environment == "test"
        assert config.ryu.host == "localhost"
        assert config.ryu.port == 8080
        assert config.output.directory == "test_data"
        assert config_manager._current_config == config
    
    def test_load_config_json(self, config_manager, temp_config_dir, sample_config_dict):
        """Test caricamento configurazione da file JSON"""
        # Crea file di configurazione JSON
        config_file = temp_config_dir / "test.json"
        with open(config_file, 'w') as f:
            json.dump(sample_config_dict, f)
        
        # Carica configurazione
        config = config_manager.load_config(str(config_file))
        
        assert isinstance(config, CollectorConfig)
        assert config.environment == "test"
        assert config.ryu.host == "localhost"
    
    def test_load_config_by_environment(self, config_manager, temp_config_dir, sample_config_dict):
        """Test caricamento configurazione per ambiente"""
        # Crea file di configurazione per ambiente development
        config_file = temp_config_dir / "development.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_dict, f)
        
        # Carica configurazione per ambiente
        config = config_manager.load_config(environment="development")
        
        assert isinstance(config, CollectorConfig)
        assert config.environment == "test"  # dal file
    
    def test_load_config_file_not_found(self, config_manager):
        """Test errore quando file di configurazione non esiste"""
        with pytest.raises(FileNotFoundError):
            config_manager.load_config("nonexistent.yaml")
    
    def test_load_config_invalid_yaml(self, config_manager, temp_config_dir):
        """Test errore con YAML malformato"""
        config_file = temp_config_dir / "invalid.yaml"
        with open(config_file, 'w') as f:
            f.write("invalid: yaml: content: [")
        
        with pytest.raises(Exception):
            config_manager.load_config(str(config_file))
    
    def test_load_config_invalid_json(self, config_manager, temp_config_dir):
        """Test errore con JSON malformato"""
        config_file = temp_config_dir / "invalid.json"
        with open(config_file, 'w') as f:
            f.write('{"invalid": json}')
        
        with pytest.raises(Exception):
            config_manager.load_config(str(config_file))
    
    @patch.dict(os.environ, {
        'NSC_RYU_HOST': 'test-host',
        'NSC_RYU_PORT': '9090',
        'NSC_RYU_TIMEOUT': '45.0',
        'NSC_RYU_USE_HTTPS': 'true',
        'NSC_OUTPUT_DIR': '/tmp/test',
        'NSC_COLLECTION_INTERVAL': '15.0',
        'NSC_LOG_LEVEL': 'DEBUG'
    })
    def test_environment_overrides(self, config_manager, temp_config_dir, sample_config_dict):
        """Test override da variabili d'ambiente"""
        # Crea file di configurazione
        config_file = temp_config_dir / "test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_dict, f)
        
        # Carica configurazione con override
        config = config_manager.load_config(str(config_file))
        
        assert config.ryu.host == "test-host"
        assert config.ryu.port == 9090
        assert config.ryu.timeout == 45.0
        assert config.ryu.use_https is True
        assert config.output.directory == "/tmp/test"
        assert config.collection.interval == 15.0
        assert config.logging.level == "DEBUG"
    
    def test_validate_config_valid(self, config_manager):
        """Test validazione configurazione valida"""
        config = CollectorConfig()
        result = config_manager.validate_config(config)
        
        assert result.is_valid
        assert len(result.errors) == 0
    
    def test_validate_config_invalid_ryu(self, config_manager):
        """Test validazione configurazione Ryu invalida"""
        config = CollectorConfig()
        config.ryu.host = ""  # Host vuoto
        config.ryu.port = 70000  # Porta invalida
        config.ryu.timeout = -1  # Timeout negativo
        
        result = config_manager.validate_config(config)
        
        assert not result.is_valid
        assert len(result.errors) >= 3
        assert any("host cannot be empty" in error for error in result.errors)
        assert any("port must be between" in error for error in result.errors)
        assert any("timeout must be positive" in error for error in result.errors)
    
    def test_validate_config_invalid_retry(self, config_manager):
        """Test validazione configurazione retry invalida"""
        config = CollectorConfig()
        config.retry.max_attempts = 0
        config.retry.initial_delay = -1
        config.retry.max_delay = 0.5  # Minore di initial_delay (ma initial_delay è negativo)
        config.retry.backoff_factor = 0.5
        
        result = config_manager.validate_config(config)
        
        assert not result.is_valid
        assert len(result.errors) >= 3  # Cambiato da 4 a 3
    
    def test_validate_config_invalid_output(self, config_manager):
        """Test validazione configurazione output invalida"""
        config = CollectorConfig()
        config.output.directory = ""
        config.output.filename_pattern = ""
        config.output.max_history_files = 0
        
        result = config_manager.validate_config(config)
        
        assert not result.is_valid
        assert len(result.errors) >= 3
    
    def test_validate_config_invalid_collection(self, config_manager):
        """Test validazione configurazione collection invalida"""
        config = CollectorConfig()
        config.collection.interval = -1
        config.collection.max_workers = 0
        
        result = config_manager.validate_config(config)
        
        assert not result.is_valid
        assert len(result.errors) >= 2
    
    def test_validate_config_invalid_logging(self, config_manager):
        """Test validazione configurazione logging invalida"""
        config = CollectorConfig()
        config.logging.level = "INVALID"
        config.logging.max_file_size = -1
        config.logging.backup_count = -1
        
        result = config_manager.validate_config(config)
        
        assert not result.is_valid
        assert len(result.errors) >= 3
    
    def test_validate_config_warnings(self, config_manager):
        """Test generazione warning durante validazione"""
        config = CollectorConfig()
        config.ryu.use_https = True
        config.ryu.verify_ssl = False
        config.collection.interval = 0.5  # Molto basso
        config.collection.max_workers = 25  # Molto alto
        
        result = config_manager.validate_config(config)
        
        assert result.is_valid  # Dovrebbe essere valida ma con warning
        assert len(result.warnings) >= 3
    
    def test_get_ryu_endpoint(self, config_manager, temp_config_dir, sample_config_dict):
        """Test ottenimento endpoint Ryu"""
        # Carica configurazione
        config_file = temp_config_dir / "test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_dict, f)
        config_manager.load_config(str(config_file))
        
        endpoint = config_manager.get_ryu_endpoint()
        assert endpoint == "http://localhost:8080"
    
    def test_get_ryu_endpoint_no_config(self, config_manager):
        """Test errore quando non c'è configurazione caricata"""
        with pytest.raises(ValueError, match="No configuration loaded"):
            config_manager.get_ryu_endpoint()
    
    def test_get_output_directory(self, config_manager, temp_config_dir, sample_config_dict):
        """Test ottenimento directory di output"""
        config_file = temp_config_dir / "test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_dict, f)
        config_manager.load_config(str(config_file))
        
        output_dir = config_manager.get_output_directory()
        assert output_dir == Path("test_data")
    
    def test_get_collection_interval(self, config_manager, temp_config_dir, sample_config_dict):
        """Test ottenimento intervallo di raccolta"""
        config_file = temp_config_dir / "test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_dict, f)
        config_manager.load_config(str(config_file))
        
        interval = config_manager.get_collection_interval()
        assert interval == 30.0
    
    def test_get_current_config(self, config_manager, temp_config_dir, sample_config_dict):
        """Test ottenimento configurazione corrente"""
        config_file = temp_config_dir / "test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_dict, f)
        config = config_manager.load_config(str(config_file))
        
        current_config = config_manager.get_current_config()
        assert current_config == config
    
    def test_reload_config(self, config_manager, temp_config_dir, sample_config_dict):
        """Test ricaricamento configurazione modificata"""
        config_file = temp_config_dir / "test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_dict, f)
        
        # Carica configurazione iniziale
        config_manager.load_config(str(config_file))
        original_host = config_manager.get_current_config().ryu.host
        
        # Modifica configurazione
        sample_config_dict["ryu"]["host"] = "modified-host"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_dict, f)
        
        # Simula modifica del timestamp
        import time
        time.sleep(0.1)
        os.utime(config_file, None)
        
        # Ricarica configurazione
        reloaded = config_manager.reload_config()
        
        assert reloaded
        assert config_manager.get_current_config().ryu.host == "modified-host"
        assert config_manager.get_current_config().ryu.host != original_host
    
    def test_reload_config_no_changes(self, config_manager, temp_config_dir, sample_config_dict):
        """Test ricaricamento quando non ci sono modifiche"""
        config_file = temp_config_dir / "test.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(sample_config_dict, f)
        
        config_manager.load_config(str(config_file))
        
        # Nessuna modifica al file
        reloaded = config_manager.reload_config()
        
        assert not reloaded
    
    def test_list_available_environments(self, config_manager, temp_config_dir):
        """Test lista ambienti disponibili"""
        # Crea file di configurazione per diversi ambienti
        environments = ["development", "production", "staging"]
        for env in environments:
            config_file = temp_config_dir / f"{env}.yaml"
            config_file.write_text("environment: " + env)
        
        # Crea anche file da ignorare
        (temp_config_dir / "example.yaml").write_text("environment: example")
        (temp_config_dir / "template.json").write_text('{"environment": "template"}')
        
        available_envs = config_manager.list_available_environments()
        
        assert set(available_envs) == set(environments)
        assert "example" not in available_envs
        assert "template" not in available_envs
    
    def test_create_environment_config_production(self, config_manager):
        """Test creazione configurazione per ambiente production"""
        config = config_manager.create_environment_config("production")
        
        assert config.environment == "production"
        assert config.logging.level == "INFO"
        assert config.logging.console_output is False
        assert config.collection.continuous_mode is True
        assert config.collection.interval == 10.0
        assert config.output.pretty_print is False
        assert config.output.compress_old_files is True
    
    def test_create_environment_config_development(self, config_manager):
        """Test creazione configurazione per ambiente development"""
        config = config_manager.create_environment_config("development")
        
        assert config.environment == "development"
        assert config.logging.level == "DEBUG"
        assert config.logging.console_output is True
        assert config.collection.continuous_mode is False
        assert config.collection.interval == 30.0
        assert config.output.pretty_print is True
    
    def test_create_environment_config_testing(self, config_manager):
        """Test creazione configurazione per ambiente testing"""
        config = config_manager.create_environment_config("testing")
        
        assert config.environment == "testing"
        assert config.logging.level == "WARNING"
        assert config.logging.file_path is None
        assert config.collection.interval == 5.0
        assert config.output.directory == "test_data"
    
    def test_create_environment_config_with_base(self, config_manager):
        """Test creazione configurazione con base personalizzata"""
        base_config = CollectorConfig()
        base_config.ryu.host = "custom-host"
        base_config.ryu.port = 9999
        
        config = config_manager.create_environment_config("custom", base_config)
        
        assert config.environment == "custom"
        assert config.ryu.host == "custom-host"
        assert config.ryu.port == 9999
    
    def test_save_environment_config(self, config_manager, temp_config_dir):
        """Test salvataggio configurazione per ambiente"""
        config = CollectorConfig()
        config.environment = "test_save"
        config.ryu.host = "save-test-host"
        
        config_manager.save_environment_config("test_save", config)
        
        # Verifica che il file sia stato creato
        config_file = temp_config_dir / "test_save.yaml"
        assert config_file.exists()
        
        # Verifica contenuto
        loaded_config = CollectorConfig.load_from_file(str(config_file))
        assert loaded_config.environment == "test_save"
        assert loaded_config.ryu.host == "save-test-host"
    
    def test_convert_env_value_types(self, config_manager):
        """Test conversione tipi per variabili d'ambiente"""
        config_dict = {
            "ryu": {"port": 8080, "use_https": False, "timeout": 30.0},
            "logging": {"level": "INFO"}
        }
        
        # Test conversione int
        result = config_manager._convert_env_value("9090", "ryu", "port", config_dict)
        assert result == 9090
        assert isinstance(result, int)
        
        # Test conversione bool
        result = config_manager._convert_env_value("true", "ryu", "use_https", config_dict)
        assert result is True
        
        result = config_manager._convert_env_value("false", "ryu", "use_https", config_dict)
        assert result is False
        
        # Test conversione float
        result = config_manager._convert_env_value("45.5", "ryu", "timeout", config_dict)
        assert result == 45.5
        assert isinstance(result, float)
        
        # Test conversione string
        result = config_manager._convert_env_value("DEBUG", "logging", "level", config_dict)
        assert result == "DEBUG"
        assert isinstance(result, str)
    
    def test_convert_env_value_invalid(self, config_manager):
        """Test conversione invalida per variabili d'ambiente"""
        config_dict = {"ryu": {"port": 8080}}
        
        # Valore non convertibile
        result = config_manager._convert_env_value("invalid", "ryu", "port", config_dict)
        assert result is None


class TestValidationResult:
    """Test per ValidationResult"""
    
    def test_init(self):
        """Test inizializzazione ValidationResult"""
        result = ValidationResult(is_valid=True)
        
        assert result.is_valid
        assert len(result.errors) == 0
        assert len(result.warnings) == 0
    
    def test_add_error(self):
        """Test aggiunta errore"""
        result = ValidationResult(is_valid=True)
        result.add_error("Test error")
        
        assert not result.is_valid
        assert len(result.errors) == 1
        assert result.errors[0] == "Test error"
    
    def test_add_warning(self):
        """Test aggiunta warning"""
        result = ValidationResult(is_valid=True)
        result.add_warning("Test warning")
        
        assert result.is_valid  # Warning non invalida
        assert len(result.warnings) == 1
        assert result.warnings[0] == "Test warning"
    
    def test_multiple_errors_warnings(self):
        """Test aggiunta multipli errori e warning"""
        result = ValidationResult(is_valid=True)
        
        result.add_error("Error 1")
        result.add_error("Error 2")
        result.add_warning("Warning 1")
        result.add_warning("Warning 2")
        
        assert not result.is_valid
        assert len(result.errors) == 2
        assert len(result.warnings) == 2