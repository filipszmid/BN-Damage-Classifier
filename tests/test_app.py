import httpx
import pytest
from loguru import logger

URL = "http://localhost:8000/read-report/"
URL_DELETE= "http://localhost:8000/delete-logs/"
PHOTO_PATH = "tests/APZU3211393_418675_20231212_0747334299019332773351257.webp"

def test_upload_photo():
    with open(PHOTO_PATH, 'rb') as f:
        files = {
            "photo": ("APZU3211393_418675_20231212_0747334299019332773351257.webp", f, "image/webp"),
            "report_name": (None, "APZU3211393_418675_20231212_0747334299019332773351257.webp"),
            "container_type": (None, "RF")
        }
        response = httpx.post(URL, files=files, timeout=30.0)

    assert response.status_code == 200
    response = response.json()
    logger.debug(response)
    assert "File" in response['description']
    assert "saved at" in response['description']
    response = httpx.delete(URL_DELETE+response['pipeline_id'])
    assert response.status_code == 200
    logger.debug(response.json())
