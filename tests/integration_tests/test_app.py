import httpx
import pytest
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

URL = "http://localhost/api/read-report/"
URL_DELETE = "http://localhost/api/delete-logs/"
PHOTO_PATH = "tests/APZU3211393_418675_20231212_0747334299019332773351257.webp"
SHIPOWNER = "cma"

@pytest.mark.asyncio
async def test_upload_photo():
    client = AsyncIOMotorClient(
        "mongodb://localhost:27017"
    )
    mongodb = client["image_recognition_db"]
    with open(PHOTO_PATH, "rb") as f:
        files = {
            "report": (
                "APZU3211393_418675_20231212_0747334299019332773351257.webp",
                f,
                "image/webp",
            ),
            "shipowner": (None, SHIPOWNER),
            "container_type": (None, "dc"),
        }
        response = httpx.post(URL, files=files, timeout=260.0)

    assert response.status_code == 200
    response = response.json()
    pipeline_id = response["pipeline_id"]
    logger.debug(response)
    assert "File" in response["description"]
    assert "saved at" in response["description"]
    response = httpx.delete(URL_DELETE + SHIPOWNER + "/" + response["pipeline_id"])
    assert response.status_code == 200
    logger.debug(response.json())
    await mongodb["row_map_dataset"].delete_many({"pipeline_timestamp": pipeline_id})
    await mongodb["reports"].delete_one({"pipeline_timestamp": pipeline_id})

