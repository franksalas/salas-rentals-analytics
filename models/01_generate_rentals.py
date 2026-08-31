import pandas as pd
from sdv.metadata import MultiTableMetadata
from sdv.multi_table import HMASynthesizer
import sqlite3

def create_rental_seed_data():
    """Create a seed dataset tailored to Salas Rentals (Heavy Equipment in Houston)."""
    equipment = pd.DataFrame({
        'EquipmentID': ['EQ-101', 'EQ-102', 'EQ-103', 'EQ-104', 'EQ-105'],
        'Description': [
            'Caterpillar 320 Excavator', 
            'Bobcat T76 Skid Steer', 
            '8x24 Steel Trench Shield', 
            '1" Steel Road Plate 8x10',
            'JCB 509-42 Telehandler'
        ],
        'DailyRate': [450.00, 250.00, 125.00, 15.00, 350.00],
        'ReplacementCost': [150000.00, 65000.00, 8500.00, 1200.00, 95000.00],
        'AssetCategory': ['Earthmoving', 'Earthmoving', 'Trench Safety', 'Plates', 'Material Handling']
    })

    contracts = pd.DataFrame({
        'ContractID': ['RC-001', 'RC-002', 'RC-003', 'RC-004'],
        'CustomerID': ['CUST-88', 'CUST-92', 'CUST-88', 'CUST-15'],
        'OutDate': pd.to_datetime(['2025-10-01', '2025-10-15', '2026-01-10', '2026-03-22']),
        'ExpectedReturnDate': pd.to_datetime(['2025-10-15', '2025-11-15', '2026-02-10', '2026-04-22']),
        'ActualReturnDate': pd.to_datetime(['2025-10-14', '2025-11-20', None, None]),
        'Status': ['Returned', 'Returned', 'On-Rent', 'Overdue']
    })

    contract_lines = pd.DataFrame({
        'LineID': ['L-1', 'L-2', 'L-3', 'L-4', 'L-5'],
        'ContractID': ['RC-001', 'RC-001', 'RC-002', 'RC-003', 'RC-004'],
        'EquipmentID': ['EQ-101', 'EQ-102', 'EQ-103', 'EQ-101', 'EQ-104'],
        'Quantity': [1, 2, 10, 1, 4]
    })

    return {'Equipment': equipment, 'Contracts': contracts, 'ContractLines': contract_lines}

def generate_sdv_data():
    seed_data = create_rental_seed_data()
    
    print("1. Defining Metadata and Relationships...")
    metadata = MultiTableMetadata()
    metadata.detect_from_dataframes(seed_data)
    
    # 1. Force key columns to be 'id' type
    metadata.update_column(table_name='Equipment', column_name='EquipmentID', sdtype='id')
    metadata.update_column(table_name='Contracts', column_name='ContractID', sdtype='id')
    metadata.update_column(table_name='ContractLines', column_name='LineID', sdtype='id')
    
    # Ensure foreign keys are treated as IDs
    metadata.update_column(table_name='ContractLines', column_name='ContractID', sdtype='id')
    metadata.update_column(table_name='ContractLines', column_name='EquipmentID', sdtype='id')
    metadata.update_column(table_name='Contracts', column_name='CustomerID', sdtype='id')
    
    # 2. Define Primary Keys
    metadata.set_primary_key(table_name='Equipment', column_name='EquipmentID')
    metadata.set_primary_key(table_name='Contracts', column_name='ContractID')
    metadata.set_primary_key(table_name='ContractLines', column_name='LineID')
    
    # 3. Define Foreign Keys
    metadata.add_relationship(
        parent_table_name='Contracts',
        child_table_name='ContractLines',
        parent_primary_key='ContractID',
        child_foreign_key='ContractID'
    )
    metadata.add_relationship(
        parent_table_name='Equipment',
        child_table_name='ContractLines',
        parent_primary_key='EquipmentID',
        child_foreign_key='EquipmentID'
    )

    print("2. Training the SDV Synthesizer...")
    synthesizer = HMASynthesizer(metadata)
    synthesizer.fit(seed_data)
    
    print("3. Generating Synthetic Rental Data at Scale...")
    synthetic_data = synthesizer.sample(scale=100) # Increased scale for more robust data
    
    print("4. Saving to SQLite Database...")
    with sqlite3.connect('salas_rentals_system.db') as conn:
        for table_name, df in synthetic_data.items():
            df.to_sql(table_name, conn, if_exists='replace', index=False)
            print(f" - Saved {len(df)} rows to {table_name}")

if __name__ == '__main__':
    generate_sdv_data()