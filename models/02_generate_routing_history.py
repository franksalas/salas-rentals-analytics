import pandas as pd
import sqlite3
import random
from datetime import timedelta
import uuid

def generate_messy_routing():
    print("1. Connecting to Database to fetch valid Assets and Contracts...")
    conn = sqlite3.connect("salas_rentals_system.db")

    try:
        lines_df = pd.read_sql("SELECT ContractID, EquipmentID FROM ContractLines", conn)
        contracts_df = pd.read_sql("SELECT ContractID, OutDate, ActualReturnDate FROM Contracts", conn)
    except Exception as e:
        print("Error: Make sure you ran generate_salas_rental.py first!")
        return

    merged = lines_df.merge(contracts_df, on="ContractID")
    history_records = []

    print("2. Generating clean operational history...")
    for _, row in merged.iterrows():
        contract_id = row["ContractID"]
        equip_id = row["EquipmentID"]
        start_date = pd.to_datetime(row["OutDate"])

        # Base expected workflow
        workflow = [
            ("Reserved", start_date - timedelta(days=random.randint(2, 7))),
            ("Dispatched", start_date - timedelta(hours=random.randint(2, 12))),
            ("On-Site", start_date),
        ]

        if pd.notna(row["ActualReturnDate"]):
            end_date = pd.to_datetime(row["ActualReturnDate"])
            workflow.extend([
                ("Off-Rent", end_date),
                ("Inspected", end_date + timedelta(days=random.randint(1, 3))),
                ("Available", end_date + timedelta(days=random.randint(4, 5))),
            ])

        for status, timestamp in workflow:
            history_records.append({
                "RoutingID": str(uuid.uuid4()),
                "EquipmentID": equip_id,
                "ContractID": contract_id,
                "Status": status,
                "EventTimestamp": timestamp,
            })

    df_history = pd.DataFrame(history_records)

    print("3. Injecting 'Dirty Data' (Duplicates, Time-Travel, Orphaned Records)...")
    dirty_records = []

    # 1. Inject Duplicates
    on_site_records = df_history[df_history["Status"] == "On-Site"].sample(frac=0.1)
    for _, row in on_site_records.iterrows():
        duplicate = row.to_dict()  
        duplicate["EventTimestamp"] += timedelta(seconds=random.randint(1, 59))
        duplicate["RoutingID"] = str(uuid.uuid4())
        dirty_records.append(duplicate)

    # 2. Inject Out-Of-Order Timestamps (Time Travel)
    time_travel_records = df_history[df_history["Status"] == "Off-Rent"].sample(frac=0.05)
    for _, row in time_travel_records.iterrows():
        bad_record = row.to_dict()  
        bad_record["EventTimestamp"] -= timedelta(days=90)
        bad_record["RoutingID"] = str(uuid.uuid4())
        dirty_records.append(bad_record)

    # 3. Inject Orphaned Records
    dirty_records.append({
        "RoutingID": str(uuid.uuid4()),
        "EquipmentID": "EQ-9999-GHOST",
        "ContractID": "RC-UNKNOWN",
        "Status": "Dispatched",
        "EventTimestamp": pd.Timestamp.now(),
    })

    df_final = (
        pd.concat([df_history, pd.DataFrame(dirty_records)])
        .sample(frac=1)
        .reset_index(drop=True)
    )

    print("4. Saving RoutingHistory table to SQLite...")
    df_final.to_sql("RoutingHistory", conn, if_exists="replace", index=False)
    conn.close()

    print(f"Complete! Generated {len(df_final)} routing events with built-in anomalies.")

if __name__ == "__main__":
    generate_messy_routing()