"""Metadata-only recruitment and immutable resumable stage execution."""
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from .regions import regions_for
from .historical import windows

CORE=("salinity","water_temperature")
CODES={"salinity":"00480","water_temperature":"00010"}
UNITS={"salinity":"ppt","water_temperature":"degC"}
EXTRAS=("dissolved_oxygen","discharge","gage_height","specific_conductance")
EXTRA_COLS=["statistic_id","sublocation_identifier","primary_status"]


def sha(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for chunk in iter(lambda:f.read(1024*1024),b""):
            h.update(chunk)
    return h.hexdigest()


def json_at(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def save(p,value):
    p=Path(p)
    tmp=p.with_suffix(p.suffix+".tmp")
    tmp.write_text(json.dumps(value,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    tmp.replace(p)


def choose(stations,periods,regions,start,end,excluded,per_region=6,max_concepts=4):
    if not 1<=per_region<=6 or not 2<=max_concepts<=4:
        raise ValueError("invalid recruitment quotas")
    sites={}
    for r in stations:
        site=r.get("site_id","")
        if r.get("dataset_id")!="usgs_water" or not re.fullmatch(r"USGS-[0-9]{8,15}",site):
            continue
        if site in excluded:
            continue
        membership=set(regions_for(r.get("latitude"),r.get("longitude")))&set(regions)
        if not membership:
            continue
        if site in sites and (r["latitude"],r["longitude"])!=(sites[site]["latitude"],sites[site]["longitude"]):
            raise ValueError("conflicting station coordinates")
        sites[site]=r
    options=defaultdict(lambda:defaultdict(dict))
    conflicts=set()
    for r in periods:
        site,c=r.get("site_id"),r.get("concept")
        if (site not in sites or r.get("dataset_id")!="usgs_water" or
            c not in CORE+EXTRAS or r.get("evidence")!="time_series_first_last_metadata" or
            r.get("statistic_id")!="00011" or not r.get("series_id") or
            not re.fullmatch(r"[0-9]{5}",r.get("parameter_code","")) or not r.get("unit")):
            continue
        if c in CORE and (r["parameter_code"]!=CODES[c] or r["unit"]!=UNITS[c]):
            continue
        try:
            if date.fromisoformat(r["begin_utc"][:10])>date.fromisoformat(start) or date.fromisoformat(r["end_utc"][:10])<date.fromisoformat(end):
                continue
        except (KeyError,ValueError):
            continue
        sid=r["series_id"]; key=site,c,sid
        previous=options[site][c].get(sid)
        fields=("parameter_code","unit","vertical_datum","statistic_id","sublocation_identifier","primary_status","begin_utc","end_utc")
        if previous and any(previous.get(k)!=r.get(k) for k in fields):
            conflicts.add(key)
        options[site][c][sid]=r
    candidates=[]
    for site,groups in sorted(options.items()):
        selected={}
        for c,group in groups.items():
            items=[r for sid,r in group.items() if (site,c,sid) not in conflicts]
            if not items:
                continue
            selected[c]=min(items,key=lambda r:(
                c in CORE and r.get("sublocation_identifier","").strip().casefold()!="near bottom",
                r.get("primary_status","").lower() not in ("primary","true","1"),
                r["begin_utc"],r["series_id"]))
        if not all(c in selected for c in CORE):
            continue
        cs=list(CORE)+[c for c in EXTRAS if c in selected]
        near=all(selected[c].get("sublocation_identifier","").strip().casefold()=="near bottom" for c in CORE)
        membership=[r for r in regions if r in regions_for(sites[site]["latitude"],sites[site]["longitude"])]
        candidates.append(dict(site_id=site,site_name=sites[site].get("site_name",""),
             latitude=sites[site]["latitude"],longitude=sites[site]["longitude"],
             membership=membership,near_bottom_metadata=near,concepts=cs[:max_concepts],sources=selected))
    # Round-robin allocation; one canonical station appears only once.
    chosen={}; counts=defaultdict(int)
    while True:
        progress=False
        for region in regions:
            if counts[region]>=per_region:
                continue
            available=[x for x in candidates if x["site_id"] not in chosen and region in x["membership"]]
            if not available:
                continue
            x=min(available,key=lambda x:(not x["near_bottom_metadata"],-len(x["concepts"]),x["site_id"]))
            chosen[x["site_id"]]=region; counts[region]+=1; progress=True
        if not progress:
            break
    plan=[]; shortlist=[]
    for x in candidates:
        site=x["site_id"]; region=chosen.get(site,"")
        shortlist.append(dict(site_id=site,site_name=x["site_name"],latitude=x["latitude"],longitude=x["longitude"],
            screening_regions=";".join(x["membership"]),selected_region=region,
            near_bottom_metadata=x["near_bottom_metadata"],concepts=";".join(x["concepts"]),
            status="metadata_only_not_observed"))
        if not region:
            continue
        for c in x["concepts"]:
            r=x["sources"][c]
            plan.append(dict(panel_id="m11_"+site.replace("-","_"),region=region,dataset_id="usgs_water",
                site_id=site,concept=c,parameter_code=r["parameter_code"],series_id=r["series_id"],
                unit=r["unit"],vertical_datum=r.get("vertical_datum",""),start_date=start,end_date=end,
                mode="continuous",metadata_start=r["begin_utc"],metadata_end=r["end_utc"],
                selection_status="metadata_candidate_validate_real_observations",
                **{k:r.get(k,"") for k in EXTRA_COLS}))
    if len({(r["site_id"],r["series_id"]) for r in plan})!=len(plan):
        raise ValueError("duplicate selected source series")
    return plan,shortlist


def request_count(plan):
    return sum(len(list(windows(r["start_date"],r["end_date"]))) for r in plan)


class Stages:
    """Hash checkpoints, preserve failed attempts, never silently overwrite."""
    def __init__(self,root,config,resume):
        self.root=Path(root); self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/"checkpoint.json"
        if self.path.exists():
            if not resume:
                raise ValueError("existing run; use --resume")
            self.state=json_at(self.path)
            if self.state["config"]!=config:
                raise ValueError("frozen configuration changed; use a new output root")
        else:
            if any(self.root.iterdir()):
                raise ValueError("nonempty output without checkpoint")
            self.state={"config":config,"stages":{}}
            save(self.path,self.state)

    def run(self,key,action,check=lambda _:True,dependencies=()):
        stages=self.state["stages"]
        deps={d:stages[d]["files"] for d in dependencies}
        if any(stages[d]["status"]!="complete" for d in dependencies):
            raise ValueError("incomplete dependency")
        old=stages.get(key)
        if old and old["status"]=="complete":
            if old["dependencies"]!=deps:
                raise ValueError("stage dependencies changed")
            p=self.root/old["path"]
            if self.hashes(p)!=old["files"]:
                raise ValueError("completed checkpoint hash changed: "+key)
            print("REUSE",key,flush=True)
            return p
        n=1 if old is None else old["attempt"]+1
        p=self.root/"stages"/key/f"attempt_{n:02d}"
        if p.exists():
            raise ValueError("attempt directory already exists")
        stages[key]={"status":"running","attempt":n,"path":p.relative_to(self.root).as_posix(),"dependencies":deps}
        save(self.path,self.state)
        print("RUN",key,flush=True)
        try:
            result=action(p)
            if not check(result):
                raise RuntimeError("stage validation failed: "+key)
            files=self.hashes(p)
            if not files:
                raise ValueError("empty stage output")
            stages[key].update(status="complete",files=files)
        except BaseException:
            stages[key]["status"]="failed"
            save(self.path,self.state)
            raise
        save(self.path,self.state)
        return p

    @staticmethod
    def hashes(p):
        return {f.relative_to(p).as_posix():sha(f) for f in sorted(p.rglob("*")) if f.is_file()}

    def verify_all(self):
        for k,v in self.state["stages"].items():
            if v["status"]=="complete" and self.hashes(self.root/v["path"])!=v["files"]:
                raise ValueError("completed checkpoint hash changed: "+k)
