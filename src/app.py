import json
import os
from typing import List

from dotenv import load_dotenv
from fastapi import FastAPI, Body
from fastapi import HTTPException, status
from fastapi import UploadFile, File, Form
from fastapi.responses import JSONResponse
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

from src.classifier.inference import ContainerDamageClassifierWorkflow
from src.config import get_project_root
from src.parser.llm_api import RepairRecommenderWorkflow
from src.parser.ocr import OCRWorkflow
from src.schema import LabelInfo, RowMap
from src.utils import custom_jsonable_encoder

load_dotenv()

app = FastAPI()


@app.on_event("startup")
async def startup_db_client():
    app.mongodb_client = AsyncIOMotorClient("mongodb://mongo:27017")
    app.mongodb = app.mongodb_client["image_recognition_db"]


@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongodb_client.close()


@app.get("/row_map")
async def get_row_map():
    """Get the current state of row map database with specific fields. [Debug]"""
    fields_to_include = {
        "pipeline_timestamp": 1,
        "processed_row": 1,
        "gpt_labels": 1,
        "code": 1,
        "user_labels": 1,
        "container_type": 1,
        "shipowner": 1,
    }
    images = (
        await app.mongodb["row_map_dataset"].find({}, fields_to_include).to_list(100)
    )
    return JSONResponse(content=[custom_jsonable_encoder(image) for image in images])


@app.delete("/delete-database", status_code=204)
async def delete_database():
    """Drops database. [Debug only]"""
    await app.mongodb_client.drop_database("image_recognition_db")
    return {"message": "Database deleted successfully"}


@app.post("/create_row_map", response_model=RowMap, status_code=status.HTTP_201_CREATED)
async def create_row_map_record(record: RowMap):
    """Creates a new row map record in database. [Debug only]"""
    new_record = await app.mongodb["row_map_dataset"].insert_one(record.dict())
    created_record = await app.mongodb["row_map_dataset"].find_one(
        {"_id": new_record.inserted_id}
    )
    if created_record is not None:
        return created_record
    raise HTTPException(status_code=400, detail="Error creating record")


@app.get("/")
async def hello_word():
    return {"message": "Welcome Screen"}


@app.post("/read-report/")
async def read_report(
    container_type: str = Form(...),
    shipowner: str = Form(...),
    report: UploadFile = File(...),
) -> JSONResponse:
    """
    Receives a report as a .webp file along with metadata, saves the file, and processes it with OCR followed by a repair recommendation workflow.

    Args:
        container_type (str): Type of the container f.e.: rf, dc.
        shipowner (str): The shipowner (aromator) f.e. cma.
        report (UploadFile): The picture of report in .webp

    Returns:
        JSONResponse: The result of the operation including file storage, OCR processing, and repair recommendations outcomes.
    """
    logger.debug(
        f"Received upload request: Report name: {report.filename}, Container type: {container_type}, Photo filename: {report.filename}"
    )

    if not report.filename.endswith(".webp"):
        return JSONResponse(
            status_code=400,
            content={"message": "Invalid file format, only .webp files are accepted"},
        )

    file_path = os.path.join(
        get_project_root(), "data", shipowner, "logs", "reports", report.filename
    )

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as buffer:
            buffer.write(await report.read())
        logger.info(f"File saved successfully at {file_path}")
    except Exception as e:
        logger.error(f"Failed to save file: {str(e)}")
        return JSONResponse(status_code=500, content={"message": "Failed to save file"})

    try:
        ocr_workflow = OCRWorkflow(
            db=app.mongodb, report_name=report.filename, shipowner=shipowner
        )
        ocr_response = await ocr_workflow.detect_text()
        pipeline_timestamp = ocr_workflow.run_ocr_pipeline(ocr_response)

        llm_workflow = RepairRecommenderWorkflow(
            app.mongodb, report.filename, pipeline_timestamp, shipowner, container_type
        )
        recommendations = llm_workflow.recommend_repairs()

        own_model_workflow = ContainerDamageClassifierWorkflow(
            db= app.mongodb, run_name="run_20240823-014941_grindable", checkpoint_id=6
        )
        own_model_recommendations = own_model_workflow.predict_repairs(llm_workflow.files, pipeline_timestamp)

        os.remove(file_path)
        return JSONResponse(
            status_code=200,
            content={
                "pipeline_id": pipeline_timestamp,
                "recommendations": recommendations,
                "local_model_recommendations": own_model_recommendations,
                "description": f"File '{report.filename}' saved at 'logs/reports/{pipeline_timestamp}-{file_path}'.  Container type: {container_type}.",
            },
        )
    except Exception as e:
        logger.error(f"Failed to process workflows: {str(e)}")
        return JSONResponse(
            status_code=500, content={"message": "Workflow processing failed"}
        )


@app.delete("/delete-logs/{shipowner}/{pipeline_id}")
async def delete_logs(shipowner: str, pipeline_id: str) -> JSONResponse:
    """
    Deletes log files based on the provided pipeline ID from all subdirectories within the logs folder.

    Args:
        pipeline_id (str): The pipeline timestamp used as an ID to identify and delete related log files.

    Returns:
        JSONResponse: The result of the deletion process.
    """
    logs_root = os.path.join(get_project_root(), "data", shipowner,  "logs")
    subdirs = [
        # "img_annotations",
        "processed_rows",
        # "raw_processed_rows",
        # "report_ocr_boxes",
        # "reports",
        # "gpt_labels",
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
    labels_dir = os.path.join(project_root, "data", "logs", "user_labels")
    os.makedirs(labels_dir, exist_ok=True)

    file_path = os.path.join(labels_dir, f"{pipeline_id}.json")
    label_dicts = [label.dict(by_alias=True) for label in labels]

    try:
        if os.getenv("VERBOSE") == "1":
            with open(file_path, "w", encoding="utf-8") as file:
                json.dump(label_dicts, file, ensure_ascii=False, indent=4)

        labels_dict = dict()
        for elem in labels:
            elem_d = elem.dict()
            labels_dict[elem_d["localisation"]] = elem_d

        for key in labels_dict.keys():
            # TODO: Edge case when the recognized code is different than real user code
            # TODO: It assumes on one record the location code is unique for a given damage
            app.mongodb["row_map_dataset"].update_one(
                {"pipeline_timestamp": pipeline_id, "code": key},
                {"$set": {"user_label": labels_dict[key]}},
            )
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
    delete_result = await app.mongodb["row_map_dataset"].delete_one({"pipeline_timestamp": pipeline_id})
    if delete_result.deleted_count == 1:
        return JSONResponse(
            status_code=200,
            content={"message": f"File {pipeline_id}.json deleted successfully."},
        )
    else:
        return JSONResponse(
            status_code=500, content={"message": "Failed to delete label"}
        )
