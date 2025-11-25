from bson import ObjectId
from fastapi.encoders import jsonable_encoder

# Custom encoder function
def custom_jsonable_encoder(obj):
    if isinstance(obj, ObjectId):
        return str(obj)
    # Let FastAPI's original encoder handle all other types
    return jsonable_encoder(obj, by_alias=True, exclude_unset=True, exclude_none=True, exclude_defaults=True, custom_encoder={ObjectId: lambda oid: str(oid)})
