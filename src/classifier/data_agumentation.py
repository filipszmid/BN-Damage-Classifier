import json
import os
from typing import List, Tuple

import cv2
import numpy as np
import pandas as pd
from loguru import logger

from src.classifier.utils import aggregate_category_counts

TRANSFORMATIONS: List[Tuple[str, float]] = (
    # Rotations at more varied angles
    [
        ("rotate", deg) for deg in range(-15, 20, 5)
    ]  # Rotating from -15 to 15 degrees at 5-degree intervals
    # Adding horizontal and vertical flips for scenarios where orientation isn't crucial
    # + [("flip", "horizontal"), ("flip", "vertical")]
    # Zoom in and out for different scales
    + [
        ("zoom", scale) for scale in (0.1, 0.2, 0.3, 0.4)
    ]  # Zoom out and zoom in scenarios
    # Grayscale conversion, only needs to be done once if at all
    + [("grayscale", 0)]
    # Brightness and contrast adjustments
    + [
        ("brightness", level) for level in (0.1, 0.2)
    ]  # Adjust brightness down by 20%, up by 20%
    + [
        ("contrast", level) for level in (1.1, 1.8)
    ]  # Adjust contrast down by 20%, up by 20%
    # Adding Gaussian noise for robustness against sensor noise or compression artifacts
    + [("noise", "gaussian")]
    # Elastic deformations for more organic variation
    + [("elastic_deformation", 1)]
)


class DataAugmentationWorkflow:
    """
    A class to handle data augmentation for image datasets, specifically designed
    for augmenting images from a repair dataset with metadata. Augmentations include
    rotations, scaling, and color transformations.
    """

    def __init__(
        self,
        input_csv_path: str,
        output_csv_path: str,
        augmented_folder: str,
        category_count_path: str,
    ):
        self.input_csv_path = input_csv_path
        self.output_csv_path = output_csv_path
        self.augmented_folder = augmented_folder
        self.category_count_path = category_count_path
        self.ensure_directory(self.augmented_folder)

    @staticmethod
    def ensure_directory(path: str):
        """Ensure that the directory exists, create if it doesn't."""
        os.makedirs(path, exist_ok=True)

    def load_data(self) -> pd.DataFrame:
        """Load dataset from the specified CSV path."""
        return pd.read_csv(self.input_csv_path)

    def load_category_counts(self) -> pd.DataFrame:
        """Load category counts to filter eligible categories for augmentation."""
        return pd.read_csv(self.category_count_path)

    def load_augmented_data(self) -> pd.DataFrame:
        """Load already augmented data to avoid reprocessing."""
        if os.path.exists(self.output_csv_path):
            return pd.read_csv(self.output_csv_path)
        else:
            return pd.DataFrame()

    def augment_image(self, img_path: str) -> List[str]:
        """
        Apply various transformations to the image and save the augmented images.
        """
        img = cv2.imread(img_path, cv2.IMREAD_COLOR)
        if img is None:
            raise FileNotFoundError(f"Image {img_path} not found.")

        augmented_images = []
        filename = os.path.basename(img_path)

        for trans_type, param in TRANSFORMATIONS:
            # logger.info(f"Applying transformation: {trans_type} for parameter: {param}")
            transformed_img = img.copy()

            if trans_type == "rotate":
                center = (img.shape[1] // 2, img.shape[0] // 2)
                M = cv2.getRotationMatrix2D(center, param, 1.0)
                transformed_img = cv2.warpAffine(img, M, (img.shape[1], img.shape[0]))
            elif trans_type == "zoom":
                scale = 1 + param
                transformed_img = cv2.resize(
                    img, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR
                )
                crop_x = (transformed_img.shape[1] - 1000) // 2
                crop_y = (transformed_img.shape[0] - 1000) // 2
                transformed_img = transformed_img[
                    crop_y : crop_y + 1000, crop_x : crop_x + 1000
                ]
            elif trans_type == "grayscale":
                transformed_img = cv2.cvtColor(transformed_img, cv2.COLOR_BGR2GRAY)
                transformed_img = cv2.cvtColor(transformed_img, cv2.COLOR_GRAY2BGR)

            elif trans_type == "flip":
                if param == "horizontal":
                    transformed_img = cv2.flip(transformed_img, 1)
                elif param == "vertical":
                    transformed_img = cv2.flip(transformed_img, 0)

            elif trans_type == "brightness":
                transformed_img = cv2.convertScaleAbs(
                    transformed_img, alpha=1, beta=param * 255
                )

            elif trans_type == "contrast":
                transformed_img = cv2.convertScaleAbs(
                    transformed_img, alpha=param, beta=0
                )

            elif trans_type == "noise":
                if param == "gaussian":
                    gauss = np.random.normal(0, 25, transformed_img.size)
                    gauss = gauss.reshape(transformed_img.shape).astype("uint8")
                    transformed_img = cv2.add(transformed_img, gauss)

            new_filename = f"{trans_type}_{param}_" + filename
            new_path = os.path.join(self.augmented_folder, new_filename)
            cv2.imwrite(new_path, transformed_img)
            augmented_images.append(new_path)

        return augmented_images

    def process_augmentation(self, num_rows: int = None):
        """Process the augmentation for selected rows in the dataset and save new CSV."""
        data = self.load_data()
        category_counts = self.load_category_counts()
        augmented_data = self.load_augmented_data()
        eligible_categories = category_counts[category_counts["counts"] < 40][
            ["location", "component", "repair_type", "damage"]
        ]

        processed_paths = (
            set(augmented_data["source_processed_row"].tolist())
            if not augmented_data.empty
            else set()
        )
        data = data.dropna(subset=["metadata"])

        # Filter eligible rows from data based on the eligible categories
        eligible_data = data[
            data.apply(
                lambda row: {
                    "location": json.loads(row["metadata"]).get("location"),
                    "component": json.loads(row["metadata"]).get("component"),
                    "repair_type": json.loads(row["metadata"]).get("repair_type"),
                    "damage": json.loads(row["metadata"]).get("damage"),
                }
                in eligible_categories.to_dict("records"),
                axis=1,
            )
        ]

        augmented_rows = []
        augmentation_count = 0

        for _, row in eligible_data.iterrows():
            if row["processed_row"] not in processed_paths:
                processed_image_path = row["processed_row"]
                try:
                    new_image_paths = self.augment_image(processed_image_path)
                    for new_path in new_image_paths:
                        new_row = row.copy()
                        new_row["source_processed_row"] = row["processed_row"]
                        new_row["processed_row"] = new_path
                        # logger.info(f"Processing{new_path}")
                        augmented_rows.append(new_row)
                        processed_paths.add(new_path)
                    augmentation_count += 1
                    if num_rows is not None and augmentation_count >= num_rows:
                        break  # Stop processing after 10 new augmentations
                except FileNotFoundError:
                    logger.error("File Not found.")
                    continue  # Skip files that are not found

        augmented_df = pd.DataFrame(augmented_rows)
        if not augmented_df.empty:
            final_df = pd.concat([augmented_data, augmented_df])
            final_df.to_csv(self.output_csv_path, index=False)


if __name__ == "__main__":
    workflow = DataAugmentationWorkflow(
        input_csv_path="../../data/cma/row_map_dataset.csv",
        output_csv_path="../../tests/row_map_dataset_with_augmentation.csv",
        augmented_folder="../../tests/reports_1_augmentation",
        category_count_path="../../tests/category_count.csv",
    )
    workflow.process_augmentation(num_rows=None)
    category_counts = aggregate_category_counts(
        "../../data/row_map_dataset_with_augmentation.csv",
        "../../data/cma/rf/model/category_count_agumentation.csv",
    )
