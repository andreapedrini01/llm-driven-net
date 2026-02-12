# LLM Module Testing with Custom JSON File

This guide explains how to test the LLM module using your `network_context_latest.json` file without using the ChatGPT API.

## Created Files

1. **convert_json_format.py** - Converts JSON format to module-compatible format
2. **test_with_your_json.py** - Complete test script that runs various module tests
3. **network_context_converted.json** - Converted JSON file (automatically generated)

## How to Use

### Step 1: Convert JSON File

Your `network_context_latest.json` file has a slightly different format than expected by the module. Run the conversion script:

```bash
python convert_json_format.py
```

This will create the `network_context_converted.json` file with the correct format.

### Step 2: Run Tests

Run the complete test script:

```bash
python test_with_your_json.py
```

## Tests Executed

The script runs 5 main tests:

### Test 1: Network State Loading
- Loads the converted JSON file
- Validates data structure
- Shows information about switches, hosts, links and anomalies

### Test 2: Intent Parsing
- Tests parsing of natural language intents (Italian)
- Extracts entities and parameters from intents
- Calculates confidence scores

Example intents tested:
- "Create a flow from host_1 to host_2 with high priority"
- "Show status of switch_0000000000000001"
- "Resolve anomaly on port 3 of switch 1"
- "Increase bandwidth of link between switch 1 and switch 2"

### Test 3: Context Analysis
- Analyzes intent context against network state
- Identifies relevant resources
- Detects potential conflicts

### Test 4: Anomaly Analysis
- Analyzes anomalies present in network state
- Classifies type and severity
- Suggests corrective actions

Anomalies detected in your file:
1. **High Utilization** on port 3 (100% usage) → CRITICAL severity
2. **High Error Rate** on port 2 (2% errors) → CRITICAL severity
3. **Isolated Switch** (Switch 4 isolated) → HIGH severity

### Test 5: Metrics Analysis
- Analyzes network metrics (bandwidth, latency, port usage)
- Identifies potential problems
- Provides recommendations

## Test Results

All tests executed successfully! ✓

### Data Loaded from Your File:
- **Switches**: 4 (all active)
- **Links**: 2
- **Hosts**: 4
- **Anomalies**: 3
- **Bandwidth Usage**: 9.4% (normal)
- **Average Latency**: 6.4 ms (within normal range)

### Critical Anomalies Identified:
1. Port 3 of Switch 1: 100% usage (CRITICAL)
2. Port 2 of Switch 2: high error rate (CRITICAL)
3. Switch 4: appears isolated from network (HIGH)

## Important Notes

### Without ChatGPT API
These tests use **only local module logic**:
- Intent parsing with local NLP
- Context analysis with deterministic algorithms
- Anomaly detection with pattern matching

### With ChatGPT API
To use ChatGPT API for smarter action generation:
1. Configure API key in `.env`
2. Use module's REST API endpoints
3. See `docs/API_USAGE.md` for details

## Required JSON Format

The module requires anomalies to have this format:

```json
{
  "anomalies": [
    {
      "id": "anomaly_1",
      "type": "traffic_spike",  // Enum: traffic_spike, latency_increase, link_failure, switch_failure, security_threat
      "severity": "critical",    // Enum: low, medium, high, critical
      "description": "Anomaly description",
      "affected_resources": ["resource_id"],
      "detected_at": "2026-02-11T17:35:50",
      "resolved_at": null,
      "metrics": {
        "confidence": 0.9
      }
    }
  ]
}
```

The `convert_json_format.py` script automatically converts your format to this.

## Next Steps

### To Test with ChatGPT API:
1. Configure `.env` with your OpenAI key
2. Start API server: `python -m src.main`
3. Use REST endpoints to submit intents

### To Integrate with Ryu:
1. Module reads JSON files from `cache/` folder
2. External module should save Ryu state to `cache/network_state.json`
3. LLM module will automatically detect changes (if file watching is enabled)

### To Run Complete Tests:
```bash
# Unit tests
pytest tests/

# Integration tests
pytest tests/test_end_to_end_integration.py

# Property-based tests (takes longer)
pytest tests/ -m "property"
```

## Troubleshooting

### Error: "File not found"
Make sure `network_context_latest.json` is in the current directory.

### Error: "Validation error"
Run `convert_json_format.py` first to convert the format.

### Error: "Module not found"
Install dependencies:
```bash
pip install -r requirements.txt
```

## Contact

For questions or issues, consult documentation in `docs/` or open an issue.
