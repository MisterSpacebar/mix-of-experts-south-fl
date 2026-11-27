"""Leakage, fairness and real-source regional regression."""
import copy
import tempfile
import unittest
from datetime import date,timedelta
from pathlib import Path

from southfl.regional_fcm import (CONCEPTS, evaluate_fold, paired_block,
                                  weighted_rows, linear_coeff, forecast, split)
from scripts.train_m10_regional_fcm import COHORT, run
from southfl.audit import read_csv


def synthetic():
    groups={}
    for i,s in enumerate(("a","b","c")):
        rows=[]
        for j in range(100):
            d=(date(2026,1,1)+timedelta(days=j)).isoformat()
            rows.append(dict(site_id=s,date=d,salinity=20+i+j*.04+(j%5)*.2,
                             water_temperature=25+i*.2+j*.03+(j%7)*.1))
        groups[s]=split(rows,"2026-01-01","2026-02-20","2026-03-12","2026-04-10")
    return groups


class RegionalTests(unittest.TestCase):
    def test_donor_only_fit_is_invariant_to_target_history_and_donor_test(self):
        data=synthetic()
        fit,rows=evaluate_fold(data,"c")
        changed=copy.deepcopy(data)
        for p in changed["c"]["train"]+changed["c"]["validation"]+changed["a"]["test"]:
            p[1][0]+=100
            p[2][0]+=100
        f2,r2=evaluate_fold(changed,"c")
        for m in ("regional_fcm","pooled_ridge","pooled_self_ar"):
            self.assertEqual(fit[m],f2[m])
            self.assertEqual(fit[m]["fit_sites"],["a","b"])
            self.assertEqual([r[m] for r in rows],[r[m] for r in r2])
        self.assertNotEqual(fit["target_local_fcm"],f2["target_local_fcm"])

    def test_test_targets_never_change_fitted_parameters(self):
        data=synthetic()
        a,_=evaluate_fold(data,"c")
        for p in data["c"]["test"]:
            p[2][0]+=10
        b,_=evaluate_fold(data,"c")
        self.assertEqual(a,b)

    def test_equal_site_weight_and_unbounded_ridge(self):
        a=("2026-01-02",[1.,1.],[4.,1.])
        b=("2026-01-03",[2.,1.],[8.,1.])
        rows=weighted_rows({"a":[a,b],"b":[a]})
        self.assertAlmostEqual(sum(x[2] for x in rows[:2]),rows[2][2])
        u,_=linear_coeff(rows,0,[0],.01,False)
        v,n=linear_coeff(rows,0,[0],.01,True)
        self.assertGreater(u[1],1)
        self.assertEqual(v[1],1)
        self.assertEqual(n,1)

    def test_paired_bootstrap_synchronous_and_reproducible(self):
        rows=[dict(site_id=s,date=(date(2026,1,1)+timedelta(days=i)).isoformat(),
                   concept="salinity",actual=0,regional_fcm=1,persistence=2)
              for s in ("a","b") for i in range(20)]
        a=paired_block(rows,"persistence",7,100)
        self.assertEqual(a,paired_block(rows,"persistence",7,100))
        self.assertEqual((a["delta_mae"],a["ci_low"],a["ci_high"]),(-1,-1,-1))
        with self.assertRaisesRegex(ValueError,"matched"):
            paired_block(rows[:-1],"persistence",7,100)

    def test_real_cohort_fit_and_immutable_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/"models"
            report=run(COHORT,out,draws=100)
            self.assertEqual(report["n_spatial_folds"],4)
            self.assertEqual(report["n_prediction_targets"],288)
            self.assertEqual(report["n_test_dates_per_site"],36)
            self.assertEqual(len(read_csv(out/"metrics.csv")),50)
            self.assertEqual(len(read_csv(out/"paired_comparisons.csv")),120)
            self.assertEqual(len(read_csv(out/"edge_weights.csv")),32)
            self.assertFalse(report["regional_transport_model_trained"])
            with self.assertRaisesRegex(ValueError,"new/empty"):
                run(COHORT,out,draws=100)
