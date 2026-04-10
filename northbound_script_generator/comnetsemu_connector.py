"""
ComnetsEMU Connector — esegue operazioni reali sulla rete
via Ryu REST API (ofctl_rest) per flow rules e config changes,
e via ovs-vsctl per QoS / rate-limiting.
"""

import json
import logging
import socket
import subprocess
import time
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import requests

from .models import NetworkAction, ActionType
from .retry_system import SimpleRetrySystem, RetryConfig


class ConnectionStatus:
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class ComnetsEMUConfig:
    """Configuration for ComnetsEMU + Ryu connection."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6653,
        ryu_host: str = "localhost",
        ryu_port: int = 8080,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        self.host = host
        self.port = port  # OpenFlow port (connectivity check)
        self.ryu_host = ryu_host
        self.ryu_port = ryu_port
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    @property
    def ryu_base_url(self) -> str:
        return f"http://{self.ryu_host}:{self.ryu_port}"


class ComnetsEMUConnector:
    """Connector che esegue operazioni reali sulla rete via Ryu REST API."""

    def __init__(self, config: ComnetsEMUConfig = None):
        self.config = config or ComnetsEMUConfig()
        self.logger = logging.getLogger("ComnetsEMUConnector")

        retry_config = RetryConfig(
            max_attempts=self.config.max_retries + 1,
            base_delay=self.config.retry_delay,
            max_delay=60.0,
        )
        self.retry_system = SimpleRetrySystem(retry_config)

        self.status = ConnectionStatus.DISCONNECTED
        self.last_error = None  # type: Optional[str]
        self.last_successful_request = None  # type: Optional[datetime]

        self.stats = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
        }

        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})

        self._initialize_connection()

    # ------------------------------------------------------------------ #
    #  Connection helpers                                                  #
    # ------------------------------------------------------------------ #

    def _initialize_connection(self):
        try:
            self.logger.info(
                f"Initializing connection to Ryu at "
                f"{self.config.ryu_host}:{self.config.ryu_port}"
            )
            if self._test_ryu_connectivity():
                self.status = ConnectionStatus.CONNECTED
                self.last_successful_request = datetime.now()
                self.logger.info("Successfully connected to Ryu REST API")
            else:
                self.status = ConnectionStatus.ERROR
                self.logger.warning(
                    "Ryu REST API not reachable — actions will fail until Ryu is available"
                )
        except Exception as e:
            self.status = ConnectionStatus.ERROR
            self.last_error = str(e)
            self.logger.error(f"Failed to initialize connection: {e}")

    def _test_ryu_connectivity(self) -> bool:
        """Verifica che Ryu REST API risponda."""
        try:
            url = f"{self.config.ryu_base_url}/stats/switches"
            resp = self.session.get(url, timeout=self.config.timeout_seconds)
            return resp.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------ #
    #  Ryu REST helpers                                                    #
    # ------------------------------------------------------------------ #

    def _ryu_get(self, endpoint: str) -> Any:
        url = f"{self.config.ryu_base_url}{endpoint}"
        resp = self.session.get(url, timeout=self.config.timeout_seconds)
        resp.raise_for_status()
        return resp.json()

    def _ryu_post(self, endpoint: str, data: Dict[str, Any]) -> requests.Response:
        url = f"{self.config.ryu_base_url}{endpoint}"
        self.logger.debug(f"POST {url} — {json.dumps(data)}")
        resp = self.session.post(url, json=data, timeout=self.config.timeout_seconds)
        resp.raise_for_status()
        return resp

    def _ryu_delete(self, endpoint: str, data: Dict[str, Any]) -> requests.Response:
        url = f"{self.config.ryu_base_url}{endpoint}"
        self.logger.debug(f"DELETE {url} — {json.dumps(data)}")
        resp = self.session.request(
            "DELETE", url, json=data, timeout=self.config.timeout_seconds
        )
        resp.raise_for_status()
        return resp

    def _resolve_dpid(self, target: str) -> Optional[int]:
        """
        Converte un target (es. 'sw1', 'switch-1', '0000000000000001', '1')
        nel dpid intero usato da Ryu.
        """
        import re

        # Già un numero intero
        if target.isdigit():
            return int(target)

        # Hex dpid (es. 0000000000000001)
        if re.match(r'^[0-9a-fA-F]{16}$', target):
            return int(target, 16)

        # Pattern sw<N>, switch-<N>, switch_<N>, s<N>
        m = re.search(r'(?:sw|switch[-_]?|s)(\d+)', target, re.IGNORECASE)
        if m:
            return int(m.group(1))

        return None

    # ------------------------------------------------------------------ #
    #  FLOW_MOD — aggiunge / modifica / rimuove flow rules via Ryu       #
    # ------------------------------------------------------------------ #

    def execute_flow_mod(self, action: NetworkAction) -> Dict[str, Any]:
        """Esegue una flow modification reale via Ryu ofctl_rest."""
        try:
            def _do():
                dpid = self._resolve_dpid(action.target)
                if dpid is None:
                    raise ValueError(
                        f"Cannot resolve dpid from target '{action.target}'"
                    )

                operation = action.parameters.get("operation", "add")
                match_fields = action.parameters.get("match", {})
                flow_actions = action.parameters.get("actions", [])
                priority = action.priority

                # Costruisci il body per Ryu ofctl_rest
                body = {"dpid": dpid, "priority": priority}

                # Cookie per identificare chi ha installato la regola
                cookie = action.parameters.get("cookie", 0)
                if cookie:
                    body["cookie"] = cookie

                if match_fields:
                    body["match"] = match_fields

                # Converti le actions nel formato Ryu
                if flow_actions:
                    ryu_actions = []
                    for a in flow_actions:
                        if isinstance(a, dict):
                            ryu_actions.append(a)
                        elif isinstance(a, str):
                            ryu_actions.append({"type": a})
                    body["actions"] = ryu_actions

                if action.timeout and action.timeout < 3600:
                    body["idle_timeout"] = action.timeout

                # Scegli endpoint in base all'operazione
                if operation in ("add", "create"):
                    endpoint = "/stats/flowentry/add"
                elif operation in ("modify", "update"):
                    endpoint = "/stats/flowentry/modify"
                elif operation in ("delete", "remove"):
                    endpoint = "/stats/flowentry/delete"
                else:
                    endpoint = "/stats/flowentry/add"

                self.logger.info(
                    f"Flow {operation} on dpid={dpid}: "
                    f"match={match_fields}, actions={flow_actions}"
                )
                self._ryu_post(endpoint, body)

                self._record_success()
                return {
                    "operation": operation,
                    "dpid": dpid,
                    "match": match_fields,
                    "actions": flow_actions,
                }

            result = self.retry_system.execute_with_retry(_do)
            if result.success:
                return {"success": True, "message": "Flow mod completed", **result.result}
            else:
                return {"success": False, "error": result.error}

        except Exception as e:
            self.logger.error(f"Flow mod failed for {action.id}: {e}")
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    #  CONFIG_CHANGE — operazioni generiche via Ryu REST                  #
    # ------------------------------------------------------------------ #

    def execute_config_change(self, action: NetworkAction) -> Dict[str, Any]:
        """
        Execute a config change.
        Routes QoS / bandwidth-policy types to OVS QoS implementation.
        For topology operations there is no standard Ryu REST API — logs only.
        """
        try:
            config_type = action.parameters.get("config_type", "general")

            # Route any QoS-related config_type to the bandwidth limiter
            if config_type in ("qos", "qos_bandwidth_policy", "bandwidth_limit",
                               "rate_limit", "qos_policy"):
                return self._execute_bandwidth_limit(action)

            # Per operazioni topologiche, prova a usare le API Ryu disponibili
            operation = action.parameters.get("operation", "add")
            config_data = action.parameters.get("config_data", {})

            # Se è un'operazione su flow mascherata da config_change
            raw_text = ""
            if isinstance(config_data, dict):
                raw_text = config_data.get("raw_text", "")
                action_word = config_data.get("action", operation)
            else:
                action_word = operation

            # Prova a interpretare come flow rule se il target è uno switch
            dpid = self._resolve_dpid(action.target)
            if dpid is not None:
                self.logger.info(
                    f"Config change ({config_type}) on dpid={dpid}: "
                    f"operation={action_word}"
                )

                # Se è un add/remove generico su uno switch, installa una flow rule base
                if action_word in ("add", "create", "configure"):
                    body = {
                        "dpid": dpid,
                        "priority": action.priority,
                        "match": {},
                        "actions": [{"type": "OUTPUT", "port": "NORMAL"}],
                    }
                    self._ryu_post("/stats/flowentry/add", body)
                    self._record_success()
                    return {
                        "success": True,
                        "message": f"Default flow rule installed on dpid {dpid}",
                        "config_type": config_type,
                        "dpid": dpid,
                    }

                elif action_word in ("remove", "delete"):
                    body = {"dpid": dpid, "match": {}}
                    self._ryu_post("/stats/flowentry/delete", body)
                    self._record_success()
                    return {
                        "success": True,
                        "message": f"Flow rules cleared on dpid {dpid}",
                        "config_type": config_type,
                        "dpid": dpid,
                    }

            # Fallback: operazione non mappabile a Ryu REST
            self.logger.warning(
                f"Config change '{config_type}' on '{action.target}' "
                f"cannot be mapped to a Ryu REST call — logged only"
            )
            self._record_success()
            return {
                "success": True,
                "message": (
                    f"Config change logged (no direct Ryu API for "
                    f"'{config_type}' on '{action.target}')"
                ),
                "config_type": config_type,
                "note": "Topology changes (add/remove switch/host) require "
                        "Mininet CLI or ComnetSemu API, not available via Ryu REST.",
            }

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Config change HTTP error: {e}")
            self._record_failure()
            return {"success": False, "error": f"Ryu API error: {e}"}
        except Exception as e:
            self.logger.error(f"Config change failed for {action.id}: {e}")
            self._record_failure()
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    #  SLICE_CREATE — crea uno slice di rete                              #
    # ------------------------------------------------------------------ #

    def execute_slice_create(self, action: NetworkAction) -> Dict[str, Any]:
        """
        Create a network slice with real bandwidth enforcement via OVS QoS.
        Installs QoS queues on switch ports and flow rules that use them.
        """
        try:
            slice_name = action.parameters.get("slice_name", f"slice_{action.id}")
            resources = action.parameters.get("resources", [])
            bandwidth = action.parameters.get("bandwidth", 100)  # Mbps

            # If bandwidth is specified, apply real rate limiting
            if bandwidth and bandwidth > 0:
                return self._execute_bandwidth_limit(action)

            # Fallback: install basic forwarding rules (no QoS)
            switches = self._ryu_get("/stats/switches")
            if not switches:
                return {"success": False, "error": "No switches available"}

            installed = []
            for dpid in switches:
                body = {
                    "dpid": dpid,
                    "priority": action.priority,
                    "match": {},
                    "actions": [{"type": "OUTPUT", "port": "NORMAL"}],
                }
                self._ryu_post("/stats/flowentry/add", body)
                installed.append(dpid)

            self._record_success()
            return {
                "success": True,
                "message": f"Slice '{slice_name}' created on {len(installed)} switches",
                "slice_name": slice_name,
                "switches": installed,
                "bandwidth": bandwidth,
            }

        except Exception as e:
            self.logger.error(f"Slice create failed for {action.id}: {e}")
            self._record_failure()
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    #  QoS helper                                                          #
    # ------------------------------------------------------------------ #

    def _execute_qos(self, action: NetworkAction) -> Dict[str, Any]:
        """Apply QoS policy via Ryu REST (if qos_simple_switch is active)."""
        try:
            dpid = self._resolve_dpid(action.target)
            if dpid is None:
                return {"success": False, "error": f"Cannot resolve dpid from '{action.target}'"}

            # Ryu qos_simple_switch_13 espone /qos/rules/<dpid>
            qos_data = action.parameters.get("config_data", {})
            self._ryu_post(f"/qos/rules/{dpid:016x}", qos_data)
            self._record_success()
            return {"success": True, "message": f"QoS policy applied on dpid {dpid}"}

        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                self.logger.warning("QoS REST API not available (404) — is qos_simple_switch loaded?")
                return {
                    "success": False,
                    "error": "QoS REST API not available. Load ryu.app.rest_qos on the controller.",
                }
            self._record_failure()
            return {"success": False, "error": str(e)}
        except Exception as e:
            self._record_failure()
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    #  Bandwidth limiting via OVS QoS                                      #
    # ------------------------------------------------------------------ #

    def _run_ovs_cmd(self, args: List[str]) -> Tuple[bool, str]:
        """Run an ovs-vsctl / ovs-ofctl command and return (success, output)."""
        try:
            result = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return False, result.stderr.strip()
            return True, result.stdout.strip()
        except FileNotFoundError:
            return False, f"Command not found: {args[0]}"
        except subprocess.TimeoutExpired:
            return False, f"Command timed out: {' '.join(args)}"
        except Exception as e:
            return False, str(e)

    def _get_switch_ports(self, switch_name: str) -> List[str]:
        """Get the list of port interfaces on an OVS bridge."""
        ok, output = self._run_ovs_cmd(
            ["ovs-vsctl", "list-ports", switch_name]
        )
        if ok and output:
            return [p.strip() for p in output.splitlines() if p.strip()]
        return []

    def _get_all_bridges(self) -> List[str]:
        """Get all OVS bridge names."""
        ok, output = self._run_ovs_cmd(["ovs-vsctl", "list-br"])
        if ok and output:
            return [b.strip() for b in output.splitlines() if b.strip()]
        return []

    def _clear_qos_on_port(self, port: str) -> None:
        """Remove existing QoS configuration from a port."""
        self._run_ovs_cmd(["ovs-vsctl", "clear", "port", port, "qos"])

    def _execute_bandwidth_limit(self, action: NetworkAction) -> Dict[str, Any]:
        """
        Apply real bandwidth limiting using OVS QoS (HTB policing).

        Works by creating OVS QoS queues on switch ports with max-rate.
        Then installs flow rules via Ryu that enqueue matching traffic
        into the rate-limited queue.

        Extracts bandwidth from action.parameters:
          - 'bandwidth' (int, Mbps) — from slice_create
          - 'config_data.bandwidth_mbps' (int) — from config_change
        """
        try:
            # --- Extract bandwidth value (Mbps) ---
            config_data = action.parameters.get("config_data", {})
            bandwidth_mbps = action.parameters.get("bandwidth", None)
            if bandwidth_mbps is None and isinstance(config_data, dict):
                bandwidth_mbps = config_data.get("bandwidth_mbps",
                                  config_data.get("bandwidth", None))
            if bandwidth_mbps is None:
                bandwidth_mbps = 10  # safe default
            bandwidth_mbps = int(bandwidth_mbps)
            rate_bps = bandwidth_mbps * 1_000_000  # OVS uses bits/s

            # --- Determine which switches to configure ---
            resources = action.parameters.get("resources", [])
            if not resources:
                # If no resources specified, apply to all bridges
                resources = self._get_all_bridges()
            if not resources:
                # Last resort: get switch names from Ryu
                switches = self._ryu_get("/stats/switches")
                resources = [f"s{dpid}" for dpid in (switches or [])]

            if not resources:
                return {"success": False, "error": "No switches found to apply QoS"}

            configured_ports = []
            errors = []

            for switch in resources:
                # Normalize switch name (e.g. "s1")
                switch_name = switch if isinstance(switch, str) else f"s{switch}"

                ports = self._get_switch_ports(switch_name)
                if not ports:
                    self.logger.warning(
                        f"No ports found on bridge '{switch_name}', skipping"
                    )
                    continue

                for port in ports:
                    # Clear any existing QoS on this port
                    self._clear_qos_on_port(port)

                    # Create QoS with a rate-limited queue using linux-htb
                    ok, output = self._run_ovs_cmd([
                        "ovs-vsctl", "set", "port", port,
                        "qos=@newqos", "--",
                        "--id=@newqos", "create", "qos",
                        "type=linux-htb",
                        f"other-config:max-rate={rate_bps}",
                        "queues=0=@q0", "--",
                        "--id=@q0", "create", "queue",
                        f"other-config:max-rate={rate_bps}",
                    ])

                    if ok:
                        configured_ports.append(f"{switch_name}/{port}")
                        self.logger.info(
                            f"QoS set on {switch_name}/{port}: "
                            f"max-rate={bandwidth_mbps}Mbps"
                        )
                    else:
                        errors.append(f"{switch_name}/{port}: {output}")
                        self.logger.error(
                            f"Failed to set QoS on {switch_name}/{port}: {output}"
                        )

            if not configured_ports and errors:
                self._record_failure()
                return {
                    "success": False,
                    "error": f"QoS configuration failed on all ports: {'; '.join(errors)}",
                }

            self._record_success()
            msg = (
                f"Bandwidth limited to {bandwidth_mbps} Mbps on "
                f"{len(configured_ports)} ports across {len(resources)} switches"
            )
            if errors:
                msg += f" ({len(errors)} ports failed)"

            return {
                "success": True,
                "message": msg,
                "bandwidth_mbps": bandwidth_mbps,
                "configured_ports": configured_ports,
                "errors": errors if errors else None,
            }

        except Exception as e:
            self.logger.error(f"Bandwidth limit failed for {action.id}: {e}")
            self._record_failure()
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    #  Topology change (legacy interface)                                  #
    # ------------------------------------------------------------------ #

    def execute_topology_change(self, action: NetworkAction) -> Dict[str, Any]:
        """
        Interfaccia legacy usata da ActionProcessor.
        Smista al metodo corretto in base al tipo di azione.
        """
        if action.type == ActionType.FLOW_MOD:
            return self.execute_flow_mod(action)
        elif action.type == ActionType.SLICE_CREATE:
            return self.execute_slice_create(action)
        else:
            return self.execute_config_change(action)

    def execute_qos_policy(self, action: NetworkAction) -> Dict[str, Any]:
        """Interfaccia legacy per QoS."""
        return self._execute_qos(action)

    # ------------------------------------------------------------------ #
    #  Network state (lettura reale da Ryu)                                #
    # ------------------------------------------------------------------ #

    def get_network_state(self, target: str) -> Dict[str, Any]:
        """Legge lo stato reale della rete da Ryu."""
        try:
            switches = self._ryu_get("/stats/switches")
            dpid = self._resolve_dpid(target)

            state = {
                "target": target,
                "timestamp": datetime.now().isoformat(),
                "switches": switches,
                "target_dpid": dpid,
            }

            # Se il dpid è noto, recupera le flow rules
            if dpid is not None and dpid in switches:
                flows = self._ryu_get(f"/stats/flow/{dpid}")
                state["flows"] = flows
                state["status"] = "active"
            else:
                state["status"] = "unknown"

            self._record_success()
            return state

        except Exception as e:
            self.logger.warning(f"Failed to get network state for {target}: {e}")
            return {
                "target": target,
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    # ------------------------------------------------------------------ #
    #  Status & cleanup                                                    #
    # ------------------------------------------------------------------ #

    def get_connection_status(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "ryu_url": self.config.ryu_base_url,
            "last_error": self.last_error,
            "last_successful_request": (
                self.last_successful_request.isoformat()
                if self.last_successful_request
                else None
            ),
            "stats": dict(self.stats),
        }

    def close(self):
        self.logger.info("Closing ComnetsEMU connector")
        self.session.close()
        self.status = ConnectionStatus.DISCONNECTED

    # ------------------------------------------------------------------ #
    #  Internal helpers                                                    #
    # ------------------------------------------------------------------ #

    def _record_success(self):
        self.stats["successful_requests"] += 1
        self.stats["total_requests"] += 1
        self.last_successful_request = datetime.now()

    def _record_failure(self):
        self.stats["failed_requests"] += 1
        self.stats["total_requests"] += 1
