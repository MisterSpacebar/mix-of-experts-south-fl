"""M10 combined experiment tests (mocked source ingestion, actual offline cohort)."""
import copy
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path

from southfl.m10_forcing import weather_rows,tide_rows,assemble,WEATHER_ID,TIDE_ID,WEATHER
from southfl.residual_fcm import fold,gate_weights,fit_residual,predict
from scripts.run_m10_residual_forcing_mixture import run
from southfl.audit import read_csv


def synthetic():
    data={}
    for i,s in enumerate(("a","b","c")):
        groups={"train":[],"validation":[],"test":[]}
        for j in range(100):
            d=(date(2026,1,1)+timedelta(days=j)).isoformat()
            x=[20+i+j*.04+(j%5)*.2,25+i*.2+j*.03+(j%7)*.1]
            y=[x[0]+.1+(j%3)*.02,x[1]-.1+(j%4)*.03]
            groups["train" if j<50 else "validation" if j<75 else "test"].append((d,x,y))
        data[s]=groups
    return data


class CombinedTests(unittest.TestCase):
    def test_weather_flags_and_lag(self):
        raw=[dict(STATION=WEATHER_ID,DATE="2026-05-28",PRCP="0",AWND="2",TMIN="20",TMAX="30",
                  PRCP_ATTRIBUTES="T,,W",AWND_ATTRIBUTES=",X,W",TMIN_ATTRIBUTES=",,W",
                  TMAX_ATTRIBUTES=",,W")]
        w=weather_rows(raw)
        self.assertEqual(w["2026-05-28"]["rain_mm"],0)
        self.assertNotIn("wind_ms",w["2026-05-28"])
        row=assemble(w,{"2026-05-29":{"coastal_level_mean_m":.2}})[0]
        self.assertEqual(row["target_date"],"2026-05-30")
        self.assertEqual(row["weather_source_date"],"2026-05-28")
        self.assertEqual(row["water_level_source_date"],"2026-05-29")
        self.assertEqual(row["coastal_level_mean_m"],.2)

    def test_observed_tide_quality_and_coverage(self):
        from datetime import datetime
        raw={"metadata":{"id":TIDE_ID},"data":[
            dict(t=(datetime(2026,6,1)+timedelta(minutes=6*i)).strftime("%Y-%m-%d %H:%M"),
                 v=str(i/100),q="v",f="0,0,0,0") for i in range(240)]}
        r=tide_rows(raw,"2026-06-01","2026-06-01")
        self.assertAlmostEqual(r["2026-06-01"]["coastal_level_range_m"],2.39)
        raw["data"]=raw["data"][:180]
        self.assertEqual(tide_rows(raw,"2026-06-01","2026-06-01"),{})

    def test_gate_persistence_fallback(self):
        weights=gate_weights([([3.,4.],[3.,4.],[10.,10.],[20.,20.],1.)])
        self.assertEqual(weights,[[1.,0.,0.],[1.,0.,0.]])

    def test_donor_fit_and_zero_gate_ignore_target_history_and_test(self):
        data=synthetic()
        a,_=fold(data,"c",{}, {})
        changed=copy.deepcopy(data)
        for period in ("train","validation","test"):
            changed["c"][period]=[(d,[x[0]+50,x[1]],[y[0]+50,y[1]])
                                  for d,x,y in changed["c"][period]]
        changed["a"]["test"]=[]
        b,_=fold(changed,"c",{}, {})
        for k in ("residual_regional","residual_unbounded","zero_shot_gate"):
            self.assertEqual(a[k],b[k])
        self.assertNotEqual(a["residual_local"],b["residual_local"])

    def test_forcing_matched_and_fallback(self):
        data=synthetic()
        forcing={d:{"rain":float(i%7)} for i,(d,x,y) in enumerate(
            data["a"]["train"]+data["a"]["validation"]+data["a"]["test"])}
        del forcing[data["a"]["test"][-1][0]]
        model,rows=fold(data,"c",forcing,{"weather":("rain",)})
        self.assertEqual(model["forcing"]["weather"]["status"],"fitted")
        def count(m):return sum(r["model"]==m for r in rows)
        self.assertEqual(count("weather_forced"),48)
        self.assertEqual(count("weather_matched_unforced"),48)
        self.assertEqual(count("weather_zero_shot_fallback"),50)
        blocked,rr=fold(data,"c",{},{"weather":("rain",)})
        self.assertEqual(blocked["forcing"]["weather"]["status"],"insufficient_train_or_validation")
        self.assertEqual(sum(r["model"]=="weather_zero_shot_fallback" for r in rr),50)

    def test_actual_baseline_replay(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"experiment"
            r=run(out)
            self.assertEqual(r["n_folds"],4)
            self.assertEqual(r["n_reference_targets"],288)
            self.assertEqual(r["n_prediction_rows"],288*11)
            self.assertEqual(r["forcing_fold_fits"],0)
            self.assertTrue(r["exploratory_reused_test_period"])
            scores=read_csv(out/"metrics.csv")
            sal=[x for x in scores if x["site_id"]=="all_sites" and x["concept"]=="salinity"
                 and x["model"]=="level_activation_ablation"][0]
            self.assertAlmostEqual(float(sal["mae"]),1.505766458545622,places=9)
            with self.assertRaisesRegex(ValueError,"new/empty"):
                run(out)
