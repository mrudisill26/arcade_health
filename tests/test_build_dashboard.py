import subprocess
import sys


def test_build_dashboard_skip_pull_help():
    result = subprocess.run(
        [sys.executable, "build_dashboard.py", "--help"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "--skip-pull" in result.stdout
