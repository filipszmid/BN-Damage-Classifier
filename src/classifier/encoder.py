import json
import os
from pathlib import Path
from typing import Dict, Set, Any

import torch
from loguru import logger

from src.classifier.utils import aggregate_category_counts


class DynamicEncoder:
    """
    A class to encode categorical data from JSON into numeric tensors that can be used for machine learning models.

    Attributes:
        location_map (Dict[str, int]): Mapping from location descriptions to unique integers.
        component_map (Dict[str, int]): Mapping from component descriptions to unique integers.
        repair_type_map (Dict[str, int]): Mapping from repair type descriptions to unique integers.
        damage_map (Dict[str, int]): Mapping from damage descriptions to unique integers.
    """

    def __init__(
        self, row_map_dataset_path: str, run_path: str, min_category_count: int = 10
    ):
        """
        Initializes the DynamicEncoder with category mappings extracted from a specified JSON file.

        Args:

        Raises:
            FileNotFoundError: If the JSON file cannot be found.
            json.JSONDecodeError: If the JSON file cannot be decoded.
        """
        self.run_path = run_path
        # Use the aggregate_category_counts to get category counts from the dataset
        category_counts_df = aggregate_category_counts(
            row_map_dataset_path, os.path.join(run_path, "category_counts.csv")
        )
        # Filter the DataFrame to get categories with counts above the threshold
        self.location_map = self._create_mapping(
            category_counts_df, "location", min_category_count
        )
        self.component_map = self._create_mapping(
            category_counts_df, "component", min_category_count
        )
        self.repair_type_map = self._create_mapping(
            category_counts_df, "repair_type", min_category_count
        )
        self.damage_map = self._create_mapping(
            category_counts_df, "damage", min_category_count
        )

    def _create_mapping(self, category_counts_df, category_name, min_count):
        """
        Creates a mapping from category descriptions to unique integers.

        Args:
            data (Any): The loaded JSON data containing category information.
            key (str): The key to extract values for creating mappings.

        Returns:
            Dict[str, int]: A dictionary mapping category descriptions to unique integers.
        """
        logger.info("Creating mappings..")
        filtered_categories = category_counts_df[
            category_counts_df["counts"] >= min_count
        ]
        unique_values = filtered_categories[category_name].unique()
        return {value: idx for idx, value in enumerate(sorted(unique_values))}

    def encode(
        self, location: str, component: str, repair_type: str, damage: str
    ) -> tuple:
        """
        Encodes the given category values into tensors based on predefined mappings.

        Args:
            location (str): The location description to encode.
            component (str): The component description to encode.
            repair_type (str): The repair type description to encode.
            damage (str): The damage description to encode.

        Returns:
            tuple: A tuple containing tensors for each category.
        """
        location_tensor = torch.tensor(
            [self.location_map.get(location, -1)], dtype=torch.long
        )
        component_tensor = torch.tensor(
            [self.component_map.get(component, -1)], dtype=torch.long
        )
        repair_type_tensor = torch.tensor(
            [self.repair_type_map.get(repair_type, -1)], dtype=torch.long
        )
        damage_tensor = torch.tensor(
            [self.damage_map.get(damage, -1)], dtype=torch.long
        )
        return (location_tensor, component_tensor, repair_type_tensor, damage_tensor)

    def save_mappings(self) -> None:
        """
        Saves the current mappings to a JSON file at the specified path.

        Args:
            path (str): The file path to save the mappings.
        """
        mappings = {
            "location": {v: k for k, v in self.location_map.items()},
            "component": {v: k for k, v in self.component_map.items()},
            "repair_type": {v: k for k, v in self.repair_type_map.items()},
            "damage": {v: k for k, v in self.damage_map.items()},
        }
        with open(os.path.join(self.run_path, "mappings.json"), "w") as f:
            json.dump(mappings, f, indent=4)


if __name__ == "__main__":
    # "../../data/metadata_reports_1.json"
    # run folder need to exist
    encoder = DynamicEncoder("../../data/cma/row_map_dataset.csv", "../../tests/test_run", 10)
    encoder.save_mappings()
