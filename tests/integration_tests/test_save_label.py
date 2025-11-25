import httpx
import pytest
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

from tests.integration_tests.test_app import PHOTO_PATH, SHIPOWNER, URL

URL_SAVE_LABEL = "http://localhost:8000/save-label/"
URL_DELETE_LABEL = "http://localhost:8000/delete-label/"


@pytest.fixture
def labels_data():
    return [
        {
            "lokalizacja": "FB3N",
            "komponent": "PANEL",
            "rodzaj naprawy": "Straighten",
            "uszkodzenie": "Dent",
            "dlugosc": None,
            "szerokosc": None,
            "ilosc": 2,
            "godziny": "0.00",
            "material": "0.00",
            "wartosc": "0.00",
        },
        {
            "lokalizacja": "DB3N",
            "komponent": "HANDLE RETAINER",
            "rodzaj naprawy": "Straighten",
            "uszkodzenie": "Bent",
            "dlugosc": None,
            "szerokosc": None,
            "ilosc": 1,
            "godziny": "0.00",
            "material": "0.00",
            "wartosc": "0.00",
        },
        {
            "lokalizacja": "DB2N",
            "komponent": "HANDLE OT",
            "rodzaj naprawy": "Straighten",
            "uszkodzenie": "Bent",
            "dlugosc": None,
            "szerokosc": None,
            "ilosc": 1,
            "godziny": "0.25",
            "material": "0.00",
            "wartosc": "4.75",
        },
    ]

@pytest.mark.asyncio
async def test_save_and_delete_label(labels_data):
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
        response = httpx.post(URL, files=files, timeout=60.0)

    assert response.status_code == 200
    response = response.json()

    pipeline_id = response["pipeline_id"]

    response = httpx.post(URL_SAVE_LABEL + pipeline_id, json=labels_data, timeout=30.0)
    assert (
        response.status_code == 200
    ), "Failed to save labels, server responded with an error"
    result = response.json()
    logger.debug(result)
    assert (
        "Labels saved successfully" in result["message"]
    ), "Labels were not saved successfully"
    logger.info("Response from saving labels:", result)
    response = httpx.delete(URL_DELETE_LABEL + pipeline_id)
    assert response.status_code == 200
    assert (
        f"File {pipeline_id}.json deleted successfully." in response.json()["message"]
    )
    await mongodb["row_map_dataset"].delete_many({"pipeline_timestamp": pipeline_id})
    await mongodb["reports"].delete_one({"pipeline_timestamp": pipeline_id})


