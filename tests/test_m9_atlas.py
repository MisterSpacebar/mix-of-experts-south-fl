"""M9.2 cross-axis evidence atlas: source-integrity and causal-label tests."""
import json
import math
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path
from xml.etree import ElementTree

from southfl.audit import read_csv
from southfl.m9_candidates import assess_pair
from southfl.m9_atlas import (
    validate_trained_edges,build_trained_edge_records,
    compare_site_coefficients,observed_change_associations)
from scripts.build_m9_cross_axis_atlas import run as build_atlas
from visuals.m9_atlas_render import atlas_svg


class AtlasEvidenceUnitTests(unittest.TestCase):
    def test_trained_edges_must_match_fitted_matrix_and_direction(self):
        model=dict(
            concepts=["discharge","salinity"],
            matrix_source_to_target=[[.8,-.2],[.15,.7]])
        rows=[
            dict(source_concept="discharge",target_concept="discharge",
                 weight=".8"),
            dict(source_concept="discharge",target_concept="salinity",
                 weight="-.2"),
            dict(source_concept="salinity",target_concept="discharge",
                 weight=".15"),
            dict(source_concept="salinity",target_concept="salinity",
                 weight=".7"),
        ]
        edges=validate_trained_edges(model,rows)
        self.assertAlmostEqual(edges[("salinity","discharge")],.15)
        with self.assertRaisesRegex(ValueError,"differs from original"):
            validate_trained_edges(model,[
                dict(row,weight=".25") if row["source_concept"]=="salinity"
                and row["target_concept"]=="discharge" else row
                for row in rows])
        with self.assertRaisesRegex(ValueError,"duplicate fitted"):
            validate_trained_edges(model,rows+[rows[0]])
        with self.assertRaisesRegex(ValueError,"missing fitted"):
            validate_trained_edges(model,rows[1:])

    def test_station_category_bridges_are_not_pooled(self):
        a=dict(site_id="USGS-A",panel_id="p1",region="big_cypress",
               _edges={("discharge","discharge"):.8,
                       ("discharge","salinity"):-.2,
                       ("salinity","discharge"):.15,
                       ("salinity","salinity"):.7})
        b=dict(a,site_id="USGS-B",panel_id="p2",
               _edges={**a["_edges"],("discharge","salinity"):.22})
        all_edges,bridges=build_trained_edge_records([a,b],.08)
        self.assertEqual(len(all_edges),8)
        self.assertEqual(len([x for x in all_edges
                              if x["cross_category"]]),4)
        p=[dict(pair_id="USGS-A__USGS-B",site_a="USGS-A",site_b="USGS-B",
                geographic_candidate=True,n_common_one_day_transitions=30)]
        comparisons=compare_site_coefficients([a,b],p,.08)
        self.assertEqual(len(comparisons),4)
        changed=next(x for x in comparisons if
                     x["source_concept"]=="discharge" and
                     x["target_concept"]=="salinity")
        self.assertEqual(changed["sign_comparison"],
                         "both_above_threshold_opposite_sign")
        self.assertTrue(all(x["model_status"]==
                "trained_within_one_station_full_FCM" for x in all_edges))

    def test_aligned_cross_site_change_covariation_is_undirected(self):
        d0=date(2026,1,1)
        dates=[d0+timedelta(days=i) for i in range(45)]
        def mk(sid,lat,lon,scale):
            records={}
            flow=0.
            salt=0.
            for i,day in enumerate(dates):
                flow+=scale*(i%7+0.3*math.sin(i))
                salt+=scale*(math.sin(i/3)+i%3)
                records[day]=dict(discharge=str(flow),salinity=str(salt),
                                   gage_height=str(4+i*.01))
            return dict(site_id=sid,panel_id="panel_"+sid,
                region="big_cypress",latitude=lat,longitude=lon,
                candidate_discovery_regions="big_cypress;southwest_everglades_coast",
                _dates=set(dates),_concepts=["discharge","salinity","gage_height"],
                _metadata={"concept_units":
                    "discharge=ft^3/s;salinity=ppt;gage_height=ft",
                    "concept_datums":"discharge=;salinity=;gage_height="},
                _observed=records)
        a=mk("USGS-A",25.8954,-81.4555,1.)
        b=mk("USGS-B",25.926,-81.5443,2.)
        p=assess_pair(a,b)
        rows=observed_change_associations([a,b],[p],min_aligned=20)
        self.assertEqual(len(rows),4) # 2 comparable concepts × 2
        self.assertTrue(all(x["relationship_type"]==
            "undirected_contemporaneous_observed_change_covariation"
            for x in rows))
        matched=next(x for x in rows if x["concept_a"]=="discharge"
                     and x["concept_b"]=="discharge")
        self.assertGreater(float(matched["concurrent_change_pearson_r"]),.999)
        self.assertEqual(matched["n_aligned_daily_change_pairs"],44)
        self.assertFalse(any(x["concept_a"]=="gage_height" or
                             x["concept_b"]=="gage_height" for x in rows))
        sample=dict(a,_model=dict(concepts=["discharge","salinity","gage_height"]),
                    _edges={})
        svg=atlas_svg([sample],[],minimum=.08)
        ElementTree.fromstring(svg)
        self.assertIn("REGIONAL",svg.upper()) if False else self.assertIn(
            "NOT TRAINED",svg.upper())

    def test_no_cross_site_changes_when_not_geographic_candidate(self):
        day=date(2026,1,1)
        a=dict(site_id="USGS-A",panel_id="pA",region="big_cypress",
               latitude=25.9,longitude=-81.5,
               candidate_discovery_regions="big_cypress;southwest_everglades_coast",
               _dates={day},_concepts=["salinity"],_metadata={
                    "concept_units":"salinity=ppt","concept_datums":"salinity="},
               _observed={day:{"salinity":"1"}})
        b=dict(a,site_id="USGS-B",panel_id="pB",region="central_south_biscayne",
               latitude=25.57,longitude=-80.3748,
               candidate_discovery_regions="central_south_biscayne;everglades_interior")
        pair=assess_pair(a,b)
        self.assertFalse(pair["geographic_candidate"])
        self.assertEqual(observed_change_associations([a,b],[pair]),[])


class RealSourceIntegrationTests(unittest.TestCase):
    def test_three_station_committed_atlas_and_figures(self):
        repo=Path(__file__).resolve().parents[1]
        models=repo/"data/m8/layers_replication_v1"
        screen=repo/"data/m9/spatial_candidate_screen_v1"
        assign=repo/"data/m9/regional_readiness_v1_with_coords/station_assignments.csv"
        panels=[repo/"data/m7/daily_panels_verified_01",
                repo/"data/m8/replication_daily_01"]
        needed=[models/"manifest.json",models/"model_registry.csv",
                screen/"candidate_station_pairs.csv",screen/"manifest.json",
                assign]+[p/"panel_readiness.csv" for p in panels]
        if not all(p.is_file() for p in needed):
            self.skipTest("real three-station source snapshot unavailable")
        frozen_models=(models/"manifest.json").read_bytes()
        frozen_screen=(screen/"manifest.json").read_bytes()
        with tempfile.TemporaryDirectory() as td:
            dest=Path(td)/"atlas"
            summary=build_atlas(models,panels,assign,screen,dest,
                                min_weight=.08,min_aligned=20,dpi=65)
            self.assertEqual(summary["n_fitted_full_station_fcms"],3)
            self.assertEqual(summary["n_unpooled_within_station_directed_edges"],48)
            self.assertEqual(summary["n_unique_original_station_pairs"],3)
            self.assertEqual(summary["n_geographically_screened_station_pairs"],1)
            self.assertEqual(summary["n_exploratory_daily_change_concept_pair_rows"],9)
            self.assertEqual(summary["n_fitted_interstation_directed_edges"],0)
            self.assertEqual(summary["n_fitted_region_fcms"],0)
            self.assertEqual(summary["n_fitted_region_category_fcms"],0)
            self.assertEqual((models/"manifest.json").read_bytes(),frozen_models)
            self.assertEqual((screen/"manifest.json").read_bytes(),frozen_screen)
            raw_edges=read_csv(dest/"trained_station_edges_by_subsystem.csv")
            self.assertEqual(len(raw_edges),48)
            self.assertEqual(sum(e["cross_category"]=="True"
                                 for e in raw_edges),24)
            visible=sum(e["cross_category"]=="True" and
                        e["above_display_threshold"]=="True"
                        for e in raw_edges)
            self.assertEqual(summary["n_visible_cross_category_within_station_edges"],
                             visible)
            self.assertGreater(visible,0)
            pairs=read_csv(dest/"screened_cross_site_daily_change_associations.csv")
            self.assertEqual(len(pairs),9)
            self.assertEqual({r["n_aligned_daily_change_pairs"] for r in pairs},
                             {"70"})
            self.assertFalse(any(r["concept_a"]=="gage_height"
                                 for r in pairs))
            self.assertTrue((dest/"INDEX.md").is_file())
            combined=dest/"visuals/geography_category_evidence_atlas.svg"
            ElementTree.parse(combined)
            text=combined.read_text()
            self.assertIn('data-type="geographic_screening_only"',text)
            self.assertIn('data-type="fitted_station_edge"',text)
            self.assertIn("NOT TRAINED",text)
            self.assertTrue((dest/"visuals/region_category_coverage.png").is_file())
            self.assertTrue((dest/"categories/hydrology/FINDINGS.md").is_file())
            self.assertTrue((dest/"categories/water_quality/FINDINGS.md").is_file())
            self.assertTrue((dest/"regions/big_cypress/FINDINGS.md").is_file())
            near=dest/"pairs/USGS-255327081275900__USGS-255534081324000"
            self.assertTrue((near/"visuals/aligned_change_correlations.png").is_file())
            self.assertTrue((near/"FINDINGS.md").is_file())
            with self.assertRaisesRegex(ValueError,"new or empty"):
                build_atlas(models,panels,assign,screen,dest,dpi=65)

    def test_rejects_tampered_spatial_source_report(self):
        repo=Path(__file__).resolve().parents[1]
        models=repo/"data/m8/layers_replication_v1"
        screen=repo/"data/m9/spatial_candidate_screen_v1"
        assignment=repo/"data/m9/regional_readiness_v1_with_coords/station_assignments.csv"
        panels=[repo/"data/m7/daily_panels_verified_01",
                repo/"data/m8/replication_daily_01"]
        if not all(p.exists() for p in [models/"manifest.json",
                                       screen/"manifest.json",assignment]):
            self.skipTest("real source snapshot unavailable")
        with tempfile.TemporaryDirectory() as td:
            import shutil
            copy=Path(td)/"screen"
            copy.mkdir()
            for name in ("manifest.json","candidate_station_pairs.csv"):
                shutil.copy2(screen/name,copy/name)
            records=read_csv(copy/"candidate_station_pairs.csv")
            # Alter one observed-day count without altering the real panels.
            records[0]["n_common_observed_days"]="999"
            from southfl.net import write_csv
            write_csv(copy/"candidate_station_pairs.csv",records,list(records[0]))
            with self.assertRaisesRegex(ValueError,"differs from verified observations"):
                build_atlas(models,panels,assignment,copy,
                            Path(td)/"out",dpi=65)


if __name__=="__main__":
    unittest.main()
