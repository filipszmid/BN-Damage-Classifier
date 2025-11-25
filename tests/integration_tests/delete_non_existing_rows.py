import os
import pandas as pd
from loguru import logger

def check_paths(csv_path):
    try:
        # Load the data
        data = pd.read_csv(csv_path)
        if 'processed_row' not in data.columns:
            logger.warning("Column 'processed_row' does not exist in the CSV.")
            return

        # Initialize a list to store indices of rows with non-existent paths
        indices_to_drop = []
        paths_to_consider = []

        # Log all non-existent paths first
        for index, path in data['processed_row'].items():
            if isinstance(path, str) and not os.path.exists(path):
                logger.warning(f"Path does not exist: {path}")
                paths_to_consider.append((index, path))

        # Ask user if they want to delete these non-existent paths
        for index, path in paths_to_consider:
            response = input(f"Do you want to delete the record with the non-existing path '{path}'? [y/n]: ")
            if response.lower() == 'y':
                indices_to_drop.append(index)

        # Drop the selected rows and save the updated DataFrame
        if indices_to_drop:
            updated_data = data.drop(indices_to_drop)
            updated_data.to_csv(csv_path, index=False)
            logger.info(f"Updated CSV saved. Removed {len(indices_to_drop)} records.")

    except FileNotFoundError:
        logger.error(f"File not found: {csv_path}")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}")

if __name__ == "__main__":
    csv_path = "../../data/cma/row_map_dataset.csv"
    check_paths(csv_path)
