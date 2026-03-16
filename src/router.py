import json
import os
from typing import List, Dict, Any

from dotenv import load_dotenv
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

from src.classifier.inference import ContainerDamageClassifierWorkflow
from src.config import get_project_root
from src.parser.llm_api import RepairRecommenderWorkflow
from src.parser.ocr import OCRWorkflow
from src.schema import LabelInfo, RowMap
from src.utils import custom_jsonable_encoder

load_dotenv()

async def get_db_client():
    mongo_uri = os.getenv("MONGO_URI", "mongodb://mongo:27017")
    client = AsyncIOMotorClient(mongo_uri)
    return client, client["image_recognition_db"]

async def fetch_row_map(db) -> List[Dict]:
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
    images = await db["row_map_dataset"].find({}, fields_to_include).to_list(100)
    return [custom_jsonable_encoder(image) for image in images]

async def drop_database(client):
    """Drops database. [Debug only]"""
    await client.drop_database("image_recognition_db")
    return {"message": "Database deleted successfully"}

async def create_row_map_record(db, record: RowMap):
    """Creates a new row map record in database. [Debug only]"""
    new_record = await db["row_map_dataset"].insert_one(record.dict())
    created_record = await db["row_map_dataset"].find_one({"_id": new_record.inserted_id})
    if created_record is not None:
        return created_record
    raise ValueError("Error creating record")

async def process_report(
    db,
    container_type: str,
    shipowner: str,
    filename: str,
    file_bytes: bytes,
) -> Dict[str, Any]:
    """
    Receives a report as bytes along with metadata, saves the file, and processes it 
    with OCR followed by a repair recommendation workflow.
    """
    logger.debug(f"Process request: Report name: {filename}, Container type: {container_type}")

    if not filename.endswith(".webp"):
        raise ValueError("Invalid file format, only .webp files are accepted")

    file_path = os.path.join(
        get_project_root(), "data", shipowner, "logs", "reports", filename
    )

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "wb") as buffer:
            buffer.write(file_bytes)
        logger.info(f"File saved successfully at {file_path}")
    except Exception as e:
        logger.error(f"Failed to save file: {str(e)}")
        raise RuntimeError("Failed to save file")

    try:
        ocr_workflow = OCRWorkflow(db=db, report_name=filename, shipowner=shipowner)
        ocr_response = await ocr_workflow.detect_text()
        pipeline_timestamp = ocr_workflow.run_ocr_pipeline(ocr_response)

        llm_workflow = RepairRecommenderWorkflow(
            db, filename, pipeline_timestamp, shipowner, container_type
        )
        recommendations = await llm_workflow.recommend_repairs()

        own_model_workflow = ContainerDamageClassifierWorkflow(
            db=db, run_name="run_20240823-014941_grindable", checkpoint_id=6
        )
        own_model_recommendations = await own_model_workflow.predict_repairs(llm_workflow.files, pipeline_timestamp)

        os.remove(file_path)
        return {
            "pipeline_id": pipeline_timestamp,
            "recommendations": recommendations,
            "local_model_recommendations": own_model_recommendations,
            "description": f"File '{filename}' saved at 'logs/reports/{pipeline_timestamp}-{file_path}'. Container type: {container_type}.",
        }
    except Exception as e:
        logger.error(f"Failed to process workflows: {str(e)}")
        raise RuntimeError(f"Workflow processing failed: {str(e)}")

async def delete_logs(shipowner: str, pipeline_id: str) -> Dict[str, Any]:
    """Deletes log files based on the provided pipeline ID."""
    logs_root = os.path.join(get_project_root(), "data", shipowner, "logs")
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
            # if not os.path.exists(dir_path):
            #     continue
            for file in os.listdir(dir_path):
                if file.startswith(pipeline_id):
                    file_path = os.path.join(dir_path, file)
                    os.remove(file_path)
                    logger.debug(f"Deleted file: {file_path}")
                    deleted_files.append(file_path)

        if not deleted_files:
            return {"status": 404, "message": "No files found with the provided pipeline ID."}

        return {"status": 200, "message": "Files successfully deleted", "deleted_files": deleted_files}
    except Exception as e:
        logger.error(f"Failed to delete files: {str(e)}")
        raise RuntimeError("Failed to delete files")

async def save_label_to_db(db, pipeline_id: str, labels: List[LabelInfo]) -> Dict[str, Any]:
    """Saves a list of label entries to JSON and updates the DB."""
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
            await db["row_map_dataset"].update_one(
                {"pipeline_timestamp": pipeline_id, "code": key},
                {"$set": {"user_label": labels_dict[key]}},
            )
        return {"message": "Labels saved successfully", "file_path": file_path}
    except Exception as e:
        logger.error(f"Failed to save label file: {str(e)}")
        raise RuntimeError("Failed to save label file")

async def delete_label_from_db(db, pipeline_id: str) -> Dict[str, str]:
    """Deletes label by pipeline ID."""
    delete_result = await db["row_map_dataset"].delete_one({"pipeline_timestamp": pipeline_id})
    if delete_result.deleted_count == 1:
        return {"message": f"File {pipeline_id}.json deleted successfully."}
    else:
        raise ValueError("Failed to delete label - not found in database")
