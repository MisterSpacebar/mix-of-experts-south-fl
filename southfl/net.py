"""Bounded HTTPS-only agency API reads (no secrets in URLs or logs)."""
import csv
import io
import json
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

MAX_BYTES = 18_000_000


class AcquisitionError(RuntimeError):
    pass


def get_bytes(url, max_bytes=MAX_BYTES):
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise AcquisitionError("source URL must use HTTPS")
    req = urllib.request.Request(url, headers={
        "User-Agent": "southfl-fcm-research/0.2 (agency metadata inventory)",
        "Accept": "application/json, text/csv, application/xml, text/xml, */*",
    })
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            if urllib.parse.urlparse(response.url).scheme != "https":
                raise AcquisitionError("redirect to non-HTTPS URL blocked")
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise AcquisitionError(f"response exceeds {max_bytes} bytes; query smaller area")
            return data
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise AcquisitionError(f"request failed ({type(exc).__name__}) for {parsed.netloc}") from exc


def get_json(url):
    try:
        return json.loads(get_bytes(url).decode("utf-8-sig"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise AcquisitionError("expected JSON; check agency endpoint or access") from exc


def get_csv(url):
    data = get_bytes(url)
    try:
        return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    except UnicodeError as exc:
        raise AcquisitionError("expected UTF-8 CSV") from exc


def get_xml(url):
    try:
        return ET.fromstring(get_bytes(url))
    except ET.ParseError as exc:
        raise AcquisitionError("expected XML") from exc


def url_with_params(base, params):
    return base + "?" + urllib.parse.urlencode(params)


def write_csv(path, rows, columns):
    from pathlib import Path
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
