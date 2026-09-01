use case for database for salas rentals on how to transform raw data into gold layer


## Files: Generating DB
### `generate_rentals.py`
Uses the Synthetic Data Vault (SDV) to generate a statistically realistic, highly normalized relational database containing master heavy equipment data and rental contracts.
#### Tables & Fields

**Equipments** (Master Data)
	- EquipmentID: 
		- Unique primary key identifying the physical asset.
		- `EQ-101`
		- `sdv-id-nBVySd`
	- Description
		- The name and specifications of the asset
		- `8x24 Steel Trench Shield`
	- DailyRate
		- The baseline dollar amount charged per day to rent the item.
		- `41`
	- ReplacementCost
		- The total monetary value charged to the customer if the asset is destroyed or lost on-site.
		- `59785`
	- AssetCategory
		- The high-level operational classification.
		- `Trench Safety`

- **Contracts**(Transactional Core)
	- ContractID
		- Unique primary key identifying the rental agreement.
		- `sdv-id-nGTeos`
	- CustomerID
		- Foreign key identifying the client renting the equipment.
		- `CUST-15`
	- OutDate
		- The calendar date the equipment physically left the rental yard.
		- `2026-03-09 00:00:00`
	- ExpectedReturnDate
		- The initial agreed-upon date the customer stated they would return the equipment.
		- `2026-04-08 00:00:00`
	- ActualReturnDate
		- The true date the equipment was returned. Remains `NULL` if the asset is still on-rent.
		- `NULL`
	- Status
		- The overarching state of the rental agreement 
		- `On-Rent`
	- SalesRep
		- The name of the employee who manages the account and earns commissions on the revenue.
		- `Jose (Houston North)`

- **Contract line** (Transactional Core)
- LineID
	- Unique primary key for the specific row item on the contract.
	- `sdv-id-fVIkUX`
- ContractID
	- Foreign key linking back to the parent `Contracts` table.
	- `sdv-id-NSZqBz`
- EquipmentID
	- Foreign key linking to the specific asset rented from the `Equipment` table.
	- `sdv-id-BdUToU`
- Quanitty
	- The physical count of that specific asset rented on this line (e.g., 4 Gas Monitors).
	- `6`

### `generate_routing_history.py`
Reads the rental contracts and generates a messy operational tracking log, intentionally injecting duplicate pings and time-travel errors for data cleansing practice.

#### Table
**RoutingHistory** (Bronze Operational Layer)
- RoutingID
	- Unique primary key for the specific tracking event.
	- `bcdbed07-44dc-4848-9320-9302b68ba064`
- EquipmentID
	- Foreign key identifying which asset moved.
	- `sdv-id-xRSvHG`
- ContractID
	- Foreign key identifying which contract triggered the movement.
	- `sdv-id-ZJkFZN`
- Status
	- The operational state at that exact moment (e.g., Reserved, Dispatched, On-Site, Off-Rent, Inspected).
	- `Reserved`
- EventTimestamp
	- The precise date and time the system recorded the status change.
	- `2026-03-19 00:00:00`

### `generate_financials.py`
Processes the rental contracts to calculate complex accounting logic, outputting monthly amortized revenue recognition and tiered sales commissions into General Ledger tables.
Processes the raw rental timelines to calculate complex accounting logic, outputting monthly amortized revenue and tiered sales commissions based on billable days. _Generated Tables & Columns:_ `GeneralLedger` (TransactionID, ContractID, Date, Account, Debit, Credit) and `Commissions` (CommissionID, ContractID, SalesRep, PeriodEnding, CommissionRate, Amount).

### Tables
#### GeneralLedger
- TransactionID
	- Unique primary key for the double-entry accounting record.
	- `273c3eaf-ec8a-4705-8b95-182443a757af`
- ContractID
	- Foreign key linking the revenue back to the specific rental agreement.
	- `sdv-id-NSZqBz`
- Date
	- The date the revenue is officially recognized (usually the last day of the month or the return date).
	- `2026-02-28 00:00:00`
- Account
	- The financial bucket being impacted (e.g., 1100-Accounts Receivable, 4000-Rental Revenue).
	- `1100-Accounts Receivable`
- Debit
	- An accounting entry that increases an asset (like Accounts Receivable) or decreases a liability.
	- `14674`
- Credit
	- An accounting entry that increases a liability or recognizes earned revenue.
	- `0`

#### **Commissions** (Gold Financial Layer)
- CommissionID
	- Unique primary key for the payout record.
	- `c1cbb89f-b22f-4de8-95c9-dc4b29ace9de`
- ContractID
	- Foreign key linking the payout to the rental agreement.
	- `sdv-id-NSZqBz`
- SalesRep
	- The employee receiving the compensation.
	- `James (Katy)`
- PeriodEnding
	- The final date of the billing cycle that generated this specific payout.
	- `2026-02-28 00:00:00`
- CommissionRate
	- The tiered percentage applied to the revenue (5% for the first 30 days, 2% residual thereafter).
	- `0.05`
- Amount
	- The final dollar amount owed to the sales representative for that period.
	- `233.7`
---

### `etl_pipeline.py`


-------------                    |
