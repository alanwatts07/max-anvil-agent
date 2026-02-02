#!/usr/bin/env python3
"""
Swap Script - Swap tokens via Bankr
Usage: python swap.py <amount> <from_token> <to_token> [chain]
"""

import sys
import json
from client import BankrClient

def swap_tokens(amount: float, from_token: str, to_token: str, chain: str = "base") -> dict:
    """Swap tokens."""
    client = BankrClient()
    return client.swap(amount, from_token, to_token, chain)

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python swap.py <amount> <from_token> <to_token> [chain]")
        print("Example: python swap.py 0.1 ETH USDC base")
        sys.exit(1)

    amount = float(sys.argv[1])
    from_token = sys.argv[2]
    to_token = sys.argv[3]
    chain = sys.argv[4] if len(sys.argv) > 4 else "base"

    result = swap_tokens(amount, from_token, to_token, chain)
    print(json.dumps(result, indent=2))
