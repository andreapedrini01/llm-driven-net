# LLM-Driven Network Management for SDN

An intent-based networking system that uses **ChatGPT (OpenAI API)** to interpret natural language commands and automatically configure an SDN network running on **ComnetsEmu/Mininet** with a **Ryu OpenFlow controller**.

You describe what you want the network to do in plain English (e.g. *"block traffic from h1 to h3"*, *"create a 50 mbps slice between h1 and h5"*), and the system figures out the right OpenFlow rules, installs them, and verifies the result.

## Table of Contents

- [How It Works](#how-it-works)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Running the Project](#running-the-project)
- [Usage](#usage)
- [Project Structure](#project-structure)
- [Documentation](#documentation)
- [Testing](#testing)
- [Tmux Quick Reference](#tmux-quick-reference)
- [Troubleshooting](#troubleshooting)
- [Authors](#authors)
- [License](#license)

## How It Works

The system is built around three main modules that work together in a pipeline:

1. **Network State Collector** — connects to the Ryu controller REST API, collects topology (switches, links, hosts), flow tables, port statistics, and optionally runs nmap security scans via a Docker container.

2. **LLM Integration Module** — parses the user's natural language intent, analyzes the current network context, and generates a sequence of network actions. For high-confidence intents (simple, well-structured commands) it uses a fast rule-based engine. For ambiguous or complex intents it calls the OpenAI API to figure out what to do.

3. **Northbound Script Generator** — takes the validated actions and executes them on the real network through the Ryu REST API (`ofctl_rest`). Supports flow modifications, network slicing with QoS (OpenFlow meters), and configuration changes.

The system runs in **interactive mode** (`main.py`) — you type commands in a CLI, collect network state, submit intents, and confirm before execution.

### Supported Intent Types

- **Traffic control**: block/allow traffic between hosts, drop specific protocols or ports
- **Network slicing**: create, modify, or delete bandwidth-limited slices between hosts (uses OpenFlow 1.3 meters)
- **Flow rules**: add, modify, or delete OpenFlow flow entries on specific switches
- **Security scanning**: run nmap scans on network hosts and get an LLM-powered vulnerability analysis
- **General configuration**: any network configuration change that can be expressed in natural language

### Available Topologies

The project includes three topology scripts, all compatible with Mininet:

| Topology | Script | Description |
|---|---|---|
| **Tree** | `topology.py` | Tree with depth=3, fanout=3 (13 switches, 27 hosts). Good for hierarchical routing tests. |
| **Linear** | `topology_linear.py` | Chain of switches (default 6), each with 2 hosts. Good for multi-hop latency and path testing. |
| **Ring** | `topology_ring.py` | Ring of core switches (default 4), each with a cluster of 3 hosts. Good for redundant path and slicing tests. |

All topologies automatically attach a Docker-based nmap scanner container (if ComnetsEmu is available and the Docker image is built).

## Prerequisites

- **ComnetsEmu** already installed and working (see [ComnetsEmu repository](https://git.comnets.net/public-repo/comnetsemu.git) for installation instructions)
- **Python 3.8** with `venv` support
- **nmap** installed on the VM (`sudo apt install nmap`)
- An **OpenAI API key**

## Installation

### 1. Clone the repository

The project must be cloned inside the ComnetsEmu root directory:

```bash
cd ~/comnetsemu   # or wherever your comnetsemu installation is
git clone https://github.com/andreapedrini01/llm-driven-net.git
cd llm-driven-net
```

### 2. Create and activate the virtual environment

```bash
# Remove any previous venv
rm -rf venv

# Create a new venv (use python3.8 if that's what your VM has)
python3 -m venv venv

# Activate it
source venv/bin/activate
```

### 3. Install dependencies

The project uses Ryu, which needs a specific setuptools version. Use the install script:

```bash
python install.py
```

This will:
1. Install a compatible `setuptools` and `pbr` for Ryu
2. Install `ryu` without build isolation
3. Install all remaining dependencies from `requirements.txt`

You also need `nmap` and `flask` installed at the system level (outside the venv):

```bash
sudo apt install nmap
pip install flask python-nmap
```

### 4. Configure the environment

Copy the example environment file and fill in your values:

```bash
cp .env_example .env
nano .env
```

The only value you **must** change is `OPENAI_API_KEY` — replace `your-openai-api-key-here` with your actual key from [platform.openai.com/api-keys](https://platform.openai.com/api-keys). Everything else has sensible defaults.

See `.env_example` for the full list of available settings.

### 5. Build the Docker scanner image

This builds the nmap scanner container that gets attached to the topology:

```bash
docker build -t progetto-nmap-manet deployment/progetto-nmap-manet/
```

## Running the Project

You need **three terminal panes** (we recommend using tmux). All commands assume you are inside the `llm-driven-net/` directory with the venv activated.

### Terminal 1 — Ryu Controller

```bash
source venv/bin/activate
ryu-manager ryu_apps/simple_switch_13_lldp.py ryu.app.ofctl_rest ryu.app.rest_topology --observe-links
```

> The custom `simple_switch_13_lldp.py` app is a drop-in replacement for `ryu.app.simple_switch_13` that adds LLDP passthrough for proper link discovery. The `--observe-links` flag is required.

> If Ryu fails to start, try: `pip install eventlet==0.30.2`

### Terminal 2 — Mininet Topology

Make sure you are **outside** the virtual environment for this terminal (do not activate the venv here):

```bash
sudo python3 topology.py
```

Or use one of the alternative topologies:

```bash
# Linear: 6 switches in a chain, 2 hosts each
sudo python3 topology_linear.py

# Ring: 4 core switches in a ring, 3 hosts per cluster
sudo python3 topology_ring.py
```

Wait for the Mininet CLI prompt (`mininet>`). You can test connectivity:

```bash
mininet> pingall
```

### Terminal 3 — Main Application

```bash
source venv/bin/activate
sudo python3 main.py
```

You should see the startup banner with all modules initialized. Now you can use the CLI.

## Usage

### CLI Commands

| Command | Description |
|---|---|
| `collect` | Collect current network state (topology, flows, port stats) |
| `collect --security-scan` | Collect state + run nmap security scan on all hosts |
| `collect --security-scan h1 h3` | Collect state + scan only specific hosts |
| `intent <text>` | Process a natural language network intent |
| `health` | Check system health (Ryu connectivity, filesystem) |
| `clean` | Clear application cache (data/, output/, __pycache__) |
| `quit` | Exit the application |

### Intent Examples

```
> intent block traffic from h1 to h3
> intent allow traffic from h2 to h5
> intent create a slice between h1 and h10 with 50 mbps bandwidth
> intent modify slice between h1 and h10 to 100 mbps
> intent delete slice between h1 and h10
> intent add a flow rule on s1 from h1 to h2
> intent delete all flow rules on s1
```

After processing, the system shows the proposed actions and asks for confirmation before applying them to the network.

### Security Scanning

To scan hosts for vulnerabilities, the nmap Docker container must be running (it starts automatically with the topology if the image is built). Then:

```
> collect --security-scan
```

The system will:
1. Run nmap on each discovered host via the Docker scanner
2. Send the scan results + topology data to ChatGPT for analysis
3. Print a security report with vulnerabilities, configuration issues, and remediation suggestions
4. Save the report to `data/security_history/`

You can also create vulnerabilities in Mininet for testing:

```bash
# From the Mininet CLI
mininet> h1 busybox telnetd -l /bin/sh -p 23 &
mininet> h1 python3 -m http.server 8080 &
```

## Project Structure

```
llm-driven-net/
├── main.py                          # Interactive CLI (intent processing)
├── topology.py                      # Tree topology (depth=3, fanout=3)
├── topology_linear.py               # Linear chain topology
├── topology_ring.py                 # Ring topology with clusters
├── install.py                       # Dependency installer (handles Ryu)
├── check_dependencies.py            # Verify all dependencies are installed
├── clean_cache.py                   # Clear application cache
├── requirements.txt                 # Python dependencies
├── pytest.ini                       # Test configuration
│
├── llm_integration_module/          # LLM integration (core logic)
│   ├── config.py                    #   Application settings
│   ├── models/                      #   Data models (intent, actions, network, security, slices)
│   ├── services/                    #   Business logic
│   │   ├── intent_parser.py         #     NLP intent parsing
│   │   ├── chatgpt_client.py        #     OpenAI API client
│   │   ├── context_analyzer.py      #     Network context analysis
│   │   ├── action_sequencer.py      #     Action ordering and sequencing
│   │   ├── validator.py             #     Action validation and safety checks
│   │   ├── action_output.py         #     Action serialization and output
│   │   ├── prompt_engineering.py    #     Prompt construction for ChatGPT
│   │   ├── security_analyzer.py     #     LLM-powered security analysis
│   │   ├── change_summary.py        #     Post-execution change summaries
│   │   └── confidence_criteria_extractor.py
│   └── utils/                       #   Error handling, input sanitization, logging
│
├── network_state_collector/         # Network data collection
│   ├── collector.py                 #   Main collector class
│   ├── ryu_connector.py             #   Ryu REST API client
│   ├── security_scanner.py          #   Nmap scanning via Docker
│   ├── data_processor.py            #   Raw data processing
│   ├── data_validator.py            #   Data validation
│   ├── llm_integrator.py            #   Format data for LLM consumption
│   └── ...                          #   Config, filesystem, error, logging, performance managers
│
├── northbound_script_generator/     # Action execution on the network
│   ├── action_processor.py          #   Action validation and execution orchestration
│   ├── comnetsemu_connector.py      #   Ryu REST API connector (flow mods, meters, QoS)
│   ├── models.py                    #   Network action data models
│   ├── retry_system.py              #   Retry logic for failed operations
│   ├── config_loader.py             #   Configuration loading
│   └── history_manager.py           #   Execution history tracking
│
├── ryu_apps/                        # Custom Ryu applications
│   └── simple_switch_13_lldp.py     #   L2 switch with LLDP passthrough for link discovery
│
├── deployment/                      # Docker and deployment files
│   └── progetto-nmap-manet/         #   Nmap scanner Docker container
│       ├── Dockerfile
│       ├── app.py                   #     Flask web server for nmap scanning
│       └── requirements.txt
│
├── tests/                           # Test suite
│   ├── unit/                        #   Unit tests (28 test files)
│   ├── property/                    #   Property-based tests with Hypothesis (30 test files)
│   ├── integration/                 #   Integration tests (7 test files)
│   ├── mocks/                       #   Mock objects for testing
│   └── examples/                    #   Example test usage
│
├── docs/                            # Documentation
│   ├── CHATGPT_SETUP.md             #   ChatGPT API configuration guide
│   ├── PROMPT_ENGINEERING.md        #   Prompt engineering documentation
│   ├── ACTION_OUTPUT_INTERFACE.md   #   Action output format specification
│   └── STATE_FILE_READER.md         #   State file reader documentation
│
├── examples/                        # Usage examples and demos
├── data/                            # Runtime data (history, archives) — gitignored
└── output/                          # Action output files — gitignored
```

## Documentation

The `docs/` folder contains deeper technical documentation on specific subsystems:

| Document | Description |
|---|---|
| [ChatGPT Setup](docs/CHATGPT_SETUP.md) | How the OpenAI API is configured, model selection, cost tracking, and troubleshooting API errors |
| [Prompt Engineering](docs/PROMPT_ENGINEERING.md) | How prompts are built, template types, context injection, and response parsing |
| [Action Output Interface](docs/ACTION_OUTPUT_INTERFACE.md) | Format of the JSON action packages saved before execution, status lifecycle, and file locations |
| [State File Reader](docs/STATE_FILE_READER.md) | Reading network state from disk with retry logic, file watching, and JSON validation |

## Testing

```bash
# Run all tests
pytest

# Run by category
pytest tests/unit/              # Unit tests
pytest tests/property/          # Property-based tests (Hypothesis)
pytest tests/integration/       # Integration tests

# Run with coverage
pytest --cov=llm_integration_module --cov=network_state_collector --cov=northbound_script_generator

# Run a specific test file
pytest tests/unit/test_collector.py -v
```

## Tmux Quick Reference

Since you need multiple terminals, here are the essential tmux shortcuts:

| Shortcut | Action |
|---|---|
| `Ctrl+b c` | Create a new window |
| `Ctrl+b n` / `Ctrl+b p` | Next / previous window |
| `Ctrl+b %` | Split pane vertically |
| `Ctrl+b "` | Split pane horizontally |
| `Ctrl+b arrows` | Move between panes |
| `Ctrl+b x` | Close current pane |
| `Ctrl+b [` | Enter scroll mode (press `q` to exit) |

## Troubleshooting

**Ryu won't start**: Make sure `eventlet==0.30.2` is installed (`pip install eventlet==0.30.2`). Also check that no other process is using port 6653 or 8080.

**No switches found**: Make sure the Ryu controller is running before starting the topology. Check that the controller is listening on `127.0.0.1:6653`.

**Nmap scanner not working**: Verify the Docker image is built (`docker build -t progetto-nmap-manet deployment/progetto-nmap-manet/`). Check that `NMAP_SERVICE_URL=http://localhost:5000` is in your `.env` file.

**Low confidence on intents**: Try being more specific. Include host names (h1, h2), switch names (s1), and explicit actions (block, allow, create slice). The system works best with clear, structured commands.

**ChatGPT errors**: Check that your `OPENAI_API_KEY` is valid and has credits. The default model is `gpt-4o-mini` which is cost-effective for this use case.

**Mininet cleanup**: If a previous run didn't shut down cleanly, run `sudo mn -c` before starting a new topology.

## Authors

Built with ☕ and too many terminal panes by:

- **Filippo Palmieri** — [@FilizZPalm](https://github.com/FilizZPalm)
- **Andrea Pedrini** — [@andreapedrini01](https://github.com/andreapedrini01)
- **Pietro Bellini** — [@PietroB01](https://github.com/PietroB01)

## License

This project was developed for educational purposes.
