"""Synthetic file fixtures exercise the upload-to-mismatch workflow."""

from io import BytesIO
from random import Random
import httpx

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
import pytest

from backend.app.api import auth_routes, document_routes
from backend.app.main import app
from backend.app.services.document_extraction import extract_document
from backend.app.services import document_extraction


SCHEME = "/api/v1/schemes/HR-OASA-002"
UPLOAD = SCHEME + "/document-extractions/residence"
HEADERS = {"Content-Type": "application/pdf", "X-Document-Consent": "true"}


@pytest.mark.parametrize(("line", "expected"), [
    ("Student Name: Sample Student   DOB (DD/MM/YYYY): 3rd October 2006  Date of Issue: 05/07/2024", "2006-10-03"),
    ("**Date of Birth:** 03 - 10 - 2006", "2006-10-03"),
    ("DOB: Date of Issue: 05/07/2024", None),
    ("Year of Birth: 2006", None),
])
def test_extracts_only_full_labeled_birth_dates(line, expected):
    assert document_extraction._match_value("date_of_birth", line) == expected


def test_birth_certificate_and_aadhaar_names_survive_nearby_labels():
    certificate = ["| Name | Sample Student | Sex | Girl |", "Name & Designation of Official who", "Date of Birth: 08-10-1996"]
    aadhaar = ["+ Sample Student", "जन्म तिथि /", "DOB: 14/05/1997"]
    for lines, infer_name in ((certificate, False), (aadhaar, True)):
        recognized = [document_extraction.Line(line) for line in lines]
        names = [value for field, value, _ in document_extraction._line_candidates(
            recognized, ("name", "date_of_birth"), infer_name,
        ) if field == "name"]
        assert names == ["Sample Student"]


def test_extended_extraction_masks_identifiers_and_keeps_date_uncertainty(monkeypatch):
    monkeypatch.setattr(document_extraction, "_ocr_lines", lambda *_: [])
    document = digital_pdf(
        "Applicant Name: Sample Student", "Father's Name: Sample Parent", "Date of Birth: 04/05/2006",
        "House Number: 23B", "Issue date: 01/01/2024", "Document number: 1234 5678 9012",
    )
    result = extract_document(document, "application/pdf", "other")
    assert result["fields"]["date_of_birth"].original_value == "04/05/2006"
    assert result["fields"]["date_of_birth"].date_format_uncertain
    assert result["fields"]["father_name"].value == "Sample Parent"
    assert result["fields"]["house_number"].value == "23B"
    assert result["field_languages"]["father_name"] == "English"
    assert result["document_details"] == {"issued_on": "2024-01-01", "document_number": "••••9012"}


def test_student_id_and_aadhaar_birth_dates_are_compared(monkeypatch):
    from datetime import date
    from backend.app.schemas.document_checks import DocumentEvidence
    from backend.app.services.document_catalogue import DOCUMENT_TYPES
    from backend.app.services.document_checker import check_documents

    monkeypatch.setattr(document_extraction, "_ocr_lines", lambda *_: [])
    documents = []
    for kind, lines in (
        ("student_id", ("Name: Sample Student", "D0B (DD/MM/YYYY)", "03/10/2006")),
        ("aadhaar", ("Name: Sample Student", "Dat of Birth: 04/10/2006")),
    ):
        evidence_type = DOCUMENT_TYPES[kind]["evidence_type"]
        result = extract_document(digital_pdf(*lines), "application/pdf", evidence_type)
        documents.append(DocumentEvidence(document_type=evidence_type, fields=result["fields"]))

    result = check_documents(None, documents, {}, date(2026, 11, 22), compare_unconfirmed=True)
    assert {item["evidence"][0]["field"]: item["status"] for item in result["comparisons"]} == {
        "name": "exact_match",
        "date_of_birth": "clear_mismatch",
    }


def test_cloud_ocr_resizes_page_if_jpeg_compression_is_not_enough():
    image = Image.frombytes("RGB", (3200, 3200), Random(42).randbytes(3200 * 3200 * 3))
    baseline = BytesIO()
    image.save(baseline, format="JPEG", quality=70, optimize=True)
    assert baseline.tell() >= 990_000

    page = document_extraction._cloud_page_jpeg(image)

    assert len(page) < 990_000
    with Image.open(BytesIO(page)) as resized:
        assert resized.width < image.width
        assert resized.width == resized.height


def test_extracts_aadhaar_address_and_pin_from_multiple_lines():
    lines = [document_extraction.Line(text) for text in (
        "Address:", "House 12, Model Town,", "Gurugram, Haryana - 122001",
    )]
    fields = {field: value for field, value, _ in document_extraction._line_candidates(lines, ("address", "pin"))}
    assert fields == {"address": "House 12, Model Town, Gurugram, Haryana - 122001", "pin": "122001"}


def test_cloud_ocr_extracts_marksheet_birth_date_only_when_selected(monkeypatch):
    calls = []

    def annotate(url, *, headers, files, data, timeout):
        calls.append(data)
        assert url == "https://api.ocr.space/parse/image"
        assert headers["apikey"] == "test-key"
        assert files["file"][1].startswith(b"\xff\xd8")
        return httpx.Response(200, request=httpx.Request("POST", url), json={
            "OCRExitCode": 1,
            "ParsedResults": [{"FileParseExitCode": 1, "ParsedText": "Student Name: Asha Sharma\n| **Date of Birth** | 15/05/2002 |"}],
        })

    monkeypatch.setenv("OCR_SPACE_API_KEY", "test-key")
    monkeypatch.setattr(document_extraction.httpx, "post", annotate)
    monkeypatch.setattr(document_extraction, "_ocr_lines", lambda *_: [])
    file = digital_pdf("Senior Secondary Marksheet", "Issued on: 03/06/2020")
    assert not extract_document(file, "application/pdf", "age", "hi")["fields"]
    assert not calls
    result = extract_document(file, "application/pdf", "age", "hi", use_cloud=True)
    assert result["fields"]["date_of_birth"].value == "2002-05-15"
    assert result["fields"]["date_of_birth"].page == 1
    assert calls == [{"OCREngine": "3", "language": "auto"}]


def digital_pdf(*lines):
    commands = "BT /F1 18 Tf 60 700 Td 28 TL " + " T* ".join(f"({line}) Tj" for line in lines) + " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Count 1 /Kids [3 0 R] >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources "
        "<< /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(commands)} >>\nstream\n{commands}\nendstream",
    ]
    result = BytesIO(b"%PDF-1.4\n")
    result.seek(0, 2)
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(result.tell())
        result.write(f"{index} 0 obj\n{obj}\nendobj\n".encode("ascii"))
    xref = result.tell()
    result.write(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        result.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    result.write(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode("ascii"))
    return result.getvalue()


def photo(format):
    image = Image.new("RGB", (900, 300), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=42)
    draw.text((50, 55), "Applicant Name: Asha Sharma", font=font, fill="black")
    draw.text((50, 130), "State: Haryana", font=font, fill="black")
    output = BytesIO()
    image.save(output, format=format)
    return output.getvalue()


@pytest.mark.parametrize(("format", "content_type"), [("PNG", "image/png"), ("JPEG", "image/jpeg"), ("PDF", "application/pdf")])
def test_scanned_document_uses_local_ocr(format, content_type):
    result = extract_document(photo(format), content_type, "residence")
    assert result["fields"]["state"].value.casefold() == "haryana"
    assert result["fields"]["state"].ocr_confidence > 0.5
    assert result["fields"]["state"].bounding_box is not None


def test_uploaded_pdf_reaches_profile_and_cross_document_checks(monkeypatch):
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda token: "applicant")
    monkeypatch.setattr(document_routes.account_profile_service, "get_profile",
                        lambda user_id: {"profile": {"location": {"state": "Haryana"}}})
    client = TestClient(app)
    documents = []
    for state in ("Haryana", "Punjab"):
        response = client.post(
            UPLOAD, headers=HEADERS,
            content=digital_pdf("Name: Asha Sharma", f"State: {state}", "ID Number: 123456789012"),
        )
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert "123456789012" not in response.text
        fields = response.json()["fields"]
        assert fields["state"]["value"] == state
        documents.append({"document_type": "residence", "fields": fields})
    report = client.post(SCHEME + "/document-checks", json={"consent": True, "documents": documents})
    assert report.status_code == 200
    findings = {issue["code"]: issue for issue in report.json()["findings"]}
    assert findings["profile_comparison"]["evidence"][0]["page"] == 1
    assert len(findings["cross_document"]["evidence"]) == 2
    assert "Punjab" not in report.text


def test_upload_rejects_unauthorized_unconsented_and_invalid_files(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda token: None)
    assert client.post(UPLOAD, headers=HEADERS, content=b"bad").status_code == 401
    monkeypatch.setattr(auth_routes.auth_service, "user_id_for_session", lambda token: "applicant")
    assert client.post(UPLOAD, headers={"Content-Type": "application/pdf"}, content=b"bad").status_code == 422
    assert client.post(UPLOAD, headers=HEADERS, content=b"bad").status_code == 422
    assert client.post(UPLOAD, headers={**HEADERS, "Content-Type": "text/html"}, content=b"bad").status_code == 415
    monkeypatch.setattr(document_routes, "MAX_UPLOAD_BYTES", 3)
    assert client.post(UPLOAD, headers=HEADERS, content=b"long").status_code == 413


def test_extraction_omits_ambiguous_values_and_normalizes_dates():
    result = extract_document(
        digital_pdf("Name: Asha Sharma", "Name: Asha Verma", "DOB: 21/11/1966"),
        "application/pdf", "identity",
    )
    assert result["ambiguous_fields"] == ["name"]
    assert result["fields"]["date_of_birth"].value == "1966-11-21"



def test_extracts_bilingual_dob_and_split_labels_from_identity_pdf():
    result = extract_document(
        digital_pdf("Government of India", "Aman Kumar", "DOB 10 / 05 / 2002"),
        "application/pdf", "identity",
    )
    assert result["fields"]["date_of_birth"].value == "2002-05-10"
    assert result["fields"]["name"].value == "Aman Kumar"
    assert result["fields"]["name"].ocr_confidence == 0.6
    split = extract_document(digital_pdf("Name", "Aman Kumar", "DOB", "15/05/2002"),
                             "application/pdf", "identity")
    assert split["fields"]["name"].value == "Aman Kumar"
    assert split["fields"]["date_of_birth"].value == "2002-05-15"


def test_reads_student_labels_and_keeps_pdf_text_when_ocr_is_needed(monkeypatch):
    from backend.app.services import document_extraction

    monkeypatch.setattr(document_extraction, "_ocr_lines",
                        lambda image, language, supported: [document_extraction.Line("D O B 15/05/2002")])
    result = extract_document(
        digital_pdf("Student Name Aman Kumar"), "application/pdf", "other",
    )
    assert result["display_values"] == {"name": "Aman Kumar", "date_of_birth": "2002-05-15"}
    assert result["recognized_text_pages"] == 1


def test_mark_sheet_certificate_name_excludes_issuance_date():
    result = extract_document(
        digital_pdf("This is to certify that", "Aman Kumar", "Roll No 12304567", "Dated", "15/05/2020"),
        "application/pdf", "other",
    )
    assert result["display_values"] == {"name": "Aman Kumar"}


def test_identity_dob_does_not_pick_a_second_date_on_the_line():
    result = extract_document(
        digital_pdf("Aman Kumar", "DOB: 10/05/2002 Issue Date: 15/05/2020"),
        "application/pdf", "identity",
    )
    assert result["display_values"]["date_of_birth"] == "2002-05-10"
