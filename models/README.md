
```
.
|____OLAP
| |____etl_pipeline.py
|____.DS_Store
|____OLTP
| |____02_generate_routing_history.py
| |____03_generate_financials.py
| |____01_generate_rentals.py
|____README.md
|____run_models.py
```

## Files: Generating OLTP
### `generate_rentals.py`
Uses the Synthetic Data Vault (SDV) to generate a statistically realistic, highly normalized relational database containing master heavy equipment data and rental contracts.

### `generate_routing_history.py`
Reads the rental contracts and generates a messy operational tracking log, intentionally injecting duplicate pings and time-travel errors for data cleansing practice.

### `generate_financials.py`
Processes the rental contracts to calculate complex accounting logic, outputting monthly amortized revenue recognition and tiered sales commissions into General Ledger tables.
Processes the raw rental timelines to calculate complex accounting logic, outputting monthly amortized revenue and tiered sales commissions based on billable days. _Generated Tables & Columns:_ `GeneralLedger` (TransactionID, ContractID, Date, Account, Debit, Credit) and `Commissions` (CommissionID, ContractID, SalesRep, PeriodEnding, CommissionRate, Amount).
## Master Data & Transactional Core (OLTP)

### **Equipment**

| Column | Type | Purpose |
| :--- | :--- | :--- |
| **EquipmentID** | TEXT | Unique primary key identifying the physical asset |
| **Description** | TEXT | The name and specifications of the asset |
| **DailyRate** | REAL | The baseline dollar amount charged per day to rent the item |
| **ReplacementCost** | REAL | The total monetary value charged if the asset is destroyed or lost |
| **AssetCategory** | TEXT | The high-level operational classification (e.g., Trench Safety) |

### **Contracts**

| Column | Type | Purpose |
| :--- | :--- | :--- |
| **ContractID** | TEXT | Unique primary key identifying the rental agreement |
| **CustomerID** | TEXT | Identifier for the client renting the equipment |
| **OutDate** | TIMESTAMP | The calendar date the equipment physically left the rental yard |
| **ExpectedReturnDate** | TIMESTAMP | The initial agreed-upon date the customer stated they would return the equipment |
| **ActualReturnDate** | TIMESTAMP | The true date the equipment was returned |
| **Status** | TEXT | The overarching state of the rental agreement |
| **SalesRep** | TEXT | The name of the employee who manages the account and earns commissions |

### **ContractLines**

| Column | Type | Purpose |
| :--- | :--- | :--- |
| **LineID** | TEXT | Unique primary key for the specific row item on the contract |
| **ContractID** | TEXT | Foreign key linking back to the parent `Contracts` table |
| **EquipmentID** | TEXT | Foreign key linking to the specific asset rented from the `Equipment` table |
| **Quantity** | INTEGER | The physical count of that specific asset rented on this line |

### Operational Tracking (Bronze Layer)

**RoutingHistory**

| Column | Type | Purpose |
| :--- | :--- | :--- |
| **RoutingID** | TEXT | Unique primary key for the specific tracking event |
| **EquipmentID** | TEXT | Foreign key identifying which asset moved |
| **ContractID** | TEXT | Foreign key identifying which contract triggered the movement |
| **Status** | TEXT | The operational state at that exact moment |
| **EventTimestamp** | TIMESTAMP | The precise date and time the system recorded the status change |

### Financial Processing (Gold Layer)

**GeneralLedger**

| Column | Type | Purpose |
| :--- | :--- | :--- |
| **TransactionID** | TEXT | Unique primary key for the double-entry accounting record |
| **ContractID** | TEXT | Foreign key linking the revenue back to the specific rental agreement |
| **Date** | TIMESTAMP | The date the revenue is officially recognized |
| **Account** | TEXT | The financial bucket being impacted |
| **Debit** | REAL | An accounting entry that increases an asset or decreases a liability |
| **Credit** | REAL | An accounting entry that increases a liability or recognizes earned revenue |

### **Commissions**

| Column | Type | Purpose |
| :--- | :--- | :--- |
| **CommissionID** | TEXT | Unique primary key for the payout record |
| **ContractID** | TEXT | Foreign key linking the payout to the rental agreement |
| **SalesRep** | TEXT | The employee receiving the compensation |
| **PeriodEnding** | TIMESTAMP | The final date of the billing cycle that generated this specific payout |
| **CommissionRate** | REAL | The tiered percentage applied to the revenue |
| **Amount** | REAL | The final dollar amount owed to the sales representative |
---
---


## `etl_pipeline.py`

## Dimension Tables

### **Dim_Equipment**

| Column | Type | Purpose |
| :--- | :--- | :--- |
| **EquipmentKey** | INTEGER | Surrogate primary key for the equipment dimension. |
| **EquipmentID** | TEXT | Original operational identifier for the physical asset. |
| **Description** | TEXT | The name and specifications of the asset. |
| **DailyRate** | REAL | The baseline dollar amount charged per day. |
| **ReplacementCost** | REAL | The monetary value charged if the asset is destroyed. |
| **AssetCategory** | TEXT | The high-level operational classification. |
| **Valid_From** | TIMESTAMP | Timestamp indicating when this record version became active, supporting Slowly Changing Dimensions (SCD). |
| **Valid_To** | TIMESTAMP | Timestamp indicating when this record version expired. |
| **Is_Current** | INTEGER | Flag indicating if this is the currently active record version. |

### **Dim_Contract**

| Column | Type | Purpose |
| :--- | :--- | :--- |
| **ContractKey** | INTEGER | Surrogate primary key for the contract dimension. |
| **ContractID** | TEXT | Original operational identifier for the rental agreement. |
| **CustomerID** | TEXT | Identifier for the client renting the equipment. |
| **OutDate** | TIMESTAMP | Date the equipment physically left the rental yard. |
| **ExpectedReturnDate** | TEXT | The initial agreed-upon return date. |
| **ActualReturnDate** | TEXT | The true date the equipment was returned. |
| **Status** | TEXT | The overarching state of the rental agreement. |
| **SalesRep** | TEXT | The employee who manages the account and earns commissions. |

### **Dim_Date**

| Column | Type | Purpose |
| :--- | :--- | :--- |
| **DateKey** | INTEGER | Surrogate primary key for the date dimension, typically formatted as YYYYMMDD. |
| **FullDate** | TIMESTAMP | The standard datetime representation of the exact date. |
| **Year** | INTEGER | The calendar year. |
| **Quarter** | INTEGER | The calendar quarter (1-4). |
| **Month** | INTEGER | The calendar month (1-12). |
| **DayOfWeek** | TEXT | The text name of the day (e.g., Monday, Tuesday). |

## Fact Tables

### **Fact_Routing**

| Column | Type | Purpose |
| :--- | :--- | :--- |
| **RoutingID** | TEXT | Unique identifier for the specific tracking event. |
| **DateKey** | INTEGER | Foreign key linking to the `Dim_Date` table for the event date. |
| **ContractKey** | INTEGER | Foreign key linking to the `Dim_Contract` table. |
| **EquipmentKey** | INTEGER | Foreign key linking to the `Dim_Equipment` table. |
| **Status** | TEXT | The operational state at that exact moment. |
| **EventTimestamp** | TIMESTAMP | The precise date and time the system recorded the status change. |

### **Fact_Financials**

| Column | Type | Purpose |
| :--- | :--- | :--- |
| **TransactionID** | TEXT | Unique identifier for the double-entry accounting record. |
| **DateKey** | INTEGER | Foreign key linking to the `Dim_Date` table for when revenue is recognized. |
| **ContractKey** | INTEGER | Foreign key linking to the `Dim_Contract` table. |
| **Account** | TEXT | The financial bucket being impacted (e.g., Accounts Receivable, Rental Revenue). |
| **Debit** | REAL | An accounting entry that increases an asset or decreases a liability. |
| **Credit** | REAL | An accounting entry that increases a liability or recognizes earned revenue. |
---
---
