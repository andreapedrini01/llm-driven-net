"""
ComnetsEMU Connector — esegue operazioni reali sulla rete
via Ryu REST API (ofctl_rest) per flow rules, config changes,
e OpenFlow meters per bandwidth limiting.
"""

import json
import logging
import socket
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
            qos_keywords = ("qos", "bandwidth", "rate_limit", "throttle", "shaping", "policing")
            if any(kw in config_type.lower() for kw in qos_keywords):
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
    #  Bandwidth limiting via OpenFlow 1.3 Meters                          #
    # ------------------------------------------------------------------ #

    def _install_meter(self, dpid: int, meter_id: int, rate_kbps: int) -> bool:
        """
        Install an OpenFlow meter on a switch via Ryu ofctl_rest.
        Uses DSCP_REMARK band so traffic exceeding the rate is remarked
        (and effectively rate-limited by the switch pipeline).
        Falls back to DROP band if DSCP_REMARK is not supported.
        """
        # Try DROP band first — universally supported and actually enforces the limit
        meter_body = {
            "dpid": dpid,
            "meter_id": meter_id,
            "flags": ["KBPS"],
            "bands": [
                {
                    "type": "DROP",
                    "rate": rate_kbps,
                }
            ],
        }
        try:
            self._ryu_post("/stats/meterentry/add", meter_body)
            self.logger.info(
                f"Meter {meter_id} installed on dpid={dpid}: "
                f"rate={rate_kbps} kbps (DROP)"
            )
            return True
        except requests.exceptions.HTTPError as e:
            self.logger.warning(
                f"Failed to install meter {meter_id} on dpid={dpid}: {e}"
            )
            return False

    def _install_metered_flow(
        self, dpid: int, meter_id: int, match: Dict[str, Any],
        priority: int = 2000
    ) -> bool:
        """
        Install a flow rule that sends matching traffic through a meter,
        then forwards normally (OUTPUT:NORMAL).
        """
        flow_body = {
            "dpid": dpid,
            "priority": priority,
            "match": match,
            "actions": [
                {"type": "METER", "meter_id": meter_id},
                {"type": "OUTPUT", "port": "NORMAL"},
            ],
        }
        try:
            self._ryu_post("/stats/flowentry/add", flow_body)
            self.logger.info(
                f"Metered flow installed on dpid={dpid}: "
                f"meter={meter_id}, match={match}"
            )
            return True
        except requests.exceptions.HTTPError as e:
            self.logger.warning(
                f"Failed to install metered flow on dpid={dpid}: {e}"
            )
            return False

    def _resolve_host_ip(self, host_name: str) -> Optional[str]:
        """
        Resolve a host name like 'h1', 'h2' to its IP address.
        Convention: h<N> -> 10.0.0.<N>
        """
        import re
        m = re.match(r'^h(\d+)$', host_name, re.IGNORECASE)
        if m:
            host_num = int(m.group(1))
            if 1 <= host_num <= 254:
                return f"10.0.0.{host_num}"
        # Already an IP?
        if re.match(r'^\d+\.\d+\.\d+\.\d+$', host_name):
            return host_name
        return None

    def _find_host_switches(self, src_ip: Optional[str], dst_ip: Optional[str]) -> List[int]:
        """
        Find the leaf switches directly connected to the given hosts
        using the Ryu topology REST API (/v1.0/topology/hosts).
        Falls back to flow-table inspection only as last resort.
        """
        host_dpids = set()

        if not src_ip and not dst_ip:
            return []

        # Primary: use Ryu topology API (most accurate)
        try:
            hosts = self._ryu_get("/v1.0/topology/hosts")
            if isinstance(hosts, list):
                for host in hosts:
                    host_ip_entry = host.get("ipv4", [])
                    if isinstance(host_ip_entry, list):
                        ips = host_ip_entry
                    else:
                        ips = [host_ip_entry]

                    if (src_ip and src_ip in ips) or (dst_ip and dst_ip in ips):
                        port_info = host.get("port", {})
                        dpid_hex = port_info.get("dpid", "")
                        if dpid_hex:
                            try:
                                host_dpids.add(int(dpid_hex, 16))
                            except ValueError:
                                pass

                if host_dpids:
                    return list(host_dpids)
        except Exception as e:
            self.logger.debug(f"Topology API not available: {e}")

        return list(host_dpids)

    def _host_name_to_dpid(self, host_name: str, all_switches: List[int]) -> Optional[int]:
        """
        Find the leaf switch directly connected to a host.

        Strategy (in order):
        1. Ryu topology REST API (/v1.0/topology/hosts) — most accurate
        2. Flow-table inspection: find the switch that has a flow rule
           delivering traffic TO this host's IP via a specific output port
           (leaf switches have host-facing ports, intermediate switches
           forward to other switches via different ports)
        """
        import re
        m = re.match(r'^h(\d+)$', host_name, re.IGNORECASE)
        if not m:
            return None

        host_ip = self._resolve_host_ip(host_name)
        if not host_ip:
            return None

        # --- Strategy 1: Ryu topology API ---
        try:
            hosts = self._ryu_get("/v1.0/topology/hosts")
            if isinstance(hosts, list):
                for host in hosts:
                    host_ips = host.get("ipv4", [])
                    if isinstance(host_ips, str):
                        host_ips = [host_ips]
                    if host_ip in host_ips:
                        port_info = host.get("port", {})
                        dpid_hex = port_info.get("dpid", "")
                        if dpid_hex:
                            try:
                                dpid = int(dpid_hex, 16)
                                self.logger.info(
                                    f"Host {host_name} ({host_ip}) is on "
                                    f"dpid={dpid} port={port_info.get('port_no')} "
                                    f"(via topology API)"
                                )
                                return dpid
                            except ValueError:
                                pass
        except Exception as e:
            self.logger.debug(f"Topology API lookup failed for {host_name}: {e}")

        # --- Strategy 2: Flow-table inspection ---
        # On a leaf switch, traffic to a host goes to a specific port.
        # On intermediate switches, traffic goes to another switch port.
        # We look for the switch where nw_dst matches AND the number of
        # links (inter-switch connections) is lowest — leaf switches have
        # fewer inter-switch links than core/aggregation switches.
        # More precisely: find switches that have a flow with nw_dst=host_ip
        # and pick the one with the highest output port number relative to
        # its total ports (hosts are typically on the last ports).
        self.logger.debug(
            f"Falling back to flow-table inspection for {host_name}"
        )

        # Get topology links to identify inter-switch ports
        inter_switch_ports: Dict[int, set] = {}
        try:
            links = self._ryu_get("/v1.0/topology/links")
            if isinstance(links, list):
                for link in links:
                    src = link.get("src", {})
                    dpid_hex = src.get("dpid", "")
                    port_no = src.get("port_no", "")
                    if dpid_hex and port_no:
                        try:
                            d = int(dpid_hex, 16)
                            p = int(port_no)
                            inter_switch_ports.setdefault(d, set()).add(p)
                        except ValueError:
                            pass
        except Exception:
            pass

        # Now find which switch delivers traffic to host_ip via a non-switch port
        for dpid in all_switches:
            try:
                flows_resp = self._ryu_get(f"/stats/flow/{dpid}")
                flows = (
                    flows_resp.get(str(dpid), [])
                    if isinstance(flows_resp, dict) else []
                )
                switch_ports = inter_switch_ports.get(dpid, set())

                for flow in flows:
                    match_f = flow.get("match", {})
                    if match_f.get("nw_dst") != host_ip:
                        continue

                    # Check if the output port is a host-facing port
                    actions = flow.get("actions", [])
                    for act in actions:
                        if isinstance(act, str) and act.startswith("OUTPUT:"):
                            try:
                                port = int(act.split(":")[1])
                                if port not in switch_ports:
                                    self.logger.info(
                                        f"Host {host_name} ({host_ip}) is on "
                                        f"dpid={dpid} port={port} "
                                        f"(via flow-table inspection)"
                                    )
                                    return dpid
                            except (ValueError, IndexError):
                                pass
            except Exception:
                continue

        return None

    def _execute_bandwidth_limit(self, action: NetworkAction) -> Dict[str, Any]:
        """
        Apply real bandwidth limiting using OpenFlow 1.3 meters.

        Strategy:
        - Install meters ONLY on the leaf switches directly connected
          to the involved hosts (not on all switches in the network).
        - This ensures that only traffic between the specified hosts
          is rate-limited, without affecting other host pairs.

        This works with any Ryu app that loads ofctl_rest and uses OF1.3.
        No sudo, no ovs-vsctl needed.
        """
        try:
            # --- Extract bandwidth ---
            config_data = action.parameters.get("config_data", {})
            bandwidth_mbps = action.parameters.get("bandwidth", None)
            if bandwidth_mbps is None and isinstance(config_data, dict):
                bandwidth_mbps = config_data.get("bandwidth_mbps",
                                  config_data.get("bandwidth", None))
            if bandwidth_mbps is None:
                bandwidth_mbps = 10  # safe default
            bandwidth_mbps = int(bandwidth_mbps)
            rate_kbps = bandwidth_mbps * 1000  # meters use kbps

            # --- Extract host names/IPs for match rules ---
            src_host = None
            dst_host = None

            # 1. Try config_data (from config_change actions)
            if isinstance(config_data, dict):
                src_host = config_data.get("src_host")
                dst_host = config_data.get("dst_host")

            # 2. Fallback: parse host names from slice_name, description,
            #    or any text field. ChatGPT often puts them in slice_name
            #    like "bw-h1-h2-10mbps" or "bw-limit-h1-h2-10mbps"
            if not src_host or not dst_host:
                import re
                # Collect all text fields that might contain host references
                text_sources = [
                    action.parameters.get("slice_name", ""),
                    action.description or "",
                    str(action.parameters),
                ]
                search_text = " ".join(text_sources)

                # Find all h<N> patterns
                host_matches = re.findall(r'\bh(\d+)\b', search_text, re.IGNORECASE)
                # Deduplicate while preserving order
                seen = set()
                unique_hosts = []
                for h in host_matches:
                    if h not in seen:
                        seen.add(h)
                        unique_hosts.append(f"h{h}")

                if len(unique_hosts) >= 2:
                    if not src_host:
                        src_host = unique_hosts[0]
                    if not dst_host:
                        dst_host = unique_hosts[1]
                elif len(unique_hosts) == 1:
                    if not src_host:
                        src_host = unique_hosts[0]

            self.logger.info(
                f"Bandwidth limit: extracted hosts src={src_host}, dst={dst_host}"
            )

            src_ip = self._resolve_host_ip(src_host) if src_host else None
            dst_ip = self._resolve_host_ip(dst_host) if dst_host else None

            # --- Determine which switches to configure ---
            # Only install meters on leaf switches connected to the hosts
            all_switches = self._ryu_get("/stats/switches") or []

            target_dpids = set()

            # Try to find the specific leaf switches for each host
            if src_host:
                dpid = self._host_name_to_dpid(src_host, all_switches)
                if dpid is not None:
                    target_dpids.add(dpid)
                    self.logger.info(f"Host {src_host} found on dpid={dpid}")

            if dst_host:
                dpid = self._host_name_to_dpid(dst_host, all_switches)
                if dpid is not None:
                    target_dpids.add(dpid)
                    self.logger.info(f"Host {dst_host} found on dpid={dpid}")

            # If flow-table discovery didn't work, try IP-based discovery
            if not target_dpids and (src_ip or dst_ip):
                discovered = self._find_host_switches(src_ip, dst_ip)
                if discovered:
                    target_dpids.update(discovered)
                    self.logger.info(
                        f"Discovered host switches via flow inspection: {discovered}"
                    )

            # Last resort: if we still can't find the right switches,
            # use only the resources list from the action (but NOT all switches)
            if not target_dpids:
                resources = action.parameters.get("resources", [])
                if resources:
                    for r in resources:
                        dpid = self._resolve_dpid(str(r))
                        if dpid is not None and dpid in all_switches:
                            target_dpids.add(dpid)

            # Final fallback: if nothing worked, apply to all (with warning)
            if not target_dpids:
                self.logger.warning(
                    "Could not determine host switches — "
                    "applying meter to all switches as fallback"
                )
                target_dpids = set(all_switches)

            target_dpids = list(target_dpids)

            if not target_dpids:
                return {"success": False, "error": "No switches available"}

            self.logger.info(
                f"Installing bandwidth limit on {len(target_dpids)} switch(es): "
                f"{target_dpids} (total switches in network: {len(all_switches)})"
            )

            # Use a deterministic meter ID based on bandwidth to avoid collisions
            base_meter_id = (bandwidth_mbps % 65000) + 1

            meters_ok = []
            flows_ok = []
            errors = []

            for dpid in target_dpids:
                meter_id = base_meter_id

                # Step 1: Install meter
                if not self._install_meter(dpid, meter_id, rate_kbps):
                    errors.append(f"dpid={dpid}: meter install failed")
                    continue
                meters_ok.append(dpid)

                # Step 2: Install metered flow rules
                # IMPORTANT: Always match BOTH src AND dst IP to avoid
                # limiting unrelated traffic on the same switch.
                if src_ip and dst_ip:
                    # Forward direction: src -> dst
                    match_fwd = {"dl_type": 2048, "nw_src": src_ip, "nw_dst": dst_ip}
                    if self._install_metered_flow(dpid, meter_id, match_fwd):
                        flows_ok.append(f"dpid={dpid} {src_ip}->{dst_ip}")

                    # Reverse direction: dst -> src
                    match_rev = {"dl_type": 2048, "nw_src": dst_ip, "nw_dst": src_ip}
                    if self._install_metered_flow(dpid, meter_id, match_rev):
                        flows_ok.append(f"dpid={dpid} {dst_ip}->{src_ip}")
                else:
                    # Without both IPs we cannot selectively limit traffic.
                    # Log a warning but still apply a broad match as last resort.
                    self.logger.warning(
                        f"Missing src or dst IP (src={src_ip}, dst={dst_ip}) — "
                        f"cannot create selective meter rules on dpid={dpid}. "
                        f"Applying broad IPv4 match (will affect all traffic on this switch)."
                    )
                    match_all = {"dl_type": 2048}
                    if self._install_metered_flow(dpid, meter_id, match_all):
                        flows_ok.append(f"dpid={dpid} all-ipv4 (broad)")

            if not meters_ok:
                self._record_failure()
                return {
                    "success": False,
                    "error": (
                        f"Meter installation failed on all {len(target_dpids)} switches. "
                        f"Errors: {'; '.join(errors)}. "
                        "Make sure the Ryu controller supports OpenFlow 1.3 meters "
                        "(e.g. simple_switch_13 + ofctl_rest)."
                    ),
                }

            self._record_success()
            msg = (
                f"Bandwidth limited to {bandwidth_mbps} Mbps: "
                f"{len(meters_ok)} meters on leaf switch(es) {meters_ok}, "
                f"{len(flows_ok)} flow rules"
            )
            if src_ip and dst_ip:
                msg += f" (between {src_ip} and {dst_ip})"
            if errors:
                msg += f" ({len(errors)} switches failed)"

            return {
                "success": True,
                "message": msg,
                "bandwidth_mbps": bandwidth_mbps,
                "rate_kbps": rate_kbps,
                "meters_installed": meters_ok,
                "flows_installed": flows_ok,
                "errors": errors if errors else None,
            }

        except Exception as e:
            self.logger.error(f"Bandwidth limit failed for {action.id}: {e}")
            self._record_failure()
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    #  SLICE_DELETE — remove a network slice (meters + flow rules)         #
    # ------------------------------------------------------------------ #

    def execute_slice_delete(self, action: NetworkAction) -> Dict[str, Any]:
        """
        Delete a network slice by removing its metered flow rules and meters.
        Identifies the slice by src_host/dst_host or by parsing host names
        from the slice_name / description fields.
        """
        try:
            import re

            config_data = action.parameters.get("config_data", {})
            src_host = config_data.get("src_host") if isinstance(config_data, dict) else None
            dst_host = config_data.get("dst_host") if isinstance(config_data, dict) else None

            # Fallback: parse host names from text fields
            if not src_host or not dst_host:
                text_sources = [
                    action.parameters.get("slice_name", ""),
                    action.description or "",
                    str(action.parameters),
                ]
                host_matches = re.findall(r'\bh(\d+)\b', " ".join(text_sources), re.IGNORECASE)
                seen = set()
                unique_hosts = []
                for h in host_matches:
                    if h not in seen:
                        seen.add(h)
                        unique_hosts.append(f"h{h}")
                if len(unique_hosts) >= 2:
                    src_host = src_host or unique_hosts[0]
                    dst_host = dst_host or unique_hosts[1]

            src_ip = self._resolve_host_ip(src_host) if src_host else None
            dst_ip = self._resolve_host_ip(dst_host) if dst_host else None

            if not src_ip or not dst_ip:
                return {
                    "success": False,
                    "error": "Cannot determine slice hosts — provide src_host and dst_host",
                }

            all_switches = self._ryu_get("/stats/switches") or []
            flows_removed = []
            meters_removed = []
            errors = []

            for dpid in all_switches:
                try:
                    flows_resp = self._ryu_get(f"/stats/flow/{dpid}")
                    flows = flows_resp.get(str(dpid), []) if isinstance(flows_resp, dict) else []

                    for flow in flows:
                        match = flow.get("match", {})
                        nw_src = match.get("nw_src")
                        nw_dst = match.get("nw_dst")

                        is_fwd = (nw_src == src_ip and nw_dst == dst_ip)
                        is_rev = (nw_src == dst_ip and nw_dst == src_ip)

                        if is_fwd or is_rev:
                            # Check if this flow uses a meter
                            actions_list = flow.get("actions", [])
                            meter_id = None
                            for act in actions_list:
                                if isinstance(act, str) and act.startswith("METER:"):
                                    try:
                                        meter_id = int(act.split(":")[1])
                                    except (ValueError, IndexError):
                                        pass
                                elif isinstance(act, dict) and act.get("type") == "METER":
                                    meter_id = act.get("meter_id")

                            # Delete the flow rule using non-strict delete
                            del_body = {
                                "dpid": dpid,
                                "table_id": flow.get("table_id", 0),
                                "priority": flow.get("priority", 2000),
                                "match": match,
                            }
                            self._ryu_post("/stats/flowentry/delete", del_body)
                            flows_removed.append(f"dpid={dpid} {nw_src}->{nw_dst}")

                            # Delete the associated meter
                            if meter_id and meter_id not in [m[1] for m in meters_removed]:
                                meter_del = {"dpid": dpid, "meter_id": meter_id}
                                try:
                                    self._ryu_post("/stats/meterentry/delete", meter_del)
                                    meters_removed.append((dpid, meter_id))
                                except Exception as me:
                                    self.logger.warning(
                                        f"Failed to delete meter {meter_id} on dpid={dpid}: {me}"
                                    )

                except Exception as e:
                    errors.append(f"dpid={dpid}: {e}")

            if not flows_removed:
                self._record_failure()
                return {
                    "success": False,
                    "error": f"No slice flow rules found between {src_ip} and {dst_ip}",
                }

            self._record_success()
            return {
                "success": True,
                "message": (
                    f"Slice deleted: removed {len(flows_removed)} flow rules "
                    f"and {len(meters_removed)} meters between {src_ip} and {dst_ip}"
                ),
                "flows_removed": flows_removed,
                "meters_removed": [(d, m) for d, m in meters_removed],
                "errors": errors if errors else None,
            }

        except Exception as e:
            self.logger.error(f"Slice delete failed for {action.id}: {e}")
            self._record_failure()
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    #  SLICE_MODIFY — modify bandwidth of an existing slice               #
    # ------------------------------------------------------------------ #

    def execute_slice_modify(self, action: NetworkAction) -> Dict[str, Any]:
        """
        Modify an existing network slice by deleting old meters/flows
        and reinstalling them with the new bandwidth.
        """
        try:
            # Step 1: Delete the existing slice
            del_result = self.execute_slice_delete(action)
            if del_result.get("success"):
                self.logger.info(
                    f"Old slice removed: {del_result.get('message')}"
                )
                # Give the switch time to process the deletions
                time.sleep(0.5)
            else:
                self.logger.info(
                    "No existing slice to modify — creating new slice instead"
                )

            # Step 2: Recreate with new bandwidth
            return self._execute_bandwidth_limit(action)

        except Exception as e:
            self.logger.error(f"Slice modify failed for {action.id}: {e}")
            self._record_failure()
            return {"success": False, "error": str(e)}

    # ------------------------------------------------------------------ #
    #  LOAD_BALANCE — distribute traffic across multiple hosts             #
    # ------------------------------------------------------------------ #

    def execute_load_balance(self, action: NetworkAction) -> Dict[str, Any]:
        """
        Implement load balancing using OpenFlow group tables (SELECT type).

        Distributes traffic destined to a virtual IP across multiple backend
        hosts using round-robin selection at the switch level.

        Parameters expected in action.parameters:
            - backends: list of host names (e.g. ["h1", "h2", "h3"])
            - virtual_ip: optional virtual IP for the service
            - config_data: dict with dst_hosts, virtual_ip
        """
        try:
            import re

            config_data = action.parameters.get("config_data", {})
            backends = action.parameters.get("backends", [])
            virtual_ip = action.parameters.get("virtual_ip")

            if isinstance(config_data, dict):
                if not backends:
                    backends = config_data.get("dst_hosts", config_data.get("backends", []))
                if not virtual_ip:
                    virtual_ip = config_data.get("virtual_ip")

            # Fallback: parse host names from text fields
            if not backends:
                text_sources = [
                    action.description or "",
                    str(action.parameters),
                ]
                host_matches = re.findall(r'\bh(\d+)\b', " ".join(text_sources), re.IGNORECASE)
                seen = set()
                for h in host_matches:
                    if h not in seen:
                        seen.add(h)
                        backends.append(f"h{h}")

            if len(backends) < 2:
                return {
                    "success": False,
                    "error": "Load balancing requires at least 2 backend hosts",
                }

            # Resolve backend IPs
            backend_ips = []
            for host in backends:
                ip = self._resolve_host_ip(host)
                if ip:
                    backend_ips.append({"host": host, "ip": ip})
                else:
                    self.logger.warning(f"Cannot resolve IP for backend host {host}")

            if len(backend_ips) < 2:
                return {
                    "success": False,
                    "error": f"Could only resolve {len(backend_ips)} backend IPs, need at least 2",
                }

            # If no virtual IP, use 10.0.0.100 as default
            if not virtual_ip:
                virtual_ip = "10.0.0.100"

            all_switches = self._ryu_get("/stats/switches") or []
            if not all_switches:
                return {"success": False, "error": "No switches available"}

            # Find the switch(es) to install the group on
            target_dpids = set()
            for b in backend_ips:
                dpid = self._host_name_to_dpid(b["host"], all_switches)
                if dpid is not None:
                    target_dpids.add(dpid)

            if not target_dpids:
                target_dpids = {all_switches[0]}

            group_id = abs(hash(virtual_ip)) % 65000 + 1
            groups_ok = []
            flows_ok = []
            errors = []

            for dpid in target_dpids:
                # Step 1: Install SELECT group table with equal-weight buckets
                buckets = []
                for b in backend_ips:
                    buckets.append({
                        "weight": 1,
                        "actions": [
                            {"type": "SET_FIELD", "field": "ipv4_dst", "value": b["ip"]},
                            {"type": "OUTPUT", "port": "NORMAL"},
                        ],
                    })

                group_body = {
                    "dpid": dpid,
                    "type": "SELECT",
                    "group_id": group_id,
                    "buckets": buckets,
                }

                self.logger.info(
                    f"Installing group table on dpid={dpid}: "
                    f"group_id={group_id}, buckets={len(buckets)}"
                )

                try:
                    self._ryu_post("/stats/groupentry/add", group_body)
                    groups_ok.append(dpid)
                    self.logger.info(f"Group {group_id} installed on dpid={dpid}")
                except Exception as e1:
                    self.logger.warning(
                        f"Group add failed on dpid={dpid}: {e1}, trying modify..."
                    )
                    try:
                        self._ryu_post("/stats/groupentry/modify", group_body)
                        groups_ok.append(dpid)
                        self.logger.info(f"Group {group_id} modified on dpid={dpid}")
                    except Exception as e2:
                        self.logger.error(
                            f"Group install failed on dpid={dpid}: add={e1}, modify={e2}"
                        )
                        errors.append(f"dpid={dpid}: group install failed: add={e1}, modify={e2}")
                        continue

                # Step 2: Flow rule to redirect virtual IP traffic to group table
                flow_body = {
                    "dpid": dpid,
                    "priority": 3000,
                    "match": {"dl_type": 2048, "nw_dst": virtual_ip},
                    "actions": [{"type": "GROUP", "group_id": group_id}],
                }
                try:
                    self._ryu_post("/stats/flowentry/add", flow_body)
                    flows_ok.append(f"dpid={dpid} vip={virtual_ip}")
                except Exception as e:
                    errors.append(f"dpid={dpid}: flow install failed: {e}")

            if not groups_ok:
                self._record_failure()
                return {
                    "success": False,
                    "error": f"Group table installation failed on all switches. Errors: {'; '.join(errors)}",
                }

            self._record_success()
            backend_str = ", ".join(f"{b['host']}({b['ip']})" for b in backend_ips)
            return {
                "success": True,
                "message": (
                    f"Load balancing configured: virtual_ip={virtual_ip} -> "
                    f"[{backend_str}] on {len(groups_ok)} switch(es)"
                ),
                "virtual_ip": virtual_ip,
                "backends": backend_ips,
                "group_id": group_id,
                "groups_installed": groups_ok,
                "flows_installed": flows_ok,
                "errors": errors if errors else None,
            }

        except Exception as e:
            self.logger.error(f"Load balance failed for {action.id}: {e}")
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
