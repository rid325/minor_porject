"""Move legacy encrypted document blobs to Cloudinary without changing document IDs."""

from base64 import urlsafe_b64decode, urlsafe_b64encode
from hmac import compare_digest

from cryptography.fernet import InvalidToken
from pymongo.errors import PyMongoError

from backend.app import config  # Load backend/.env for the standalone command.
from backend.app.services.cloudinary_storage import CloudinaryStorage, CloudinaryStorageError
from backend.app.services.document_storage import _cipher, get_database


def migrate(collection, cloud, cipher):
    migrated = failed = 0
    for record in collection.find({"encrypted_file": {"$exists": True}}).batch_size(1):
        asset = f"yojna-documents/{record['_id']}.txt"
        original = record["encrypted_file"]
        try:
            plaintext = cipher.decrypt(original)
            try:
                cloud.put(asset, urlsafe_b64decode(original))
            except CloudinaryStorageError:
                # A prior attempt may have uploaded the asset before updating MongoDB.
                pass
            copy = cipher.decrypt(urlsafe_b64encode(cloud.get(asset)))
            if not compare_digest(plaintext, copy):
                failed += 1
                continue
            result = collection.update_one(
                {"_id": record["_id"], "owner_id": record["owner_id"], "encrypted_file": {"$exists": True}},
                {"$set": {"cloudinary_asset": asset}, "$unset": {"encrypted_file": ""}},
            )
            if result.modified_count:
                migrated += 1
            elif collection.find_one({"_id": record["_id"]}) is None:
                cloud.delete(asset)
        except (CloudinaryStorageError, InvalidToken, PyMongoError):
            failed += 1
    return migrated, failed


def main():
    collection = get_database().saved_documents
    migrated, failed = migrate(collection, CloudinaryStorage(), _cipher())
    remaining = collection.count_documents({"encrypted_file": {"$exists": True}})
    print(f"Migrated: {migrated}. Failed: {failed}. MongoDB file blobs remaining: {remaining}.")
    return int(bool(failed or remaining))


if __name__ == "__main__":
    raise SystemExit(main())
