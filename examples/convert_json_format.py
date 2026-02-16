"""
Script per convertire il file network_context_latest.json nel formato compatibile
con il modello NetworkState del modulo LLM.
"""

import json
from datetime import datetime
from pathlib import Path


def convert_anomaly_type(original_type: str) -> str:
    """Converte il tipo di anomalia nel formato enum."""
    mapping = {
        "high_utilization": "traffic_spike",
        "high_error_rate": "link_failure",
        "isolated_switch": "switch_failure",
    }
    return mapping.get(original_type, "traffic_spike")


def convert_severity(severity_value: float) -> str:
    """Converte il valore numerico di severità in enum."""
    if severity_value >= 0.9:
        return "critical"
    elif severity_value >= 0.7:
        return "high"
    elif severity_value >= 0.4:
        return "medium"
    else:
        return "low"


def convert_json_format(input_file: str, output_file: str):
    """Converte il JSON nel formato compatibile."""
    
    print(f"Caricamento file: {input_file}")
    with open(input_file, 'r') as f:
        data = json.load(f)
    
    # Converti le anomalie
    if "anomalies" in data:
        converted_anomalies = []
        for i, anomaly in enumerate(data["anomalies"]):
            converted = {
                "id": f"anomaly_{i+1}",
                "type": convert_anomaly_type(anomaly.get("type", "traffic_spike")),
                "severity": convert_severity(anomaly.get("severity", 0.5)),
                "description": anomaly.get("description", ""),
                "affected_resources": anomaly.get("affected_components", []),
                "detected_at": datetime.fromtimestamp(anomaly.get("timestamp", datetime.now().timestamp())).isoformat(),
                "resolved_at": None,
                "metrics": {
                    "confidence": anomaly.get("confidence", 0.0),
                    "original_severity": anomaly.get("severity", 0.0)
                }
            }
            converted_anomalies.append(converted)
        
        data["anomalies"] = converted_anomalies
        print(f"✓ Convertite {len(converted_anomalies)} anomalie")
    
    # Salva il file convertito
    print(f"Salvataggio file convertito: {output_file}")
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print("✓ Conversione completata!")
    return output_file


def main():
    input_file = "network_context_latest.json"
    output_file = "network_context_converted.json"
    
    if not Path(input_file).exists():
        print(f"✗ File {input_file} non trovato!")
        return
    
    try:
        convert_json_format(input_file, output_file)
        print(f"\nPuoi ora usare il file '{output_file}' per testare il modulo.")
    except Exception as e:
        print(f"✗ Errore durante la conversione: {e}")


if __name__ == "__main__":
    main()
