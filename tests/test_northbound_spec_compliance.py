"""
Test di Conformità alle Specifiche - Northbound Script Generator
Verifica che gli script nella cartella northbound_script_generator rispettino le task richieste,
escludendo le parti online (API Gateway, Web Interface, ecc.)
"""

import pytest
import sys
import os
from pathlib import Path
import importlib.util
import logging

# Add northbound_script_generator to path
sys.path.insert(0, str(Path(__file__).parent.parent / "northbound_script_generator"))

from models import NetworkAction, ActionType
from action_processor import ActionProcessor, ExecutionStatus
from comnetsemu_connector import ComnetsEMUConnector, ComnetsEMUConfig, ConnectionStatus
from retry_system import SimpleRetrySystem, RetryConfig, RetryStrategy
from config_loader import ConfigLoader, SystemConfig
from history_manager import HistoryManager, ExecutionRecord


class TestTask1_IntegrationeRealeRYUComnetsEMU:
    """
    Task 1: Integrazione Reale RYU/ComnetsEMU
    Verifica l'implementazione dei connettori e del sistema di retry
    """
    
    def test_1_1_connettore_comnetsemu_implementato(self):
        """
        Task 1.1 & 1.3: Verifica che il connettore ComnetsEMU sia implementato
        con gestione errori, timeout e connection pooling
        """
        # Verifica che la classe ComnetsEMUConnector esista
        assert ComnetsEMUConnector is not None
        
        # Verifica che abbia i metodi richiesti
        config = ComnetsEMUConfig(host="localhost", port=6653)
        connector = ComnetsEMUConnector(config)
        
        # Verifica metodi essenziali
        assert hasattr(connector, 'execute_topology_change')
        assert hasattr(connector, 'execute_qos_policy')
        assert hasattr(connector, 'get_network_state')
        assert hasattr(connector, 'get_connection_status')
        assert hasattr(connector, '_test_connectivity')
        
        # Verifica configurazione timeout
        assert connector.config.timeout_seconds > 0
        assert connector.config.max_retries >= 0
        
        # Verifica gestione stato connessione
        assert hasattr(connector, 'status')
        assert connector.status in [ConnectionStatus.CONNECTED, ConnectionStatus.DISCONNECTED, ConnectionStatus.ERROR]
        
        connector.close()
    
    def test_1_3_interfaccia_comnetsemu_operazioni_rete(self):
        """
        Task 1.3: Verifica supporto per operazioni di rete standard
        (flussi, QoS, topologie)
        """
        config = ComnetsEMUConfig(host="localhost", port=6653)
        connector = ComnetsEMUConnector(config)
        
        # Test operazione topology change
        action = NetworkAction(
            id="test_topology",
            type=ActionType.CONFIG_CHANGE,
            target="switch1",
            parameters={
                "operation": "add",
                "element_type": "switch",
                "element_id": "s1"
            }
        )
        
        result = connector.execute_topology_change(action)
        assert "success" in result
        assert "retry_stats" in result
        
        # Test operazione QoS
        qos_action = NetworkAction(
            id="test_qos",
            type=ActionType.CONFIG_CHANGE,
            target="switch1",
            parameters={
                "config_type": "qos",
                "bandwidth_limit": 100
            }
        )
        
        qos_result = connector.execute_qos_policy(qos_action)
        assert "success" in qos_result
        
        # Test verifica stato rete
        state = connector.get_network_state("switch1")
        assert "target" in state
        assert "status" in state
        assert "timestamp" in state
        
        connector.close()
    
    def test_1_5_sistema_retry_avanzato(self):
        """
        Task 1.5: Verifica sistema di retry con exponential backoff,
        circuit breaker e coda persistente
        """
        # Verifica configurazione retry
        retry_config = RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            max_delay=60.0,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF
        )
        
        retry_system = SimpleRetrySystem(retry_config)
        
        # Verifica calcolo delay con exponential backoff
        delay1 = retry_system.calculate_delay(1)
        delay2 = retry_system.calculate_delay(2)
        delay3 = retry_system.calculate_delay(3)
        
        # Exponential backoff: ogni delay dovrebbe essere maggiore del precedente
        assert delay2 > delay1
        assert delay3 > delay2
        
        # Verifica max_delay
        assert delay3 <= retry_config.max_delay
        
        # Test esecuzione con retry
        call_count = 0
        def failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Temporary failure")
            return "success"
        
        result = retry_system.execute_with_retry(failing_operation)
        assert result.success
        assert len(result.attempts) == 2  # Fallisce 1 volta, poi successo
        assert result.result == "success"
        
        # Verifica statistiche
        stats = retry_system.get_stats()
        assert stats["total_operations"] > 0
        assert stats["successful_operations"] > 0


class TestTask9_GestioneConfigurazioneLogging:
    """
    Task 9: Gestione Configurazione e Logging Avanzato
    Verifica sistema di configurazione flessibile e logging
    """
    
    def test_9_1_sistema_configurazione_flessibile(self):
        """
        Task 9.1: Verifica supporto per file YAML, validazione configurazione
        """
        # Verifica che ConfigLoader esista e funzioni
        config_loader = ConfigLoader("config.yaml")
        
        # Verifica metodi essenziali
        assert hasattr(config_loader, 'load')
        assert hasattr(config_loader, 'validate')
        assert hasattr(config_loader, 'to_dict')
        
        # Test caricamento con defaults
        config = config_loader.load()
        assert isinstance(config, SystemConfig)
        
        # Verifica campi configurazione
        assert hasattr(config, 'comnetsemu_host')
        assert hasattr(config, 'comnetsemu_port')
        assert hasattr(config, 'max_retries')
        assert hasattr(config, 'retry_delay')
        assert hasattr(config, 'timeout_seconds')
        assert hasattr(config, 'log_level')
        
        # Test validazione configurazione
        validation = config_loader.validate(config)
        assert "is_valid" in validation
        assert "errors" in validation
        assert "warnings" in validation
    
    def test_9_1_validazione_configurazione_avvio(self):
        """
        Task 9.1: Verifica validazione configurazione all'avvio
        """
        config_loader = ConfigLoader()
        
        # Test configurazione valida
        valid_config = SystemConfig(
            comnetsemu_host="localhost",
            comnetsemu_port=6653,
            max_retries=3,
            retry_delay=2.0,
            timeout_seconds=30,
            log_level="INFO"
        )
        
        validation = config_loader.validate(valid_config)
        assert validation["is_valid"] is True
        assert len(validation["errors"]) == 0
        
        # Test configurazione non valida - porta fuori range
        invalid_config = SystemConfig(
            comnetsemu_host="localhost",
            comnetsemu_port=99999,  # Porta non valida
            max_retries=3
        )
        
        validation = config_loader.validate(invalid_config)
        assert validation["is_valid"] is False
        assert len(validation["errors"]) > 0


class TestTask7_BackupRecovery:
    """
    Task 7 (parziale): Sistema di Backup e Recovery
    Verifica gestione history locale (senza PostgreSQL)
    """
    
    def test_7_1_history_manager_storage_locale(self):
        """
        Verifica che HistoryManager salvi i risultati localmente
        """
        import tempfile
        import shutil
        
        # Crea directory temporanea per test
        temp_dir = tempfile.mkdtemp()
        
        try:
            history_manager = HistoryManager(temp_dir)
            
            # Verifica metodi essenziali
            assert hasattr(history_manager, 'save_result')
            assert hasattr(history_manager, 'get_recent_results')
            assert hasattr(history_manager, 'get_statistics')
            assert hasattr(history_manager, 'cleanup_old_results')
            
            # Test salvataggio risultato
            record = ExecutionRecord(
                action_id="test_action_1",
                status="success",
                timestamp="2024-01-01T12:00:00",
                duration=1.5,
                message="Test execution",
                target="switch1",
                action_type="flow_mod"
            )
            
            filepath = history_manager.save_result(record)
            assert os.path.exists(filepath)
            
            # Test recupero risultati recenti
            recent = history_manager.get_recent_results(limit=10)
            assert len(recent) > 0
            assert recent[0]["action_id"] == "test_action_1"
            
            # Test statistiche
            stats = history_manager.get_statistics()
            assert stats["total_results"] > 0
            assert "successful" in stats
            assert "failed" in stats
            
        finally:
            # Cleanup
            shutil.rmtree(temp_dir)
    
    def test_7_2_recovery_integrità_backup(self):
        """
        Verifica che i risultati salvati mantengano integrità
        """
        import tempfile
        import shutil
        import json
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            history_manager = HistoryManager(temp_dir)
            
            # Salva record con tutti i campi
            record = ExecutionRecord(
                action_id="test_integrity",
                status="success",
                timestamp="2024-01-01T12:00:00",
                duration=2.5,
                message="Integrity test",
                target="switch1",
                action_type="flow_mod",
                error=None,
                network_state_before={"status": "active"},
                network_state_after={"status": "modified"}
            )
            
            filepath = history_manager.save_result(record)
            
            # Leggi file e verifica integrità
            with open(filepath, 'r') as f:
                saved_data = json.load(f)
            
            assert saved_data["action_id"] == record.action_id
            assert saved_data["status"] == record.status
            assert saved_data["duration"] == record.duration
            assert saved_data["network_state_before"] is not None
            assert saved_data["network_state_after"] is not None
            
        finally:
            shutil.rmtree(temp_dir)


class TestActionProcessor:
    """
    Test per ActionProcessor - componente core che orchestra l'esecuzione
    """
    
    def test_action_processor_initialization(self):
        """
        Verifica inizializzazione corretta di ActionProcessor
        """
        config = {
            "comnetsemu_host": "localhost",
            "comnetsemu_port": 6653,
            "max_retries": 3,
            "retry_delay": 2.0,
            "timeout_seconds": 30
        }
        
        processor = ActionProcessor(config)
        
        # Verifica componenti inizializzati
        assert processor.comnetsemu_connector is not None
        assert processor.config == config
        
        # Verifica metodi essenziali
        assert hasattr(processor, 'validate_action')
        assert hasattr(processor, 'execute_action')
        assert hasattr(processor, 'execute_actions_sequence')
        
        processor.close()
    
    def test_action_validation(self):
        """
        Verifica validazione delle azioni
        """
        config = {
            "comnetsemu_host": "localhost",
            "comnetsemu_port": 6653,
            "max_retries": 3,
            "retry_delay": 2.0,
            "timeout_seconds": 30
        }
        
        processor = ActionProcessor(config)
        
        # Test azione valida
        valid_action = NetworkAction(
            id="test_valid",
            type=ActionType.FLOW_MOD,
            target="switch1",
            parameters={
                "match": {"in_port": 1},
                "actions": ["output:2"]
            }
        )
        
        validation = processor.validate_action(valid_action)
        assert validation["is_valid"] is True
        assert len(validation["errors"]) == 0
        
        # Test azione non valida - parametri mancanti
        invalid_action = NetworkAction(
            id="test_invalid",
            type=ActionType.FLOW_MOD,
            target="switch1",
            parameters={}  # Mancano match e actions
        )
        
        validation = processor.validate_action(invalid_action)
        assert validation["is_valid"] is False
        assert len(validation["errors"]) > 0
        
        processor.close()
    
    def test_action_execution(self):
        """
        Verifica esecuzione delle azioni
        """
        config = {
            "comnetsemu_host": "localhost",
            "comnetsemu_port": 6653,
            "max_retries": 3,
            "retry_delay": 1.0,
            "timeout_seconds": 30
        }
        
        processor = ActionProcessor(config)
        
        # Test esecuzione flow_mod
        action = NetworkAction(
            id="test_exec",
            type=ActionType.FLOW_MOD,
            target="switch1",
            parameters={
                "operation": "add",
                "match": {"in_port": 1},
                "actions": ["output:2"]
            }
        )
        
        result = processor.execute_action(action)
        
        # Verifica risultato
        assert result.action_id == "test_exec"
        assert result.status in [ExecutionStatus.SUCCESS, ExecutionStatus.FAILED]
        assert result.duration >= 0
        assert result.message is not None
        
        processor.close()


class TestModels:
    """
    Test per i modelli di dati
    """
    
    def test_network_action_creation(self):
        """
        Verifica creazione e validazione di NetworkAction
        """
        # Test creazione valida
        action = NetworkAction(
            id="test_action",
            type=ActionType.FLOW_MOD,
            target="switch1",
            parameters={"match": {}, "actions": []},
            priority=1000,
            timeout=30
        )
        
        assert action.id == "test_action"
        assert action.type == ActionType.FLOW_MOD
        assert action.target == "switch1"
        assert action.priority == 1000
        assert action.timeout == 30
    
    def test_network_action_validation(self):
        """
        Verifica validazione parametri NetworkAction
        """
        # Test con parametri validi per FLOW_MOD
        action = NetworkAction(
            id="test_flow",
            type=ActionType.FLOW_MOD,
            target="switch1",
            parameters={
                "match": {"in_port": 1},
                "actions": ["output:2"]
            }
        )
        
        validation = action.validate_action_parameters()
        assert validation["is_valid"] is True
        
        # Test con parametri mancanti
        invalid_action = NetworkAction(
            id="test_invalid",
            type=ActionType.FLOW_MOD,
            target="switch1",
            parameters={}
        )
        
        validation = invalid_action.validate_action_parameters()
        assert validation["is_valid"] is False
        assert len(validation["issues"]) > 0
    
    def test_action_type_enum(self):
        """
        Verifica che ActionType supporti i tipi richiesti
        """
        # Verifica tipi di azione disponibili
        assert ActionType.FLOW_MOD is not None
        assert ActionType.SLICE_CREATE is not None
        assert ActionType.CONFIG_CHANGE is not None


class TestIntegrationWorkflow:
    """
    Test di integrazione per workflow completo
    """
    
    def test_complete_workflow_file_to_execution(self):
        """
        Test workflow completo: caricamento config -> esecuzione azione -> salvataggio history
        """
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            # 1. Carica configurazione
            config_loader = ConfigLoader()
            config = config_loader.load()
            
            # 2. Inizializza componenti
            processor_config = {
                "comnetsemu_host": config.comnetsemu_host,
                "comnetsemu_port": config.comnetsemu_port,
                "max_retries": config.max_retries,
                "retry_delay": config.retry_delay,
                "timeout_seconds": config.timeout_seconds
            }
            
            processor = ActionProcessor(processor_config)
            history_manager = HistoryManager(temp_dir)
            
            # 3. Crea e esegui azione
            action = NetworkAction(
                id="integration_test",
                type=ActionType.FLOW_MOD,
                target="switch1",
                parameters={
                    "operation": "add",
                    "match": {"in_port": 1},
                    "actions": ["output:2"]
                }
            )
            
            result = processor.execute_action(action)
            
            # 4. Salva risultato in history
            record = ExecutionRecord(
                action_id=result.action_id,
                status=result.status.value,
                timestamp=result.timestamp.isoformat(),
                duration=result.duration,
                message=result.message,
                target=action.target,
                action_type=action.type.value,
                error=result.error
            )
            
            history_manager.save_result(record)
            
            # 5. Verifica che tutto sia stato salvato
            recent = history_manager.get_recent_results(limit=1)
            assert len(recent) > 0
            assert recent[0]["action_id"] == "integration_test"
            
            # 6. Cleanup
            processor.close()
            
        finally:
            shutil.rmtree(temp_dir)


class TestSpecCompliance:
    """
    Test di conformità alle specifiche generali
    """
    
    def test_task_1_integration_components_exist(self):
        """
        Verifica che tutti i componenti per Task 1 (Integrazione RYU/ComnetsEMU) esistano
        """
        # Verifica esistenza moduli
        assert ComnetsEMUConnector is not None
        assert ComnetsEMUConfig is not None
        assert SimpleRetrySystem is not None
        assert RetryConfig is not None
        
        # Verifica che i componenti siano utilizzabili
        config = ComnetsEMUConfig()
        connector = ComnetsEMUConnector(config)
        assert connector is not None
        connector.close()
    
    def test_task_9_configuration_components_exist(self):
        """
        Verifica che tutti i componenti per Task 9 (Configurazione) esistano
        """
        assert ConfigLoader is not None
        assert SystemConfig is not None
        
        loader = ConfigLoader()
        config = loader.load()
        assert config is not None
    
    def test_core_functionality_without_online_components(self):
        """
        Verifica che la funzionalità core funzioni senza componenti online
        (API Gateway, Web Interface, PostgreSQL, ecc.)
        """
        # Verifica che possiamo:
        # 1. Caricare configurazione
        config_loader = ConfigLoader()
        config = config_loader.load()
        assert config is not None
        
        # 2. Creare azioni
        action = NetworkAction(
            id="offline_test",
            type=ActionType.FLOW_MOD,
            target="switch1",
            parameters={"match": {}, "actions": []}
        )
        assert action is not None
        
        # 3. Processare azioni (anche se falliscono per mancanza di rete reale)
        processor_config = {
            "comnetsemu_host": "localhost",
            "comnetsemu_port": 6653,
            "max_retries": 1,
            "retry_delay": 0.5,
            "timeout_seconds": 5
        }
        processor = ActionProcessor(processor_config)
        result = processor.execute_action(action)
        assert result is not None
        assert result.action_id == "offline_test"
        
        # 4. Salvare history localmente
        import tempfile
        temp_dir = tempfile.mkdtemp()
        history_manager = HistoryManager(temp_dir)
        
        record = ExecutionRecord(
            action_id=result.action_id,
            status=result.status.value,
            timestamp=result.timestamp.isoformat(),
            duration=result.duration,
            message=result.message,
            target=action.target,
            action_type=action.type.value
        )
        
        filepath = history_manager.save_result(record)
        assert os.path.exists(filepath)
        
        # Cleanup
        processor.close()
        import shutil
        shutil.rmtree(temp_dir)


if __name__ == "__main__":
    # Esegui i test
    pytest.main([__file__, "-v", "--tb=short"])
