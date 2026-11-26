"""Select promising same-site USGS multivariable panels from verified metadata.

The choice is metadata-scored, not a claim of observed overlap or readiness.
Do not combine sites or geodetic datums based on rough region rectangles.
"""
from collections import defaultdict
from datetime import date,timedelta

PLAN_COLS=["panel_id","region","dataset_id","site_id","concept","parameter_code",
           "series_id","unit","vertical_datum","start_date","end_date","mode",
           "metadata_start","metadata_end","selection_status"]

# Meaningfully different first-pass physical states; conductivity and salinity
# may still be highly collinear, assessed during the model QA stage.
CONCEPT_ORDER=["dissolved_oxygen","discharge","salinity",
               "water_temperature","gage_height","specific_conductance",
               "stream_stage_elevation","groundwater_elevation",
               "water_velocity","precipitation","ph"]


def select_panels(periods,stations,end_date,days=120,max_panels=3,
                  max_concepts=4,min_concepts=3,site_filter=None,
                  exclude_sites=None,max_per_region=None,region_filter=None):
    end=date.fromisoformat(end_date)
    begin=end-timedelta(days=days-1)
    if not 60<=days<=366:
        raise ValueError("history must span between 60 and 366 days")
    if not 1<=max_panels<=8 or not 2<=min_concepts<=max_concepts<=8:
        raise ValueError("bad panel or concept caps")
    if max_per_region is not None and not 1<=max_per_region<=8:
        raise ValueError("max_per_region must be 1..8")
    excluded=set(exclude_sites or ())
    selected_regions=set(region_filter or ())
    if selected_regions:
        from .regions import REGIONS
        if not selected_regions.issubset(REGIONS):
            raise ValueError("region filter contains unknown discovery region")
    sites={(s["dataset_id"],s["site_id"]):s for s in stations}
    candidates=defaultdict(lambda:defaultdict(list))
    for r in periods:
        if r.get("dataset_id")!="usgs_water":
            continue
        site=r["site_id"]
        if site in excluded:
            continue
        if site_filter and site not in site_filter:
            continue
        if ("usgs_water",site) not in sites or r.get("concept") not in CONCEPT_ORDER:
            continue
        code=r.get("parameter_code","")
        if len(code)!=5 or not code.isdigit() or not r.get("series_id"):
            continue
        if r.get("evidence")!="time_series_first_last_metadata":
            continue
        try:
            first=date.fromisoformat(r["begin_utc"][:10])
            last=date.fromisoformat(r["end_utc"][:10])
        except (ValueError,KeyError):
            continue
        if first>begin or last<end:
            continue
        # Never select multiple units for the same concept automatically.
        candidates[site][r["concept"]].append(r)

    scored=[]
    for site,groups in candidates.items():
        chosen={}
        for concept,options in groups.items():
            # Choose primary/longest source series deterministically.
            # Multiple candidate series remain available in source metadata,
            # while the downloaded stream is checked against the selected ID.
            options=sorted(options,key=lambda r:(
                str(r.get("primary_status","")).lower() not in ("primary","true","1"),
                r.get("sublocation_identifier","") not in ("","main"),
                r["begin_utc"],r["series_id"]))
            chosen[concept]=options[0]
        if len(chosen)<min_concepts:
            continue
        ordered=sorted(chosen,key=lambda c:CONCEPT_ORDER.index(c))
        # Avoid selecting salinity and conductance simultaneously where possible,
        # as both approximate dissolved salts, but do not claim they are identical.
        if "salinity" in ordered and "specific_conductance" in ordered and len(ordered)>max_concepts:
            ordered.remove("specific_conductance")
        ordered=ordered[:max_concepts]
        if len(ordered)<min_concepts:
            continue
        site_meta=sites[("usgs_water",site)]
        regions=[x for x in site_meta.get("regions","").split(";") if x]
        if not regions:
            regions=["unassigned"]
        if selected_regions:
            regions=[r for r in regions if r in selected_regions]
            if not regions:
                continue
        scored.append((len(ordered),len(chosen),site,regions,chosen,ordered))
    # Prefer sites with more independent concepts; balance across regions
    # rather than automatically prioritizing Biscayne.
    scored.sort(key=lambda x:(-x[0],-x[1],x[2]))
    selected,region_counts=[],defaultdict(int)
    for row in scored:
        _,_,site,regions,chosen,ordered=row
        eligible=[region for region in regions
                  if max_per_region is None or
                  region_counts[region]<max_per_region]
        if not eligible:
            continue
        region=min(eligible,key=lambda x:(region_counts[x],x))
        selected.append((site,region,chosen,ordered))
        region_counts[region]+=1
        if len(selected)==max_panels:
            break
    tasks=[]
    for pidx,(site,region,chosen,ordered) in enumerate(selected,1):
        panel_id=f"panel_{pidx:02d}_{site.replace('-','_')}"
        for concept in ordered:
            r=chosen[concept]
            tasks.append(dict(
                panel_id=panel_id,region=region,dataset_id="usgs_water",
                site_id=site,concept=concept,parameter_code=r["parameter_code"],
                series_id=r["series_id"],unit=r.get("unit",""),
                vertical_datum=r.get("vertical_datum",""),
                start_date=begin.isoformat(),end_date=end.isoformat(),
                mode="continuous",metadata_start=r["begin_utc"],
                metadata_end=r["end_utc"],
                selection_status="metadata_candidate_validate_real_observations"))
    return tasks
