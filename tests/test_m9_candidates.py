"""Tests for M9.1 geographic pair screening and source provenance."""
import hashlib
import json
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from xml.etree import ElementTree

from southfl.audit import read_csv
from southfl.net import write_csv
from southfl.m9_regions import station_evidence
from southfl.m9_candidates import (
    dates_summary,assess_pair,assess_scopes,candidate_regions,
    summarize_discovery_regions,inventory_audit)
from scripts.screen_m9_spatial_candidates import run as screen


def fixture(site,region,lat,lon,start=0,days=100):
    p="panel_"+site.replace("-","_")
    meta={
        "site_id":site,"panel_id":p,"region":region,
        "status":"candidate_for_held_out_evaluation",
        "concepts":"discharge;salinity;water_temperature;gage_height",
        "concept_units":"discharge=ft^3/s;salinity=ppt;water_temperature=degC;gage_height=ft",
        "concept_datums":"discharge=;salinity=;water_temperature=;gage_height=",
        "n_complete_days":days,
        "n_consecutive_daily_pairs":days-1,
    }
    records=[]
    for i in range(days):
        records.append({
            "site_id":site,"panel_id":p,
            "date":(date(2026,7,1)+timedelta(days=i+start)).isoformat(),
            "discharge":"25","salinity":"17","water_temperature":"28",
            "gage_height":"4"})
    info={site:dict(dataset_id="usgs_water",site_id=site,
                    latitude=lat,longitude=lon,site_name=site,
                    source_url="https://api.waterdata.usgs.gov/")}
    return station_evidence(meta,records,info)


class CandidateTests(unittest.TestCase):
    def test_aligned_transitions_accumulate_with_gaps(self):
        first={date(2026,7,1)+timedelta(days=i) for i in range(90)}
        second=first-{date(2026,7,8),date(2026,7,16)}
        result=dates_summary(first,second)
        self.assertEqual(result["n_common_observed_days"],88)
        self.assertEqual(result["n_common_one_day_transitions"],85)
        self.assertEqual(result["longest_contiguous_common_days"],74)

    def test_overlapping_rectangles_do_not_duplicate_site_pairs(self):
        east=fixture("USGS-EAST","big_cypress",25.8953889,-81.4555)
        pumpkin=fixture("USGS-PUMPKIN",
                        "southwest_everglades_coast",25.926,-81.54430556,
                        start=10)
        biscayne=fixture("USGS-BLACK","central_south_biscayne",25.57,
                         -80.3747778)
        pair=assess_pair(east,pumpkin)
        self.assertEqual(pair["n_shared_discovery_regions"],2)
        self.assertEqual(pair["spatial_screening_basis"],
                         "overlapping_discovery_rectangles")
        self.assertTrue(pair["geographic_candidate"])
        self.assertAlmostEqual(pair["distance_km"],9.5,delta=.25)
        self.assertEqual(pair["n_common_observed_days"],90)
        self.assertEqual(pair["n_common_one_day_transitions"],89)
        self.assertEqual(pair["n_compatible_concepts"],3)
        self.assertEqual(pair["datum_unverified_concepts"],"gage_height")
        s=assess_scopes(pair,79,2)
        hydro=next(x for x in s if
                   x["scope_level"]=="category" and x["scope"]=="hydrology")
        wq=next(x for x in s if
                x["scope_level"]=="category" and x["scope"]=="water_quality")
        self.assertEqual(hydro["spatial_candidate_status"],
                         "insufficient_verified_same_unit_concepts")
        self.assertEqual(wq["n_scope_compatible_concepts"],2)
        self.assertEqual(wq["spatial_candidate_status"],
                         "candidate_only_pending_connectivity_and_spatial_validation")
        distant=assess_pair(east,biscayne,max_distance_km=30)
        self.assertFalse(distant["geographic_candidate"])
        whole=[east,pumpkin,biscayne]
        allpairs=[assess_pair(a,b) for a,b in (
            (east,pumpkin),(east,biscayne),(pumpkin,biscayne))]
        allscopes=[x for p in allpairs for x in assess_scopes(p)]
        summary=summarize_discovery_regions(whole,allpairs,allscopes)
        by={r["candidate_region"]:r for r in summary}
        self.assertEqual(by["big_cypress"]["n_unique_screened_station_pairs"],1)
        self.assertEqual(by["southwest_everglades_coast"]["n_unique_screened_station_pairs"],1)
        self.assertEqual(len({p["pair_id"] for p in allpairs}),3)

    def test_no_fake_connectivity_when_station_coordinates_absent(self):
        a=fixture("USGS-A","big_cypress",25.89,-81.45)
        b=fixture("USGS-B","big_cypress",25.91,-81.5)
        a["latitude"]="";a["longitude"]=""
        a["candidate_discovery_regions"]=""
        pair=assess_pair(a,b)
        self.assertTrue(pair["geographic_candidate"])
        self.assertEqual(pair["coordinate_status"],
                         "one_or_both_coordinates_unverified")
        scoped=assess_scopes(pair)
        self.assertTrue(all(x["spatial_candidate_status"]==
                            "source_coordinates_required" for x in scoped))
        self.assertEqual(pair["hydrological_connectivity"],"NOT_VERIFIED")

    def test_skip_legacy_inventory_identifiers_with_audit(self):
        canonical=dict(dataset_id="usgs_water",site_id="USGS-A",
                       latitude="25.9",longitude="-81.5",
                       source_url="https://example.gov/")
        old=dict(canonical,site_id="FL005-02286320")
        resolved,audit=inventory_audit([canonical,old],
                                       required={"USGS-A","USGS-B"})
        self.assertEqual(list(resolved),["USGS-A"])
        self.assertEqual(len(audit),2)
        self.assertEqual(audit[0]["reason"],
                         "alternate_agency_prefixed_identifier_not_a_panel_key")
        self.assertEqual(audit[1]["reason"],
                         "modeled_station_not_resolved_in_coordinate_inventory")
        with self.assertRaisesRegex(ValueError,"conflicting canonical"):
            inventory_audit([canonical,dict(canonical,longitude="-80.9")])


class RealSnapshotTests(unittest.TestCase):
    def test_real_committed_three_site_geometry_and_temporal_counts(self):
        repo=Path(__file__).resolve().parents[1]
        models=repo/"data/m8/layers_replication_v1"
        panels=[
            repo/"data/m7/daily_panels_verified_01",
            repo/"data/m8/replication_daily_01",
        ]
        assignments=repo/"data/m9/regional_readiness_v1_with_coords/station_assignments.csv"
        needed=[models/"manifest.json",models/"model_registry.csv",
                assignments]+[p/"panel_readiness.csv" for p in panels]
        if not all(x.exists() for x in needed):
            self.skipTest("committed 3-site source snapshot not in checkout")
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"review"
            result=screen(models,panels,root,
                          assignments=assignments,dpi=65)
            self.assertEqual(result["n_original_sites"],3)
            self.assertEqual(result["n_unique_independent_station_pairs"],3)
            self.assertEqual(result["n_geographic_screening_candidates"],1)
            self.assertEqual(result["n_unique_pairs_in_shared_rectangles"],1)
            self.assertEqual(result["n_regional_fcms_trained"],0)
            pairs=read_csv(root/"candidate_station_pairs.csv")
            selected=[p for p in pairs if p["geographic_candidate"]=="True"]
            self.assertEqual(len(selected),1)
            pair=selected[0]
            self.assertEqual(pair["n_shared_discovery_regions"],"2")
            self.assertEqual(pair["n_common_observed_days"],"89")
            self.assertEqual(pair["n_common_one_day_transitions"],"70")
            self.assertEqual(pair["longest_contiguous_common_days"],"7")
            self.assertEqual(pair["n_compatible_concepts"],"3")
            self.assertEqual(pair["datum_unverified_concepts"],"gage_height")
            self.assertAlmostEqual(float(pair["distance_km"]),9.5,delta=.25)
            summary=read_csv(root/"discovery_region_summary.csv")
            self.assertEqual(len(summary),14)
            for reg in ("big_cypress","southwest_everglades_coast"):
                self.assertEqual(
                    next(s for s in summary
                         if s["candidate_region"]==reg)
                    ["n_unique_screened_station_pairs"],"1")
            memberships=read_csv(root/"cross_rectangle_pair_memberships.csv")
            self.assertEqual(len(memberships),2)
            self.assertEqual(len({m["pair_id"] for m in memberships}),1)
            sub=read_csv(root/"candidate_pair_subsystems.csv")
            water=next(x for x in sub if x["pair_id"]==pair["pair_id"]
                       and x["scope_level"]=="category"
                       and x["scope"]=="water_quality")
            self.assertEqual(water["spatial_candidate_status"],
                             "insufficient_aligned_one_day_transitions")
            self.assertTrue((root/"INDEX.md").exists())
            image=root/"regions"/"big_cypress"/"visuals"/"candidate_station_graph.svg"
            ElementTree.parse(image)
            self.assertIn("NOT TRAINED",image.read_text())
            with self.assertRaisesRegex(ValueError,"new or empty"):
                screen(models,panels,root,assignments=assignments,dpi=65)

    def test_assignment_hash_or_model_identity_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            assignment=root/"assigned.csv"
            write_csv(assignment,[dict(panel_id="unknown",site_id="USGS-X",
                                       region="big_cypress",panel_sha256="abc")],
                      ["panel_id","site_id","region","panel_sha256"])
            from scripts.screen_m9_spatial_candidates import _load_coordinates
            with self.assertRaisesRegex(ValueError,"not in frozen models"):
                _load_coordinates({},assignments=assignment)


if __name__=="__main__":
    unittest.main()
