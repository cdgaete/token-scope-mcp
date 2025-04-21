#!/usr/bin/env python3
"""
TokenScope
Token-Aware Directory Explorer for LLMs
Main entry point for running the MCP server.
"""

import os
import sys
import argparse

# Parse command line arguments
parser = argparse.ArgumentParser(description="TokenScope: Token-Aware Directory Explorer for LLMs")
parser.add_argument("--base-path", type=str, help="Base directory for security validation. All file operations will be restricted to this directory.")
args = parser.parse_args()

from tokenscope.token_scope import mcp, set_base_path

if args.base_path is None:
    raise ValueError("Base path is required.")
if not os.path.exists(args.base_path) or not os.path.isdir(args.base_path):
    print(f"Error: Base path does not exist or is not a directory: {args.base_path}")
    sys.exit(1)
# Use absolute path
base_path = os.path.abspath(args.base_path)

# Set the base path for the MCP server
set_base_path(base_path)

def main():
    """Main entry point for the TokenScope server."""
    try:
        mcp.run()
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
