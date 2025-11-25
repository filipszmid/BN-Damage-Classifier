import os

import pytest

from src.parser.ocr import OCRWorkflow, move_report_from_tests_to_logs

# Constants
REPORT_NAME = "APZU3211393_418675_20231212_0747334299019332773351257.webp"
TESTS_DIR = "tests/integration_tests"
LOGS_DIR = "data/cma/logs"


@pytest.fixture(scope="function")
def setup_and_cleanup():
    """Prepare the environment for tests and clean up specifically by pipeline timestamp after tests."""
    expected_dirs = [
        # "img_annotations",
        "processed_rows",
        # "raw_processed_rows",
        # "report_ocr_boxes",
        # "reports"
    ]
    for subdir in expected_dirs:
        os.makedirs(os.path.join(LOGS_DIR, subdir), exist_ok=True)

    yield
    for subdir in expected_dirs:
        dir_path = os.path.join(LOGS_DIR, subdir)
        for file in os.listdir(dir_path):
            if file.startswith(pipeline_timestamp):
                os.remove(os.path.join(dir_path, file))
    os.remove(os.path.join(LOGS_DIR, "reports", REPORT_NAME))


@pytest.mark.asyncio
async def test_complete_ocr_workflow(setup_and_cleanup):
    """Test OCR workflow from moving the file to processing OCR and checking file creations."""
    from motor.motor_asyncio import AsyncIOMotorClient

    move_report_from_tests_to_logs(REPORT_NAME, "cma")
    mongodb_client = AsyncIOMotorClient("mongodb://localhost:27017")
    mongodb = mongodb_client["image_recognition_db"]
    workflow = OCRWorkflow(mongodb, REPORT_NAME, "cma")
    response = await workflow.detect_text()
    global pipeline_timestamp
    pipeline_timestamp = workflow.run_ocr_pipeline(response)
    expected_dirs = [
        # "img_annotations",
        "processed_rows",
        # "raw_processed_rows",
        # "report_ocr_boxes",
        # "reports"
    ]
    for subdir in expected_dirs:
        full_dir_path = os.path.join(LOGS_DIR, subdir)
        files_with_timestamp = [
            f for f in os.listdir(full_dir_path) if f.startswith(pipeline_timestamp)
        ]
        assert (
            files_with_timestamp
        ), f"No files starting with {pipeline_timestamp} found in {full_dir_path}"
    await mongodb["row_map_dataset"].delete_many({"pipeline_timestamp": pipeline_timestamp})
    await mongodb["reports"].delete_one({"pipeline_timestamp": pipeline_timestamp})