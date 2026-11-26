"""M9 geographic readiness: real-source structure, no fabricated spatial FCMs."""
import hashlib
import json
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from xml.etree import ElementTree

from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.regions import REGIONS
from southfl.panels import PANEL_SUMMARY_COLS
from southfl.sources import STATION_COLUMNS
from southfl.m9_regions import (
    station_evidence,station_lookup,pair_evidence,summarize_scope,longest_streak,
    STATION_COLS,PAIR_COLS,SCOPE_COLS)
from scripts.build_m9_region_readiness import run as regional_run


def make_panel(folder,site,region,offset=0,n=120):
    pid="panel_"+site.replace("-","_")
    start=date(2026,5,1)+timedelta(days=offset)
    observations=[]
    for i in range(n):
        observations.append(dict(
            date=(start+timedelta(days=i)).isoformat(),
            site_id=site,panel_id=pid,
            discharge=30+i*.1,salinity=12+i*.01,
            gage_height=4+i*.005))
    write_csv(folder/(pid+".csv"),observations,
              ["date","site_id","panel_id","discharge","salinity","gage_height"])
    row=dict(panel_id=pid,region=region,site_id=site,
        concepts="discharge;salinity;gage_height",
        concept_units="discharge=ft^3/s;salinity=ppt;gage_height=ft",
        concept_datums="discharge=;salinity=;gage_height=",
        source_series_ids="discharge=d1;salinity=s1;gage_height=g1",
        n_requested_days=n,n_complete_days=n,n_consecutive_daily_pairs=n-1,
        n_dropped_partial_days=0,n_excluded_source_values=0,
        first_complete_day=observations[0]["date"],
        last_complete_day=observations[-1]["date"],
        status="candidate_for_held_out_evaluation",
        reason="synthetic observed-only fixture")
    return row,observations


def setup_fixture(root,metadata=True):
    panel_root=root/"panels";panel_root.mkdir()
    models=root/"models";models.mkdir()
    sources=[
        ("USGS-A","big_cypress",0),
        ("USGS-B","big_cypress",20),
        ("USGS-C","north_biscayne",15),
    ]
    rows=[];registry=[]
    for site,region,offset in sources:
        meta,observations=make_panel(panel_root,site,region,offset)
        rows.append(meta)
        pid=meta["panel_id"]
        relative=f"levels/dataset/{pid}"
        output=models/relative
        (output/"visuals").mkdir(parents=True)
        (output/"fcm_model.json").write_text('{"method":"fixture"}')
        (output/"FINDINGS.md").write_text("station findings")
        (output/"DATA.md").write_text("observed USGS source")
        (output/"visuals/network.svg").write_text(
            '<svg xmlns="http://www.w3.org/2000/svg"/>')
        data=(panel_root/(pid+".csv")).read_bytes()
        registry.append(dict(
            panel_id=pid,site_id=site,region=region,
            level="dataset",category="",subcategory="",
            status="trained_station_expert",model_directory=relative,
            panel_sha256=hashlib.sha256(data).hexdigest(),
        ))
    write_csv(panel_root/"panel_readiness.csv",rows,PANEL_SUMMARY_COLS)
    (panel_root/"panels_manifest.json").write_text(json.dumps(
        {"observations_sha256":"0"*64,"synthetic_only":True}))
    write_csv(models/"model_registry.csv",registry,
              ["panel_id","site_id","region","level","category","subcategory",
               "status","model_directory","panel_sha256"])
    (models/"manifest.json").write_text('{"synthetic_only":true}')
    station_file=root/"stations.csv"
    if metadata:
        station_rows=[]
        for site,lat,lon in [
            ("USGS-A",25.88,-81.51),
            ("USGS-B",25.89,-81.45),
            ("USGS-C",25.89,-80.21),
        ]:
            station_rows.append(dict(
                dataset_id="usgs_water",provider="USGS",site_id=site,
                site_name=site,latitude=lat,longitude=lon,
                regions="",source_url="https://waterdata.usgs.gov/",
                retrieved_at_utc="2026-11-24T00:00:00Z",
                location_type="monitoring location",coverage_status="metadata_only"))
        write_csv(station_file,station_rows,STATION_COLUMNS)
    return panel_root,models,station_file


class GeographicReadinessTests(unittest.TestCase):
    def test_consecutive_overlap_and_unverified_stage_reference(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);root.mkdir(exist_ok=True)
            a,obs=make_panel(root,"USGS-A","big_cypress",0,110)
            b,ob2=make_panel(root,"USGS-B","big_cypress",20,110)
            inventory=station_lookup([
                dict(dataset_id="usgs_water",site_id="USGS-A",
                     latitude=25.88,longitude=-81.5),
                dict(dataset_id="usgs_water",site_id="USGS-B",
                     latitude=25.9,longitude=-81.45),
            ])
            sa=station_evidence(a,obs,inventory)
            sb=station_evidence(b,ob2,inventory)
            result=pair_evidence(sa,sb)
            self.assertEqual(result["n_common_observed_days"],90)
            self.assertEqual(result["longest_consecutive_overlap_days"],90)
            self.assertEqual(result["n_compatible_concepts"],2)
            self.assertEqual(result["unverified_datum_concepts"],"gage_height")
            self.assertEqual(result["connectivity_status"],
                             "not_assessed_by_bbox_or_station_distance")
            scope=summarize_scope("big_cypress","region","all_environmental_categories",
                                  [sa,sb],[],[result],min_sites=2,
                                  min_overlap_days=79)
            self.assertEqual(scope["readiness_status"],
                             "candidate_for_connectivity_and_spatial_holdout_review")
            self.assertEqual(scope["regional_fcm_status"],"NOT_TRAINED")
            self.assertFalse(scope["has_verified_hydrological_connectivity"])
            no_coords=station_evidence(a,obs)
            p=pair_evidence(no_coords,sb)
            blocked=summarize_scope("big_cypress","region","all_environmental_categories",
                                    [no_coords,sb],[],[p],2,79)
            self.assertEqual(blocked["readiness_status"],
                             "coordinate_verification_required")

    def test_no_auto_assigning_a_station_to_multiple_rectangles(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a,obs=make_panel(root,"USGS-A","big_cypress")
            item=station_evidence(a,obs,station_lookup([
                dict(dataset_id="usgs_water",site_id="USGS-A",
                     latitude=25.9,longitude=-81.5)]))
            self.assertEqual(item["region"],"big_cypress")
            self.assertIn("big_cypress",item["candidate_discovery_regions"])
            self.assertEqual(item["screening_region_basis"],
                             "existing_panel_plan_discovery_region_not_watershed")

    def test_mismatched_region_and_same_site_pairs_fail(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);a,obs=make_panel(root,"USGS-A","big_cypress")
            b,ob2=make_panel(root,"USGS-B","north_biscayne")
            sa,sb=station_evidence(a,obs),station_evidence(b,ob2)
            with self.assertRaisesRegex(ValueError,"same selected screening region"):
                pair_evidence(sa,sb)
            with self.assertRaisesRegex(ValueError,"not independent"):
                pair_evidence(sa,sa)
            obs[0]["site_id"]="USGS-WRONG"
            with self.assertRaisesRegex(ValueError,"mismatched"):
                station_evidence(a,obs)

    def test_conflicting_geolocations_quarantined(self):
        a=dict(dataset_id="usgs_water",site_id="USGS-A",
               latitude=25.9,longitude=-81.5)
        b=dict(a,longitude=-80.3)
        with self.assertRaisesRegex(ValueError,"conflicting canonical"):
            station_lookup([a,b])


class GeographicBrowserTests(unittest.TestCase):
    def test_full_region_browser_preserves_source_models(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            panels,models,stations=setup_fixture(root)
            preserved=(models/"manifest.json").read_bytes()
            out=root/"regional"
            result=regional_run(models,[panels],out,stations,
                                min_sites=2,min_overlap_days=79,dpi=65)
            self.assertEqual(result["n_screening_regions"],len(REGIONS))
            self.assertEqual(result["n_distinct_source_sites"],3)
            self.assertEqual(result["n_regions_with_an_observed_station"],2)
            self.assertEqual(result["n_within_region_independent_station_pairs"],1)
            self.assertEqual(result["n_trained_geographic_region_fcms"],0)
            self.assertEqual((models/"manifest.json").read_bytes(),preserved)
            b=out/"regions/big_cypress"
            for p in [
                out/"INDEX.md",
                out/"region_index.csv",
                out/"region_scope_readiness.csv",
                out/"within_region_pairs.csv",
                out/"visuals/regional_station_coverage.png",
                b/"FINDINGS.md",b/"station_overlap_pairs.csv",
                b/"visuals/observed_station_concept_graph.svg",
                b/"visuals/observed_daily_timeline.png",
                b/"visuals/discovery_rectangle.png",
                b/"subsystems/hydrology/FINDINGS.md",
                b/"subsystems/hydrology/surface_flow/FINDINGS.md",
                out/"regions/florida_bay/FINDINGS.md",
                out/"regions/florida_bay/visuals/observed_station_concept_graph.svg",
                out/"regions/florida_bay/subsystems/ecology/FINDINGS.md",
            ]:
                self.assertTrue(p.exists(),str(p))
            ElementTree.parse(b/"visuals/observed_station_concept_graph.svg")
            text=(b/"visuals/observed_station_concept_graph.svg").read_text()
            self.assertIn("NOT TRAINED",text)
            self.assertIn("NOT an FCM",text.replace("not fitted edges","NOT an FCM"))
            rows=read_csv(out/"region_index.csv")
            b_row=next(r for r in rows if r["region"]=="big_cypress")
            self.assertEqual(b_row["n_distinct_stations"],"2")
            self.assertEqual(b_row["region_readiness"],
                             "candidate_for_connectivity_and_spatial_holdout_review")
            untrained=next(r for r in rows if r["region"]=="florida_bay")
            self.assertEqual(untrained["region_readiness"],
                             "no_observed_station_panels")
            with self.assertRaisesRegex(ValueError,"new or empty"):
                regional_run(models,[panels],out,stations,dpi=65)

    def test_committed_three_station_snapshot_if_available(self):
        root=Path(__file__).resolve().parents[1]
        models=root/"data/m8/layers_replication_v1"
        panels=[root/"data/m7/daily_panels_verified_01",
                root/"data/m8/replication_daily_01"]
        required=[models/"model_registry.csv",models/"manifest.json"]+[
            p/"panel_readiness.csv" for p in panels]
        if not all(p.exists() for p in required):
            self.skipTest("committed three-station source files not available")
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"m9"
            report=regional_run(models,panels,out,dpi=65)
            self.assertEqual(report["n_distinct_source_sites"],3)
            self.assertEqual(report["n_regions_with_an_observed_station"],3)
            self.assertEqual(report["n_within_region_independent_station_pairs"],0)
            self.assertEqual(report["n_trained_geographic_region_fcms"],0)
            self.assertEqual(len(read_csv(out/"region_index.csv")),len(REGIONS))
            for region in ("big_cypress","southwest_everglades_coast",
                           "central_south_biscayne"):
                rows=read_csv(out/"region_index.csv")
                row=next(r for r in rows if r["region"]==region)
                self.assertEqual(row["n_distinct_stations"],"1")
                self.assertEqual(row["region_readiness"],
                                 "one_station_only_no_regional_model")

    def test_duplicate_snapshot_same_site_not_counted_as_independent(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);panels,models,stations=setup_fixture(root)
            rows=read_csv(panels/"panel_readiness.csv")
            row=next(r for r in rows if r["site_id"]=="USGS-A")
            another=dict(row,panel_id="panel_DUPLICATE")
            write_csv(panels/"panel_readiness.csv",rows+[another],
                      PANEL_SUMMARY_COLS)
            with self.assertRaisesRegex(ValueError,"dataset models and daily"):
                regional_run(models,[panels],root/"out",dpi=65)


if __name__=="__main__":
    unittest.main()
