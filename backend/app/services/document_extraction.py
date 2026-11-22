"""Read supported application fields from PDFs and images without saving uploads."""

from contextlib import closing
from dataclasses import dataclass
from datetime import date, datetime
from functools import lru_cache
from io import BytesIO
import csv
import os
import shutil
import subprocess
from unicodedata import category
import re

import httpx
import pypdfium2 as pdfium
from PIL import Image, ImageOps, UnidentifiedImageError

from ..schemas.document_checks import EvidenceField
from .document_checker import normalized_value
from .document_language import ascii_digits, detected_language, english_display

MAX_UPLOAD_BYTES = 8 * 1024 * 1024
MAX_PAGES = 5
MAX_IMAGE_PIXELS = 20_000_000
IMAGE_FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG"}
CONTENT_TYPES = {"application/pdf", *IMAGE_FORMATS}
PERSON_FIELDS = ("name", "father_name", "mother_name", "date_of_birth", "gender", "place_of_birth")
ADDRESS_FIELDS = ("address", "house_number", "street", "sector", "village", "city", "state", "district", "pin")
FIELDS_BY_TYPE = {
    "identity": (*PERSON_FIELDS, *ADDRESS_FIELDS),
    "residence": ("name", *ADDRESS_FIELDS),
    "age": (*PERSON_FIELDS, *ADDRESS_FIELDS),
    "bank": ("name",),
    "category": ("name", "social_category"),
    "disability": ("name", "disability_percentage"),
    "other": (*PERSON_FIELDS, *ADDRESS_FIELDS),
    "income": ("name", "annual_household_income"),
    "family_id": (*PERSON_FIELDS, *ADDRESS_FIELDS),
}
LABELS = {
    "name": r"(?:applicant(?:'s)? name|account holder(?:'s)?(?: name)?|full name|student(?:'s)? name|candidate(?:'s)? name|name of (?:the )?(?:student|candidate|applicant|holder)|name)",
    "date_of_birth": r"(?:date?\s+of\s+birth|birth\s+date|birthdate|d\s*\.?\s*[o0]\s*\.?\s*b\.?)",
    "state": r"(?:state|state/ut)",
    "district": r"district",
    "pin": r"(?:pin(?:\s*code)?|postal code)",
    "annual_household_income": r"(?:annual (?:household|family) income|(?:household|family) annual income|(?:household|family) income per annum)",
    "expires_on": r"(?:expires on|valid (?:till|until|through)|expir(?:y|ation) date)",
}
LABELS.update({
    "name": rf"(?:{LABELS['name']}|आवेदक का नाम|खाताधारक का नाम|विद्यार्थी का नाम|छात्र का नाम|अभ्यर्थी का नाम|उम्मीदवार का नाम|पूरा नाम|नाम|ਬਿਨੈਕਾਰ ਦਾ ਨਾਮ|ਖਾਤਾਧਾਰਕ ਦਾ ਨਾਮ|ਵਿਦਿਆਰਥੀ ਦਾ ਨਾਮ|ਉਮੀਦਵਾਰ ਦਾ ਨਾਮ|ਪੂਰਾ ਨਾਮ|ਨਾਂ|ਨਾਮ)",
    "date_of_birth": rf"(?:{LABELS['date_of_birth']}|जन्म तिथि|जन्म तारीख|जन्म दिनांक|ਜਨਮ ਮਿਤੀ|ਜਨਮ ਤਾਰੀਖ)",
    "address": r"(?:(?:permanent|residential|current|postal|correspondence) address|address|स्थायी पता|वर्तमान पता|पता|ਪੱਕਾ ਪਤਾ|ਪਤਾ)",
    "father_name": r"(?:father(?:['’]s)? name|name of father|पिता का नाम|ਪਿਤਾ ਦਾ ਨਾਮ)",
    "mother_name": r"(?:mother(?:['’]s)? name|name of mother|माता का नाम|ਮਾਤਾ ਦਾ ਨਾਮ)",
    "gender": r"(?:gender|sex|लिंग|ਲਿੰਗ)",
    "place_of_birth": r"(?:place of birth|birthplace|जन्म स्थान|ਜਨਮ ਸਥਾਨ)",
    "house_number": r"(?:house (?:number|no\.?)|मकान संख्या|ਮਕਾਨ ਨੰਬਰ)",
    "street": r"(?:street|road|गली|ਗਲੀ)",
    "sector": r"(?:sector|सेक्टर|ਸੈਕਟਰ)",
    "village": r"(?:village|गाँव|गांव|ਪਿੰਡ)",
    "city": r"(?:city|town|शहर|ਸ਼ਹਿਰ)",
    "issued_on": r"(?:date of issue|issue date|issued on|जारी करने की तारीख|ਜਾਰੀ ਕਰਨ ਦੀ ਮਿਤੀ)",
    "issuing_authority": r"(?:issuing authority|issued by|जारीकर्ता|ਜਾਰੀ ਕਰਨ ਵਾਲੀ ਅਥਾਰਟੀ)",
    "document_number": r"(?:document (?:number|no\.?)|passport (?:number|no\.?)|registration (?:number|no\.?)|licen[cs]e (?:number|no\.?)|certificate (?:number|no\.?)|aadhaar (?:number|no\.?)|pan (?:number|no\.?))",
    "state": rf"(?:{LABELS['state']}|राज्य|प्रदेश|ਰਾਜ|ਸੂਬਾ)",
    "district": rf"(?:{LABELS['district']}|जिला|ज़िला|जनपद|ਜ਼ਿਲ੍ਹਾ|ਜਿਲ੍ਹਾ|ਜ਼ਿਲਾ)",
    "pin": rf"(?:{LABELS['pin']}|पिन\s*कोड|पिन|ਪਿੰਨ\s*ਕੋਡ|ਪਿਨ\s*ਕੋਡ)",
    "annual_household_income": rf"(?:{LABELS['annual_household_income']}|वार्षिक पारिवारिक आय|परिवार की वार्षिक आय|कुल वार्षिक पारिवारिक आय|ਪਰਿਵਾਰ ਦੀ ਸਾਲਾਨਾ ਆਮਦਨ|ਸਾਲਾਨਾ ਪਰਿਵਾਰਕ ਆਮਦਨ)",
    "social_category": r"(?:social category|caste category|category|श्रेणी|वर्ग|जाति|ਸ਼੍ਰੇਣੀ|ਵਰਗ|ਜਾਤੀ)",
    "disability_percentage": r"(?:disability percentage|percentage of disability|दिव्यांगता प्रतिशत|विकलांगता का प्रतिशत|ਅਪੰਗਤਾ ਪ੍ਰਤੀਸ਼ਤ|ਦਿਵਿਆਂਗਤਾ ਪ੍ਰਤੀਸ਼ਤ)",
    "expires_on": rf"(?:{LABELS['expires_on']}|वैधता की तिथि|तक मान्य|समाप्ति तिथि|ਵੈਧਤਾ ਮਿਤੀ|ਮਿਆਦ ਪੁੱਗਣ ਦੀ ਮਿਤੀ|ਤੱਕ ਵੈਧ)",
})
PATTERNS = {
    key: re.compile(rf"^\s*{label}\s*(?:[:=–-]\s*|\s{{2,}})(.{{1,120}}?)\s*$", re.IGNORECASE)
    for key, label in LABELS.items()
}


DATE_TOKEN = re.compile(r"(?<!\d)(?:\d{4}\s*-\s*\d{1,2}\s*-\s*\d{1,2}|\d{1,2}\s*[/.-]\s*\d{1,2}\s*[/.-]\s*\d{4}|\d{1,2}(?:st|nd|rd|th)?[ -]+[A-Za-z]{3,9}[ -]+\d{4})(?!\d)", re.I)
EXPLICIT_NAME = re.compile(
    rf"^\s*(?:{LABELS['name']})(?:\s*[:=–-]\s*|\s+)(.+?)\s*$", re.IGNORECASE,
)
CERTIFICATION_NAME = re.compile(r"^\s*this\s+is\s+to\s+certify\s+that\b\s*(?:[:=–-]\s*)?(.*)$", re.I)
NON_SUBJECT_NAME = re.compile(r"^(?:of\b|as per\b|[&/]\s*(?:designation|address)\b|father\b|mother\b|guardian\b|spouse\b)", re.IGNORECASE)
COMPOSITE_NAME_LINE = re.compile(r"\s+(?:(?:sex|gender)\s*[:=]|(?:date of birth|d\.?o\.?b\.?|जन्म तिथि|ਜਨਮ ਮਿਤੀ)\b)", re.IGNORECASE)
DATE_LABEL = re.compile(
    rf"(?<!\w){LABELS['date_of_birth']}(?=[:=–\-/|(\s\d]|$)", re.IGNORECASE,
)
OTHER_DATE_LABEL = re.compile(r"\b(?:date of issue|issue date|issued on|date of (?:result|examination|declaration|printing)|expiry date)\b", re.I)
MONTH_FIRST = re.compile(r"\bmm\s*[/.-]\s*dd\s*[/.-]\s*yyyy\b", re.I)
DOB_LABEL_ONLY = re.compile(
    rf"^\s*{LABELS['date_of_birth']}\s*(?:\(\s*dd\s*[/.-]\s*mm\s*[/.-]\s*yyyy\s*\))?\s*[:=–-]?\s*$",
    re.I,
)
EXPIRY_LABEL = re.compile(rf"^\s*{LABELS['expires_on']}\s*(?=[:=–\-\s]|$)", re.IGNORECASE)
SPACED_LABELS = {
    field: re.compile(rf"^\s*{label}\s+(.{{1,120}}?)\s*$", re.IGNORECASE)
    for field, label in LABELS.items() if field != "name"
}
NAME_EXCLUSIONS = re.compile(
    r"government|india|aadhaar|authority|certificate|father|mother|address|male|female|"
    r"भारत|सरकार|आधार|पिता|माता|ਪਿਤਾ|ਮਾਤਾ|ਭਾਰਤ|ਸਰਕਾਰ|ਆਧਾਰ", re.IGNORECASE,
)


LABEL_ONLY = re.compile(
    rf"^\s*(?:{'|'.join(LABELS.values())})\s*[:=–-]?\s*$", re.IGNORECASE,
)
ADDRESS_START = re.compile(rf"^\s*{LABELS['address']}\s*[:=–-]\s*(.*)$", re.IGNORECASE)
ADDRESS_OF_OTHER_PERSON = re.compile(rf"^\s*{LABELS['address']}\s+of\b", re.IGNORECASE)
ADDRESS_PIN = re.compile(r"(?<!\d)([1-9]\d{5})\s*[.]*$")


class InvalidUpload(ValueError):
    pass


class OCRUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class Line:
    text: str
    confidence: float | None = None
    box: tuple[int, int, int, int] | None = None


@lru_cache(maxsize=1)
def _ocr_engine():
    from rapidocr import RapidOCR

    return RapidOCR(params={"Global.log_level": "error", "EngineConfig.onnxruntime.intra_op_num_threads": 2})


def _tesseract_lines(image: Image.Image, executable: str, language: str, sparse: bool = False) -> list[Line]:
    image_bytes = BytesIO()
    image.convert("RGB").save(image_bytes, format="PNG")
    languages = {"en": "eng", "auto": "eng+hin+pan", "hi": "hin+eng", "pa": "pan+eng"}
    selected_languages = languages[language]
    if sparse and language in {"hi", "pa"}:
        selected_languages = "eng+" + selected_languages.split("+", 1)[0]
    try:
        process = subprocess.run(
            [executable, "stdin", "stdout", "-l", selected_languages, "-c", "tessedit_create_tsv=1"] + (["--psm", "11"] if sparse else []),
            input=image_bytes.getvalue(), capture_output=True, timeout=25, check=False,
            env={**os.environ, "OMP_THREAD_LIMIT": "2"},
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OCRUnavailable("The multilingual reader is unavailable.") from exc
    if process.returncode or b"Failed loading language" in process.stderr:
        raise OCRUnavailable("Install the English, Hindi and Punjabi OCR language packs.")
    rows = csv.DictReader(process.stdout.decode("utf-8-sig", errors="replace").splitlines(), delimiter="\t")
    required_columns = {"level", "text", "left", "top", "width", "height", "block_num", "par_num", "line_num", "conf"}
    if not required_columns.issubset(rows.fieldnames or []):
        raise OCRUnavailable("The reader could not process this scan. You can enter the details manually.")
    groups = {}
    for row in rows:
        if row["level"] != "5" or not row["text"].strip():
            continue
        x, y, width, height = (int(row[key]) for key in ("left", "top", "width", "height"))
        key = tuple(row[key] for key in ("block_num", "par_num", "line_num"))
        groups.setdefault(key, []).append(Line(row["text"], float(row["conf"]) / 100,
                                               (x, y, x + width, y + height)))
    lines = []
    for words in groups.values():
        box = (min(word.box[0] for word in words), min(word.box[1] for word in words),
               max(word.box[2] for word in words), max(word.box[3] for word in words))
        lines.append(Line(" ".join(word.text for word in words), min(word.confidence for word in words), box))
    return _join_ocr_labels(lines)


def _ocr_lines(image: Image.Image, language: str, supported: tuple[str, ...]) -> list[Line]:
    image.thumbnail((2400, 2400))
    executable = os.getenv("TESSERACT_CMD") or shutil.which("tesseract")
    if language != "en":
        if not executable:
            raise OCRUnavailable("Automatic reading is unavailable for this scan. You can enter the document details manually.")
        lines = _tesseract_lines(image, executable, language)
        if not any(_line_candidates(lines, supported)):
            sparse = _tesseract_lines(ImageOps.autocontrast(image.convert("L")), executable, language, sparse=True)
            if any(_line_candidates(sparse, supported)):
                return sparse
            if language != "auto":
                mixed = _tesseract_lines(image, executable, "auto")
                if any(_line_candidates(mixed, supported)):
                    return mixed
            if not lines:
                return sparse
        return lines
    try:
        import numpy as np

        result = _ocr_engine()(np.asarray(image.convert("RGB"))[:, :, ::-1].copy())
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise OCRUnavailable("Image reading is temporarily unavailable.") from exc
    if result.txts is None or result.boxes is None or result.scores is None:
        return _tesseract_lines(image, executable, "en", sparse=True) if executable else []
    lines = [
        Line(text, float(score), (int(box[:, 0].min()), int(box[:, 1].min()),
                                  int(box[:, 0].max()), int(box[:, 1].max())))
        for text, score, box in zip(result.txts, result.scores, result.boxes)
    ]
    lines = _join_ocr_labels(lines)
    if executable and not any(_line_candidates(lines, supported)):
        sparse = _tesseract_lines(image, executable, "en", sparse=True)
        if any(_line_candidates(sparse, supported)):
            return sparse
    return lines


def _join_ocr_labels(lines: list[Line]) -> list[Line]:
    joined = []
    for label in lines:
        if not LABEL_ONLY.fullmatch(label.text) or label.box is None:
            continue
        x1, y1, x2, y2 = label.box
        height = max(1, y2 - y1)
        neighbors = [
            item for item in lines
            if item.box is not None and x2 - 2 <= item.box[0] <= x2 + 8 * height
            and abs(item.box[1] + item.box[3] - y1 - y2) <= height
            and not LABEL_ONLY.fullmatch(item.text)
        ]
        if neighbors:
            value = min(neighbors, key=lambda item: item.box[0])
            text = label.text.rstrip(" :=–-") + ": " + value.text
            joined.append(Line(text, min(label.confidence, value.confidence),
                               (x1, min(y1, value.box[1]), value.box[2], max(y2, value.box[3]))))
    return lines + joined


def _cloud_page_jpeg(image: Image.Image) -> bytes:
    original = image.convert("RGB")
    # Keep the largest readable image that fits the free API's 1 MB limit.
    for edge in (3200, 2560, 2048, 1600, 1280, 960, 640):
        page = original.copy()
        page.thumbnail((edge, edge), Image.Resampling.LANCZOS)
        for quality in (92, 82, 70):
            buffer = BytesIO()
            page.save(buffer, format="JPEG", quality=quality, optimize=True)
            if buffer.tell() < 990_000:
                return buffer.getvalue()
    raise OCRUnavailable("This page could not be prepared for OCR.space. Try using the local reader.")


def _cloud_ocr_lines(image: Image.Image, key: str) -> list[Line]:
    jpeg = _cloud_page_jpeg(image)
    try:
        response = httpx.post(
            "https://api.ocr.space/parse/image",
            headers={"apikey": key},
            files={"file": ("page.jpg", jpeg, "image/jpeg")},
            data={"OCREngine": "3", "language": "auto"},
            timeout=45,
        )
        response.raise_for_status()
        result = response.json()
        if result.get("IsErroredOnProcessing") or str(result.get("OCRExitCode")) != "1":
            raise ValueError("OCR.space returned an OCR error")
        parsed = result["ParsedResults"][0]
        if str(parsed.get("FileParseExitCode")) != "1":
            raise ValueError("OCR.space could not parse the page")
        return [Line(line.strip()) for line in parsed["ParsedText"].splitlines() if line.strip()]
    except (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        raise OCRUnavailable("OCR.space could not read this file. Check the API key and quota or try the local reader.") from exc


def _pages(data: bytes, content_type: str, supported: tuple[str, ...], language: str, cloud_key: str = ""):
    def recognize(image):
        if cloud_key:
            return _cloud_ocr_lines(image, cloud_key)
        return _ocr_lines(image, language, supported)

    if content_type == "application/pdf":
        if not data.startswith(b"%PDF-"):
            raise InvalidUpload("Select a valid PDF file.")
        try:
            with pdfium.PdfDocument(data) as document:
                if not 1 <= len(document) <= MAX_PAGES:
                    raise InvalidUpload(f"Upload a PDF with 1 to {MAX_PAGES} pages.")
                for index in range(len(document)):
                    with closing(document[index]) as page:
                        with closing(page.get_textpage()) as text_page:
                            if text_page.count_chars() > 50_000:
                                raise InvalidUpload("A page contains too much text to process.")
                            text = text_page.get_text_bounded()
                        lines = [Line(line) for line in text.splitlines() if line.strip()]
                        text_fields = {field for field, _, _ in _line_candidates(lines, supported)}
                        if not cloud_key and {"name", "date_of_birth"}.intersection(supported) <= text_fields and text_fields:
                            yield index + 1, lines, []
                            continue
                        width, height = page.get_size()
                        if min(width, height) <= 0:
                            raise InvalidUpload("A page has invalid dimensions.")
                        with closing(page.render(scale=min(3, 2400 / max(width, height)))) as bitmap:
                            try:
                                scanned = recognize(bitmap.to_pil())
                            except OCRUnavailable:
                                if cloud_key or not lines:
                                    raise
                                scanned = []
                        # Prefer the embedded text for fields already available on the PDF page.
                        yield index + 1, lines, scanned
        except pdfium.PdfiumError as exc:
            raise InvalidUpload("Use a readable, unlocked PDF.") from exc
        return

    try:
        with Image.open(BytesIO(data), formats=[IMAGE_FORMATS[content_type]]) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise InvalidUpload("The image exceeds 20 megapixels.")
            if getattr(image, "n_frames", 1) != 1:
                raise InvalidUpload("Upload a single-frame image.")
            yield 1, [], recognize(ImageOps.exif_transpose(image))
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise InvalidUpload("Use a readable PNG or JPEG image.") from exc


def _field_value(field: str, value: str) -> str | None:
    value = value.strip()
    if not value or len(value) > 120:
        return None
    if field == "disability_percentage":
        value = value.removesuffix("%").strip()
        if not re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", value):
            return None
    if field == "document_number":
        value = ascii_digits(re.sub(r"[ -]", "", value))
        return "••••" + value[-4:] if re.fullmatch(r"[A-Za-z0-9]{5,30}", value) else None
    if field == "issuing_authority":
        return value if any(char.isalpha() for char in value) else None
    if field in {"date_of_birth", "expires_on", "issued_on"}:
        value = ascii_digits(value)
        value = re.sub(r"(?<=\d)(?:st|nd|rd|th)\b", "", value, flags=re.I)
        value = re.sub(r"\s*([/.-])\s*", r"\1", value)
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%B-%Y"):
            try:
                return datetime.strptime(value, fmt).date().isoformat()
            except ValueError:
                continue
        return None
    if field == "annual_household_income":
        value = ascii_digits(value)
        value = re.sub(r"^(?:₹|INR\b|Rs\.?|रु\.?|रुपये|ਰੁ\.?|ਰੁਪਏ)\s*", "", value, flags=re.IGNORECASE)
        value = re.sub(r"\s*(?:/-|per annum|प्रति वर्ष|ਸਾਲਾਨਾ)$", "", value, flags=re.IGNORECASE)
        if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{2,3})+)(?:\.[0-9]{1,2})?", value):
            return None
    normalized = normalized_value(field, value)
    if normalized is None:
        return None
    return format(normalized, "f") if field == "annual_household_income" else ascii_digits(value) if field in {"pin", "disability_percentage"} else value


def _match_value(field: str, text: str) -> str | None:
    if field == "address" and ADDRESS_OF_OTHER_PERSON.match(text):
        return None
    if field == "date_of_birth":
        text = text.replace("**", "").replace("__", "").translate(str.maketrans("–—−", "---"))
    if "|" in text:
        cells = [cell.strip(" *") for cell in text.strip().strip("|").split("|")]
        for key, value in zip(cells, cells[1:]):
            label_cell = key.rstrip(": ")
            if value and re.fullmatch(LABELS[field], label_cell, re.IGNORECASE):
                text = label_cell + ": " + value
                break
    match = PATTERNS[field].match(text)
    if field in {"date_of_birth", "expires_on", "issued_on"}:
        date_labels = (DATE_LABEL if field == "date_of_birth" else EXPIRY_LABEL if field == "expires_on"
                       else re.compile(rf"^\s*{LABELS['issued_on']}\b", re.I))
        label = date_labels.search(text)
        if label or match:
            remainder = ascii_digits(text[label.end():] if label else match[1]).lstrip(" :=–-/|")
            if field == "date_of_birth":
                remainder = OTHER_DATE_LABEL.split(remainder, maxsplit=1)[0]
            immediate = DATE_TOKEN.match(remainder)
            dates = [immediate[0]] if immediate else DATE_TOKEN.findall(remainder)
            if len(dates) == 1:
                token = dates[0]
                if field == "date_of_birth" and MONTH_FIRST.search(remainder):
                    numeric = re.fullmatch(r"(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*(\d{4})", token)
                    if numeric:
                        token = f"{numeric[2]}/{numeric[1]}/{numeric[3]}"
                return _field_value(field, token)
        return None
    if field == "name":
        named = match or EXPLICIT_NAME.match(text)
        if named:
            name = COMPOSITE_NAME_LINE.split(named[1].strip(), maxsplit=1)[0]
            if len(name) <= 120 and not NON_SUBJECT_NAME.match(name):
                return _field_value(field, name)
        return None
    if not match and field in SPACED_LABELS:
        match = SPACED_LABELS[field].match(text)
    return _field_value(field, match[1].strip()) if match else None


def _line_candidates(lines: list[Line], supported: tuple[str, ...], infer_name: bool = False):
    found_name = False
    birth_index = None
    for index, line in enumerate(lines):
        for field in supported:
            value = _match_value(field, line.text)
            source = line
            if field == "address":
                address = ADDRESS_START.match(line.text)
                if address and not ADDRESS_PIN.search(ascii_digits(address[1])):
                    chunks = [address[1]]
                    for following in lines[index + 1:index + 5]:
                        if any(_match_value(key, following.text) for key in LABELS if key != "pin") or LABEL_ONLY.fullmatch(following.text):
                            break
                        chunks.append(following.text)
                        if ADDRESS_PIN.search(ascii_digits(following.text)):
                            value = _field_value(field, " ".join(filter(None, chunks)))
                            break
            if value is None and index + 1 < len(lines) and LABEL_ONLY.fullmatch(line.text):
                following = lines[index + 1]
                if not LABEL_ONLY.fullmatch(following.text) and (
                    field != "name" or not NAME_EXCLUSIONS.search(following.text)
                ):
                    value = _match_value(field, line.text.rstrip(" :=–-") + ": " + following.text)
                    source = following
            if value is None and field == "date_of_birth" and index + 1 < len(lines):
                heading = line.text.replace("**", "").replace("__", "").strip(" |")
                following = lines[index + 1]
                if DOB_LABEL_ONLY.fullmatch(heading) and DATE_TOKEN.fullmatch(ascii_digits(following.text.strip(" |*"))):
                    value = _match_value(field, heading + " " + following.text)
                    source = following
            if value is not None:
                if field == "address" and "pin" in supported:
                    pin = ADDRESS_PIN.search(ascii_digits(value))
                    if pin:
                        yield "pin", pin[1], source
                if field == "name":
                    found_name = True
                if field == "date_of_birth" and birth_index is None:
                    birth_index = index
                yield field, value, source
    if found_name or "name" not in supported:
        return
    if infer_name and birth_index is not None:
        birth_box = lines[birth_index].box
        for previous in reversed(lines[max(0, birth_index - 3):birth_index]):
            if birth_box and previous.box and (previous.box[2] <= birth_box[0] or previous.box[0] >= birth_box[2]):
                continue
            text = previous.text.strip(" +|*/")
            if DATE_LABEL.search(text) or DOB_LABEL_ONLY.fullmatch(text):
                continue
            name = _candidate_name(text)
            if name:
                yield "name", name, Line(name, min(previous.confidence or 0.6, 0.6), previous.box)
                return
    for index, line in enumerate(lines):
        certification = CERTIFICATION_NAME.match(line.text)
        if not certification:
            continue
        following = lines[index + 1] if index + 1 < len(lines) else None
        source = line if certification[1].strip() else following
        if source:
            name = _candidate_name(certification[1] if source is line else source.text)
            if name:
                yield "name", name, Line(name, min(source.confidence or 0.6, 0.6), source.box)
                return


def _candidate_name(value: str) -> str | None:
    text = value.strip()
    if (2 <= len(text.split()) <= 5 and len(text) <= 80
            and all(char.isalpha() or char.isspace() or char in ".'’-" or category(char).startswith("M")
                    for char in text)
            and not NAME_EXCLUSIONS.search(text) and not LABEL_ONLY.fullmatch(text)
            and not NON_SUBJECT_NAME.match(text)):
        return text
    return None


def extract_document(data: bytes, content_type: str, document_type: str, language: str = "en", use_cloud: bool = False) -> dict:
    cloud_key = os.getenv("OCR_SPACE_API_KEY", "").strip() if use_cloud else ""
    if use_cloud and not cloud_key:
        raise OCRUnavailable("Cloud OCR is unavailable. Configure an OCR.space key on the server or uncheck Cloud OCR to use the local reader.")
    supported = (*FIELDS_BY_TYPE[document_type], "expires_on", "issued_on", "issuing_authority", "document_number")
    extracted: dict[str, EvidenceField] = {}
    ambiguous = set()
    unreadable_pages = []
    page_count = 0
    recognized_text_pages = 0
    for page_count, lines, scanned in _pages(data, content_type, supported, language, cloud_key):
        candidates = list(_line_candidates(lines, supported, document_type == "identity"))
        if scanned:
            existing = {field for field, _, _ in candidates}
            candidates.extend(item for item in _line_candidates(scanned, supported, document_type == "identity")
                              if item[0] not in existing)
        if lines or scanned:
            recognized_text_pages += 1
        else:
            unreadable_pages.append(page_count)
        for field, value, line in candidates:
            if field in ambiguous:
                continue
            previous = extracted.get(field)
            if previous and normalized_value(field, previous.value) != normalized_value(field, value):
                ambiguous.add(field)
                del extracted[field]
                continue
            if previous is None or (line.confidence or 0) > (previous.ocr_confidence or 0):
                original_value = value
                if field in {"date_of_birth", "expires_on", "issued_on"}:
                    for token in DATE_TOKEN.findall(line.text.translate(str.maketrans("–—−", "---"))):
                        if _field_value(field, token) == value or (field == "date_of_birth" and MONTH_FIRST.search(line.text)):
                            original_value = token
                            break
                numeric = re.fullmatch(r"(\d{1,2})\s*[/.-]\s*(\d{1,2})\s*[/.-]\s*\d{4}", ascii_digits(original_value))
                uncertain = (field == "date_of_birth" and document_type == "other" and numeric is not None
                             and int(numeric[1]) <= 12 and int(numeric[2]) <= 12 and numeric[1] != numeric[2]
                             and not re.search(r"(?:dd\s*[/.-]\s*mm|mm\s*[/.-]\s*dd)\s*[/.-]\s*yyyy", line.text, re.I))
                extracted[field] = EvidenceField(
                    value=value, original_value=original_value, page=page_count, bounding_box=line.box,
                    ocr_confidence=line.confidence, date_format_uncertain=uncertain,
                )

    expiry = extracted.pop("expires_on", None)
    details = {field: extracted.pop(field).value for field in ("issued_on", "issuing_authority", "document_number") if field in extracted}
    return {
        "fields": extracted,
        "extraction_status": "success" if extracted and not unreadable_pages else "partial" if extracted else "no_fields",
        "field_languages": {field: detected_language(evidence.original_value or evidence.value)
                            for field, evidence in extracted.items()},
        "document_details": details,
        "display_values": {field: english_display(field, evidence.value) for field, evidence in extracted.items()},
        "expires_on": date.fromisoformat(expiry.value) if expiry else None,
        "page_count": page_count,
        "recognized_text_pages": recognized_text_pages,
        "unreadable_pages": unreadable_pages,
        "ambiguous_fields": sorted(ambiguous - {"issued_on", "issuing_authority", "document_number"}),
    }





def validate_upload(data: bytes, content_type: str) -> None:
    """Validate a file for storage without running OCR."""
    if content_type == "application/pdf":
        if not data.startswith(b"%PDF-"):
            raise InvalidUpload("Select a valid PDF file.")
        try:
            with pdfium.PdfDocument(data) as document:
                if not 1 <= len(document) <= MAX_PAGES:
                    raise InvalidUpload(f"Upload a PDF with 1 to {MAX_PAGES} pages.")
        except pdfium.PdfiumError as exc:
            raise InvalidUpload("Use a readable, unlocked PDF.") from exc
        return
    try:
        with Image.open(BytesIO(data), formats=[IMAGE_FORMATS[content_type]]) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS or getattr(image, "n_frames", 1) != 1:
                raise InvalidUpload("Use a single-frame image up to 20 megapixels.")
            image.load()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as exc:
        raise InvalidUpload("Use a readable PNG or JPEG image.") from exc












