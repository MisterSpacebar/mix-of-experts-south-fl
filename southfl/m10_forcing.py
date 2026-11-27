"""Bounded observed forcing acquisition; regional proxies, not local causal drivers."""
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from math import isfinite
from pathlib import Path
from statistics import mean

from .net import get_json, url_with_params, write_csv, AcquisitionError
from .audit import read_csv
from .temporal_integrity import verify_historical_hash

WEATHER_ID="USW00012897"
TIDE_ID="8725520"  # Fort Myers; Naples inventory is historical/inactive
WEATHER=("rain_mm","wind_ms","air_tmin_c","air_tmax_c")
TIDE=("coastal_level_mean_m","coastal_level_range_m")
FEATURES={"weather":WEATHER,"weather_water_level":WEATHER+TIDE}
START="2026-05-27"
END="2026-11-20"
COLS=["target_date","weather_source_date","water_level_source_date",*WEATHER,*TIDE]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def dates(start,end):
    d=date.fromisoformat(start)
    while d<=date.fromisoformat(end):
        yield d
        d+=timedelta(days=1)


def number(v):
    try:
        v=float(v)
        return v if isfinite(v) and v!=-9999 else None
    except (TypeError,ValueError):
        return None


def weather_rows(raw,start=START,end=END):
    if not isinstance(raw,list):
        raise ValueError("expected NCEI daily-summaries list")
    result={}
    for r in raw:
        d=r["DATE"]
        date.fromisoformat(d)
        if r["STATION"]!=WEATHER_ID or not start<=d<=end or d in result:
            raise ValueError("unexpected or duplicate weather station/date")
        row={}
        for code,name in zip(("PRCP","AWND","TMIN","TMAX"),WEATHER):
            v=number(r.get(code))
            flags=str(r.get(code+"_ATTRIBUTES","")).split(",")
            # NCEI daily attributes M,Q,S[,time]. Missing Q metadata is
            # not silently interpreted as passing QA.
            if len(flags)<3 or flags[1].strip() or v is None:
                continue
            if code in ("PRCP","AWND") and v<0:
                continue
            if code=="PRCP" and flags[0].strip().upper()=="P":
                continue  # missing precipitation presumed zero is not observed zero
            row[name]=v
        if all(k in row for k in WEATHER[-2:]) and row[WEATHER[-2]]>row[WEATHER[-1]]:
            raise ValueError("inverted air temperature extrema")
        result[d]=row
    return result


def tide_rows(raw,start,end):
    if not isinstance(raw,dict) or raw.get("error"):
        raise AcquisitionError("CO-OPS response has no usable observations")
    if str(raw.get("metadata",{}).get("id"))!=TIDE_ID:
        raise ValueError("unexpected CO-OPS station")
    result={}
    seen=set()
    for r in raw["data"]:
        stamp=datetime.strptime(r["t"],"%Y-%m-%d %H:%M")
        d=stamp.date().isoformat()
        if not start<=d<=end or stamp in seen or stamp.minute%6:
            raise ValueError("unexpected, duplicate or off-grid coastal level")
        seen.add(stamp)
        v=number(r.get("v"))
        flags=str(r.get("f","")).split(",")
        if v is None or r.get("q") not in ("p","v") or not flags or any(f.strip()!="0" for f in flags):
            continue
        result.setdefault(d,[]).append((stamp,v))
    out={}
    for d,values in result.items():
        if len(values)>=192 and (max(x[0] for x in values)-min(x[0] for x in values)).total_seconds()>=20*3600:
            v=[x[1] for x in values]
            out[d]={TIDE[0]:mean(v),TIDE[1]:max(v)-min(v)}
    return out


def assemble(weather,tide):
    rows=[]
    for day in dates("2026-05-30","2026-11-21"):
        # Target day D is forecast at the UTC day boundary. Weather
        # calendar D-2 (local-day proxy) and coastal UTC D-1 are prior.
        w=(day-timedelta(days=2)).isoformat()
        t=(day-timedelta(days=1)).isoformat()
        rows.append(dict(target_date=day.isoformat(),weather_source_date=w,
                         water_level_source_date=t,**weather.get(w,{}),**tide.get(t,{})))
    return rows


def acquire(out):
    out=Path(out)
    if out.exists() and any(out.iterdir()):
        raise ValueError("new/empty forcing output required")
    out.mkdir(parents=True,exist_ok=True)
    requests=[]
    weather,tide={},{}
    def fetch(name,url,parser):
        record={"file":name,"url":url}
        try:
            raw=get_json(url)
            p=out/name
            p.write_text(json.dumps(raw,indent=2)+"\n",encoding="utf-8")
            record["sha256"]=sha(p)
            parsed=parser(raw)
            record.update(status="success",n_usable_source_days=len(parsed))
            return parsed
        except (AcquisitionError,ValueError,KeyError,TypeError) as exc:
            record.update(status="failed",error=str(exc))
            return {}
        finally:
            requests.append(record)
    url=url_with_params("https://www.ncei.noaa.gov/access/services/data/v1",
        dict(dataset="daily-summaries",stations=WEATHER_ID,startDate=START,endDate=END,
             dataTypes="PRCP,AWND,TMIN,TMAX",units="metric",includeAttributes="true",format="json"))
    weather=fetch("weather.json",url,weather_rows)
    start=date.fromisoformat(START)
    while start<=date.fromisoformat(END):
        stop=min(start+timedelta(days=27),date.fromisoformat(END))
        a,b=start.isoformat(),stop.isoformat()
        url=url_with_params("https://api.tidesandcurrents.noaa.gov/api/prod/datagetter",
            dict(station=TIDE_ID,product="water_level",begin_date=start.strftime("%Y%m%d"),
                 end_date=stop.strftime("%Y%m%d"),datum="MSL",time_zone="gmt",units="metric",
                 application="southfl_fcm_research",format="json"))
        tide.update(fetch(f"level_{a}.json",url,lambda raw,a=a,b=b:tide_rows(raw,a,b)))
        start=stop+timedelta(days=1)
    rows=assemble(weather,tide)
    write_csv(out/"forcing_daily.csv",rows,COLS)
    manifest=dict(weather_station=WEATHER_ID,water_level_station=TIDE_ID,
                  source_window=[START,END],weather_lag_days_from_target=2,
                  coastal_level_lag_days_from_target=1,water_level_datum="MSL",
                  weather_time_basis="source daily calendar label; retrospective lag, not proven publication latency",
                  water_level_time_basis="UTC observed 6-minute levels; provisional or verified; reject nonzero flags",
                  proxy_only=True,as_issued_availability_verified=False,
                  requests=requests,forcing_sha256=sha(out/"forcing_daily.csv"),
                  coverage={k:sum(all(x in r for x in fs) for r in rows) for k,fs in FEATURES.items()})
    (out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest


def load(out):
    out=Path(out)
    m=json.loads((out/"manifest.json").read_text(encoding="utf-8"))
    if (m["weather_station"]!=WEATHER_ID or m["water_level_station"]!=TIDE_ID
            or m["source_window"]!=[START,END] or m["water_level_datum"]!="MSL"):
        raise ValueError("forcing source identity changed")
    verify_historical_hash(out/"forcing_daily.csv",m["forcing_sha256"])
    # Rebuild features from successful source payloads, not edited CSV values.
    weather,tide={},{}
    for r in m["requests"]:
        if r["status"]!="success":
            continue
        p=out/r["file"]
        if p.parent!=out or not p.is_file():
            raise ValueError("invalid source payload path")
        verify_historical_hash(p,r["sha256"])
        raw=json.loads(p.read_text(encoding="utf-8"))
        if p.name=="weather.json":
            weather=weather_rows(raw)
        elif p.name.startswith("level_"):
            a=p.stem.removeprefix("level_")
            b=min(date.fromisoformat(a)+timedelta(days=27),date.fromisoformat(END)).isoformat()
            part=tide_rows(raw,a,b)
            if set(part)&set(tide):
                raise ValueError("duplicate source water-level day")
            tide.update(part)
        else:
            raise ValueError("unknown source payload")
    expected=assemble(weather,tide)
    stored=read_csv(out/"forcing_daily.csv")
    if len(expected)!=len(stored):
        raise ValueError("forcing date coverage mismatch")
    result={}
    for a,b in zip(expected,stored):
        if any(str(a.get(k,""))!=b[k] for k in COLS):
            raise ValueError("forcing CSV differs from source reconstruction")
        result[a["target_date"]]={k:a[k] for k in (*WEATHER,*TIDE) if k in a}
    return result,m
