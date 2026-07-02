"""Run all demo seed scripts in order for a fully populated platform."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def run(script: str):
    path = ROOT / script
    print(f"\n--- {script} ---")
    subprocess.check_call([sys.executable, str(path)], cwd=str(ROOT.parent))


if __name__ == "__main__":
    run("seed_team_data.py")
    run("seed_manager_decisions.py")
    run("seed_bias_demo.py")
    print("\nAll demo data seeded.")
