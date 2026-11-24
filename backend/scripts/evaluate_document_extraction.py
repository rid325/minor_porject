"""Evaluate labelled PDF/image fields without printing document text or personal values.

Run from the repository root with python -m backend.scripts.evaluate_document_extraction manifest.json.
Each manifest row provides file, content_type, document_type, language, and expected_fields.
Use synthetic or consented local examples. Paths are relative to the manifest.
"""
from collections import Counter, defaultdict
from pathlib import Path
import argparse
import json

from backend.app.services.document_extraction import OCRUnavailable, extract_document


def evaluate(manifest):
    scores = defaultdict(Counter)
    for sample in json.loads(manifest.read_text()):
        language = sample.get("language", "en")
        expected = sample["expected_fields"]
        try:
            extracted = extract_document((manifest.parent / sample["file"]).read_bytes(),
                                         sample["content_type"], sample["document_type"], language)["fields"]
        except OCRUnavailable:
            scores["reader"][language + "_unavailable"] += 1
            extracted = {}
        for field in expected.keys() | extracted.keys():
            tally = scores[language + "/" + field]
            item = extracted.get(field)
            if field not in expected:
                tally["unexpected"] += 1
            elif item is None:
                tally["missed"] += 1
            elif item.value == expected[field]:
                tally["exact"] += 1
            else:
                tally["incorrect"] += 1
    return dict(scores)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    print(json.dumps(evaluate(parser.parse_args().manifest), indent=2))
