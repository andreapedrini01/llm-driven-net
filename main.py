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
import os
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
from northbound_script_generator.models import NetworkAction as NorthboundAction
from northbound_script_generator.config_loader import ConfigLoader
from src.models.actions import NetworkAction as LLMAction, ActionType, ActionSequence
from src.models.network import (
    NetworkState, Topology, Switch, Link,
    NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics
)
from src.models.core import NetworkSnapshot
from src.models.intent import IntentType
from src.models.confidence import ConfidenceCriteriaBreakdown, ParameterSuggestion, ConfidenceModification
from src.services.confidence_criteria_extractor import ConfidenceCriteriaExtractor
from src.services.change_summary import generate_summary, generate_llm_summary


def snapshot_to_network_state(snapshot: NetworkSnapshot) -> NetworkState:
    """Converte un NetworkSnapshot (dal collector) in un NetworkState (per i servizi LLM)."""
    switches = [
        Switch(
            id=s.dpid,
            name=f"switch-{s.dpid}",
            dpid=s.dpid,
            ports=s.ports,
            status="active" if s.active else "inactive"
        )
        for s in snapshot.topology.switches
    ]
    links = [
        Link(
            id=f"{l.src_dpid}:{l.src_port}-{l.dst_dpid}:{l.dst_port}",
            source_switch=l.src_dpid,
            source_port=l.src_port,
            destination_switch=l.dst_dpid,
            destination_port=l.dst_port
        )
        for l in snapshot.topology.links
    ]
    return NetworkState(
        timestamp=datetime.fromtimestamp(snapshot.timestamp),
        topology=Topology(switches=switches, links=links),
        metrics=NetworkMetrics(
            bandwidth=BandwidthMetrics(
                total_capacity=1000, used_bandwidth=0,
                available_bandwidth=1000, utilization_percentage=0.0
            ),
            latency=LatencyMetrics(
                average_latency=0.0, min_latency=0.0,
                max_latency=0.0, jitter=0.0
            ),
            utilization=UtilizationMetrics(
                cpu_utilization=0.0, memory_utilization=0.0
            )
        )
    )


HISTORY_DIR = "data/history"


def save_state_to_history(network_state: NetworkState) -> str:
    """Salva il NetworkState in data/history e ritorna il path del file."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    ts = network_state.timestamp.strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(HISTORY_DIR, f"state_{ts}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(network_state.dict(), f, indent=2, default=str)
    return filepath


def update_context_cache(context_analyzer: 'ContextAnalyzer', network_state: NetworkState):
    """Aggiorna la cache del context_analyzer con lo stato corrente."""
    context_analyzer.state_cache.update_state(network_state)


# ── Soglia di confidence per generazione rule-based (senza ChatGPT) ──
RULE_BASED_CONFIDENCE_THRESHOLD = 0.8

# ── Cookie ranges per identificare chi ha installato le flow rules ──
# main.py (interattivo, comandi utente): 0x2000-0x2FFF, priorità 50000-59999
# main_auto.py (autonomo, anomaly response): 0x1000-0x1FFF, priorità 40000-49999
COOKIE_INTERACTIVE = 0x2000


def _host_to_ip(host: str) -> Optional[str]:
    """Converte un nome host Mininet (h1, h2, ...) nel suo IP (10.0.0.1, 10.0.0.2, ...)."""
    import re as _re
    m = _re.match(r'^h(\d+)$', host.strip(), _re.IGNORECASE)
    if m:
        return f"10.0.0.{m.group(1)}"
    return None


def _find_switch_target(resources: List[str], network_state: NetworkState) -> str:
    """Trova il primo switch tra le risorse, oppure usa il primo switch dalla topologia."""
    for r in resources:
        if r.lower().startswith(('sw', 's')) and not r.lower().startswith('slice'):
            return r
    # Nessuno switch nell'intent → usa il primo switch dalla topologia
    if network_state and network_state.topology and network_state.topology.switches:
        sw = network_state.topology.switches[0]
        return sw.dpid if sw.dpid else sw.id
    return "sw1"


def generate_actions_rule_based(intent_obj, network_state: NetworkState) -> List[LLMAction]:
    """
    Genera azioni di rete direttamente dalle entità estratte dal parser,
    senza interpellare ChatGPT. Usata quando la confidence è >= soglia.
    """
    import re as _re

    actions = []
    intent_type = intent_obj.intent_type
    entities = intent_obj.entities
    params = intent_obj.parameters
    raw = intent_obj.raw_text.lower()

    # Raccogli entità utili per tipo
    resources = [e.value for e in entities if e.type == 'resource']
    action_words = [e.value.lower() for e in entities if e.type == 'action']
    targets = [e.value for e in entities if e.type == 'target']

    # Separa host e switch
    hosts = [r for r in resources if _re.match(r'^h\d+$', r, _re.IGNORECASE)]
    switches = [r for r in resources if _re.match(r'^(?:sw|s)\d+$', r, _re.IGNORECASE)]

    # ── Pattern: block/allow traffic from X to Y ──
    traffic_match = _re.search(
        r'\b(block|drop|deny|allow|permit|forward)\b.*\b(?:from|src)\s+(h\d+|[\d.]+).*\b(?:to|dst)\s+(h\d+|[\d.]+)',
        raw
    )
    if traffic_match:
        verb = traffic_match.group(1)
        src_raw = traffic_match.group(2)
        dst_raw = traffic_match.group(3)

        src_ip = _host_to_ip(src_raw) if src_raw.startswith('h') else src_raw
        dst_ip = _host_to_ip(dst_raw) if dst_raw.startswith('h') else dst_raw

        is_block = verb in ('block', 'drop', 'deny')
        switch_target = _find_switch_target(resources, network_state)

        match_fields = {"dl_type": 2048}  # 0x0800 = IPv4
        if src_ip:
            match_fields["nw_src"] = src_ip
        if dst_ip:
            match_fields["nw_dst"] = dst_ip

        # Block → nessuna action (DROP implicito in OpenFlow)
        # Allow → OUTPUT NORMAL
        flow_actions = [] if is_block else [{"type": "OUTPUT", "port": "NORMAL"}]
        desc = f"{'Block' if is_block else 'Allow'} traffic {src_raw} → {dst_raw}"

        actions.append(LLMAction(
            id=f"act_{intent_obj.id}_traffic",
            type=ActionType.FLOW_MOD,
            target=switch_target,
            parameters={
                "operation": "add",
                "match": match_fields,
                "actions": flow_actions,
                "cookie": COOKIE_INTERACTIVE,
            },
            priority=params.get('priority', 50000),
            timeout=params.get('timeout', 3600) or 3600,
            description=desc,
        ))
        return actions

    # ── Pattern: block/allow all traffic on switch ──
    block_all_match = _re.search(r'\b(block|drop|deny|allow|permit)\b.*\b(?:traffic|packets)\b', raw)
    if block_all_match and not traffic_match:
        verb = block_all_match.group(1)
        is_block = verb in ('block', 'drop', 'deny')
        switch_target = _find_switch_target(resources, network_state)
        flow_actions = [] if is_block else [{"type": "OUTPUT", "port": "NORMAL"}]

        actions.append(LLMAction(
            id=f"act_{intent_obj.id}_traffic_all",
            type=ActionType.FLOW_MOD,
            target=switch_target,
            parameters={
                "operation": "add",
                "match": {},
                "actions": flow_actions,
                "cookie": COOKIE_INTERACTIVE,
            },
            priority=params.get('priority', 50000),
            timeout=params.get('timeout', 3600) or 3600,
            description=f"{'Block' if is_block else 'Allow'} all traffic on {switch_target}",
        ))
        return actions

    # ── CONFIGURATION intents ──
    if intent_type == IntentType.CONFIGURATION:

        # --- Flow rules esplicite ---
        if any(w in action_words for w in ['add', 'create', 'configure', 'set']):
            if any('flow' in t or 'rule' in t for t in targets) or 'flow' in raw:
                match_fields = {}
                for k, v in params.items():
                    if k in ('port', 'in_port'):
                        match_fields['in_port'] = int(v) if str(v).isdigit() else v
                    elif 'ip' in k:
                        match_fields['ip_dst'] = str(v)

                # Extract src/dst hosts from intent text (e.g. "from h1 to h2")
                host_match = _re.search(
                    r'\b(?:from|src)\s+(h\d+|[\d.]+).*\b(?:to|dst)\s+(h\d+|[\d.]+)',
                    raw
                )
                if host_match and 'nw_src' not in match_fields and 'nw_dst' not in match_fields:
                    src_raw = host_match.group(1)
                    dst_raw = host_match.group(2)
                    src_ip = _host_to_ip(src_raw) if src_raw.startswith('h') else src_raw
                    dst_ip = _host_to_ip(dst_raw) if dst_raw.startswith('h') else dst_raw
                    if src_ip or dst_ip:
                        match_fields["dl_type"] = 2048  # IPv4
                    if src_ip:
                        match_fields["nw_src"] = src_ip
                    if dst_ip:
                        match_fields["nw_dst"] = dst_ip

                switch_target = _find_switch_target(resources, network_state)
                actions.append(LLMAction(
                    id=f"act_{intent_obj.id}_flow",
                    type=ActionType.FLOW_MOD,
                    target=switch_target,
                    parameters={
                        "operation": "add",
                        "match": match_fields,
                        "actions": [{"type": "OUTPUT", "port": "NORMAL"}],
                        "cookie": COOKIE_INTERACTIVE,
                    },
                    priority=params.get('priority', 50000),
                    timeout=params.get('timeout', 3600) or 3600,
                    description=f"Add flow rule on {switch_target}",
                ))

            # Slice
            elif any('slice' in t for t in targets) or 'slice' in raw:
                slice_name = next((t for t in targets if 'slice' in t), f"slice_{intent_obj.id}")
                switch_target = _find_switch_target(resources, network_state)
                actions.append(LLMAction(
                    id=f"act_{intent_obj.id}_slice",
                    type=ActionType.SLICE_CREATE,
                    target=switch_target,
                    parameters={
                        "slice_name": slice_name,
                        "resources": resources if resources else ["network"],
                        "bandwidth": params.get('bandwidth', 100),
                    },
                    priority=1000,
                    timeout=30,
                    description=f"Create slice '{slice_name}'",
                ))

            # Generico config
            else:
                switch_target = _find_switch_target(resources, network_state)
                actions.append(LLMAction(
                    id=f"act_{intent_obj.id}_config",
                    type=ActionType.CONFIG_CHANGE,
                    target=switch_target,
                    parameters={
                        "config_type": "general",
                        "config_data": params if params else {"action": action_words[0] if action_words else "configure"},
                    },
                    priority=1000,
                    timeout=30,
                    description=f"Configuration change on {switch_target}",
                ))

        # --- Remove / delete ---
        elif any(w in action_words for w in ['remove', 'delete']):
            switch_target = _find_switch_target(resources, network_state)
            # Se si parla di flow/rule → delete flow entry
            if any('flow' in t or 'rule' in t for t in targets) or 'flow' in raw:
                actions.append(LLMAction(
                    id=f"act_{intent_obj.id}_delflow",
                    type=ActionType.FLOW_MOD,
                    target=switch_target,
                    parameters={
                        "operation": "delete",
                        "match": {},
                        "actions": [],
                    },
                    priority=1000,
                    timeout=30,
                    description=f"Delete flow rules on {switch_target}",
                ))
            else:
                actions.append(LLMAction(
                    id=f"act_{intent_obj.id}_remove",
                    type=ActionType.CONFIG_CHANGE,
                    target=switch_target,
                    parameters={
                        "config_type": "remove",
                        "config_data": {"resources": resources, "targets": targets},
                    },
                    priority=1000,
                    timeout=30,
                    description=f"Remove on {switch_target}",
                ))

        # --- Fallback config ---
        else:
            switch_target = _find_switch_target(resources, network_state)
            actions.append(LLMAction(
                id=f"act_{intent_obj.id}_cfg",
                type=ActionType.CONFIG_CHANGE,
                target=switch_target,
                parameters={
                    "config_type": "general",
                    "config_data": params if params else {"raw_text": intent_obj.raw_text},
                },
                priority=1000,
                timeout=30,
                description=f"Configuration on {switch_target}",
            ))

    # ── ANOMALY_RESPONSE intents ──
    elif intent_type == IntentType.ANOMALY_RESPONSE:
        switch_target = _find_switch_target(resources, network_state)
        actions.append(LLMAction(
            id=f"act_{intent_obj.id}_fix",
            type=ActionType.CONFIG_CHANGE,
            target=switch_target,
            parameters={
                "config_type": "anomaly_fix",
                "config_data": {
                    "action": action_words[0] if action_words else "fix",
                    "resources": resources,
                    "raw_text": intent_obj.raw_text,
                },
            },
            priority=500,
            timeout=60,
            description=f"Anomaly fix on {switch_target}",
        ))

    # ── QUERY intents → nessuna azione di rete ──
    elif intent_type == IntentType.QUERY:
        pass

    return actions


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
        confidence_extractor = ConfidenceCriteriaExtractor()
        logger.info("✓ LLM Module inizializzato")
        
        # 3. Inizializza Northbound Script Generator
        logger.info("Inizializzazione Northbound Script Generator...")
        action_processor_config = {
            "comnetsemu_host": "localhost",
            "comnetsemu_port": 6653,
            "ryu_host": "localhost",
            "ryu_port": 8080,
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
        logger.info("  - 'collect --security-scan': Raccoglie + analisi sicurezza su tutti gli host")
        logger.info("  - 'collect --security-scan h1 h2': Raccoglie + analisi sicurezza su h1 e h2")
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
                
                # Comando: collect [--security-scan [host ...]]
                if user_input.lower().startswith('collect'):
                    parts = user_input.split()
                    security_scan = False
                    host_filter = None

                    if '--security-scan' in parts:
                        security_scan = True
                        idx = parts.index('--security-scan')
                        hosts = parts[idx + 1:]
                        host_filter = hosts if hosts else None

                    if security_scan:
                        if host_filter:
                            logger.info(f"Raccolta stato + scansione sicurezza per: {', '.join(host_filter)}")
                        else:
                            logger.info("Raccolta stato + scansione sicurezza (tutti gli host)...")
                    else:
                        logger.info("Raccolta stato della rete...")

                    snapshot = collector.collect_snapshot(
                        security_scan=security_scan,
                        host_filter=host_filter
                    )

                    if snapshot:
                        logger.info(f"✓ Snapshot raccolto con successo")
                        logger.info(f"  Timestamp: {snapshot.get_timestamp_iso()}")
                        logger.info(f"  Switch: {len(snapshot.topology.switches)}")
                        logger.info(f"  Link: {len(snapshot.topology.links)}")

                        # Converti e salva nella cache + history
                        network_state = snapshot_to_network_state(snapshot)
                        update_context_cache(context_analyzer, network_state)
                        history_file = save_state_to_history(network_state)
                        logger.info(f"  ✓ Stato salvato in cache e in {history_file}")

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
                    
                    # Converti snapshot in NetworkState per i servizi LLM
                    network_state = snapshot_to_network_state(snapshot)
                    
                    # Aggiorna cache e salva in history
                    update_context_cache(context_analyzer, network_state)
                    save_state_to_history(network_state)
                    
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
                        ambiguity_analysis = intent_parser.detect_ambiguity(intent_obj, network_state)
                        if ambiguity_analysis.get('clarification_needed'):
                            logger.warning("Chiarimenti necessari:")
                            for question in ambiguity_analysis.get('questions', []):
                                logger.warning(f"  - {question}")
                            
                            # Chiedi all'utente se vuole continuare
                            response = input("\nVuoi continuare comunque? (s/n): ").strip().lower()
                            if response != 's':
                                logger.info("Operazione annullata")
                                continue
                    
                    # Step 3: Analizza contesto
                    logger.info("\nStep 3: Analisi contesto di rete...")
                    contextualized_intent = context_analyzer.analyze_context(intent_obj)
                    logger.info(f"✓ Contesto analizzato")
                    
                    if contextualized_intent.conflicts:
                        logger.warning("⚠ Conflitti rilevati:")
                        for conflict in contextualized_intent.conflicts:
                            logger.warning(f"  - {conflict}")
                    
                    if contextualized_intent.recommendations:
                        logger.info("Raccomandazioni:")
                        for rec in contextualized_intent.recommendations:
                            logger.info(f"  - {rec}")
                    
                    # Step 4: Genera azioni
                    # Se la confidence è alta, genera azioni rule-based senza ChatGPT
                    use_rule_based = intent_obj.confidence >= RULE_BASED_CONFIDENCE_THRESHOLD

                    if intent_obj.intent_type == IntentType.QUERY:
                        logger.info("\nStep 4: Intent di tipo QUERY — nessuna azione di rete da generare.")
                        logger.info("  Usa 'collect' o 'health' per ottenere informazioni sulla rete.")
                        continue

                    actions = []

                    if use_rule_based:
                        logger.info(f"\nStep 4: Generazione azioni RULE-BASED (confidence {intent_obj.confidence:.2f} >= {RULE_BASED_CONFIDENCE_THRESHOLD})")
                        actions = generate_actions_rule_based(intent_obj, network_state)
                        if actions:
                            logger.info(f"✓ {len(actions)} azioni generate (rule-based, senza ChatGPT)")
                        else:
                            logger.warning("⚠ Nessuna azione generata dal rule-based, fallback a ChatGPT...")
                            use_rule_based = False

                    if not use_rule_based:
                        logger.info(f"\nStep 4: Generazione azioni con ChatGPT (confidence {intent_obj.confidence:.2f} < {RULE_BASED_CONFIDENCE_THRESHOLD})")

                        # Get confidence criteria breakdown for enriched prompt
                        breakdown = intent_parser.get_confidence_breakdown(intent_obj)
                        logger.info(f"  Confidence breakdown: base={breakdown.base_confidence:.3f}, "
                                    f"entity={breakdown.entity_boost:.3f}, type={breakdown.type_boost:.3f}, "
                                    f"token={breakdown.token_boost:.3f}, quality={breakdown.quality_boost:.3f}, "
                                    f"penalties={breakdown.penalties:.3f}, final={breakdown.final_score:.3f}")

                        # Build criteria-enriched prompt
                        system_msg, user_prompt, prompt_config = prompt_system.build_confidence_enriched_prompt(
                            intent_obj, breakdown, network_state
                        )

                        async def generate_actions_llm():
                            resp = await chatgpt_client.generate_response(
                                prompt=user_prompt,
                                system_message=system_msg
                            )
                            return resp

                        try:
                            llm_response = asyncio.run(generate_actions_llm())
                            logger.info(f"✓ Risposta LLM ricevuta")
                            logger.info(f"  Tokens: {llm_response.tokens_used}, Latency: {llm_response.latency:.2f}s")

                            # Parse both actions and parameter suggestions
                            actions, suggestions = action_sequencer.parse_actions_and_suggestions(llm_response.content)
                            logger.info(f"  Parsed {len(actions)} actions, {len(suggestions)} parameter suggestions")

                            # Extract modifications from suggestions if present
                            if suggestions:
                                modifications = confidence_extractor.extract_modifications(breakdown, suggestions)
                                logger.info(f"  Extracted {len(modifications)} confidence modifications:")
                                for mod in modifications:
                                    logger.info(f"    - {mod.target_field}: '{mod.source_suggestion.suggested_parameter}' "
                                                f"-> '{mod.suggested_value}' (estimated score: {mod.estimated_new_score:.3f})")
                        except Exception as e:
                            logger.error(f"✗ Errore ChatGPT: {e}", exc_info=True)
                            continue

                    if not actions:
                        logger.warning("⚠ Nessuna azione generata. Verifica l'intento e riprova.")
                        continue

                    try:
                        # Step 5: Sequenzia azioni
                        logger.info(f"\nStep 5: Sequenziamento di {len(actions)} azioni...")
                        action_sequence = action_sequencer.sequence_actions(
                            actions,
                            intent_id=intent_obj.id,
                            sequence_id=f"seq_{intent_obj.id}"
                        )
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
                            action_sequence
                        )
                        logger.info(f"✓ Azioni salvate")

                        # Step 8: Chiedi conferma ed esegui
                        logger.info("\n" + "=" * 60)
                        response = input("Vuoi eseguire queste azioni sulla rete? (s/n): ").strip().lower()

                        if response == 's':
                            logger.info("\nStep 8: Esecuzione azioni sulla rete...")

                            results = []
                            for i, action in enumerate(action_sequence.actions, 1):
                                logger.info(f"  Esecuzione azione {i}/{len(action_sequence.actions)}: {action.id}")

                                # Converti l'azione al formato NorthboundAction
                                network_action = NorthboundAction(
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

                            # Step 8.5: Change summary
                            try:
                                llm_summary_text = None
                                if os.environ.get("ENABLE_LLM_SUMMARY", "").lower() == "true":
                                    llm_summary_text = asyncio.run(
                                        generate_llm_summary(
                                            chatgpt_client, intent_text,
                                            action_sequence.actions, results
                                        )
                                    )

                                summary = generate_summary(
                                    intent_text=intent_text,
                                    confidence=intent_obj.confidence,
                                    actions=action_sequence.actions,
                                    results=results,
                                    llm_summary=llm_summary_text,
                                    threshold=RULE_BASED_CONFIDENCE_THRESHOLD
                                )
                                print(summary)
                            except Exception as e:
                                logger.error(f"Error generating change summary: {e}")

                            # Step 9: Verifica stato finale
                            logger.info("\nStep 9: Verifica stato finale...")
                            final_snapshot = collector.collect_snapshot()

                            if final_snapshot:
                                logger.info("✓ Stato finale raccolto")
                                logger.info(f"  Switch: {len(final_snapshot.topology.switches)}")
                                logger.info(f"  Link: {len(final_snapshot.topology.links)}")

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
