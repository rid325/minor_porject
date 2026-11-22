from datetime import date
from types import SimpleNamespace

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from PIL import Image

from backend.app.api import auth_routes, document_routes
from backend.app.main import app
from backend.app.schemas.document_checks import DocumentEvidence
from backend.app.services import document_extraction, document_storage
from backend.app.services.document_checker import check_documents, name_similarity, normalized_value
from backend.tests.test_document_upload import digital_pdf


def test_multilingual_labels_digits_and_comparisons(monkeypatch):
    text = [
        document_extraction.Line("नाम: अमन कुमार"),
        document_extraction.Line("ਰਾਜ: ਹਰਿਆਣਾ"),
        document_extraction.Line("State: Haryana"),
        document_extraction.Line("ज़िला: अंबाला"),
        document_extraction.Line("ਪਿੰਨ ਕੋਡ: ੧੩੪੦੦੧"),
    ]
    monkeypatch.setattr(document_extraction, "_pages", lambda *args: iter([(1, text, [])]))
    extracted = document_extraction.extract_document(b"", "application/pdf", "residence", "auto")
    assert extracted["display_values"]["state"] == "Haryana"
    assert extracted["display_values"]["district"] == "Ambala"
    assert extracted["display_values"]["pin"] == "134001"
    assert extracted["display_values"]["name"].isascii()
    assert extracted["fields"]["state"].value == "ਹਰਿਆਣਾ"
    profile = {"location": {"state": "Haryana", "district": "Ambala", "pin": "134001"}}
    scheme = document_routes.repository.get("HR-OASA-002")
    report = check_documents(scheme, [
        DocumentEvidence(document_type="residence", fields=extracted["fields"]),
    ], profile, date(2026, 11, 21))
    assert len(report["comparisons"]) == 3
    assert {item["status"] for item in report["comparisons"]} == {"exact_match"}
    assert document_extraction._match_value("date_of_birth", "ਜਨਮ ਮਿਤੀ: ੨੧/੧੧/੧੯੬੬") == "1966-11-21"
    assert document_extraction._match_value("annual_household_income", "वार्षिक पारिवारिक आय: ₹२,००,०००") == "200000"
    assert normalized_value("social_category", "ਅਨੁਸੂਚਿਤ ਜਾਤੀ") == "sc"
    assert name_similarity("aman kumar", normalized_value("name", "ਅਮਨ ਕੁਮਾਰ")) == "likely_match"


def test_mixed_ocr_invokes_local_engine_and_preserves_evidence(monkeypatch):
    def tesseract(command, **options):
        assert command == ["tesseract", "stdin", "stdout", "-l", "eng+hin+pan", "-c", "tessedit_create_tsv=1"]
        assert options["input"].startswith(b"\x89PNG")
        output = (
            "level\tblock_num\tpar_num\tline_num\tleft\ttop\twidth\theight\tconf\ttext\n"
            "5\t1\t1\t1\t10\t20\t40\t15\t92\tਰਾਜ:\n"
            "5\t1\t1\t1\t55\t20\t75\t15\t89\tਪੰਜਾਬ\n"
        )
        return SimpleNamespace(stdout=output.encode(), stderr=b"", returncode=0)

    monkeypatch.setattr(document_extraction.subprocess, "run", tesseract)
    lines = document_extraction._tesseract_lines(Image.new("RGB", (200, 100)), "tesseract", "auto")
    assert document_extraction._match_value("state", lines[0].text) == "ਪੰਜਾਬ"
    assert lines[0].confidence == 0.89
    assert lines[0].box == (10, 20, 130, 35)


class Collection:
    def __init__(self):
        self.records = {}

    def insert_one(self, record):
        self.records[record["_id"]] = record

    def find(self, query, projection):
        assert projection == {"encrypted_file": 0}
        items = [item for item in self.records.values() if item["owner_id"] == query["owner_id"]]
        return SimpleNamespace(sort=lambda order: items)

    def find_one(self, query, projection=None):
        record = self.records.get(query["_id"])
        return record if record and record["owner_id"] == query["owner_id"] else None

    def delete_one(self, query):
        record = self.find_one(query)
        if record:
            del self.records[query["_id"]]
        return SimpleNamespace(deleted_count=int(record is not None))


def test_cloudinary_stores_encrypted_files_and_preserves_legacy_documents(monkeypatch):
    import httpx
    from backend.app.services import cloudinary_storage

    collection = Collection()
    assets = {}
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    monkeypatch.delenv("DOCUMENT_STORAGE_PROVIDER", raising=False)
    monkeypatch.setenv("DOCUMENT_STORAGE_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(document_storage, "get_database", lambda: SimpleNamespace(saved_documents=collection))
    data = digital_pdf("Applicant Name: Sample Student", "Date of Birth: 03/10/2006")
    legacy = document_storage.save("owner", "aadhaar", "en", "application/pdf", data)

    def post(url, *, data, timeout, files=None):
        assert data["type"] == "authenticated"
        assert data["api_key"] == "test-key"
        assert len(data["signature"]) == 64
        asset = data["public_id"]
        if files:
            assert url.endswith("/raw/upload")
            assets[asset] = files["file"][1]
            return httpx.Response(200, request=httpx.Request("POST", url), json={
                "public_id": asset, "resource_type": "raw", "type": "authenticated",
            })
        assert url.endswith("/raw/destroy")
        del assets[asset]
        return httpx.Response(200, request=httpx.Request("POST", url), json={"result": "ok"})

    def get(url, *, params, timeout, follow_redirects):
        assert url.endswith("/raw/download")
        assert params["type"] == "authenticated"
        return httpx.Response(200, request=httpx.Request("GET", url), content=assets[params["public_id"]])

    monkeypatch.setenv("CLOUDINARY_URL", "cloudinary://test-key:test-secret@test-cloud")
    monkeypatch.setattr(cloudinary_storage.httpx, "post", post)
    monkeypatch.setattr(cloudinary_storage.httpx, "get", get)
    saved = document_storage.save("owner", "aadhaar", "en", "application/pdf", data)
    assert data not in next(iter(assets.values()))
    assert all("encrypted_file" not in item for item in collection.records.values() if "cloudinary_asset" in item)
    assert "cloudinary_asset" not in saved
    assert document_storage.get_document("stranger", saved["id"]) is None
    assert document_storage.get_document("owner", saved["id"]) == (saved, data)
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda token: token or None)
    monkeypatch.setattr(document_extraction, "_ocr_lines", lambda *_: [])
    path = "/api/v1/saved-document-extractions/" + saved["id"] + "/identity"
    response = TestClient(app).post(path, headers={"Cookie": "yojna_session=owner", "X-Document-Consent": "true"})
    assert response.status_code == 200
    assert response.json()["fields"]["date_of_birth"]["value"] == "2006-10-03"
    assert document_storage.get_document("owner", legacy["id"]) == (legacy, data)
    assert not document_storage.delete_document("stranger", saved["id"])
    assert document_storage.delete_document("owner", saved["id"])
    assert not assets


def test_saved_library_encrypts_files_and_enforces_ownership(monkeypatch):
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    monkeypatch.delenv("DOCUMENT_STORAGE_PROVIDER", raising=False)
    collection = Collection()
    monkeypatch.setenv("DOCUMENT_STORAGE_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(document_storage, "get_database", lambda: SimpleNamespace(saved_documents=collection))
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda token: token or None)
    client = TestClient(app)
    owner = {"Cookie": "yojna_session=owner"}
    stranger = {"Cookie": "yojna_session=stranger"}
    headers = {**owner, "Content-Type": "application/pdf", "X-Document-Consent": "true"}
    data = digital_pdf("State: Haryana")
    assert client.post("/api/v1/saved-documents/aadhaar", headers=headers, content=data).status_code == 422
    response = client.post("/api/v1/saved-documents/domicile?language=auto", headers=headers, content=data)
    assert response.status_code == 201
    document = response.json()
    assert document["label"] == "Domicile Certificate"
    assert document["evidence_type"] == "residence"
    stored = next(iter(collection.records.values()))
    assert data not in stored["encrypted_file"]
    assert client.get("/api/v1/saved-documents", headers=owner).json() == [document]
    assert client.get("/api/v1/saved-documents", headers=stranger).json() == []
    path = "/api/v1/saved-documents/" + document["id"]
    assert client.get(path + "/file", headers=owner).content == data
    assert client.get(path + "/file", headers=stranger).status_code == 404
    extraction = "/api/v1/schemes/HR-OASA-002/saved-document-extractions/" + document["id"] + "/residence"
    assert client.post(extraction, headers={**headers}).json()["fields"]["state"]["value"] == "Haryana"
    assert client.post(extraction, headers={**stranger, "X-Document-Consent": "true"}).status_code == 404
    assert client.delete(path, headers=stranger).status_code == 404
    assert client.delete(path, headers=owner).status_code == 204
    assert client.get(path + "/file", headers=owner).status_code == 404



def test_selected_saved_documents_produce_a_standalone_mismatch(monkeypatch):
    monkeypatch.delenv("CLOUDINARY_URL", raising=False)
    monkeypatch.delenv("DOCUMENT_STORAGE_PROVIDER", raising=False)
    collection = Collection()
    monkeypatch.setenv("DOCUMENT_STORAGE_KEY", Fernet.generate_key().decode())
    monkeypatch.setattr(document_storage, "get_database", lambda: SimpleNamespace(saved_documents=collection))
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda token: "owner")
    monkeypatch.setattr(document_routes.account_profile_service, "get_profile", lambda owner: {})
    client = TestClient(app)
    headers = {"Content-Type": "application/pdf", "X-Document-Consent": "true"}
    documents = []
    for kind, value in (("aadhaar", "10/05/2002"), ("birth", "15/05/2002")):
        save = client.post("/api/v1/saved-documents/" + kind, headers={**headers, "X-Masked-Aadhaar": "true"},
                           content=digital_pdf("DOB: " + value))
        assert save.status_code == 201
        document_id = save.json()["id"]
        read = client.post("/api/v1/saved-document-extractions/" + document_id + "/age",
                           headers={"X-Document-Consent": "true"})
        assert read.status_code == 200
        documents.append({"document_type": "age", "fields": read.json()["fields"]})
    check = client.post("/api/v1/document-checks", json={"consent": True, "documents": documents})
    assert check.status_code == 200
    finding = next(item for item in check.json()["findings"] if item["code"] == "cross_document")
    assert [item["document"] for item in finding["evidence"]] == [1, 2]
    assert {item["field"] for item in finding["evidence"]} == {"date_of_birth"}



