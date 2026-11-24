"""Application document checklist and account-scoped, transient checks."""

from datetime import datetime, timedelta, timezone

from anyio import CapacityLimiter, WouldBlock, fail_after
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from pymongo.errors import PyMongoError
from starlette.concurrency import run_in_threadpool
from starlette.requests import ClientDisconnect

from ..schemas.document_checks import DocumentCheckRequest, DocumentLanguage, DocumentType
from ..schemas.document_resolution import ResolutionRequest
from ..services import account_profile_service, auth_service, document_storage
from ..services.document_checker import CHECKLISTS, check_documents, preparation_items
from ..services.document_extraction import (
    CONTENT_TYPES, FIELDS_BY_TYPE, MAX_UPLOAD_BYTES, InvalidUpload, OCRUnavailable,
    extract_document, validate_upload,
)
from ..services.document_catalogue import DOCUMENT_TYPES
from ..services.document_resolution import InvalidMismatch, build_resolution
from ..services.scheme_service import SchemeNotFound
from .auth_routes import _handle_auth_error, _require_user_id
from .routes import repository


class EvidenceRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request: Request):
            try:
                return await handler(request)
            except RequestValidationError as exc:
                raise HTTPException(
                    status_code=422,
                    detail="Check document types, field formats, page numbers, and processing consent.",
                ) from exc

        return safe_handler


router = APIRouter(route_class=EvidenceRoute, tags=["document checks"])
_extraction_slot = CapacityLimiter(1)


def _catalogue_scheme(scheme_id: str):
    try:
        scheme = repository.get(scheme_id)
    except SchemeNotFound as exc:
        raise HTTPException(status_code=404, detail="Scheme was not found.") from exc
    return scheme


@router.get("/schemes/{scheme_id}/document-checklist")
def document_checklist(scheme_id: str):
    scheme = _catalogue_scheme(scheme_id)
    return {
        "version": f"{scheme.last_checked}.v1",
        "items": preparation_items(scheme),
        "instructions": scheme.documents_required,
        "conditional": scheme.conditional_documents,
        "source": scheme.source_url,
        "required_types": CHECKLISTS.get((scheme_id, str(scheme.last_checked)), ()),
    }


def _saved_profile(user_id):
    try:
        saved = account_profile_service.get_profile(user_id)
    except (auth_service.AuthNotConfigured, PyMongoError) as exc:
        raise _handle_auth_error(exc) from exc
    return dict((saved or {}).get("profile") or {})


@router.post("/document-checks")
@router.post("/schemes/{scheme_id}/document-checks")
def run_document_check(body: DocumentCheckRequest, request: Request, response: Response, scheme_id: str | None = None):
    user_id = _require_user_id(request)
    scheme = _catalogue_scheme(scheme_id) if scheme_id is not None else None
    profile = _saved_profile(user_id)
    household = dict(profile.get("household") or {})
    if household.get("household_annual_income") is None:
        household["household_annual_income"] = household.get("family_income")
    profile["household"] = household
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    response.headers["Cache-Control"] = "no-store"
    items = preparation_items(scheme) if scheme else []
    if body.preparation.keys() - {item["id"] for item in items}:
        raise HTTPException(409, "The checklist changed. Reload the scheme before continuing.")
    report = check_documents(scheme, body.documents, profile, today, compare_unconfirmed=body.compare_unconfirmed)
    report["preparation"] = [{**item, "answer": body.preparation.get(item["id"], "unsure")} for item in items]
    return report


async def _read_upload(request):
    if request.headers.get("X-Document-Consent") != "true":
        raise HTTPException(status_code=422, detail="Consent is required to process the file.")
    content_type = request.headers.get("content-type", "").partition(";")[0].strip().lower()
    if content_type not in CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Upload a PDF, PNG, or JPEG.")
    data = bytearray()
    try:
        with fail_after(30):
            async for chunk in request.stream():
                if len(data) + len(chunk) > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Upload a file up to 8 MB.")
                data.extend(chunk)
    except TimeoutError as exc:
        raise HTTPException(status_code=408, detail="The upload took too long. Try again.") from exc
    except ClientDisconnect as exc:
        raise HTTPException(status_code=400, detail="The upload was interrupted.") from exc
    return bytes(data), content_type


async def _process_file(process, *arguments):
    try:
        _extraction_slot.acquire_nowait()
    except WouldBlock as exc:
        raise HTTPException(status_code=429, detail="The reader is busy. Try again in a moment.") from exc
    try:
        return await run_in_threadpool(process, *arguments)
    except InvalidUpload as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OCRUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        _extraction_slot.release()


@router.post("/document-extractions/{document_type}")
@router.post("/schemes/{scheme_id}/document-extractions/{document_type}")
async def extract_uploaded_document(
    document_type: DocumentType, request: Request, response: Response,
    language: DocumentLanguage = "en", scheme_id: str | None = None,
):
    await run_in_threadpool(_require_user_id, request)
    if scheme_id is not None:
        await run_in_threadpool(_catalogue_scheme, scheme_id)
    if document_type not in FIELDS_BY_TYPE:
        raise HTTPException(status_code=422, detail="Select the evidence type before uploading.")
    data, content_type = await _read_upload(request)
    response.headers["Cache-Control"] = "no-store"
    return await _process_file(
        extract_document, data, content_type, document_type, language,
        request.headers.get("X-Cloud-OCR-Consent") == "true",
    )


def _storage_call(operation, *arguments):
    try:
        return operation(*arguments)
    except (document_storage.StorageUnavailable, document_storage.CloudinaryStorageError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except (auth_service.AuthNotConfigured, PyMongoError) as exc:
        raise _handle_auth_error(exc) from exc


def _saved_file(user_id, document_id):
    document = _storage_call(document_storage.get_document, user_id, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Saved document was not found.")
    return document


@router.get("/document-types")
def available_document_types():
    return DOCUMENT_TYPES


@router.get("/saved-documents")
def list_saved_documents(request: Request, response: Response):
    user_id = _require_user_id(request)
    response.headers["Cache-Control"] = "no-store"
    return _storage_call(document_storage.list_documents, user_id)


@router.post("/saved-documents/{document_type}", status_code=201)
async def save_document(
    document_type: str, request: Request, response: Response, language: DocumentLanguage = "auto",
):
    user_id = await run_in_threadpool(_require_user_id, request)
    if document_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail="Choose a document type from the list.")
    if document_type == "aadhaar" and request.headers.get("X-Masked-Aadhaar") != "true":
        raise HTTPException(status_code=422, detail="Only save a masked copy of Aadhaar.")
    data, content_type = await _read_upload(request)
    await _process_file(validate_upload, data, content_type)
    response.headers["Cache-Control"] = "no-store"
    return await run_in_threadpool(
        _storage_call, document_storage.save, user_id, document_type, language, content_type, data,
    )


@router.get("/saved-documents/{document_id}/file")
def download_document(document_id: str, request: Request):
    metadata, data = _saved_file(_require_user_id(request), document_id)
    extension = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpg"}[metadata["content_type"]]
    return Response(data, media_type=metadata["content_type"], headers={
        "Cache-Control": "no-store",
        "Content-Disposition": f'attachment; filename="{metadata["type"]}.{extension}"',
        "X-Content-Type-Options": "nosniff",
    })


@router.delete("/saved-documents/{document_id}", status_code=204)
def delete_saved_document(document_id: str, request: Request):
    user_id = _require_user_id(request)
    if not _storage_call(document_storage.delete_document, user_id, document_id):
        raise HTTPException(status_code=404, detail="Saved document was not found.")
    return Response(status_code=204, headers={"Cache-Control": "no-store"})


@router.post("/saved-document-extractions/{document_id}/{document_type}")
@router.post("/schemes/{scheme_id}/saved-document-extractions/{document_id}/{document_type}")
async def extract_saved_document(
    document_id: str, document_type: DocumentType, request: Request, response: Response,
    language: DocumentLanguage | None = None, scheme_id: str | None = None,
):
    user_id = await run_in_threadpool(_require_user_id, request)
    if scheme_id is not None:
        await run_in_threadpool(_catalogue_scheme, scheme_id)
    if request.headers.get("X-Document-Consent") != "true":
        raise HTTPException(status_code=422, detail="Consent is required to process the file.")
    if document_type not in FIELDS_BY_TYPE:
        raise HTTPException(status_code=422, detail="Select the evidence type before reading the document.")
    metadata, data = await run_in_threadpool(_saved_file, user_id, document_id)
    response.headers["Cache-Control"] = "no-store"
    return await _process_file(
        extract_document, data, metadata["content_type"], document_type, language or metadata["language"],
        request.headers.get("X-Cloud-OCR-Consent") == "true",
    )



@router.post("/document-resolutions")
@router.post("/schemes/{scheme_id}/document-resolutions")
def resolve_document_mismatch(
    body: ResolutionRequest, request: Request, response: Response, scheme_id: str | None = None,
):
    user_id = _require_user_id(request)
    scheme = _catalogue_scheme(scheme_id) if scheme_id is not None else None
    response.headers["Cache-Control"] = "no-store"
    try:
        return build_resolution(body, scheme, _saved_profile(user_id))
    except InvalidMismatch as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/document-resolution-example")
@router.get("/schemes/{scheme_id}/document-resolution-example")
def document_resolution_example(scheme_id: str | None = None):
    """Render a fixed example without reading the user's account or calling AI."""
    scheme = _catalogue_scheme(scheme_id) if scheme_id is not None else None
    sample = ResolutionRequest(
        documents=(
            {"kind": "aadhaar", "value": "2002-05-10"},
            {"kind": "birth", "value": "2002-05-15"},
        ),
        field="date_of_birth",
    )
    return {
        "documents": [
            {"label": DOCUMENT_TYPES[item.kind]["label"], "value": item.value}
            for item in sample.documents
        ],
        "guide": build_resolution(
            sample, scheme, {"location": {"state": "Haryana", "district": "Gurugram"}},
        ),
    }

