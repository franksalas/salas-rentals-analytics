import subprocess
import sys
from pathlib import Path

scripts_to_run = [
    # salas_rentals_system.db
    "OLTP/01_generate_rentals.py",
    "OLTP/02_generate_routing_history.py",
    "OLTP/03_generate_financials.py",
    # salas_rentals_data_warehouse.db
    "OLAP/etl_pipeline.py",
]

current_dir = Path(__file__).parent

for script_name in scripts_to_run:
    script_path = current_dir / script_name
    print(f"\n{'='*40}")
    print(f"Running: {script_name}")
    print(f"{'='*40}")

    try:
        # Run the script and wait for it to finish
        subprocess.run([sys.executable, script_path], check=True)
        print(f"Finished: {script_name}")

    except subprocess.CalledProcessError as e:
        print(f"Error: {script_name} failed with exit code {e.returncode}")
    except FileNotFoundError:
        print(f"Error: Could not find {script_name} in {current_dir}")
