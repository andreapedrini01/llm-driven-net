#!/usr/bin/env python3
"""
Main Integration Script
Integra i tre moduli per monitorare e gestire la rete ComnetsEmu:
- network_state_collector: raccoglie lo stato della rete
- src/services (LLM module): interpreta intenti e propone azioni
- northbound_script_generator: applica le azioni validate alla rete
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List

# Import moduli esistenti
from network_state_collector.collector import NetworkStateCollector
from src.models import CollectorConfig
from src.services.intent_parser import IntentParser
from src.services.chatgpt_client import ChatGPTClient
from src.services.context_analyzer import ContextAnalyzer
from src.services.action_sequencer import ActionSequencer
from src.services.validator import Validator
from src.services.action_output import ActionOutputService
from src.services.prompt_engineering import PromptEngineeringSystem
from northbound_script_generator.action_processor import ActionProcessor
from northbound_script_generator.models import NetworkAction
from northbound_script_generator.config_loader import ConfigLoader


def setup_logging():
    """Configura il logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('integration.log')
        ]
    )


def main():
    """Entry point principale"""
    setup_logging()
    logger = logging.getLogger("MainIntegration")
    
    logger.info("=" * 60)
    logger.info("Avvio Network Monitoring Integration")
    logger.info("=" * 60)
    
    try:
        # 1. Inizializza Network State Collector
        logger.info("Inizializzazione Network State Collector...")
        collector = NetworkStateCollector(config_path=None, environment="development")
        logger.info("✓ Network State Collector inizializzato")
        
        # 2. Inizializza LLM Module (tutti i componenti)
        logger.info("Inizializzazione LLM Module...")
        intent_parser = IntentParser()
        chatgpt_client = ChatGPTClient()
        context_analyzer = ContextAnalyzer()
        action_sequencer = ActionSequencer()
        validator = Validator()
        action_output = ActionOutputService()
        prompt_system = PromptEngineeringSystem()
        logger.info("✓ LLM Module inizializzato")
        
        # 3. Inizializza Northbound Script Generator
        logger.info("Inizializzazione Northbound Script Generator...")
        action_processor_config = {
            "comnetsemu_host": "localhost",
            "comnetsemu_port": 5000,
            "max_retries": 3,
            "retry_delay": 2.0,
            "timeout_seconds": 30
        }
        action_processor = ActionProcessor(action_processor_config)
        logger.info("✓ Northbound Script Generator inizializzato")
        
        logger.info("=" * 60)
        logger.info("Tutti i moduli inizializzati con successo!")
        logger.info("=" * 60)
        
        # Modalità interattiva
        logger.info("\nModalità interattiva attiva")
        logger.info("Comandi disponibili:")
        logger.info("  - 'collect': Raccoglie lo stato della rete")
        logger.info("  - 'intent <testo>': Processa un intento in linguaggio naturale")
        logger.info("  - 'health': Verifica lo stato di salute del sistema")
        logger.info("  - 'quit' o 'exit': Termina il programma")
        logger.info("")
        
        while True:
            try:
                # Leggi comando dall'utente
                user_input = input("\n> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    logger.info("Terminazione programma...")
                    break
                
                # Comando: collect
                if user_input.lower() == 'collect':
                    logger.info("Raccolta stato della rete...")
                    snapshot = collector.collect_snapshot()
                    
                    if snapshot:
                        logger.info(f"✓ Snapshot raccolto con successo")
                        logger.info(f"  Timestamp: {snapshot.get_timestamp_iso()}")
                        logger.info(f"  Switch: {len(snapshot.topology.switches)}")
                        logger.info(f"  Link: {len(snapshot.topology.links)}")
                        
                        # Mostra anomalie se presenti
                        if snapshot.anomalies:
                            logger.warning(f"  ⚠ Anomalie rilevate: {len(snapshot.anomalies)}")
                            for anomaly in snapshot.anomalies[:3]:  # Mostra prime 3
                                logger.warning(f"    - {anomaly.type}: {anomaly.description} (severity: {anomaly.severity})")
                    else:
                        logger.error("✗ Errore nella raccolta dello snapshot")
                    
                    continue
                
                # Comando: health
                if user_input.lower() == 'health':
                    logger.info("Verifica stato di salute del sistema...")
                    health = collector.get_health_status()
                    
                    logger.info(f"Stato generale: {health.overall_status.value}")
                    logger.info(f"Uptime: {health.uptime_seconds:.1f} secondi")
                    
                    if health.components:
                        logger.info("Componenti:")
                        for name, component in health.components.items():
                            status_icon = "✓" if component.status.value == "healthy" else "✗"
                            logger.info(f"  {status_icon} {name}: {component.status.value}")
                    
                    continue
                
                # Comando: intent
                if user_input.lower().startswith('intent '):
                    intent_text = user_input[7:].strip()
                    
                    if not intent_text:
                        logger.warning("Fornisci un intento dopo 'intent'")
                        continue
                    
                    logger.info(f"Processamento intento: '{intent_text}'")
                    logger.info("=" * 60)
                    
                    # Step 1: Raccogli stato della rete
                    logger.info("Step 1: Raccolta stato della rete...")
                    snapshot = collector.collect_snapshot()
                    
                    if not snapshot:
                        logger.error("✗ Impossibile raccogliere lo stato della rete")
                        continue
                    
                    logger.info(f"✓ Stato della rete raccolto")
                    logger.info(f"  Switch: {len(snapshot.topology.switches)}, Links: {len(snapshot.topology.links)}")
                    
                    # Step 2: Parsa l'intento
                    logger.info("\nStep 2: Parsing intento...")
                    intent_obj = intent_parser.parse_intent(intent_text, user_id="cli_user")
                    logger.info(f"✓ Intento parsato")
                    logger.info(f"  Tipo: {intent_obj.intent_type.value}")
                    logger.info(f"  Confidence: {intent_obj.confidence:.2f}")
                    logger.info(f"  Entità estratte: {len(intent_obj.entities)}")
                    
                    # Verifica se serve chiarimento
                    if intent_obj.confidence < 0.7:
                        logger.warning("⚠ Confidence bassa, potrebbe servire chiarimento")
                        ambiguity_analysis = intent_parser.detect_ambiguity(intent_obj, snapshot)
                        if ambiguity_analysis['clarification_needed']:
                            clarifications = intent_parser.generate_clarification_requests(
                                intent_obj, ambiguity_analysis, snapshot
                            )
                            logger.warning("Chiarimenti necessari:")
                            for clarification in clarifications:
                                logger.warning(f"  - {clarification}")
                            
                            # Chiedi all'utente se vuole continuare
                            response = input("\nVuoi continuare comunque? (s/n): ").strip().lower()
                            if response != 's':
                                logger.info("Operazione annullata")
                                continue
                    
                    # Step 3: Analizza contesto
                    logger.info("\nStep 3: Analisi contesto di rete...")
                    contextualized_intent = context_analyzer.analyze_context(intent_obj, snapshot)
                    logger.info(f"✓ Contesto analizzato")
                    
                    if contextualized_intent.conflicts:
                        logger.warning("⚠ Conflitti rilevati:")
                        for conflict in contextualized_intent.conflicts:
                            logger.warning(f"  - {conflict}")
                    
                    if contextualized_intent.recommendations:
                        logger.info("Raccomandazioni:")
                        for rec in contextualized_intent.recommendations:
                            logger.info(f"  - {rec}")
                    
                    # Step 4: Genera azioni con LLM
                    logger.info("\nStep 4: Generazione azioni con ChatGPT...")
                    
                    # Usa il prompt engineering system
                    prompt = prompt_system.build_action_generation_prompt(
                        contextualized_intent,
                        network_state=snapshot
                    )
                    
                    # Chiamata asincrona a ChatGPT
                    async def generate_actions():
                        response = await chatgpt_client.generate_response(
                            prompt=prompt,
                            system_message="You are a network automation assistant. Generate network actions in JSON format based on the user's intent and current network state."
                        )
                        return response
                    
                    try:
                        response = asyncio.run(generate_actions())
                        logger.info(f"✓ Risposta LLM ricevuta")
                        logger.info(f"  Tokens: {response.tokens_used}, Latency: {response.latency:.2f}s")
                        
                        # Step 5: Parsa e sequenzia azioni
                        logger.info("\nStep 5: Parsing e sequenziamento azioni...")
                        actions = action_sequencer.parse_actions_from_response(response.content)
                        action_sequence = action_sequencer.sequence_actions(actions, contextualized_intent)
                        logger.info(f"✓ {len(action_sequence.actions)} azioni sequenziate")
                        
                        # Mostra le azioni
                        logger.info("Azioni proposte:")
                        for i, action in enumerate(action_sequence.actions, 1):
                            logger.info(f"  {i}. {action.type.value} su {action.target}")
                        
                        # Step 6: Valida azioni
                        logger.info("\nStep 6: Validazione azioni...")
                        validation_result = validator.validate_actions(action_sequence)
                        
                        if not validation_result.is_valid:
                            logger.error("✗ Validazione fallita:")
                            for error in validation_result.errors:
                                logger.error(f"  - {error}")
                            continue
                        
                        logger.info("✓ Azioni validate con successo")
                        
                        # Step 7: Salva azioni per esecuzione
                        logger.info("\nStep 7: Salvataggio azioni...")
                        output_result = action_output.save_actions(
                            action_sequence,
                            intent_id=intent_obj.id,
                            user_id="cli_user"
                        )
                        logger.info(f"✓ Azioni salvate in: {output_result.output_file}")
                        
                        # Step 8: Chiedi conferma ed esegui
                        logger.info("\n" + "=" * 60)
                        response = input("Vuoi eseguire queste azioni sulla rete? (s/n): ").strip().lower()
                        
                        if response == 's':
                            logger.info("\nStep 8: Esecuzione azioni sulla rete...")
                            
                            results = []
                            for i, action in enumerate(action_sequence.actions, 1):
                                logger.info(f"  Esecuzione azione {i}/{len(action_sequence.actions)}: {action.id}")
                                
                                # Converti l'azione al formato NetworkAction
                                network_action = NetworkAction(
                                    id=action.id,
                                    type=action.type,
                                    target=action.target,
                                    parameters=action.parameters,
                                    priority=getattr(action, 'priority', 100),
                                    timeout=getattr(action, 'timeout', 30)
                                )
                                
                                result = action_processor.execute_action(network_action)
                                results.append(result)
                                
                                if result.status.value == "success":
                                    logger.info(f"  ✓ Azione {action.id} completata ({result.duration:.2f}s)")
                                else:
                                    logger.error(f"  ✗ Azione {action.id} fallita: {result.error}")
                            
                            # Step 9: Verifica stato finale
                            logger.info("\nStep 9: Verifica stato finale...")
                            final_snapshot = collector.collect_snapshot()
                            
                            if final_snapshot:
                                logger.info("✓ Stato finale raccolto")
                                logger.info(f"  Switch: {len(final_snapshot.topology.switches)}")
                                logger.info(f"  Link: {len(final_snapshot.topology.links)}")
                                
                                # Confronta con stato iniziale
                                if len(final_snapshot.topology.switches) != len(snapshot.topology.switches):
                                    logger.info(f"  Δ Switch: {len(final_snapshot.topology.switches) - len(snapshot.topology.switches)}")
                                if len(final_snapshot.topology.links) != len(snapshot.topology.links):
                                    logger.info(f"  Δ Links: {len(final_snapshot.topology.links) - len(snapshot.topology.links)}")
                            
                            # Riepilogo
                            successful = sum(1 for r in results if r.status.value == "success")
                            failed = sum(1 for r in results if r.status.value == "failed")
                            
                            logger.info("\n" + "=" * 60)
                            logger.info("RIEPILOGO ESECUZIONE")
                            logger.info("=" * 60)
                            logger.info(f"Totale azioni: {len(results)}")
                            logger.info(f"Successi: {successful}")
                            logger.info(f"Fallimenti: {failed}")
                            logger.info(f"Success rate: {(successful / len(results) * 100):.1f}%")
                            logger.info("=" * 60)
                        else:
                            logger.info("Esecuzione annullata dall'utente")
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"✗ Errore nel parsing della risposta LLM: {e}")
                        logger.error(f"Risposta ricevuta: {response.content[:200]}...")
                    except Exception as e:
                        logger.error(f"✗ Errore nel processamento: {e}", exc_info=True)
                    
                    continue
                
                # Comando non riconosciuto
                logger.warning(f"Comando non riconosciuto: '{user_input}'")
                logger.info("Usa 'collect', 'intent <testo>', 'health', o 'quit'")
                
            except KeyboardInterrupt:
                logger.info("\nInterruzione ricevuta...")
                break
            except Exception as e:
                logger.error(f"Errore: {e}", exc_info=True)
        
        # Cleanup
        logger.info("Chiusura connessioni...")
        action_processor.close()
        logger.info("✓ Programma terminato")
        
    except Exception as e:
        logger.error(f"Errore fatale: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
