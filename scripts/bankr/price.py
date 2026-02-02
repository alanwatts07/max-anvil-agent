#!/usr/bin/env python3
"""
Price Script - Get token prices via Bankr
Usage: python price.py <token>
"""

import sys
import json
from client import BankrClient

def get_price(token: str) -> dict:
    """Get token price."""
    client = BankrClient()
    return client.get_price(token)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python price.py <token>")
        print("Example: python price.py ETH")
        sys.exit(1)

    result = get_price(sys.argv[1])
    print(json.dumps(result, indent=2))
