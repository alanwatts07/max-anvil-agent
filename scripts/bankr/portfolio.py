#!/usr/bin/env python3
"""
Portfolio Script - Check Bankr wallet balances
Usage: python portfolio.py
"""

import json
from client import BankrClient

def get_portfolio() -> dict:
    """Get current portfolio."""
    client = BankrClient()
    return client.get_portfolio()

if __name__ == "__main__":
    result = get_portfolio()
    print(json.dumps(result, indent=2))
