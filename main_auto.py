#!/usr/bin/env python3
"""
Main Autonomo — Monitora la rete e reagisce automaticamente alle anomalie.
Gira in background senza intervento dell'utente.

Cookie range: 0x1000-0x1FFF
Priority range: 40000-49999
(Le regole dell'utente da main.py hanno priorità più alta e vincono sempre)

Anomalie gestite:
  - switch_down   → rerouting del traffico sugli switch rimasti
  - switch_added  → inizializzazione con flow rule base
  - link_down     → rerouting: installa percorsi alternativi
  - switch_inactive → tentativo di riattivazione con flow rule base
  - port_stats    → rilevamento congestione e bilanciamento
"""

import json
import logging
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Optional, Dict, Any, List, Set, Tuple

from network_state_collector.collector import NetworkStateCollector
from src.services.context_analyzer import ContextAnalyzer
from src.services.action_sequencer import ActionSequencer
from src.services.validator import Validator
from src.services.action_output import ActionOutputService
from northbound_script_generator.action_processor import ActionProcessor
from northbound_script_generator.models import NetworkAction as NorthboundAction
from src.models.actions import NetworkAction as LLMAction, ActionType
from src.models.network import (
    NetworkState, Topology, Switch, Link,
    NetworkMetrics, BandwidthMetrics, LatencyMetrics, UtilizationMetrics,
)
from src.models.core import NetworkSnapshot
from src.models.intent import IntentType

from main import (
    snapshot_to_network_state,
    save_state_to_history,
    update_context_cache,
)

# ── Configurazione ──
COOKIE_AUTO = 0x1000
POLL_INTERVAL = 15          # secondi tra un check e l'altro
PRIORITY_AUTO = 40000       # priorità base per regole automatiche
PRIORITY_REROUTE = 41000    # priorità per regole di rerouting (sopra le auto base)
HISTORY_DIR = "data/history"
AUTO_LOG_FILE = "auto_monitor.log"


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(AUTO_LOG_FILE),
        ],
    )


# ====================================================================== #
#  Grafo di rete — per calcolare percorsi alternativi                     #
# ====================================================================== #

class NetworkGraph:
    """
    Grafo della topologia di rete costruito dai link.
    Usato per trovare percorsi alternativi quando un link o switch cade.
    """

    def __init__(self):
        # adjacency: switch_id → {neighbor_switch_id: (src_port, dst_port)}
        self.adjacency = defaultdict(dict)  # type: Dict[str, Dict[str, Tuple[int, int]]]
        # host_map: host_ip → (switch_id, port)
        self.host_map = {}  # type: Dict[str, Tuple[str, int]]

    def build_from_state(self, state: NetworkState):
        """Costruisce il grafo dalla topologia corrente."""
        self.adjacency.clear()

        if not state.topology.links:
            return

        for link in state.topology.links:
            src = link.source_switch
            dst = link.destination_switch
            src_port = link.source_port
            dst_port = link.destination_port
            self.adjacency[src][dst] = (src_port, dst_port)
            self.adjacency[dst][src] = (dst_port, src_port)

    def build_host_map(self, state: NetworkState):
        """
        Costruisce la mappa host → (switch, porta).
        Convenzione Mininet: h<N> è connesso allo switch sulla porta N
        (o porta 1 se c'è un solo host per switch).
        """
        self.host_map.clear()
        for sw in state.topology.switches:
            # In una topologia Mininet standard, gli host sono sulle porte
            # non usate dai link inter-switch
            used_ports = set()
            for neighbor, (src_port, _) in self.adjacency.get(sw.id, {}).items():
                used_ports.add(src_port)

            # Le porte rimanenti sono probabilmente connesse a host
            if sw.ports:
                for port in sw.ports:
                    if port not in used_ports and port != 0xFFFE:  # skip LOCAL port
                        # Convenzione: host su porta N ha IP 10.0.0.N
                        host_ip = f"10.0.0.{port}"
                        self.host_map[host_ip] = (sw.id, port)

    def find_path(self, src_switch: str, dst_switch: str,
                  exclude_switches: Set[str] = None,
                  exclude_links: Set[Tuple[str, str]] = None) -> Optional[List[str]]:
        """
        BFS per trovare un percorso tra due switch,
        escludendo switch e link specificati.
        """
        if exclude_switches is None:
            exclude_switches = set()
        if exclude_links is None:
            exclude_links = set()

        if src_switch == dst_switch:
            return [src_switch]

        if src_switch in exclude_switches or dst_switch in exclude_switches:
            return None

        visited = {src_switch}
        queue = [[src_switch]]

        while queue:
            path = queue.pop(0)
            current = path[-1]

            for neighbor in self.adjacency.get(current, {}):
                if neighbor in visited or neighbor in exclude_switches:
                    continue
                if (current, neighbor) in exclude_links or (neighbor, current) in exclude_links:
                    continue

                new_path = path + [neighbor]
                if neighbor == dst_switch:
                    return new_path

                visited.add(neighbor)
                queue.append(new_path)

        return None  # nessun percorso trovato

    def get_all_switches(self) -> Set[str]:
        return set(self.adjacency.keys())

    def get_port_between(self, sw_a: str, sw_b: str) -> Optional[Tuple[int, int]]:
        """Ritorna (porta_su_a, porta_su_b) per il link tra a e b."""
        if sw_b in self.adjacency.get(sw_a, {}):
            return self.adjacency[sw_a][sw_b]
        return None


# ====================================================================== #
#  Network Monitor                                                         #
# ====================================================================== #

class NetworkMonitor:
    """Monitora la rete e reagisce automaticamente."""

    def __init__(self):
        self.logger = logging.getLogger("AutoMonitor")

        # Componenti
        self.collector = NetworkStateCollector(config_path=None, environment="development")
        self.context_analyzer = ContextAnalyzer()
        self.action_sequencer = ActionSequencer()
        self.validator = Validator()
        self.action_output = ActionOutputService()
        self.action_processor = ActionProcessor({
            "comnetsemu_host": "localhost",
            "comnetsemu_port": 6653,
            "ryu_host": "localhost",
            "ryu_port": 8080,
            "max_retries": 3,
            "retry_delay": 2.0,
            "timeout_seconds": 30,
        })

        # Stato
        self.previous_state = None   # type: Optional[NetworkState]
        self.previous_snapshot = None  # type: Optional[NetworkSnapshot]
        self.graph = NetworkGraph()
        self.previous_graph = NetworkGraph()
        self.anomaly_history = []    # type: List[Dict[str, Any]]
        self.installed_reroutes = [] # type: List[str]  # action IDs installati
        self.running = True

    # ------------------------------------------------------------------ #
    #  Raccolta stato                                                      #
    # ------------------------------------------------------------------ #

    def collect_state(self) -> Optional[NetworkState]:
        """Raccoglie lo stato della rete e lo salva."""
        snapshot = self.collector.collect_snapshot()
        if not snapshot:
            self.logger.error("Impossibile raccogliere lo snapshot")
            return None

        network_state = snapshot_to_network_state(snapshot)
        update_context_cache(self.context_analyzer, network_state)
        save_state_to_history(network_state)

        self.previous_snapshot = snapshot
        return network_state

    # ------------------------------------------------------------------ #
    #  Rilevamento anomalie                                                #
    # ------------------------------------------------------------------ #

    def detect_anomalies(self, current: NetworkState) -> List[Dict[str, Any]]:
        """Confronta lo stato corrente con quello precedente e rileva anomalie."""
        anomalies = []

        if self.previous_state is None:
            self.previous_state = current
            return anomalies

        prev = self.previous_state

        # 1. Switch scomparsi
        prev_switch_ids = {s.id for s in prev.topology.switches}
        curr_switch_ids = {s.id for s in current.topology.switches}

        for sw_id in (prev_switch_ids - curr_switch_ids):
            anomalies.append({
                "type": "switch_down",
                "severity": "critical",
                "target": sw_id,
                "message": f"Switch {sw_id} non più raggiungibile",
                "prev_state": prev,
                "curr_state": current,
            })

        # 2. Nuovi switch
        for sw_id in (curr_switch_ids - prev_switch_ids):
            anomalies.append({
                "type": "switch_added",
                "severity": "info",
                "target": sw_id,
                "message": f"Nuovo switch rilevato: {sw_id}",
                "curr_state": current,
            })

        # 3. Link persi
        prev_links = {l.id: l for l in prev.topology.links} if prev.topology.links else {}
        curr_links = {l.id: l for l in current.topology.links} if current.topology.links else {}

        for link_id in (set(prev_links) - set(curr_links)):
            link = prev_links[link_id]
            anomalies.append({
                "type": "link_down",
                "severity": "high",
                "target": link_id,
                "link": link,
                "message": (
                    f"Link perso: {link.source_switch}:{link.source_port} "
                    f"↔ {link.destination_switch}:{link.destination_port}"
                ),
                "prev_state": prev,
                "curr_state": current,
            })

        # 4. Switch inattivi
        for sw in current.topology.switches:
            if hasattr(sw, "status") and sw.status == "inactive":
                anomalies.append({
                    "type": "switch_inactive",
                    "severity": "high",
                    "target": sw.id,
                    "message": f"Switch {sw.id} risulta inattivo",
                    "curr_state": current,
                })

        self.previous_state = current
        return anomalies

    # ------------------------------------------------------------------ #
    #  Generazione azioni — REROUTING                                      #
    # ------------------------------------------------------------------ #

    def _generate_reroute_for_link_down(self, anomaly: Dict[str, Any]) -> List[LLMAction]:
        """
        Quando un link cade, trova percorsi alternativi e installa
        flow rules per deviare il traffico.
        """
        actions = []
        link = anomaly["link"]
        curr_state = anomaly["curr_state"]

        sw_a = link.source_switch
        sw_b = link.destination_switch
        port_a = link.source_port
        port_b = link.destination_port

        self.logger.info(
            f"Rerouting: link {sw_a}:{port_a} ↔ {sw_b}:{port_b} perso, "
            f"cerco percorso alternativo..."
        )

        # Costruisci il grafo dalla topologia CORRENTE (senza il link perso)
        self.graph.build_from_state(curr_state)
        self.graph.build_host_map(curr_state)

        # Trova percorso alternativo tra sw_a e sw_b
        alt_path = self.graph.find_path(sw_a, sw_b)

        if alt_path and len(alt_path) > 1:
            self.logger.info(
                f"Rerouting: percorso alternativo trovato: "
                f"{' → '.join(alt_path)}"
            )

            # Installa flow rules lungo il percorso alternativo
            # Per ogni coppia di switch consecutivi nel percorso,
            # installa una regola che inoltra il traffico sulla porta giusta
            ts = int(time.time())

            for i in range(len(alt_path) - 1):
                curr_sw = alt_path[i]
                next_sw = alt_path[i + 1]

                ports = self.graph.get_port_between(curr_sw, next_sw)
                if not ports:
                    self.logger.warning(
                        f"Rerouting: nessuna porta trovata tra {curr_sw} e {next_sw}"
                    )
                    continue

                out_port = ports[0]  # porta su curr_sw verso next_sw

                # Flow rule: tutto il traffico che doveva andare verso sw_b
                # viene inoltrato sulla porta verso il prossimo hop
                action_id = f"auto_reroute_{curr_sw}_{ts}_{i}"
                actions.append(LLMAction(
                    id=action_id,
                    type=ActionType.FLOW_MOD,
                    target=curr_sw,
                    parameters={
                        "operation": "add",
                        "match": {},
                        "actions": [{"type": "OUTPUT", "port": out_port}],
                        "cookie": COOKIE_AUTO,
                    },
                    priority=PRIORITY_REROUTE,
                    timeout=3600,
                    description=(
                        f"Auto reroute: {curr_sw} → porta {out_port} "
                        f"(verso {next_sw})"
                    ),
                ))

            # Anche il percorso inverso (da sw_b verso sw_a)
            rev_path = list(reversed(alt_path))
            for i in range(len(rev_path) - 1):
                curr_sw = rev_path[i]
                next_sw = rev_path[i + 1]

                ports = self.graph.get_port_between(curr_sw, next_sw)
                if not ports:
                    continue

                out_port = ports[0]
                action_id = f"auto_reroute_rev_{curr_sw}_{ts}_{i}"
                actions.append(LLMAction(
                    id=action_id,
                    type=ActionType.FLOW_MOD,
                    target=curr_sw,
                    parameters={
                        "operation": "add",
                        "match": {},
                        "actions": [{"type": "OUTPUT", "port": out_port}],
                        "cookie": COOKIE_AUTO,
                    },
                    priority=PRIORITY_REROUTE,
                    timeout=3600,
                    description=(
                        f"Auto reroute reverse: {curr_sw} → porta {out_port} "
                        f"(verso {next_sw})"
                    ),
                ))

        else:
            self.logger.error(
                f"Rerouting: NESSUN percorso alternativo tra {sw_a} e {sw_b}. "
                f"La rete è partizionata."
            )

        return actions

    def _generate_reroute_for_switch_down(self, anomaly: Dict[str, Any]) -> List[LLMAction]:
        """
        Quando uno switch cade, trova percorsi alternativi per tutti i flussi
        che passavano per quello switch.
        """
        actions = []
        dead_sw = anomaly["target"]
        curr_state = anomaly["curr_state"]

        self.logger.info(f"Rerouting: switch {dead_sw} down, ricalcolo percorsi...")

        # Costruisci grafo dalla topologia corrente (lo switch morto non c'è più)
        self.graph.build_from_state(curr_state)
        self.graph.build_host_map(curr_state)

        # Usa il grafo precedente per sapere chi era connesso allo switch morto
        neighbors = list(self.previous_graph.adjacency.get(dead_sw, {}).keys())

        if len(neighbors) < 2:
            self.logger.warning(
                f"Rerouting: switch {dead_sw} aveva {len(neighbors)} vicini, "
                f"nessun rerouting possibile"
            )
            return actions

        self.logger.info(
            f"Rerouting: switch {dead_sw} aveva vicini: {neighbors}"
        )

        # Per ogni coppia di vicini, trova un percorso alternativo
        ts = int(time.time())
        action_idx = 0

        for i, sw_a in enumerate(neighbors):
            for sw_b in neighbors[i + 1:]:
                # Cerca percorso alternativo escludendo lo switch morto
                alt_path = self.graph.find_path(
                    sw_a, sw_b,
                    exclude_switches={dead_sw}
                )

                if alt_path and len(alt_path) > 1:
                    self.logger.info(
                        f"Rerouting {sw_a} ↔ {sw_b}: {' → '.join(alt_path)}"
                    )

                    # Installa flow rules lungo il percorso
                    for j in range(len(alt_path) - 1):
                        curr_sw = alt_path[j]
                        next_sw = alt_path[j + 1]

                        ports = self.graph.get_port_between(curr_sw, next_sw)
                        if not ports:
                            continue

                        # Direzione andata
                        actions.append(LLMAction(
                            id=f"auto_swdown_{curr_sw}_{ts}_{action_idx}",
                            type=ActionType.FLOW_MOD,
                            target=curr_sw,
                            parameters={
                                "operation": "add",
                                "match": {},
                                "actions": [{"type": "OUTPUT", "port": ports[0]}],
                                "cookie": COOKIE_AUTO,
                            },
                            priority=PRIORITY_REROUTE,
                            timeout=3600,
                            description=(
                                f"Auto reroute (sw {dead_sw} down): "
                                f"{curr_sw} → porta {ports[0]}"
                            ),
                        ))
                        action_idx += 1

                else:
                    self.logger.warning(
                        f"Rerouting: nessun percorso alternativo {sw_a} ↔ {sw_b}"
                    )

        return actions

    # ------------------------------------------------------------------ #
    #  Generazione azioni — dispatcher                                     #
    # ------------------------------------------------------------------ #

    def generate_auto_actions(self, anomaly: Dict[str, Any]) -> List[LLMAction]:
        """Genera azioni correttive per un'anomalia rilevata."""
        anomaly_type = anomaly["type"]
        target = anomaly["target"]

        if anomaly_type == "switch_down":
            return self._generate_reroute_for_switch_down(anomaly)

        elif anomaly_type == "link_down":
            return self._generate_reroute_for_link_down(anomaly)

        elif anomaly_type == "switch_inactive":
            # Prova a reinstallare flow rule base
            return [LLMAction(
                id=f"auto_reactivate_{target}_{int(time.time())}",
                type=ActionType.FLOW_MOD,
                target=target,
                parameters={
                    "operation": "add",
                    "match": {},
                    "actions": [{"type": "OUTPUT", "port": "CONTROLLER"}],
                    "cookie": COOKIE_AUTO,
                },
                priority=PRIORITY_AUTO,
                timeout=3600,
                description=f"Auto: reinstall base flow on inactive {target}",
            )]

        elif anomaly_type == "switch_added":
            # Nuovo switch → flow rule base + OUTPUT:CONTROLLER
            # così simple_switch_13 può imparare i MAC
            return [LLMAction(
                id=f"auto_init_{target}_{int(time.time())}",
                type=ActionType.FLOW_MOD,
                target=target,
                parameters={
                    "operation": "add",
                    "match": {},
                    "actions": [{"type": "OUTPUT", "port": "CONTROLLER"}],
                    "cookie": COOKIE_AUTO,
                },
                priority=PRIORITY_AUTO,
                timeout=3600,
                description=f"Auto: initialize new switch {target}",
            )]

        return []

    # ------------------------------------------------------------------ #
    #  Esecuzione azioni                                                   #
    # ------------------------------------------------------------------ #

    def execute_actions(self, actions: List[LLMAction], anomaly: Dict[str, Any]):
        """Sequenzia, valida ed esegue le azioni automatiche."""
        if not actions:
            return

        try:
            seq_id = f"auto_seq_{int(time.time())}"
            intent_id = f"auto_{anomaly['type']}_{int(time.time())}"

            # Sequenzia
            action_sequence = self.action_sequencer.sequence_actions(
                actions, intent_id=intent_id, sequence_id=seq_id
            )
            self.logger.info(
                f"Auto: {len(action_sequence.actions)} azioni sequenziate per "
                f"anomalia '{anomaly['type']}'"
            )

            # Valida
            validation = self.validator.validate_actions(action_sequence)
            if not validation.is_valid:
                self.logger.error(
                    f"Auto: validazione fallita: {validation.errors}"
                )
                return

            # Salva
            self.action_output.save_actions(action_sequence)

            # Esegui
            executed = 0
            for i, action in enumerate(action_sequence.actions, 1):
                self.logger.info(
                    f"Auto: esecuzione {i}/{len(action_sequence.actions)}: "
                    f"{action.id}"
                )
                network_action = NorthboundAction(
                    id=action.id,
                    type=action.type,
                    target=action.target,
                    parameters=action.parameters,
                    priority=getattr(action, "priority", PRIORITY_AUTO),
                    timeout=getattr(action, "timeout", 30),
                )
                result = self.action_processor.execute_action(network_action)

                if result.status.value == "success":
                    self.logger.info(
                        f"  ✓ {action.id} completata ({result.duration:.2f}s)"
                    )
                    self.installed_reroutes.append(action.id)
                    executed += 1
                else:
                    self.logger.error(f"  ✗ {action.id} fallita: {result.error}")

            # Registra
            self.anomaly_history.append({
                "timestamp": datetime.now().isoformat(),
                "anomaly": {
                    "type": anomaly["type"],
                    "severity": anomaly["severity"],
                    "target": anomaly["target"],
                    "message": anomaly["message"],
                },
                "actions_generated": len(actions),
                "actions_executed": executed,
            })

        except Exception as e:
            self.logger.error(f"Auto: errore esecuzione: {e}", exc_info=True)

    # ------------------------------------------------------------------ #
    #  Loop principale                                                     #
    # ------------------------------------------------------------------ #

    def run(self):
        """Loop principale di monitoraggio."""
        self.logger.info("=" * 60)
        self.logger.info("Avvio Network Auto-Monitor")
        self.logger.info(f"  Intervallo polling: {POLL_INTERVAL}s")
        self.logger.info(f"  Cookie: 0x{COOKIE_AUTO:04X}")
        self.logger.info(f"  Priorità base: {PRIORITY_AUTO}")
        self.logger.info(f"  Priorità reroute: {PRIORITY_REROUTE}")
        self.logger.info(f"  Log file: {AUTO_LOG_FILE}")
        self.logger.info("=" * 60)

        # Primo collect per stabilire la baseline
        self.logger.info("Raccolta stato iniziale (baseline)...")
        initial_state = self.collect_state()
        if initial_state:
            self.previous_state = initial_state
            self.graph.build_from_state(initial_state)
            self.graph.build_host_map(initial_state)
            # Salva il grafo come "precedente" per il rerouting
            self.previous_graph.build_from_state(initial_state)
            self.previous_graph.build_host_map(initial_state)

            sw_count = len(initial_state.topology.switches)
            link_count = (
                len(initial_state.topology.links)
                if initial_state.topology.links else 0
            )
            self.logger.info(f"✓ Baseline: {sw_count} switch, {link_count} link")
        else:
            self.logger.warning(
                "⚠ Impossibile raccogliere baseline, continuo comunque"
            )

        # Loop di monitoraggio
        cycle = 0
        while self.running:
            try:
                time.sleep(POLL_INTERVAL)
                cycle += 1

                self.logger.info(f"\n--- Ciclo {cycle} ---")

                # 1. Raccogli stato
                current_state = self.collect_state()
                if not current_state:
                    self.logger.warning("Skip ciclo: impossibile raccogliere stato")
                    continue

                sw_count = len(current_state.topology.switches)
                link_count = (
                    len(current_state.topology.links)
                    if current_state.topology.links else 0
                )
                self.logger.info(f"Stato: {sw_count} switch, {link_count} link")

                # Aggiorna il grafo precedente PRIMA di rilevare anomalie
                self.previous_graph.build_from_state(self.previous_state)
                self.previous_graph.build_host_map(self.previous_state)

                # 2. Rileva anomalie
                anomalies = self.detect_anomalies(current_state)

                if not anomalies:
                    self.logger.info("✓ Nessuna anomalia rilevata")
                    continue

                # 3. Gestisci anomalie
                self.logger.warning(f"⚠ {len(anomalies)} anomalie rilevate:")
                for anomaly in anomalies:
                    self.logger.warning(
                        f"  [{anomaly['severity'].upper()}] {anomaly['message']}"
                    )

                    # Genera e esegui azioni correttive
                    actions = self.generate_auto_actions(anomaly)
                    if actions:
                        self.logger.info(
                            f"  → {len(actions)} azioni correttive generate"
                        )
                        self.execute_actions(actions, anomaly)
                    else:
                        self.logger.info(
                            "  → Nessuna azione automatica possibile"
                        )

            except KeyboardInterrupt:
                self.logger.info("\nInterruzione ricevuta, chiusura...")
                self.running = False
            except Exception as e:
                self.logger.error(
                    f"Errore nel ciclo {cycle}: {e}", exc_info=True
                )

        # Cleanup
        self.logger.info("Chiusura connessioni...")
        self.action_processor.close()

        # Salva report finale
        if self.anomaly_history:
            report_path = os.path.join(HISTORY_DIR, "auto_report.json")
            os.makedirs(HISTORY_DIR, exist_ok=True)
            with open(report_path, "w") as f:
                json.dump(self.anomaly_history, f, indent=2)
            self.logger.info(f"Report anomalie salvato in {report_path}")

        self.logger.info(
            f"Auto-monitor terminato. "
            f"Anomalie gestite: {len(self.anomaly_history)}"
        )


def main():
    setup_logging()
    monitor = NetworkMonitor()
    monitor.run()


if __name__ == "__main__":
    main()
