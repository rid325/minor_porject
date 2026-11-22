"""Encrypted per-account application document storage."""

from datetime import datetime, timezone
from base64 import urlsafe_b64decode, urlsafe_b64encode
import os
from contextlib import suppress

from bson import ObjectId
from bson.errors import InvalidId
from cryptography.fernet import Fernet, InvalidToken
from pymongo.errors import PyMongoError

from .auth_service import get_database
from .document_catalogue import DOCUMENT_TYPES
from .cloudinary_storage import CloudinaryStorage, CloudinaryStorageError


class StorageUnavailable(RuntimeError):
    pass


def _cipher():
    try:
        return Fernet(os.environ["DOCUMENT_STORAGE_KEY"].strip().encode("ascii"))
    except (KeyError, ValueError, UnicodeError) as exc:
        raise StorageUnavailable("Saved documents require a configured storage encryption key.") from exc


def _metadata(record):
    return {
        "id": str(record["_id"]),
        "type": record["type"],
        **DOCUMENT_TYPES[record["type"]],
        "language": record["language"],
        "content_type": record["content_type"],
        "created_at": record["created_at"],
    }


def save(owner_id, document_type, language, content_type, data):
    record = {
        "_id": ObjectId(),
        "owner_id": owner_id,
        "type": document_type,
        "language": language,
        "content_type": content_type,
        "created_at": datetime.now(timezone.utc),
    }
    encrypted = _cipher().encrypt(data)
    collection = get_database().saved_documents
    if os.getenv("CLOUDINARY_URL", "").strip() or os.getenv("DOCUMENT_STORAGE_PROVIDER") == "cloudinary":
        cloud = CloudinaryStorage()
        asset = f"yojna-documents/{record['_id']}.txt"
        # Decode the Fernet token's transport encoding to fit Cloudinary's file limit.
        cloud.put(asset, urlsafe_b64decode(encrypted))
        record["cloudinary_asset"] = asset
        try:
            collection.insert_one(record)
        except PyMongoError:
            with suppress(PyMongoError, CloudinaryStorageError):
                if collection.find_one({"_id": record["_id"]}) is None:
                    cloud.delete(asset)
            raise
    else:
        record["encrypted_file"] = encrypted
        collection.insert_one(record)
    return _metadata(record)


def list_documents(owner_id):
    records = get_database().saved_documents.find({"owner_id": owner_id}, {"encrypted_file": 0})
    return [_metadata(record) for record in records.sort([("created_at", -1), ("_id", -1)])]


def _owner_filter(owner_id, document_id):
    try:
        return {"_id": ObjectId(document_id), "owner_id": owner_id}
    except InvalidId:
        return None


def get_document(owner_id, document_id):
    query = _owner_filter(owner_id, document_id)
    record = get_database().saved_documents.find_one(query) if query else None
    if record is None:
        return None
    try:
        encrypted = (urlsafe_b64encode(CloudinaryStorage().get(record["cloudinary_asset"]))
                     if "cloudinary_asset" in record else record["encrypted_file"])
        data = _cipher().decrypt(encrypted)
    except InvalidToken as exc:
        raise StorageUnavailable("The saved document could not be decrypted.") from exc
    return _metadata(record), data


def delete_document(owner_id, document_id):
    query = _owner_filter(owner_id, document_id)
    if query is None:
        return False
    collection = get_database().saved_documents
    for _ in range(2):
        record = collection.find_one(query, {"cloudinary_asset": 1})
        if record is None:
            return False
        asset = record.get("cloudinary_asset")
        if asset:
            CloudinaryStorage().delete(asset)
        storage_match = asset if asset else {"$exists": False}
        if collection.delete_one({**query, "cloudinary_asset": storage_match}).deleted_count:
            return True
    raise StorageUnavailable("The saved document changed during deletion. Try again.")
