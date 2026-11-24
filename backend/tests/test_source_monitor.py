import httpx

from backend.scripts import monitor_sources


def test_partial_discovery_reports_failed_and_empty_directories(monkeypatch):
    def fetch(url, **kwargs):
        request = httpx.Request("GET", url)
        if "gurugram" in url:
            raise httpx.ConnectError("offline", request=request)
        markup = '<a href="/scheme/example/">example</a>' if "ludhiana" in url else ""
        return httpx.Response(200, text=markup, request=request)

    monkeypatch.setattr(monitor_sources.httpx, "get", fetch)
    found, errors = monitor_sources.discover()
    assert found == ["https://ludhiana.nic.in/scheme/example/"]
    assert {httpx.URL(entry["feed"]).host for entry in errors} == {
        "hpshimla.nic.in", "chandigarh.gov.in", "gurugram.gov.in",
    }
