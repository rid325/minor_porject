"""Snapshot official references and queue changes for editorial review."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


import httpx


def fingerprint(url):
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=10) as response:
            response.raise_for_status()
            digest = hashlib.sha256()
            size = 0
            for chunk in response.iter_bytes():
                size += len(chunk)
                if size > 32_000_000:
                    raise ValueError("reference exceeds 32 MB")
                digest.update(chunk)
            return {"sha256": digest.hexdigest(), "destination": str(response.url)}
    except (httpx.HTTPError, ValueError) as exc:
        return {"error": str(exc)}


def discover():
    # District scheme directories publish ordinary links, including scheme detail pages.
    urls = set()
    errors = []
    for host in ("hpshimla.nic.in", "chandigarh.gov.in", "gurugram.gov.in", "ludhiana.nic.in"):
        directory = f"https://{host}/scheme/"
        found = set()
        try:
            response = httpx.get(directory, timeout=12, follow_redirects=True)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            errors.append({"feed": directory, "discovery_error": str(exc)})
            continue
        for url in re.findall(r'href=["\']([^"\']+)["\']', response.text):
            url = str(response.url.join(url))
            if urlsplit(url).hostname == host and re.fullmatch(r"/scheme/[^/]+/?", urlsplit(url).path):
                found.add(url)
        if not found:
            errors.append({"feed": directory, "discovery_error": "No scheme links found"})
        urls.update(found)
    return sorted(urls), errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    directory = parser.parse_args().directory
    directory.mkdir(parents=True, exist_ok=True)
    state = directory / "baseline.json"
    previous = json.loads(state.read_text()) if state.exists() else {}
    schemes = json.loads((Path(__file__).resolve().parents[1] / "data/schemes.seed.json").read_text())["schemes"]
    refs = {}
    for scheme in schemes:
        for field in ("source_url", "additional_sources", "application_url"):
            for url in re.split(r"[|;]\s*(?=https?://)", scheme.get(field) or ""):
                if url.strip().startswith(("https://", "http://")):
                    refs.setdefault(url.strip(), set()).add(scheme["scheme_id"])
    baseline = previous.get("sources", {})
    queue = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for url, result in zip(refs, pool.map(fingerprint, refs)):
            if "error" in result or (url in baseline and baseline[url] != result):
                queue.append({"url": url, "schemes": sorted(refs[url]), **result})
            if "error" not in result:
                baseline[url] = result
    known = previous.get("discovered", [])
    discovered, errors = discover()
    queue.extend(errors)
    candidates = sorted(set(discovered) - set(known) - refs.keys())
    (directory / "review.json").write_text(json.dumps({"reference_changes": queue, "discovery_candidates": candidates}, indent=2))
    temp = state.with_suffix(".tmp")
    temp.write_text(json.dumps({"sources": baseline, "discovered": sorted(set(known) | set(discovered))}))
    temp.replace(state)
    print(f"{len(refs)} references checked, {len(queue)} issues, {len(candidates)} discovery candidates")


if __name__ == "__main__":
    main()
