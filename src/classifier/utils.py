import json

import pandas as pd
from loguru import logger


def load_json(mappings_path):
    with open(mappings_path, "r") as file:
        return json.load(file)


def merge_and_save_csv(path1: str, path2: str, output_path: str):
    """
    Loads two CSV files, merges them into one DataFrame, and saves the result to disk.

    Args:
    path1 (str): File path to the first CSV file.
    path2 (str): File path to the second CSV file.
    output_path (str): File path where the merged CSV file will be saved.
    """
    df1 = pd.read_csv(path1)
    df2 = pd.read_csv(path2)

    merged_df = pd.concat([df1, df2], ignore_index=True)

    merged_df.to_csv(output_path, index=False)


def aggregate_category_counts(dataset_path: str, output_file: str ="../../data/model/category_count.csv") -> pd.DataFrame:
    """
    Aggregates counts of records for each combination of categorical attributes from a CSV dataset,
    ignoring records with missing or invalid metadata.

    Args:
        dataset_path (str): Path to the CSV file containing the dataset.

    Returns:
        pd.DataFrame: A DataFrame containing the counts for each category combination.
    """
    data = pd.read_csv(dataset_path)

    data = data.dropna(subset=['metadata'])
    data['metadata'] = data['metadata'].apply(json.loads)

    data['location'] = data['metadata'].apply(lambda x: x.get('location', ''))
    data['component'] = data['metadata'].apply(lambda x: x.get('component', ''))
    data['repair_type'] = data['metadata'].apply(lambda x: x.get('repair_type', ''))
    data['damage'] = data['metadata'].apply(lambda x: x.get('damage', ''))

    category_counts = data.groupby(['location', 'component', 'repair_type', 'damage']).size()
    category_counts = category_counts.reset_index(name='counts')
    category_counts.to_csv(output_file, index=False)
    logger.info("Category count:")
    logger.info(category_counts)
    return category_counts


if __name__ == "__main__":
    aggregate_category_counts("../../data/cma/row_map_dataset.csv", "../../tests/category_count.csv")