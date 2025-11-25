from pydantic import BaseModel


class LabelInfo(BaseModel):
    localisation: str
    component: str | None
    repair_type: str | None
    damage: str | None
    length: float | None
    width: float | None
    quantity: int | None
    hours: str | None
    material: str | None
    cost: str | None


class RowMap(BaseModel):
    pipeline_timestamp: str
    shipowner: str | None
    container_type: str | None
    destination_image: str | None
    processed_row: str | None
    processed_row_blob: bytes | None
    report_name: str | None
    report_in_db_id: str | None
    code: str | None
    user_label: dict | None
    img_annotation: str | None
    gpt_label: str | None

class Report(BaseModel):
    pipeline_timestamp: str
    report_blob: bytes | None
    report_name: str | None
    shipowner: str | None
