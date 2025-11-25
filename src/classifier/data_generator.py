import os
import pandas as pd
import json

from src.config import get_project_root
from src.parser.ocr import OCRWorkflow
from PIL import Image
from loguru import logger

from src.parser.utils import move_report_from_tests_to_logs


class DataGeneratorWorkflow:
    def __init__(self, shipowner: str, container_type: str, num_iterations=None):
        self.shipowner = shipowner
        self.container_type = container_type
        self.base_path = os.path.join(
            get_project_root(), "data", shipowner, container_type
        )
        self.input_reports_dir = os.path.join(self.base_path, "reports_1")
        self.dataset_path = os.path.join(self.base_path, "row_map_dataset.csv")
        self.metadata_path = os.path.join(self.base_path, "metadata_reports_1.json")
        self.processed_rows_dir = os.path.join(self.base_path, "logs/processed_rows")
        self.num_iterations = num_iterations
        self.metadata = self.load_metadata()
        self.dataset_df = self.load_or_initialize_dataset()
        self.reports_dest_dir = os.path.join(self.base_path, "logs/reports")
        logger.info("DataGeneratorWorkflow initialized.")

    def load_metadata(self):
        with open(self.metadata_path, "r") as file:
            metadata = json.load(file)
        self.df = pd.json_normalize(metadata, "naprawy", ["nr kontenera", "zdjecia"])
        self.df.columns = [
            "location",
            "component",
            "repair_type",
            "damage",
            "length",
            "width",
            "quantity",
            "hours",
            "material_cost",
            "value",
            "containerNo",
            "images",
        ]
        logger.info("Metadata loaded")
        return metadata

    def load_or_initialize_dataset(self):
        if os.path.exists(self.dataset_path):
            df = pd.read_csv(self.dataset_path)
            logger.info("Dataset loaded from existing file")
        else:
            df = pd.DataFrame(
                columns=[
                    "source_image",
                    "destination_image",
                    "processed_row",
                    "report_name",
                    "code",
                    "metadata",
                    "label",
                ]
            )
            logger.info("No existing dataset found, initializing new dataset")
        return df

    def update_dataset(self, data_row):
        self.dataset_df = self.dataset_df._append(data_row, ignore_index=True)
        self.dataset_df.to_csv(self.dataset_path, index=False)
        logger.info("Dataset updated and saved")

    def process_reports(self):
        reports = os.listdir(self.input_reports_dir)
        processed_reports = set(self.dataset_df["report_name"].unique())
        iterations = 0

        logger.info("Starting to process reports_1")
        for report in reports:
            if self.num_iterations and iterations >= self.num_iterations:
                logger.info(
                    f"Reached maximum number of iterations: {self.num_iterations}"
                )
                break
            if report not in processed_reports:
                iterations += 1
                logger.info(f"Processing report: {report}")
                self.process_single_report(report)

    def process_single_report(self, report_name):
        move_report_from_tests_to_logs(
            report_name,
            self.shipowner,
            self.container_type,
            os.path.join(self.shipowner, self.container_type, "data/reports_1/"),
        )
        workflow = OCRWorkflow(report_name)
        response = workflow.detect_text()
        pipeline_id = workflow.run_ocr_pipeline(response)

        # Extract and process the saved images with recognized codes
        processed_images = os.listdir(self.processed_rows_dir)
        for image_file in processed_images:
            if pipeline_id in image_file:
                code = image_file.split("-")[-1].split(".")[
                    0
                ]  # Extracting code from filename
                logger.info(f"Processing code: {code} in file: {image_file}")
                df_entries = self.filter_relevant_metadata(code, report_name)
                if df_entries.empty:
                    logger.warning(
                        f"No matching metadata record found for code: {code}"
                    )
                    data_row = {
                        "source_image": os.path.join(
                            self.input_reports_dir, report_name
                        ),
                        "destination_image": os.path.join(
                            self.reports_dest_dir, pipeline_id + "-" + report_name
                        ),
                        "processed_row": os.path.join(
                            self.processed_rows_dir, image_file
                        ),
                        "report_name": report_name,
                        "code": code,
                        "metadata": None,
                        "label": None,
                    }
                    self.update_dataset(data_row)
                    # self.display_image(data_row["processed_row"])

                for _, entry in df_entries.iterrows():
                    data_row = {
                        "source_image": os.path.join(
                            self.input_reports_dir, report_name
                        ),
                        "destination_image": os.path.join(
                            self.reports_dest_dir, pipeline_id + "-" + report_name
                        ),
                        "processed_row": os.path.join(
                            self.processed_rows_dir, image_file
                        ),
                        "report_name": report_name,
                        "code": code,
                        "metadata": entry.to_json(),
                        "label": 1,
                    }
                    self.update_dataset(data_row)
                    # self.display_image(data_row["processed_row"])

        # No code on the whole report recognized case
        data_row = {
            "source_image": os.path.join(self.input_reports_dir, report_name),
            "destination_image": os.path.join(
                self.reports_dest_dir, pipeline_id + "-" + report_name
            ),
            "processed_row": None,
            "report_name": report_name,
            "code": None,
            "metadata": None,
            "label": None,
        }
        self.update_dataset(data_row)

        os.remove(os.path.join(self.reports_dest_dir, report_name))

    def filter_relevant_metadata(self, code, report_name):
        filtered_df = self.df[
            (self.df["location"] == code)
            & (self.df["images"].apply(lambda x: report_name in x))
        ]
        return filtered_df

    def display_image(self, image_path):
        img = Image.open(image_path)
        img.show()  # Adjust if necessary for your environment
        logger.info(f"Displaying image: {image_path}")


if __name__ == "__main__":
    workflow = DataGeneratorWorkflow(
        shipowner="cma", container_type="rf", num_iterations=1000
    )
    workflow.process_reports()

    # workflow.display_image("../../logs/processed_rows/20240715205744982-APZU3809390_306327_20220808_1304158658810559891262153-DB3N.png")
