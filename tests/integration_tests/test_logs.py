import asyncio

import pytest
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient


@pytest.fixture
async def rows_map_data():
    """Fetches row map data from MongoDB asynchronously."""

    client = AsyncIOMotorClient(
        "mongodb://localhost:27017"
    )
    db = client["image_recognition_db"]
    collection = db["row_map_dataset"]

    cursor = collection.find({}, {"processed_row": 1, "_id": 0})
    data = await cursor.to_list(length=100)  # Adjust length as needed length=100
    # await client.close()  # It's a good practice to close the client
    return data


HOST_PROJECT_ROOT = "/home/lorbi/Desktop/ALL-BAL-CV/BAL-Damage-Classifier"


async def file_exists_in_docker(container_name, path):
    """Asynchronously check if file exists in Docker container."""
    # Strip host-absolute project root so the path becomes the container-mounted path
    # e.g. /home/.../BAL-Damage-Classifier/data/cma/... -> /data/cma/...
    path = path.replace("../../", "")  # legacy normalisation
    path = path.replace(HOST_PROJECT_ROOT, "")
    cmd = f"docker exec {container_name} test -f {path}"

    proc = await asyncio.create_subprocess_shell(
        cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    return proc.returncode == 0


@pytest.mark.asyncio
async def test_processed_rows_are_valid_paths(rows_map_data):
    """Asynchronously test to ensure all entries in 'processed_row' are valid paths inside the Docker container."""
    container_name = "bal-damage-classifier-app-1"
    if not rows_map_data:
        logger.info("No data fetched from MongoDB. Test always pass.")
        return
    for record in rows_map_data:
        logger.info(f"Looking for: {record}")
        if "processed_row" in record:
            path = record["processed_row"]
            exists = await file_exists_in_docker(container_name, path)
            assert exists, f"File does not exist in Docker container at path: {path}"
        else:
            assert False, "Column 'processed_row' does not exist in the fetched data."
