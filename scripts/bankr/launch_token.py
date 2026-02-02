#!/usr/bin/env python3
"""
Token Launch Script - Launch tokens via Bankr/Clanker
Usage: python launch_token.py <name> <symbol> [chain]
"""

import sys
import json
from client import BankrClient

def launch_token(name: str, symbol: str, chain: str = "base") -> dict:
    """Launch a new token."""
    client = BankrClient()
    return client.launch_token(name, symbol, chain)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python launch_token.py <name> <symbol> [chain]")
        print("Example: python launch_token.py 'Slop Launcher' SLOP base")
        sys.exit(1)

    name = sys.argv[1]
    symbol = sys.argv[2]
    chain = sys.argv[3] if len(sys.argv) > 3 else "base"

    result = launch_token(name, symbol, chain)
    print(json.dumps(result, indent=2))
