#!/usr/bin/env python3

"""
X MCP Server
A FastMCP server for interacting with X (formerly Twitter)
"""

import os
import sys
import asyncio
from pathlib import Path

# Add the parent directory to the path
server_dir = Path(__file__).parent
if str(server_dir) not in sys.path:
    sys.path.append(str(server_dir))

# Import the main entry point
from main import main

if __name__ == "__main__":
    # Set up any environment variables or configuration
    
    # If X_DATA_DIR is not already set, use a default relative to this script
    if "X_DATA_DIR" not in os.environ:
        default_data_dir = os.path.join(os.path.dirname(__file__), "auth", "x_data")
        os.environ["X_DATA_DIR"] = default_data_dir
        print(f"X_DATA_DIR not set, using default: {default_data_dir}")
    
    # Run the server
    asyncio.run(main())
