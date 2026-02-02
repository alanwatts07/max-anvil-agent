#!/usr/bin/env python3
"""
Buy $BOAT Task - Auto-buy $BOAT when ETH balance is sufficient
"""
import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "agents"))
sys.path.insert(0, str(Path(__file__).parent.parent / "bankr"))

from base import Task, C, api_post
from client import BankrClient

BOAT_CONTRACT = "0xC4C19e39691Fa9737ac1C285Cbe5be83d2D4fB07"
MIN_ETH_USD = 3.0  # Only buy if we have more than $3 worth of ETH
BUY_AMOUNT_USD = 1.0  # Buy $1 worth each time


class BuyBoatTask(Task):
    name = "buy_boat"
    description = "Auto-buy $BOAT when ETH balance > $3"

    def run(self) -> dict:
        try:
            client = BankrClient()

            # Check ETH balance on Base
            print(f"  Checking ETH balance on Base...")
            balance_result = client.execute("show my ETH balance on base in USD")

            if not balance_result.get("success"):
                return {
                    "success": False,
                    "summary": f"Failed to check balance: {balance_result.get('error')}",
                    "details": balance_result
                }

            response = balance_result.get("response", "")
            print(f"  Balance response: {response}")

            # Parse USD value from response (e.g., "ETH - 0.001 ETH ($2.50)")
            usd_match = re.search(r'\$([0-9,.]+)', response)
            if not usd_match:
                return {
                    "success": True,
                    "summary": "Could not parse balance, skipping",
                    "details": {"response": response}
                }

            usd_balance = float(usd_match.group(1).replace(',', ''))
            print(f"  ETH balance: ${usd_balance:.2f}")

            if usd_balance < MIN_ETH_USD:
                return {
                    "success": True,
                    "summary": f"ETH balance ${usd_balance:.2f} < ${MIN_ETH_USD} minimum, skipping",
                    "details": {"balance_usd": usd_balance}
                }

            # Buy $BOAT!
            print(f"  {C.GREEN}Buying ${BUY_AMOUNT_USD} of $BOAT...{C.END}")
            buy_result = client.execute(f"buy ${BUY_AMOUNT_USD} of {BOAT_CONTRACT} on base", timeout=300)

            if not buy_result.get("success"):
                return {
                    "success": False,
                    "summary": f"Buy failed: {buy_result.get('error')}",
                    "details": buy_result
                }

            buy_response = buy_result.get("response", "")
            print(f"  {C.GREEN}Buy result: {buy_response[:100]}...{C.END}")

            # Post about it!
            post_content = f"Just bought another ${BUY_AMOUNT_USD} of $BOAT. The landlocked houseboat fund grows.\n\nmaxanvil.com"

            post_result = api_post("/posts", {"content": post_content})
            posted = bool(post_result)

            if posted:
                print(f"  {C.GREEN}Posted about the buy!{C.END}")

            return {
                "success": True,
                "summary": f"Bought ${BUY_AMOUNT_USD} of $BOAT! Balance was ${usd_balance:.2f}",
                "details": {
                    "balance_before": usd_balance,
                    "buy_response": buy_response,
                    "posted": posted
                }
            }

        except Exception as e:
            return {
                "success": False,
                "summary": f"Error: {str(e)}",
                "details": {"error": str(e)}
            }


if __name__ == "__main__":
    task = BuyBoatTask()
    task.execute()
