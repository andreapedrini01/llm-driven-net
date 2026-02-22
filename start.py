#!/usr/bin/env python3
"""
Convenience wrapper to start the Northbound Script Generator system.

This script allows you to start the system from the project root without
needing to specify the full path to the start_system.py file.

Usage:
    python start.py
"""

import sys
from pathlib import Path

# Ensure project root is in path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run the main system
if __name__ == "__main__":
    # Import after path is set
    from northbound_script_generator import start_system
    
    # Run the main function
    import asyncio
    asyncio.run(start_system.main())
