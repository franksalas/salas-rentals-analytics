import pandas as pd
import sqlite3
import uuid
from datetime import timedelta
import calendar
import random

def generate_rental_financials():
    print("1. Connecting to Database to pull Contract and Equipment data...")
    conn = sqlite3.connect("salas_rentals_system.db")

    try:
        contracts_df = pd.read_sql("SELECT * FROM Contracts", conn)
        lines_df = pd.read_sql("SELECT * FROM ContractLines", conn)
        equip_df = pd.read_sql("SELECT EquipmentID, DailyRate FROM Equipment", conn)
    except Exception as e:
        print("Error reading tables. Ensure generate_salas_rental.py was run first.")
        return

    # Assign Houston-based Sales Reps to each contract
    sales_reps = ["Jose (Houston North)", "Maria (Houston South)", "James (Katy)", "Sarah (Pasadena)"]

    contracts_df["SalesRep"] = [
        random.choice(sales_reps) for _ in range(len(contracts_df))
    ]

    # Merge everything to get the full picture per line item
    merged = lines_df.merge(contracts_df, on="ContractID").merge(
        equip_df, on="EquipmentID"
    )

    gl_entries = []
    commissions = []

    print("2. Processing Revenue Recognition & Commissions...")

    for _, row in merged.iterrows():
        contract_id = row["ContractID"]
        start_date = pd.to_datetime(row["OutDate"])

        # If the item is still On-Rent, bill up to ExpectedReturnDate for synthetic purposes
        end_date = (
            pd.to_datetime(row["ActualReturnDate"])
            if pd.notna(row["ActualReturnDate"])
            else pd.to_datetime(row["ExpectedReturnDate"])
        )

        daily_rate = row["DailyRate"]
        qty = row["Quantity"]
        rep = row["SalesRep"]

        current_date = start_date
        days_on_rent_total = 0

        # Loop through each calendar month the equipment is on rent
        while current_date <= end_date:
            last_day_of_month = pd.Timestamp(
                year=current_date.year,
                month=current_date.month,
                day=calendar.monthrange(current_date.year, current_date.month)[1],
            )
            billing_end_date = min(last_day_of_month, end_date)

            # Calculate billable days in this specific month
            billable_days = (billing_end_date - current_date).days + 1
            monthly_revenue = billable_days * daily_rate * qty

            # GL Entry: Debit Accounts Receivable
            gl_entries.append({
                "TransactionID": str(uuid.uuid4()),
                "ContractID": contract_id,
                "Date": billing_end_date, 
                "Account": "1100-Accounts Receivable",
                "Debit": round(monthly_revenue, 2),
                "Credit": 0.0,
            })

            # GL Entry: Credit Rental Revenue
            gl_entries.append({
                "TransactionID": str(uuid.uuid4()),
                "ContractID": contract_id,
                "Date": billing_end_date,
                "Account": "4000-Rental Revenue",
                "Debit": 0.0,
                "Credit": round(monthly_revenue, 2),
            })

            # Tiered Commission Logic: 5% for the first 30 days, 2% thereafter
            days_on_rent_total += billable_days
            if days_on_rent_total <= 30:
                commission_rate = 0.05
            else:
                commission_rate = 0.02

            commissions.append({
                "CommissionID": str(uuid.uuid4()),
                "ContractID": contract_id,
                "SalesRep": rep,
                "PeriodEnding": billing_end_date,
                "CommissionRate": commission_rate,
                "Amount": round(monthly_revenue * commission_rate, 2),
            })

            # Move to the first day of the next month
            current_date = last_day_of_month + timedelta(days=1)

    df_gl = pd.DataFrame(gl_entries)
    df_commissions = pd.DataFrame(commissions)

    print("3. Saving Financials to Database...")
    df_gl.to_sql("GeneralLedger", conn, if_exists="replace", index=False)
    df_commissions.to_sql("Commissions", conn, if_exists="replace", index=False)

    # Save the updated contracts table so the SalesRep column persists
    contracts_df.to_sql("Contracts", conn, if_exists="replace", index=False)

    conn.close()
    print(f"Complete! Generated {len(df_gl)} GL entries and {len(df_commissions)} Commission records.")

if __name__ == "__main__":
    generate_rental_financials()