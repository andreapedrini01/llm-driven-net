"""
Security data models for the collect-security-scan feature.

Defines:
- OpenPort: single open port info from nmap
- NmapResult: nmap scan result for a single host
- SecuritySnapshot: NetworkSnapshot + nmap results (composition)
- SecurityReport: LLM analysis output
- NmapNotFoundError: raised when nmap is not installed
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json
from datetime import datetime

from .core import NetworkSnapshot


class NmapNotFoundError(Exception):
    """Raised when nmap is not installed on the system."""
    pass


@dataclass
class OpenPort:
    port: int
    protocol: str   # "tcp" | "udp"
    state: str      # "open" | "filtered" | "closed"
    service: str    # e.g. "ssh", "http"
    version: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "port": self.port,
            "protocol": self.protocol,
            "state": self.state,
            "service": self.service,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OpenPort":
        return cls(
            port=data["port"],
            protocol=data["protocol"],
            state=data["state"],
            service=data["service"],
            version=data.get("version", ""),
        )


@dataclass
class NmapResult:
    ip: str
    status: str                     # "scanned" | "unreachable" | "timeout" | "error"
    open_ports: List[OpenPort]
    os_detection: Optional[str]     # detected OS, None if unavailable
    scan_duration_s: float
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ip": self.ip,
            "status": self.status,
            "open_ports": [p.to_dict() for p in self.open_ports],
            "os_detection": self.os_detection,
            "scan_duration_s": self.scan_duration_s,
            "error_message": self.error_message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NmapResult":
        return cls(
            ip=data["ip"],
            status=data["status"],
            open_ports=[OpenPort.from_dict(p) for p in data.get("open_ports", [])],
            os_detection=data.get("os_detection"),
            scan_duration_s=data["scan_duration_s"],
            error_message=data.get("error_message"),
        )


@dataclass
class SecuritySnapshot:
    snapshot: NetworkSnapshot
    security_scan: Dict[str, NmapResult]  # ip -> NmapResult

    def to_dict(self) -> Dict[str, Any]:
        d = self.snapshot.to_dict()
        d["security_scan"] = {ip: result.to_dict() for ip, result in self.security_scan.items()}
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecuritySnapshot":
        security_scan_raw = data.pop("security_scan", {})
        snapshot = NetworkSnapshot.from_dict(data)
        security_scan = {ip: NmapResult.from_dict(v) for ip, v in security_scan_raw.items()}
        return cls(snapshot=snapshot, security_scan=security_scan)

    @classmethod
    def from_json(cls, json_str: str) -> "SecuritySnapshot":
        data = json.loads(json_str)
        return cls.from_dict(data)


@dataclass
class SecurityReport:
    vulnerabilities: List[str]
    configuration_issues: List[str]
    security_properties: List[str]
    timestamp: float            # epoch of the report
    snapshot_timestamp: float   # timestamp of the analysed snapshot
    raw_response: Optional[str] = None  # populated only if JSON parsing fails

    def to_dict(self) -> Dict[str, Any]:
        return {
            "vulnerabilities": self.vulnerabilities,
            "configuration_issues": self.configuration_issues,
            "security_properties": self.security_properties,
            "timestamp": self.timestamp,
            "snapshot_timestamp": self.snapshot_timestamp,
            "raw_response": self.raw_response,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SecurityReport":
        return cls(
            vulnerabilities=data["vulnerabilities"],
            configuration_issues=data["configuration_issues"],
            security_properties=data["security_properties"],
            timestamp=data["timestamp"],
            snapshot_timestamp=data["snapshot_timestamp"],
            raw_response=data.get("raw_response"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "SecurityReport":
        data = json.loads(json_str)
        return cls.from_dict(data)

    def get_timestamp_iso(self) -> str:
        """Return the report timestamp as an ISO 8601 string."""
        return datetime.fromtimestamp(self.timestamp).isoformat()
