import argparse
import http.server
import socket
import socketserver
import sys
from pathlib import Path

from scoring import (
    load_engagement_data,
    load_request_master,
    merge_datasets,
    compute_health_scores,
    export_health_json,
)
from render import render_dashboard

DATA_DIR = Path("data")
ENGAGEMENT_CSV = DATA_DIR / "databricksaracade.csv"
REQUEST_MASTER_CSV = DATA_DIR / "request_master.csv"
HEALTH_JSON = DATA_DIR / "arcade_health.json"
DASHBOARD_HTML = Path("arcade_health_dashboard.html")


def main():
    parser = argparse.ArgumentParser(
        description="Build the Arcade Health Dashboard"
    )
    parser.add_argument(
        "--skip-pull",
        action="store_true",
        help="Skip data pull from Databricks/Sheets, use existing CSVs",
    )
    parser.add_argument(
        "--no-serve",
        action="store_true",
        help="Don't start a local server after building",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port for local server (default: 8000)",
    )
    args = parser.parse_args()

    # Stage 1: Data Pull
    if not args.skip_pull:
        print("Stage 1: Pulling fresh data from Databricks and Google Sheets...")
        try:
            from data_to_csv_v1 import run as refresh_data
            refresh_data()
        except Exception as e:
            print(f"Data pull failed: {e}")
            print("Run with --skip-pull to use existing CSVs.")
            sys.exit(1)
    else:
        print("Stage 1: Skipping data pull (using existing CSVs)")

    # Verify CSVs exist
    for path in [ENGAGEMENT_CSV, REQUEST_MASTER_CSV]:
        if not path.exists():
            print(f"Error: {path} not found. Run without --skip-pull to fetch data.")
            sys.exit(1)

    # Stage 2: Score
    print("Stage 2: Computing health scores...")
    engagement = load_engagement_data(str(ENGAGEMENT_CSV))
    rm = load_request_master(str(REQUEST_MASTER_CSV))
    merged = merge_datasets(engagement, rm)
    scored = compute_health_scores(merged)
    result = export_health_json(scored, str(HEALTH_JSON), request_master=rm)
    print(f"  Scored {result['summary']['total_arcades']} arcades")
    print(f"  Lifecycle status breakdown: {result['summary']['by_status']}")
    rm_counts = result["summary"].get("request_master_row_counts_by_status", {})
    if rm_counts:
        print(f"  Request Master Status column: {rm_counts}")
    print(f"  Average health score: {result['summary']['avg_health_score']}")
    print(f"  Saved to {HEALTH_JSON}")

    # Stage 3: Render
    print("Stage 3: Rendering dashboard...")
    output = render_dashboard(str(HEALTH_JSON), str(DASHBOARD_HTML))
    print(f"  Dashboard saved to {output}")
    print()

    port = args.port
    if args.no_serve:
        print(f"Done! View at: http://localhost:{port}/{DASHBOARD_HTML}")
        return

    handler = http.server.SimpleHTTPRequestHandler

    class ReusableServer(socketserver.TCPServer):
        allow_reuse_address = True

    try:
        server = ReusableServer(("", port), handler)
    except OSError:
        sock = socket.socket()
        sock.bind(("", 0))
        port = sock.getsockname()[1]
        sock.close()
        server = ReusableServer(("", port), handler)

    print(f"Done! Dashboard is live at: http://localhost:{port}/{DASHBOARD_HTML}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
