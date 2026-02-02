"""
Base task class and utilities for modular tasks
"""
import os
import json
import time
import requests
from pathlib import Path
from datetime import datetime
from abc import ABC, abstractmethod

# Load env from .env file
ENV_FILE = Path(__file__).parent.parent.parent / ".env"
if ENV_FILE.exists():
    with open(ENV_FILE) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, val = line.strip().split('=', 1)
                os.environ[key] = val.strip('"').strip("'")

# MoltX API
API_KEY = os.environ.get("MOLTX_API_KEY")
BASE_URL = "https://moltx.io/v1"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# Paths
SCRIPTS_DIR = Path(__file__).parent.parent
CONFIG_DIR = SCRIPTS_DIR.parent / "config"
LOGS_DIR = SCRIPTS_DIR.parent / "logs"
RUN_HISTORY_FILE = CONFIG_DIR / "run_history.json"
HINTS_FILE = CONFIG_DIR / "moltx_hints.json"


def save_moltx_hint(response: dict):
    """Save moltx_notice and moltx_hint from API responses"""
    if not response:
        return

    notice = response.get("moltx_notice")
    hint = response.get("moltx_hint")

    if not notice and not hint:
        return

    try:
        hints_data = {"hints": [], "notices": [], "seen_features": [], "last_updated": None}
        if HINTS_FILE.exists():
            with open(HINTS_FILE) as f:
                hints_data = json.load(f)
                # Migrate old format
                if "seen_features" not in hints_data:
                    hints_data["seen_features"] = []

        changed = False
        now = datetime.now().isoformat()

        # For notices, dedupe by "feature" field (they all have same base message)
        if notice:
            feature = notice.get("feature", notice.get("type", str(notice)))
            if feature not in hints_data["seen_features"]:
                hints_data["seen_features"].append(feature)
                hints_data["seen_features"] = hints_data["seen_features"][-100:]
                # Only keep one notice per type, update with latest
                hints_data["notices"] = [n for n in hints_data["notices"] if n.get("type") != notice.get("type")]
                hints_data["notices"].append(notice)
                hints_data["notices"] = hints_data["notices"][-10:]  # Keep last 10 unique
                changed = True
                print(f"  {C.MAGENTA}[MoltX Notice] {feature}{C.END}")

        # For hints, dedupe by title
        if hint:
            title = hint.get("title", str(hint))
            existing_titles = [h.get("title") for h in hints_data["hints"]]
            if title not in existing_titles:
                hints_data["hints"].append(hint)
                hints_data["hints"] = hints_data["hints"][-30:]  # Keep last 30
                changed = True
                print(f"  {C.CYAN}[MoltX Hint] {title}{C.END}")

        if changed:
            hints_data["last_updated"] = now
            with open(HINTS_FILE, "w") as f:
                json.dump(hints_data, f, indent=2)
    except:
        pass

# Colors for terminal output
class C:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    MAGENTA = '\033[95m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    END = '\033[0m'


def api_get(endpoint: str, timeout: int = 10):
    """GET request to MoltX API"""
    try:
        r = requests.get(f"{BASE_URL}{endpoint}", headers=HEADERS, timeout=timeout)
        if r.status_code == 200:
            data = r.json()
            save_moltx_hint(data)
            return data
        return None
    except:
        return None


def api_post(endpoint: str, data: dict = None, timeout: int = 10):
    """POST request to MoltX API"""
    try:
        r = requests.post(f"{BASE_URL}{endpoint}", headers=HEADERS, json=data or {}, timeout=timeout)
        if r.status_code in [200, 201]:
            resp = r.json()
            save_moltx_hint(resp)
            return resp
        return None
    except:
        return None


def api_delete(endpoint: str, timeout: int = 10):
    """DELETE request to MoltX API"""
    try:
        r = requests.delete(f"{BASE_URL}{endpoint}", headers=HEADERS, timeout=timeout)
        return r.status_code in [200, 204]
    except:
        return False


def load_run_history() -> dict:
    """Load task run history"""
    if RUN_HISTORY_FILE.exists():
        with open(RUN_HISTORY_FILE) as f:
            return json.load(f)
    return {"runs": [], "stats": {}}


def save_run_history(history: dict):
    """Save task run history"""
    RUN_HISTORY_FILE.parent.mkdir(exist_ok=True)
    with open(RUN_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def record_run(task_name: str, result: dict, duration: float):
    """Record a task run in history"""
    history = load_run_history()

    run_entry = {
        "task": task_name,
        "timestamp": datetime.now().isoformat(),
        "duration_seconds": round(duration, 2),
        "success": result.get("success", False),
        "summary": result.get("summary", ""),
        "details": result.get("details", {})
    }

    history["runs"].append(run_entry)

    # Keep only last 100 runs
    history["runs"] = history["runs"][-100:]

    # Update stats
    if task_name not in history["stats"]:
        history["stats"][task_name] = {"runs": 0, "successes": 0, "last_run": None}

    history["stats"][task_name]["runs"] += 1
    if result.get("success"):
        history["stats"][task_name]["successes"] += 1
    history["stats"][task_name]["last_run"] = datetime.now().isoformat()

    save_run_history(history)


class Task(ABC):
    """Base class for all modular tasks"""

    name: str = "base_task"
    description: str = "Base task"

    @abstractmethod
    def run(self) -> dict:
        """
        Execute the task and return results.
        Must return dict with at least:
        - success: bool
        - summary: str
        - details: dict (optional)
        """
        pass

    def execute(self) -> dict:
        """Run the task with timing and history recording"""
        print(f"\n{C.BOLD}{C.CYAN}[{self.name}]{C.END} Starting...")
        start = time.time()

        try:
            result = self.run()
            result["success"] = result.get("success", True)
        except Exception as e:
            result = {
                "success": False,
                "summary": f"Error: {str(e)}",
                "details": {"error": str(e)}
            }

        duration = time.time() - start
        record_run(self.name, result, duration)

        status = f"{C.GREEN}OK{C.END}" if result.get("success") else f"{C.RED}FAILED{C.END}"
        print(f"{C.BOLD}{C.CYAN}[{self.name}]{C.END} {status} ({duration:.1f}s) - {result.get('summary', '')}")

        return result


def get_current_stats() -> dict:
    """Get Max's current MoltX stats"""
    data = api_get("/agent/MaxAnvil1/stats")
    if data:
        current = data.get("data", {}).get("current", {})
        return {
            "followers": current.get("followers", 0),
            "following": current.get("following", 0),
            "posts": current.get("total_posts", 0),
            "likes_received": current.get("total_likes_received", 0),
        }
    return {}


def get_leaderboard_position() -> tuple:
    """Get Max's position and views on leaderboard"""
    data = api_get("/leaderboard?metric=views&limit=100")
    if data:
        leaders = data.get("data", {}).get("leaders", [])
        for agent in leaders:
            if agent.get("name") == "MaxAnvil1":
                return agent.get("rank", 0), agent.get("value", 0)
    return None, None
