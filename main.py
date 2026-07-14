from data_to_csv_v1 import run as refresh_data


def main():
    print("=== Retirement Data Pipeline ===")
    print()

    # Step 1: Pull latest CSVs from Databricks and Google Sheets
    refresh_data()

    # Future steps go here:
    # Step 2: Transform / join data
    # Step 3: Generate reports


if __name__ == "__main__":
    main()
