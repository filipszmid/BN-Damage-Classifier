import os
import pytest
from src.parser.ocr import OCRWorkflow, move_report_from_tests_to_logs

# Constants
REPORT_NAME = "APZU3211393_418675_20231212_0747334299019332773351257.webp"
TESTS_DIR = "tests"
LOGS_DIR = "logs"

@pytest.fixture(scope='function')
def setup_and_cleanup():
    """Prepare the environment for tests and clean up specifically by pipeline timestamp after tests."""
    expected_dirs = [
        "img_annotations",
        "processed_rows",
        "raw_processed_rows",
        "report_ocr_boxes",
        "reports"
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
def test_complete_ocr_workflow(setup_and_cleanup):
    """Test OCR workflow from moving the file to processing OCR and checking file creations."""
    move_report_from_tests_to_logs(REPORT_NAME)

    workflow = OCRWorkflow(REPORT_NAME)
    response = workflow.detect_text()
    global pipeline_timestamp
    pipeline_timestamp = workflow.run_ocr_pipeline(response)
    expected_dirs = [
        "img_annotations",
        "processed_rows",
        "raw_processed_rows",
        "report_ocr_boxes",
        "reports"
    ]
    for subdir in expected_dirs:
        full_dir_path = os.path.join(LOGS_DIR, subdir)
        files_with_timestamp = [f for f in os.listdir(full_dir_path) if f.startswith(pipeline_timestamp)]
        assert files_with_timestamp, f"No files starting with {pipeline_timestamp} found in {full_dir_path}"

