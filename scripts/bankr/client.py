#!/usr/bin/env python3
"""
Bankr API Client - Interface with Bankr.bot API
"""

import os
import json
import time
import requests
from typing import Optional, Dict, Any

class BankrClient:
    """Client for Bankr.bot API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("BANKR_API_KEY")
        self.api_url = os.environ.get("BANKR_API_URL", "https://api.bankr.bot")

        if not self.api_key:
            raise ValueError("BANKR_API_KEY not set")

    def _headers(self) -> Dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "Content-Type": "application/json"
        }

    def submit_job(self, prompt: str) -> Dict[str, Any]:
        """Submit a job to Bankr and get job ID."""
        try:
            response = requests.post(
                f"{self.api_url}/agent/prompt",
                headers=self._headers(),
                json={"prompt": prompt}
            )
            if not response.ok:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "error": response.text,
                    "url": response.url
                }
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Check status of a submitted job."""
        try:
            response = requests.get(
                f"{self.api_url}/agent/job/{job_id}",
                headers=self._headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def cancel_job(self, job_id: str) -> Dict[str, Any]:
        """Cancel a pending job."""
        try:
            response = requests.post(
                f"{self.api_url}/agent/job/{job_id}/cancel",
                headers=self._headers()
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            return {"success": False, "error": str(e)}

    def execute(self, prompt: str, timeout: int = 120) -> Dict[str, Any]:
        """Submit job and wait for completion."""
        # Submit the job
        print(f"Submitting: {prompt}")
        submit_result = self.submit_job(prompt)
        print(f"Submit result: {submit_result}")

        if submit_result.get("success") == False:
            return submit_result

        # Handle different job_id field names
        job_id = submit_result.get("jobId") or submit_result.get("job_id") or submit_result.get("id")
        if not job_id:
            return {"success": False, "error": f"No job_id in response: {submit_result}"}

        print(f"Job ID: {job_id}")

        # Poll for completion
        start_time = time.time()
        last_update_count = 0
        while time.time() - start_time < timeout:
            status = self.get_job_status(job_id)
            job_status = status.get("status", "unknown")

            # Report status updates
            updates = status.get("statusUpdates", [])
            if len(updates) > last_update_count:
                for update in updates[last_update_count:]:
                    print(f"  Status: {update}")
                last_update_count = len(updates)

            if job_status == "completed":
                return {
                    "success": True,
                    "job_id": job_id,
                    "response": status.get("response"),
                    "transactions": status.get("transactions", [])
                }
            elif job_status == "failed":
                return {
                    "success": False,
                    "job_id": job_id,
                    "error": status.get("error", "Job failed")
                }
            elif job_status == "cancelled":
                return {
                    "success": False,
                    "job_id": job_id,
                    "error": "Job was cancelled"
                }

            time.sleep(2)  # Poll every 2 seconds

        return {"success": False, "error": "Timeout waiting for job completion"}

    def get_portfolio(self) -> Dict[str, Any]:
        """Get current portfolio/balances."""
        return self.execute("show my complete portfolio with USD values")

    def get_price(self, token: str) -> Dict[str, Any]:
        """Get current price of a token."""
        return self.execute(f"what is the current price of {token}")

    def swap(self, amount: float, from_token: str, to_token: str, chain: str = "base") -> Dict[str, Any]:
        """Swap tokens."""
        return self.execute(f"swap {amount} {from_token} to {to_token} on {chain}")

    def launch_token(self, name: str, symbol: str, chain: str = "base") -> Dict[str, Any]:
        """Launch a new token via Clanker."""
        return self.execute(f"launch a token called {name} with symbol {symbol} on {chain}")

    def send(self, amount: float, token: str, to_address: str) -> Dict[str, Any]:
        """Send tokens to an address."""
        return self.execute(f"send {amount} {token} to {to_address}")


# Convenience functions for CLI usage
def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python client.py <prompt>")
        print("Example: python client.py 'show my portfolio'")
        sys.exit(1)

    client = BankrClient()
    prompt = " ".join(sys.argv[1:])
    result = client.execute(prompt)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
