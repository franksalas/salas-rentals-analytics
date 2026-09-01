import pandas as pd
import sqlite3
import numpy as np
from datetime import datetime


def extract_data(source_db):
    print("1. Extracting data from OLTP database...")
    conn = sqlite3.connect(source_db)

    tables = {}
    for table in [
        "Equipment",
        "Contracts",
        "ContractLines",
        "GeneralLedger",
        "Commissions",
        "RoutingHistory",
    ]:
        tables[table] = pd.read_sql(f"SELECT * FROM {table}", conn)

    conn.close()
    return tables


def clean_routing_data(routing_df, contracts_df, equipment_df):
    print("2. Cleansing dirty Operations data...")

    # FIX: Add format='mixed' so pandas can handle strings with and without fractional seconds
    routing_df["EventTimestamp"] = pd.to_datetime(
        routing_df["EventTimestamp"], format="mixed"
    )
    contracts_df["OutDate"] = pd.to_datetime(contracts_df["OutDate"], format="mixed")

    initial_count = len(routing_df)

    # A. Remove Orphaned Records (Equipment or Contracts that don't exist)
    valid_equip = equipment_df["EquipmentID"].unique()
    valid_contracts = contracts_df["ContractID"].unique()
    routing_df = routing_df[
        routing_df["EquipmentID"].isin(valid_equip)
        & routing_df["ContractID"].isin(valid_contracts)
    ]

    # B. Fix Duplicates (Keep the earliest timestamp for a given status per equipment/contract)
    routing_df = routing_df.sort_values("EventTimestamp").drop_duplicates(
        subset=["ContractID", "EquipmentID", "Status"], keep="first"
    )

    # C. Fix Time Travel (Events that happen before the contract OutDate - except Reserved/Dispatched)
    # We join with contracts to check dates
    merged = routing_df.merge(
        contracts_df[["ContractID", "OutDate"]], on="ContractID", how="left"
    )

    # A rule: 'Off-Rent', 'Inspected', 'Available' cannot happen before the OutDate
    post_rent_statuses = ["Off-Rent", "Inspected", "Available"]
    time_travel_mask = (merged["Status"].isin(post_rent_statuses)) & (
        merged["EventTimestamp"] < merged["OutDate"]
    )

    # Drop the time-travel records
    routing_df = routing_df[~time_travel_mask.values].copy()

    final_count = len(routing_df)
    print(f"   -> Removed {initial_count - final_count} anomalous records.")

    return routing_df


def build_dim_equipment_scd2(equipment_df):
    print("3. Building Dim_Equipment (Applying SCD Type 2 for price hikes)...")

    # Base load of all equipment
    base_dim = equipment_df.copy()
    base_dim["Valid_From"] = pd.to_datetime("1900-01-01")
    # FIX: Changed 9999-12-31 to 2099-12-31 to avoid pandas nanosecond overflow
    base_dim["Valid_To"] = pd.to_datetime("2099-12-31")
    base_dim["Is_Current"] = True

    # SIMULATE A MID-YEAR PRICE HIKE FOR TRENCH SAFETY EQUIPMENT
    hike_date = pd.to_datetime("2026-06-01")

    # Identify items to update
    trench_items = base_dim[base_dim["AssetCategory"] == "Trench Safety"].copy()

    # Expire old records
    base_dim.loc[base_dim["AssetCategory"] == "Trench Safety", "Valid_To"] = (
        hike_date - pd.Timedelta(days=1)
    )
    base_dim.loc[base_dim["AssetCategory"] == "Trench Safety", "Is_Current"] = False

    # Create new active records with 15% rate increase
    trench_items["DailyRate"] = trench_items["DailyRate"] * 1.15
    trench_items["Valid_From"] = hike_date
    # FIX: Changed 9999-12-31 to 2099-12-31
    trench_items["Valid_To"] = pd.to_datetime("2099-12-31")
    trench_items["Is_Current"] = True

    # Combine and generate Surrogate Keys
    dim_equipment = pd.concat([base_dim, trench_items]).reset_index(drop=True)
    dim_equipment.insert(0, "EquipmentKey", range(1, len(dim_equipment) + 1))

    return dim_equipment


def build_dimensions(tables):
    print("4. Building remaining Dimensions...")
    dims = {}

    # Dim_Contract
    contracts = tables["Contracts"].copy()
    contracts.insert(0, "ContractKey", range(1, len(contracts) + 1))
    dims["Dim_Contract"] = contracts

    # Dim_Date (Simple calendar generation for 2025-2027)
    date_range = pd.date_range(start="2025-01-01", end="2027-12-31")
    dims["Dim_Date"] = pd.DataFrame(
        {
            "DateKey": date_range.strftime("%Y%m%d").astype(int),
            "FullDate": date_range,
            "Year": date_range.year,
            "Quarter": date_range.quarter,
            "Month": date_range.month,
            "DayOfWeek": date_range.day_name(),
        }
    )

    return dims


def build_facts(tables, dims, clean_routing):
    print("5. Building Fact Tables (Joining Surrogate Keys)...")
    facts = {}

    dim_contract = dims["Dim_Contract"]
    dim_equip = dims["Dim_Equipment"]

    # ----------------------------------------------------
    # FACT FINANCIALS
    # ----------------------------------------------------
    gl = tables["GeneralLedger"].copy()
    gl["Date"] = pd.to_datetime(gl["Date"])

    # Join ContractKey
    fact_fin = gl.merge(
        dim_contract[["ContractID", "ContractKey"]], on="ContractID", how="left"
    )

    # Join DateKey
    fact_fin["DateKey"] = fact_fin["Date"].dt.strftime("%Y%m%d").astype(int)

    # Select final columns
    facts["Fact_Financials"] = fact_fin[
        ["TransactionID", "DateKey", "ContractKey", "Account", "Debit", "Credit"]
    ]

    # ----------------------------------------------------
    # FACT ROUTING (Operations)
    # ----------------------------------------------------
    routing = clean_routing.copy()
    routing["EventTimestamp"] = pd.to_datetime(routing["EventTimestamp"])

    # Join ContractKey
    fact_rout = routing.merge(
        dim_contract[["ContractID", "ContractKey"]], on="ContractID", how="left"
    )

    # Join EquipmentKey (SCD Type 2 Join!)
    # We must match the EquipmentID AND ensure the EventTimestamp falls between Valid_From and Valid_To
    fact_rout = fact_rout.merge(
        dim_equip[["EquipmentKey", "EquipmentID", "Valid_From", "Valid_To"]],
        on="EquipmentID",
    )

    # Filter to only the valid SCD record for the time of the event
    scd_mask = (fact_rout["EventTimestamp"] >= fact_rout["Valid_From"]) & (
        fact_rout["EventTimestamp"] <= fact_rout["Valid_To"]
    )
    fact_rout = fact_rout[scd_mask].copy()

    # Join DateKey
    fact_rout["DateKey"] = fact_rout["EventTimestamp"].dt.strftime("%Y%m%d").astype(int)

    facts["Fact_Routing"] = fact_rout[
        [
            "RoutingID",
            "DateKey",
            "ContractKey",
            "EquipmentKey",
            "Status",
            "EventTimestamp",
        ]
    ]

    return facts


def load_data(dims, facts, target_db):
    print("6. Loading Data Warehouse...")
    conn = sqlite3.connect(target_db)

    for name, df in dims.items():
        df.to_sql(name, conn, if_exists="replace", index=False)
        print(f"   -> Loaded {name} ({len(df)} rows)")

    for name, df in facts.items():
        df.to_sql(name, conn, if_exists="replace", index=False)
        print(f"   -> Loaded {name} ({len(df)} rows)")

    conn.close()
    print("\nETL Pipeline Complete! Data Warehouse is ready.")


if __name__ == "__main__":
    source = "salas_rentals_system.db"
    target = "salas_rentals_data_warehouse.db"

    # Run the Pipeline
    raw_tables = extract_data(source)
    cleaned_routing = clean_routing_data(
        raw_tables["RoutingHistory"], raw_tables["Contracts"], raw_tables["Equipment"]
    )

    dimensions = build_dimensions(raw_tables)
    dimensions["Dim_Equipment"] = build_dim_equipment_scd2(raw_tables["Equipment"])

    fact_tables = build_facts(raw_tables, dimensions, cleaned_routing)

    load_data(dimensions, fact_tables, target)
