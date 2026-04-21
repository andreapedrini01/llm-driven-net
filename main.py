#!/usr/bin/env python3
"""
Main Integration Script
Integrates the three modules to monitor and manage the ComnetsEmu network:
- network_state_collector: collects network state
- src/services (LLM module): interprets intents and proposes actions
- northbound_script_generator: applies validated actions to the network
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

# Import existing modules
from network_state_collector.collector import NetworkStateCollector
from llm_integration_module.models import CollectorConfig
from llm_integration_module.services.intent_parser import IntentParser
from llm_integration_module.services.chatgpt_client import ChatGPTClient
from llm_integration_module.services.context_analyzer import ContextAnalyzer
from llm_integration_module.services.action_sequencer import ActionSequencer
from llm_integration_module.services.validator import Validator
from llm_integration_module.services.action_output import ActionOutputService
from llm_integration_module.services.prompt_engineering import PromptEngineeringSystem
from northbound_script_generator.action_processor import ActionProcessor
from northbound_script_generator.models import NetworkAction as NorthboundAction
from northbound_script_generator.config_loader import ConfigLoader
from llm_integration_module.models.actions import NetworkAction as LLMAction, ActionType, ActionSequence
from llm_integration_module.models.network import (
    NetworkState, Topology, Switch, Link, Flow,
    NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics
)
from llm_integration_module.models.core import NetworkSnapshot
from llm_integration_module.models.intent import IntentType
from llm_integration_module.models.confidence import ConfidenceCriteriaBreakdown, ParameterSuggestion, ConfidenceModification
from llm_integration_module.services.confidence_criteria_extractor import ConfidenceCriteriaExtractor
from llm_integration_module.services.change_summary import generate_summary, generate_llm_summary
from clean_cache import clean_all as clean_application_cache


def snapshot_to_network_state(snapshot: NetworkSnapshot) -> NetworkState:
    """Converts a NetworkSnapshot (from collector) into a NetworkState (for LLM services)."""
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

    # Map flow stats from collector to Flow model
    flows = []
    flow_stats = snapshot.flow_stats or {}
    for dpid, dpid_flows in flow_stats.items():
        for idx, f in enumerate(dpid_flows):
            flows.append(Flow(
                id=f"{dpid}-flow-{idx}",
                switch_id=dpid,
                match_fields=f.get("match", {}),
                actions=[{"type": "OUTPUT", "port": a} if isinstance(a, str) else a
                         for a in f.get("actions", [])],
                priority=f.get("priority", 0),
                idle_timeout=f.get("idle_timeout", 0),
                hard_timeout=f.get("hard_timeout", 0),
                byte_count=f.get("byte_count", 0),
                packet_count=f.get("packet_count", 0),
            ))

    return NetworkState(
        timestamp=datetime.fromtimestamp(snapshot.timestamp),
        topology=Topology(switches=switches, links=links),
        flows=flows,
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
    """Saves the NetworkState to data/history and returns the file path."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    ts = network_state.timestamp.strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(HISTORY_DIR, f"state_{ts}.json")
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(network_state.dict(), f, indent=2, default=str)
    return filepath


def update_context_cache(context_analyzer: 'ContextAnalyzer', network_state: NetworkState):
    """Updates the context_analyzer cache with the current state."""
    context_analyzer.state_cache.update_state(network_state)


# ── Confidence threshold for rule-based generation (without ChatGPT) ──
RULE_BASED_CONFIDENCE_THRESHOLD = 0.8

# ── Cookie ranges to identify who installed the flow rules ──
# main.py (interactive, user commands): 0x2000-0x2FFF, priority 50000-59999
# main_auto.py (autonomous, anomaly response): 0x1000-0x1FFF, priority 40000-49999
COOKIE_INTERACTIVE = 0x2000


def _host_to_ip(host: str) -> Optional[str]:
    """Converts a Mininet host name (h1, h2, ...) to its IP (10.0.0.1, 10.0.0.2, ...)."""
    import re as _re
    m = _re.match(r'^h(\d+)$', host.strip(), _re.IGNORECASE)
    if m:
        return f"10.0.0.{m.group(1)}"
    return None


def _find_switch_target(resources: List[str], network_state: NetworkState) -> str:
    """Finds the first switch among resources, or uses the first switch from the topology."""
    for r in resources:
        if r.lower().startswith(('sw', 's')) and not r.lower().startswith('slice'):
            return r
    # No switch in the intent → use the first switch from the topology
    if network_state and network_state.topology and network_state.topology.switches:
        sw = network_state.topology.switches[0]
        return sw.dpid if sw.dpid else sw.id
    return "sw1"


def generate_actions_rule_based(intent_obj, network_state: NetworkState) -> List[LLMAction]:
    """
    Generates network actions directly from entities extracted by the parser,
    without calling ChatGPT. Used when confidence is >= threshold.
    """
    import re as _re

    actions = []
    intent_type = intent_obj.intent_type
    entities = intent_obj.entities
    params = intent_obj.parameters
    raw = intent_obj.raw_text.lower()

    # Collect useful entities by type
    resources = [e.value for e in entities if e.type == 'resource']
    action_words = [e.value.lower() for e in entities if e.type == 'action']
    targets = [e.value for e in entities if e.type == 'target']

    # Separate hosts and switches
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

        # Block → no action (implicit DROP in OpenFlow)
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

    # ── Pattern: load balance traffic across hosts ──
    lb_match = _re.search(
        r'\b(?:load[- ]?balanc|distribute|spread|balance)\b',
        raw
    )
    if lb_match:
        # Extract all host names from resources or raw text
        host_resources = [r for r in (resources or []) if _re.match(r'^h\d+$', str(r), _re.IGNORECASE)]
        if len(host_resources) < 2:
            # Try to parse from raw text
            raw_hosts = _re.findall(r'\bh(\d+)\b', raw, _re.IGNORECASE)
            seen = set()
            for h in raw_hosts:
                if h not in seen:
                    seen.add(h)
                    if f"h{h}" not in host_resources:
                        host_resources.append(f"h{h}")

        # Extract virtual IP if specified
        vip_match = _re.search(r'(?:virtual[- ]?ip|vip)[:\s]*([\d.]+)', raw)
        virtual_ip = vip_match.group(1) if vip_match else None

        switch_target = _find_switch_target(resources, network_state)
        lb_config = {"dst_hosts": host_resources}
        if virtual_ip:
            lb_config["virtual_ip"] = virtual_ip

        actions.append(LLMAction(
            id=f"act_{intent_obj.id}_lb",
            type=ActionType.LOAD_BALANCE,
            target=switch_target,
            parameters={
                "backends": host_resources,
                "virtual_ip": virtual_ip,
                "config_data": lb_config,
            },
            priority=3000,
            timeout=30,
            description=f"Load balance traffic across {', '.join(host_resources)}"
                + (f" (vip={virtual_ip})" if virtual_ip else ""),
        ))
        return actions

    # ── Pattern: delete/remove slice ──
    slice_del_match = _re.search(
        r'\b(?:delete|remove|destroy|drop)\b.*\bslice\b|\bslice\b.*\b(?:delete|remove|destroy|drop)\b',
        raw
    )
    if slice_del_match:
        host_resources = [r for r in (resources or []) if _re.match(r'^h\d+$', str(r), _re.IGNORECASE)]
        if len(host_resources) < 2:
            raw_hosts = _re.findall(r'\bh(\d+)\b', raw, _re.IGNORECASE)
            seen = set()
            for h in raw_hosts:
                if h not in seen:
                    seen.add(h)
                    if f"h{h}" not in host_resources:
                        host_resources.append(f"h{h}")

        src_host = host_resources[0] if len(host_resources) >= 1 else None
        dst_host = host_resources[1] if len(host_resources) >= 2 else None
        switch_target = _find_switch_target(resources, network_state)

        del_config = {}
        if src_host:
            del_config["src_host"] = src_host
        if dst_host:
            del_config["dst_host"] = dst_host

        actions.append(LLMAction(
            id=f"act_{intent_obj.id}_slice_del",
            type=ActionType.SLICE_DELETE,
            target=switch_target,
            parameters={
                "config_data": del_config,
            },
            priority=1000,
            timeout=30,
            description=f"Delete slice"
                + (f" between {src_host} and {dst_host}" if src_host and dst_host else ""),
        ))
        return actions

    # ── Pattern: modify slice bandwidth ──
    slice_mod_match = _re.search(
        r'\b(?:modify|change|update|resize|adjust)\b.*\bslice\b|\bslice\b.*\b(?:modify|change|update|resize|adjust)\b',
        raw
    )
    if slice_mod_match:
        host_resources = [r for r in (resources or []) if _re.match(r'^h\d+$', str(r), _re.IGNORECASE)]
        if len(host_resources) < 2:
            raw_hosts = _re.findall(r'\bh(\d+)\b', raw, _re.IGNORECASE)
            seen = set()
            for h in raw_hosts:
                if h not in seen:
                    seen.add(h)
                    if f"h{h}" not in host_resources:
                        host_resources.append(f"h{h}")

        src_host = host_resources[0] if len(host_resources) >= 1 else None
        dst_host = host_resources[1] if len(host_resources) >= 2 else None
        switch_target = _find_switch_target(resources, network_state)

        mod_config = {
            "bandwidth_mbps": params.get('bandwidth', 100),
        }
        if src_host:
            mod_config["src_host"] = src_host
        if dst_host:
            mod_config["dst_host"] = dst_host

        actions.append(LLMAction(
            id=f"act_{intent_obj.id}_slice_mod",
            type=ActionType.SLICE_MODIFY,
            target=switch_target,
            parameters={
                "bandwidth": params.get('bandwidth', 100),
                "config_data": mod_config,
            },
            priority=1000,
            timeout=30,
            description=f"Modify slice"
                + (f" between {src_host} and {dst_host}" if src_host and dst_host else "")
                + f" to {params.get('bandwidth', 100)} Mbps",
        ))
        return actions

    # ── CONFIGURATION intents ──
    # --- Explicit flow rules ---
    if intent_type == IntentType.CONFIGURATION:

        # --- Explicit flow rules ---
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

                # Extract source/destination hosts from resources list
                host_resources = [r for r in (resources or []) if _re.match(r'^h\d+$', str(r), _re.IGNORECASE)]
                src_host = host_resources[0] if len(host_resources) >= 1 else None
                dst_host = host_resources[1] if len(host_resources) >= 2 else None

                slice_config_data = {
                    "bandwidth_mbps": params.get('bandwidth', 100),
                }
                if src_host:
                    slice_config_data["src_host"] = src_host
                if dst_host:
                    slice_config_data["dst_host"] = dst_host

                actions.append(LLMAction(
                    id=f"act_{intent_obj.id}_slice",
                    type=ActionType.SLICE_CREATE,
                    target=switch_target,
                    parameters={
                        "slice_name": slice_name,
                        "resources": resources if resources else ["network"],
                        "bandwidth": params.get('bandwidth', 100),
                        "config_data": slice_config_data,
                    },
                    priority=1000,
                    timeout=30,
                    description=f"Create slice '{slice_name}'"
                        + (f" between {src_host} and {dst_host}" if src_host and dst_host else ""),
                ))

            # Generic config
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
        # Delete slice
        elif any(w in action_words for w in ['remove', 'delete']):
            switch_target = _find_switch_target(resources, network_state)

            # Delete slice
            if any('slice' in t for t in targets) or 'slice' in raw:
                host_resources = [r for r in (resources or []) if _re.match(r'^h\d+$', str(r), _re.IGNORECASE)]
                src_host = host_resources[0] if len(host_resources) >= 1 else None
                dst_host = host_resources[1] if len(host_resources) >= 2 else None
                del_config = {}
                if src_host:
                    del_config["src_host"] = src_host
                if dst_host:
                    del_config["dst_host"] = dst_host
                actions.append(LLMAction(
                    id=f"act_{intent_obj.id}_slice_del",
                    type=ActionType.SLICE_DELETE,
                    target=switch_target,
                    parameters={"config_data": del_config},
                    priority=1000,
                    timeout=30,
                    description=f"Delete slice"
                        + (f" between {src_host} and {dst_host}" if src_host and dst_host else ""),
                ))

            # Delete flow rules
            elif any('flow' in t or 'rule' in t for t in targets) or 'flow' in raw:
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
        # Generic fallback
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

    # ── QUERY intents → no network actions ──
    elif intent_type == IntentType.QUERY:
        pass

    return actions


def setup_logging():
    """Configure logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('integration.log')
        ]
    )


def main():
    """Main entry point"""
    setup_logging()
    logger = logging.getLogger("MainIntegration")
    
    try:
        # 1. Initialize Network State Collector
        errors = []
        try:
            collector = NetworkStateCollector(config_path=None, environment="development")
        except Exception as e:
            errors.append(("Network State Collector", str(e)))

        # 2. Initialize LLM Module (all components)
        try:
            intent_parser = IntentParser()
            chatgpt_client = ChatGPTClient()
            context_analyzer = ContextAnalyzer()
            action_sequencer = ActionSequencer()
            validator = Validator()
            action_output = ActionOutputService()
            prompt_system = PromptEngineeringSystem()
            confidence_extractor = ConfidenceCriteriaExtractor()
        except Exception as e:
            errors.append(("LLM Module", str(e)))

        # 3. Initialize Northbound Script Generator
        try:
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
        except Exception as e:
            errors.append(("Northbound Script Generator", str(e)))

        # Restore console logging

        # Show startup result
        if errors:
            print("\n╔══════════════════════════════════════════════════════════╗")
            print("║  ⚠  STARTUP COMPLETED WITH ERRORS                      ║")
            print("╚══════════════════════════════════════════════════════════╝")
            for module, err in errors:
                print(f"  ✗ {module}: {err}")
            print()
            # If critical modules failed, abort
            if any(m in ("Network State Collector",) for m, _ in errors):
                logger.error("Critical module failed to initialize. Exiting.")
                sys.exit(1)
        else:
            print("\n╔══════════════════════════════════════════════════════════╗")
            print("║  ✓  All modules initialized — ready                     ║")
            print("╠══════════════════════════════════════════════════════════╣")
            print("║  Commands:                                              ║")
            print("║    collect                  Collect network state        ║")
            print("║    collect --security-scan  + security scan (all hosts)  ║")
            print("║    intent <text>            Process a natural language   ║")
            print("║    health                   System health check          ║")
            print("║    clean                    Clear application cache      ║")
            print("║    quit                     Exit                         ║")
            print("╚══════════════════════════════════════════════════════════╝\n")
        
        while True:
            try:
                # Read user command
                user_input = input("\n> ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    logger.info("Shutting down...")
                    break
                
                # Command: collect [--security-scan [host ...]]
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
                            logger.info(f"Collecting state + security scan for: {', '.join(host_filter)}")
                        else:
                            logger.info("Collecting state + security scan (all hosts)...")
                    else:
                        logger.info("Collecting network state...")

                    snapshot = collector.collect_snapshot(
                        security_scan=security_scan,
                        host_filter=host_filter
                    )

                    if snapshot:
                        logger.info(f"✓ Snapshot collected successfully")
                        logger.info(f"  Timestamp: {snapshot.get_timestamp_iso()}")
                        logger.info(f"  Switches: {len(snapshot.topology.switches)}")
                        logger.info(f"  Links: {len(snapshot.topology.links)}")

                        # Convert and save to cache + history
                        network_state = snapshot_to_network_state(snapshot)
                        update_context_cache(context_analyzer, network_state)
                        history_file = save_state_to_history(network_state)
                        logger.info(f"  ✓ State saved to cache and {history_file}")

                    else:
                        logger.error("✗ Error collecting snapshot")

                    continue
                
                # Command: health
                if user_input.lower() == 'health':
                    logger.info("Checking system health...")
                    health = collector.get_health_status()
                    
                    logger.info(f"Overall status: {health.overall_status.value}")
                    logger.info(f"Uptime: {health.uptime_seconds:.1f} seconds")
                    
                    if health.components:
                        logger.info("Components:")
                        for name, component in health.components.items():
                            status_icon = "✓" if component.status.value == "healthy" else "✗"
                            logger.info(f"  {status_icon} {name}: {component.status.value}")
                    
                    continue
                
                # Command: clean
                if user_input.lower() == 'clean':
                    logger.info("Cleaning application cache...")
                    result = clean_application_cache(verbose=False)
                    logger.info(f"  ✓ data/:         {result['data_files']} file(s) removed")
                    logger.info(f"  ✓ __pycache__:   {result['pycache_dirs']} directory(ies) removed")
                    logger.info("Cache cleaned successfully")
                    continue
                
                # Command: intent
                if user_input.lower().startswith('intent '):
                    intent_text = user_input[7:].strip()
                    
                    if not intent_text:
                        logger.warning("Please provide an intent after 'intent'")
                        continue
                    
                    logger.info(f"Processing intent: '{intent_text}'")
                    logger.info("=" * 60)
                    
                    # Step 1: Collect network state
                    logger.info("Step 1: Collecting network state...")
                    snapshot = collector.collect_snapshot()
                    
                    if not snapshot:
                        logger.error("✗ Unable to collect network state")
                        continue
                    
                    logger.info(f"✓ Network state collected")
                    logger.info(f"  Switches: {len(snapshot.topology.switches)}, Links: {len(snapshot.topology.links)}")
                    
                    # Convert snapshot to NetworkState for LLM services
                    network_state = snapshot_to_network_state(snapshot)
                    
                    # Update cache and save to history
                    update_context_cache(context_analyzer, network_state)
                    save_state_to_history(network_state)
                    
                    # Step 2: Parse the intent
                    logger.info("\nStep 2: Parsing intent...")
                    intent_obj = intent_parser.parse_intent(intent_text, user_id="cli_user")
                    logger.info(f"✓ Intent parsed")
                    logger.info(f"  Type: {intent_obj.intent_type.value}")
                    logger.info(f"  Confidence: {intent_obj.confidence:.2f}")
                    logger.info(f"  Entities extracted: {len(intent_obj.entities)}")
                    
                    # Check if clarification is needed
                    if intent_obj.confidence < 0.7:
                        logger.warning("⚠ Low confidence, clarification may be needed")
                        ambiguity_analysis = intent_parser.detect_ambiguity(intent_obj, network_state)
                        if ambiguity_analysis.get('clarification_needed'):
                            logger.warning("Clarification needed:")
                            for question in ambiguity_analysis.get('questions', []):
                                logger.warning(f"  - {question}")
                            
                            # Ask the user if they want to continue
                            response = input("\nContinue anyway? (y/n): ").strip().lower()
                            if response != 'y':
                                logger.info("Operation cancelled")
                                continue
                    
                    # Step 3: Analyze context
                    logger.info("\nStep 3: Analyzing network context...")
                    contextualized_intent = context_analyzer.analyze_context(intent_obj)
                    logger.info(f"✓ Context analyzed")
                    
                    if contextualized_intent.conflicts:
                        logger.warning("⚠ Conflicts detected:")
                        for conflict in contextualized_intent.conflicts:
                            logger.warning(f"  - {conflict}")
                    
                    if contextualized_intent.recommendations:
                        logger.info("Recommendations:")
                        for rec in contextualized_intent.recommendations:
                            logger.info(f"  - {rec}")
                    
                    # Step 4: Generate actions
                    # If confidence is high, generate rule-based actions without ChatGPT
                    use_rule_based = intent_obj.confidence >= RULE_BASED_CONFIDENCE_THRESHOLD

                    if intent_obj.intent_type == IntentType.QUERY:
                        logger.info("\nStep 4: QUERY intent — no network actions to generate.")
                        logger.info("  Use 'collect' or 'health' to get network information.")
                        continue

                    actions = []

                    if use_rule_based:
                        logger.info(f"\nStep 4: RULE-BASED action generation (confidence {intent_obj.confidence:.2f} >= {RULE_BASED_CONFIDENCE_THRESHOLD})")
                        actions = generate_actions_rule_based(intent_obj, network_state)
                        # Check if rule-based produced only generic CONFIG_CHANGE actions
                        # (these are fallback placeholders that don't do anything useful)
                        has_specific_actions = any(
                            a.type in (ActionType.FLOW_MOD, ActionType.SLICE_CREATE,
                                       ActionType.SLICE_MODIFY, ActionType.SLICE_DELETE,
                                       ActionType.LOAD_BALANCE)
                            or (a.type == ActionType.CONFIG_CHANGE
                                and a.parameters.get("config_type") not in ("general", "anomaly_fix"))
                            for a in actions
                        )
                        if actions and has_specific_actions:
                            logger.info(f"✓ {len(actions)} actions generated (rule-based, no ChatGPT)")
                        else:
                            if actions:
                                logger.warning("⚠ Rule-based produced only generic actions, falling back to ChatGPT...")
                            else:
                                logger.warning("⚠ No actions generated by rule-based, falling back to ChatGPT...")
                            actions = []
                            use_rule_based = False

                    if not use_rule_based:
                        if intent_obj.confidence >= RULE_BASED_CONFIDENCE_THRESHOLD:
                            logger.info(f"\nStep 4: Generating actions with ChatGPT (confidence {intent_obj.confidence:.2f} >= {RULE_BASED_CONFIDENCE_THRESHOLD}, but rule-based produced insufficient results)")
                        else:
                            logger.info(f"\nStep 4: Generating actions with ChatGPT (confidence {intent_obj.confidence:.2f} < {RULE_BASED_CONFIDENCE_THRESHOLD})")

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
                            logger.info(f"✓ LLM response received")
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
                            logger.error(f"✗ ChatGPT error: {e}", exc_info=True)
                            continue

                    if not actions:
                        logger.warning("⚠ No actions generated. Check the intent and try again.")
                        continue

                    try:
                        # Step 5: Sequence actions
                        logger.info(f"\nStep 5: Sequencing {len(actions)} actions...")
                        action_sequence = action_sequencer.sequence_actions(
                            actions,
                            intent_id=intent_obj.id,
                            sequence_id=f"seq_{intent_obj.id}"
                        )
                        logger.info(f"✓ {len(action_sequence.actions)} actions sequenced")

                        # Show the actions
                        logger.info("Proposed actions:")
                        for i, action in enumerate(action_sequence.actions, 1):
                            logger.info(f"  {i}. {action.type.value} on {action.target}")

                        # Step 6: Validate actions
                        logger.info("\nStep 6: Validating actions...")
                        validation_result = validator.validate_actions(action_sequence)

                        if not validation_result.is_valid:
                            # If from ChatGPT, filter out invalid actions and retry with valid ones
                            if not use_rule_based and validation_result.errors:
                                logger.warning("⚠ Some ChatGPT actions failed validation, filtering invalid ones...")
                                for error in validation_result.errors:
                                    logger.warning(f"  - {error}")

                                # Identify invalid action IDs from error messages
                                import re as _re_val
                                invalid_ids = set()
                                for error in validation_result.errors:
                                    m = _re_val.match(r'Action (\S+):', error)
                                    if m:
                                        invalid_ids.add(m.group(1))

                                # Filter to valid actions only
                                valid_actions = [a for a in action_sequence.actions if a.id not in invalid_ids]

                                if valid_actions:
                                    logger.info(f"  Proceeding with {len(valid_actions)} valid actions (dropped {len(action_sequence.actions) - len(valid_actions)})")
                                    action_sequence = action_sequencer.sequence_actions(
                                        valid_actions,
                                        intent_id=intent_obj.id,
                                        sequence_id=f"seq_{intent_obj.id}_filtered"
                                    )
                                else:
                                    logger.error("✗ No valid actions remaining after filtering.")
                                    continue
                            else:
                                logger.error("✗ Validation failed:")
                                for error in validation_result.errors:
                                    logger.error(f"  - {error}")
                                continue

                        logger.info("✓ Actions validated successfully")

                        # Step 7: Save actions for execution
                        logger.info("\nStep 7: Saving actions...")
                        output_result = action_output.save_actions(
                            action_sequence
                        )
                        logger.info(f"✓ Actions saved")

                        # Step 8: Ask for confirmation and execute
                        logger.info("\n" + "=" * 60)
                        response = input("Execute these actions on the network? (y/n): ").strip().lower()

                        if response == 'y':
                            logger.info("\nStep 8: Executing actions on the network...")

                            results = []
                            for i, action in enumerate(action_sequence.actions, 1):
                                logger.info(f"  Executing action {i}/{len(action_sequence.actions)}: {action.id}")

                                # Convert the action to NorthboundAction format
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
                                    logger.info(f"  ✓ Action {action.id} completed ({result.duration:.2f}s)")
                                else:
                                    logger.error(f"  ✗ Action {action.id} failed: {result.error}")

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

                            # Step 9: Verify final state
                            logger.info("\nStep 9: Verifying final state...")
                            final_snapshot = collector.collect_snapshot()

                            if final_snapshot:
                                logger.info("✓ Final state collected")
                                logger.info(f"  Switches: {len(final_snapshot.topology.switches)}")
                                logger.info(f"  Links: {len(final_snapshot.topology.links)}")

                                if len(final_snapshot.topology.switches) != len(snapshot.topology.switches):
                                    logger.info(f"  Δ Switches: {len(final_snapshot.topology.switches) - len(snapshot.topology.switches)}")
                                if len(final_snapshot.topology.links) != len(snapshot.topology.links):
                                    logger.info(f"  Δ Links: {len(final_snapshot.topology.links) - len(snapshot.topology.links)}")

                            # Summary
                            successful = sum(1 for r in results if r.status.value == "success")
                            failed = sum(1 for r in results if r.status.value == "failed")

                            logger.info("\n" + "=" * 60)
                            logger.info("EXECUTION SUMMARY")
                            logger.info("=" * 60)
                            logger.info(f"Total actions: {len(results)}")
                            logger.info(f"Succeeded: {successful}")
                            logger.info(f"Failed: {failed}")
                            logger.info(f"Success rate: {(successful / len(results) * 100):.1f}%")
                            logger.info("=" * 60)
                        else:
                            logger.info("Execution cancelled by user")

                    except Exception as e:
                        logger.error(f"✗ Processing error: {e}", exc_info=True)
                    
                    continue
                
                # Unrecognized command
                logger.warning(f"Unrecognized command: '{user_input}'")
                logger.info("Use 'collect', 'intent <text>', 'health', 'clean', or 'quit'")
                
            except KeyboardInterrupt:
                logger.info("\nInterrupt received...")
                break
            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
        
        # Cleanup
        logger.info("Closing connections...")
        action_processor.close()
        logger.info("✓ Program terminated")
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
