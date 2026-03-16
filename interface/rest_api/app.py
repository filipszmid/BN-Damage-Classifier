from typing import List

from fastapi import FastAPI, Body, Form, File, UploadFile, HTTPException, status
from fastapi.responses import JSONResponse

from src.router import (
    get_db_client,
    fetch_row_map,
    drop_database,
    create_row_map_record,
    process_report,
    delete_logs,
    save_label_to_db,
    delete_label_from_db
)
from src.schema import RowMap, LabelInfo

app = FastAPI(root_path="/api")

@app.on_event("startup")
async def startup_db_client():
    app.mongodb_client, app.mongodb = await get_db_client()

@app.on_event("shutdown")
async def shutdown_db_client():
    app.mongodb_client.close()

@app.get("/row_map")
async def get_row_map():
    images = await fetch_row_map(app.mongodb)
    return JSONResponse(content=images)

# @app.delete("/delete-database", status_code=204)
# async def delete_database_route():
#     resp = await drop_database(app.mongodb_client)
#     return JSONResponse(content=resp)

@app.post("/create_row_map", response_model=RowMap, status_code=status.HTTP_201_CREATED)
async def create_row_map_route(record: RowMap):
    try:
        created = await create_row_map_record(app.mongodb, record)
        return created
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/")
async def hello_word():
    return {"message": "Welcome Screen"}

@app.post("/read-report/")
async def read_report(
    container_type: str = Form(...),
    shipowner: str = Form(...),
    report: UploadFile = File(...)
) -> JSONResponse:
    try:
        file_bytes = await report.read()
        result = await process_report(
            db=app.mongodb,
            container_type=container_type,
            shipowner=shipowner,
            filename=report.filename,
            file_bytes=file_bytes
        )
        return JSONResponse(status_code=200, content=result)
    except ValueError as ve:
        return JSONResponse(status_code=400, content={"message": str(ve)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

@app.delete("/delete-logs/{shipowner}/{pipeline_id}")
async def delete_logs_route(shipowner: str, pipeline_id: str) -> JSONResponse:
    try:
        result = await delete_logs(shipowner, pipeline_id)
        status_code = result.pop("status", 200)
        return JSONResponse(status_code=status_code, content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

@app.post("/save-label/{pipeline_id}")
async def save_label(pipeline_id: str, labels: List[LabelInfo] = Body(...)) -> JSONResponse:
    try:
        result = await save_label_to_db(app.mongodb, pipeline_id, labels)
        return JSONResponse(status_code=200, content=result)
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})

@app.delete("/delete-label/{pipeline_id}")
async def delete_label(pipeline_id: str) -> JSONResponse:
    try:
        result = await delete_label_from_db(app.mongodb, pipeline_id)
        return JSONResponse(status_code=200, content=result)
    except ValueError as ve:
        return JSONResponse(status_code=500, content={"message": str(ve)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"message": str(e)})
