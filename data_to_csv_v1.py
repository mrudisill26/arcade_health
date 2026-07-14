import csv
import gspread
import pandas as pd
from databricks import sql
from databricks.sdk.core import Config


def fetch_databricks_data():
    """Pull arcade demo data from Databricks and save to CSV."""
    print("Connecting to Databricks...")
    cfg = Config()
    conn = sql.connect(
        server_hostname=cfg.host,
        http_path="/sql/1.0/warehouses/d3a580ac8a593ef1",
        credentials_provider=lambda: cfg.authenticate,
    )

    print("Querying dev.arcade_demo.v_arcade_name_month_v2...")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dev.arcade_demo.v_arcade_name_month_v2 ORDER BY date_ym DESC")
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    df = pd.DataFrame(rows, columns=columns)

    df.to_csv("data/databricksaracade.csv", index=False)
    print(f"Saved {len(df)} rows to data/databricksaracade.csv")

    cursor.close()
    conn.close()
    return df


def fetch_google_sheets_data():
    """Pull Request_Master from Google Sheets, filter to IE Published, save to CSV."""
    print("Connecting to Google Sheets...")
    gc = gspread.oauth()
    sh = gc.open_by_url(
        "https://docs.google.com/spreadsheets/d/1t7TJtTL-jbUaCVKVLMMOahbKcL5b1IyCf3uUSCmQo4A/edit"
    )
    worksheet = sh.worksheet("Request_Master")

    print("Pulling Request_Master data...")
    raw = worksheet.get_all_values()
    headers = raw[0]
    df = pd.DataFrame(raw[1:], columns=headers)

    # Replace newlines within cells so each spreadsheet row = one CSV row
    df = df.replace(r'\n', ' ', regex=True)

    # Filter to only "IE Published" status rows
    status_col = [c for c in headers if "status" in c.lower()]
    if not status_col:
        raise ValueError(f"Could not find a status column. Available columns: {headers}")

    df_published = df[df[status_col[0]] == "IE Published"]

    df_published.to_csv("data/request_master.csv", index=False, quoting=csv.QUOTE_ALL)
    print(f"Total rows: {len(df)} | IE Published: {len(df_published)} → saved to data/request_master.csv")

    return df_published


def run():
    print("=" * 60)
    print("Step 1: Fetch Databricks arcade data")
    print("=" * 60)
    fetch_databricks_data()

    print()
    print("=" * 60)
    print("Step 2: Fetch Google Sheets Request_Master (IE Published)")
    print("=" * 60)
    fetch_google_sheets_data()

    print()
    print("Done. CSVs are ready in data/ folder.")


if __name__ == "__main__":
    run()
