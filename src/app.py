import json
import os
from typing import List

from fastapi import FastAPI, Body
from fastapi import UploadFile, File, Form
from fastapi.responses import JSONResponse
from loguru import logger

from src.config import get_project_root
from src.parser.llm_api import RepairRecommenderWorkflow
from src.parser.ocr import OCRWorkflow
from src.schema import LabelInfo

app = FastAPI()


@app.get("/")
async def hello_word():
    return {"message": "Welcome Screen"}


@app.post("/read-report/")
async def read_report(
    report_name: str = Form(...),
    container_type: str = Form(...),
    photo: UploadFile = File(...),
) -> JSONResponse:
    """
    Receives a report as a .webp file along with metadata, saves the file, and processes it with OCR followed by a repair recommendation workflow.

    Args:
        report_name (str): Name of the report.
        container_type (str): Type of the container.
        photo (UploadFile): The photo file to process.

    Returns:
        JSONResponse: The result of the operation including file storage, OCR processing, and repair recommendations outcomes.
    """
    logger.debug(
        f"Received upload request: Report name: {report_name}, Container type: {container_type}, Photo filename: {photo.filename}"
    )

    if not photo.filename.endswith(".webp"):
        return JSONResponse(
            status_code=400,
            content={"message": "Invalid file format, only .webp files are accepted"},
        )

    file_path = os.path.join(get_project_root(), "logs", "reports", report_name)

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as buffer:
            buffer.write(await photo.read())
        logger.info(f"File saved successfully at {file_path}")
    except Exception as e:
        logger.error(f"Failed to save file: {str(e)}")
        return JSONResponse(status_code=500, content={"message": "Failed to save file"})

    try:
        ocr_workflow = OCRWorkflow(report_name)
        ocr_response = ocr_workflow.detect_text()
        pipeline_timestamp = ocr_workflow.run_ocr_pipeline(ocr_response)

        llm_workflow = RepairRecommenderWorkflow(
            report_name, pipeline_timestamp, container_type
        )
        recommendations = llm_workflow.recommend_repairs()

        return JSONResponse(
            status_code=200,
            content={
                "pipeline_id": pipeline_timestamp,
                "recommendations": recommendations,
                "description": f"File '{photo.filename}' saved at '{file_path}'. Report name: {report_name}, Container type: {container_type}.",
            },
        )
    except Exception as e:
        logger.error(f"Failed to process workflows: {str(e)}")
        return JSONResponse(
            status_code=500, content={"message": "Workflow processing failed"}
        )


@app.delete("/delete-logs/{pipeline_id}")
async def delete_logs(pipeline_id: str) -> JSONResponse:
    """
    Deletes log files based on the provided pipeline ID from all subdirectories within the logs folder.

    Args:
        pipeline_id (str): The pipeline timestamp used as an ID to identify and delete related log files.

    Returns:
        JSONResponse: The result of the deletion process.
    """
    logs_root = os.path.join(get_project_root(), "logs")
    subdirs = [
        "img_annotations",
        "processed_rows",
        "raw_processed_rows",
        "report_ocr_boxes",
        "reports",
        "gpt_labels",
    ]
    deleted_files = []

    try:
        for subdir in subdirs:
            dir_path = os.path.join(logs_root, subdir)
            for file in os.listdir(dir_path):
                if file.startswith(pipeline_id):
                    file_path = os.path.join(dir_path, file)
                    os.remove(file_path)
                    logger.debug(f"Deleted file: {file_path}")
                    deleted_files.append(file_path)

        if not deleted_files:
            return JSONResponse(
                status_code=404,
                content={"message": "No files found with the provided pipeline ID."},
            )

        return JSONResponse(
            status_code=200,
            content={
                "message": "Files successfully deleted",
                "deleted_files": deleted_files,
            },
        )
    except Exception as e:
        logger.error(f"Failed to delete files: {str(e)}")
        return JSONResponse(
            status_code=500, content={"message": "Failed to delete files"}
        )


@app.post("/save-label/{pipeline_id}")
async def save_label(
    pipeline_id: str, labels: List[LabelInfo] = Body(...)
) -> JSONResponse:
    """
    Saves a list of label entries to a JSON file in the logs/user_labels directory using the pipeline ID.
    Each label is an instance of LabelInfo, and the entire list is saved as a JSON array.

    Args:
        pipeline_id (str): A unique identifier for the session or operation, used to name the output file.
        labels (List[LabelInfo]): A list of label data submitted by the user, expected to conform to the LabelInfo model.

    Returns:
        JSONResponse: Information about the operation's success or failure and the path to the saved file.
    """
    project_root = get_project_root()
    labels_dir = os.path.join(project_root, "logs", "user_labels")
    os.makedirs(labels_dir, exist_ok=True)

    file_path = os.path.join(labels_dir, f"{pipeline_id}.json")
    label_dicts = [label.dict(by_alias=True) for label in labels]

    try:
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(label_dicts, file, ensure_ascii=False, indent=4)
        return JSONResponse(
            status_code=200,
            content={"message": "Labels saved successfully", "file_path": file_path},
        )
    except Exception as e:
        logger.error(f"Failed to save label file: {str(e)}")
        return JSONResponse(
            status_code=500, content={"message": "Failed to save label file"}
        )


@app.delete("/delete-label/{pipeline_id}")
async def delete_label(pipeline_id: str) -> JSONResponse:
    """
    Deletes a JSON file in the logs/user_labels directory using the provided pipeline ID.

    Args:
        pipeline_id (str): The pipeline ID corresponding to the file that needs to be deleted.

    Returns:
        JSONResponse: Status of the deletion operation along with a relevant message.
    """
    project_root = get_project_root()
    labels_dir = os.path.join(project_root, "logs", "user_labels")
    file_path = os.path.join(labels_dir, f"{pipeline_id}.json")

    if not os.path.exists(file_path):
        return JSONResponse(status_code=404, content={"detail": "File not found."})

    try:
        os.remove(file_path)
        return JSONResponse(
            status_code=200,
            content={"message": f"File {pipeline_id}.json deleted successfully."},
        )
    except Exception as e:
        logger.error(f"Failed to delete file: {str(e)}")
        return JSONResponse(
            status_code=500, content={"message": "Failed to delete file"}
        )
