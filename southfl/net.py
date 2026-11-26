"""Bounded HTTPS agency requests; USGS authentication is header-only.

USGS_API_KEY is read from the local process environment. Never insert API
credentials in query URLs, saved manifests, logs, exception text, or source
CSV metadata. On USGS 429, respect bounded Retry-After once or twice, then
fail explicitly instead of hammering the endpoint.
"""
import csv
import io
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from datetime import datetime,timezone

MAX_BYTES=18_000_000
USGS_API_HOST="api.waterdata.usgs.gov"

class AcquisitionError(RuntimeError):
    pass

class _USGSRedirect(urllib.request.HTTPRedirectHandler):
    """Never forward private USGS key to another host via redirect."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target=urllib.parse.urlparse(newurl)
        if target.scheme!="https" or target.hostname!=USGS_API_HOST:
            raise AcquisitionError("refused cross-origin USGS API redirect")
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def _retry_seconds(raw,attempt,max_seconds=15):
    if raw:
        raw=str(raw).strip()
        try:
            seconds=float(raw)
        except ValueError:
            try:
                dt=parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt=dt.replace(tzinfo=timezone.utc)
                seconds=(dt-datetime.now(timezone.utc)).total_seconds()
            except (ValueError,TypeError,OverflowError):
                seconds=0
        if seconds>max_seconds:
            return None
        if seconds>0:
            return seconds
    return min(max_seconds,2.0*(attempt+1))

def get_bytes(url,max_bytes=MAX_BYTES):
    parsed=urllib.parse.urlparse(url)
    if parsed.scheme!="https":
        raise AcquisitionError("source URL must use HTTPS")
    usgs=parsed.hostname==USGS_API_HOST
    headers={
        "User-Agent":"southfl-fcm-research/0.3 (source audit, bounded acquisition)",
        "Accept":"application/json, text/csv, application/xml, text/xml, */*",
    }
    if usgs:
        key=os.environ.get("USGS_API_KEY","").strip()
        if key:
            if any(x in key for x in ("\r","\n")):
                raise AcquisitionError("USGS_API_KEY contains invalid line breaks")
            headers["X-Api-Key"]=key
    req=urllib.request.Request(url,headers=headers)
    opener=urllib.request.build_opener(_USGSRedirect()) if usgs else urllib.request.build_opener()
    for attempt in range(3 if usgs else 1):
        try:
            with opener.open(req,timeout=60) as response:
                target=urllib.parse.urlparse(response.url)
                if target.scheme!="https":
                    raise AcquisitionError("redirect to non-HTTPS URL blocked")
                if usgs and target.hostname!=USGS_API_HOST:
                    raise AcquisitionError("USGS response redirected to another host")
                data=response.read(max_bytes+1)
                if len(data)>max_bytes:
                    raise AcquisitionError(f"response exceeds {max_bytes} bytes; shorten request")
                return data
        except urllib.error.HTTPError as exc:
            if usgs and exc.code==429:
                if attempt>=2:
                    raise AcquisitionError("USGS HTTP 429 rate limit after bounded retries; "
                                           "check USGS_API_KEY and wait for reset") from exc
                pause=_retry_seconds(exc.headers.get("Retry-After"),attempt)
                if pause is None:
                    raise AcquisitionError("USGS HTTP 429: Retry-After exceeds 15 seconds; "
                                           "stop rather than hammering service") from exc
                time.sleep(pause)
                continue
            raise AcquisitionError(f"HTTP {exc.code} for {parsed.netloc}") from exc
        except (urllib.error.URLError,TimeoutError) as exc:
            raise AcquisitionError(f"request failed ({type(exc).__name__}) "
                                   f"for {parsed.netloc}") from exc

def get_json(url):
    try:
        return json.loads(get_bytes(url).decode("utf-8-sig"))
    except (UnicodeError,json.JSONDecodeError) as exc:
        raise AcquisitionError("expected JSON; check agency endpoint or access") from exc

def get_csv(url):
    data=get_bytes(url)
    try:
        return list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    except UnicodeError as exc:
        raise AcquisitionError("expected UTF-8 CSV") from exc

def get_xml(url):
    try:
        return ET.fromstring(get_bytes(url))
    except ET.ParseError as exc:
        raise AcquisitionError("expected XML") from exc

def url_with_params(base,params):
    return base+"?"+urllib.parse.urlencode(params)

def write_csv(path,rows,columns):
    from pathlib import Path
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("w",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=columns,extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
