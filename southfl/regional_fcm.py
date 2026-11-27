"""Shared station-local dynamics, never a cross-station transport model."""
from datetime import date, timedelta
from math import sqrt, isfinite
from random import Random
from statistics import mean

from .fcm_model import ALPHAS, build_pairs, solve

CONCEPTS = ("salinity", "water_temperature")
MODELS = ("persistence", "pooled_self_ar", "pooled_ridge",
          "regional_fcm", "target_local_fcm")
BASELINES = tuple(m for m in MODELS if m != "regional_fcm")


def split(rows, start, train_end, val_end, end):
    """Split by target date, only within-station observed consecutive pairs."""
    if not start < train_end < val_end < end:
        raise ValueError("invalid chronological cutoffs")
    pairs = build_pairs([r for r in rows if start <= r["date"] <= end], CONCEPTS)
    return {"train": [p for p in pairs if p[0] <= train_end],
            "validation": [p for p in pairs if train_end < p[0] <= val_end],
            "test": [p for p in pairs if val_end < p[0] <= end]}


def weighted_rows(groups):
    """Equal total weight per station; sum of weights equals sample count."""
    if not groups or any(not rows for rows in groups.values()):
        raise ValueError("empty fitting group")
    n = sum(map(len, groups.values()))
    return [(x,y,n/(len(groups)*len(rows))) for _,rows in sorted(groups.items())
            for _,x,y in rows]


def scaler(rows):
    total = sum(w for _,_,w in rows)
    mu = [sum(w*x[j] for x,_,w in rows)/total for j in range(2)]
    sd = [sqrt(sum(w*(x[j]-mu[j])**2 for x,_,w in rows)/total) for j in range(2)]
    if any(not isfinite(s) or s <= 1e-10 for s in sd):
        raise ValueError("constant or invalid training predictor")
    return mu,sd


def standardize(x, mu, sd):
    return [(v-m)/s for v,m,s in zip(x,mu,sd)]


def linear_coeff(rows, target, features, alpha, bound):
    """Weighted ridge with unpenalized intercept; optional post-fit edge clip."""
    dim = len(features)+1
    gram = [[0.0]*dim for _ in range(dim)]
    rhs = [0.0]*dim
    for x,y,w in rows:
        phi = [1.0]+[x[i] for i in features]
        for i in range(dim):
            rhs[i] += w*phi[i]*y[target]
            for j in range(dim):
                gram[i][j] += w*phi[i]*phi[j]
    for i in range(1,dim):
        gram[i][i] += alpha
    raw = solve(gram,rhs)
    coeff = [raw[0],0.0,0.0]
    n_clipped = 0
    for i,v in zip(features,raw[1:]):
        coeff[i+1] = max(-1.,min(1.,v)) if bound else v
        n_clipped += coeff[i+1] != v
    return coeff,n_clipped


def z_predict(coeff,x,bound):
    raw = [w[0]+sum(a*b for a,b in zip(w[1:],x)) for w in coeff]
    return ([max(-3.,min(3.,v)) for v in raw] if bound else raw),raw


def fit(train, validation, kind):
    """No test inputs accepted; tune independently by donor validation only."""
    if kind not in ("regional_fcm","target_local_fcm","pooled_ridge","pooled_self_ar"):
        raise ValueError("unknown model")
    if set(train) != set(validation):
        raise ValueError("training and validation station sets differ")
    if any(len(train[s])<35 or len(validation[s])<15 for s in train):
        raise ValueError("insufficient fitting/validation pairs")
    if max(p[0] for rows in train.values() for p in rows) >= min(
            p[0] for rows in validation.values() for p in rows):
        raise ValueError("chronological fitting overlap")
    tr = weighted_rows(train)
    mu,sd = scaler(tr)
    def norm(groups):
        return [(standardize(x,mu,sd),standardize(y,mu,sd),w)
                for x,y,w in weighted_rows(groups)]
    tr,va = norm(train),norm(validation)
    den = sum(w for _,_,w in va)
    bounded = kind.endswith("fcm")
    def candidate(alpha,j):
        return linear_coeff(tr,j,[j] if kind=="pooled_self_ar" else [0,1],alpha,bounded)
    def loss(coeff,j):
        def one(x):
            raw=coeff[0]+sum(a*b for a,b in zip(coeff[1:],x))
            return max(-3.,min(3.,raw)) if bounded else raw
        return sum(w*abs(one(x)-y[j]) for x,y,w in va)/den
    if kind=="pooled_self_ar":
        selected=[]
        for j in range(2):
            opts=[]
            for alpha in ALPHAS:
                c,n=candidate(alpha,j)
                opts.append((loss(c,j),alpha,c,n))
            selected.append(min(opts,key=lambda a:(a[0],a[1])))
        losses,alphas,coeffs,clipped=map(list,zip(*selected))
    else:
        opts=[]
        for alpha in ALPHAS:
            fitted=[candidate(alpha,j) for j in range(2)]
            coeffs=[c for c,_ in fitted]
            losses=[loss(coeffs[j],j) for j in range(2)]
            opts.append((mean(losses),alpha,coeffs,[n for _,n in fitted],losses))
        _,alpha,coeffs,clipped,losses=min(opts,key=lambda a:(a[0],a[1]))
        alphas=[alpha]*2
    return dict(kind=kind,fit_sites=sorted(train),means=mu,scales=sd,
                alphas=alphas,coefficients_target_rows=coeffs,
                n_edge_coefficients_clipped=sum(clipped),
                validation_standardized_mae=losses,
                n_train_pairs=sum(map(len,train.values())),
                n_validation_pairs=sum(map(len,validation.values())),
                train_end=max(p[0] for rows in train.values() for p in rows),
                validation_end=max(p[0] for rows in validation.values() for p in rows),
                weighting="equal total station weight; normalized to row count",
                activation="clip[-3,3]" if bounded else "identity")


def forecast(model,x):
    z=standardize(x,model["means"],model["scales"])
    pred,raw=z_predict(model["coefficients_target_rows"],z,model["kind"].endswith("fcm"))
    return ([v*s+m for v,s,m in zip(pred,model["scales"],model["means"])],
            [a!=b for a,b in zip(pred,raw)], [abs(v)>3 for v in z])


def evaluate_fold(splits, held):
    donors={s:v for s,v in splits.items() if s!=held}
    if len(donors)<2 or held not in splits:
        raise ValueError("requires held-out site and at least two donors")
    fitted={kind:fit({s:v["train"] for s,v in donors.items()},
                     {s:v["validation"] for s,v in donors.items()},kind)
            for kind in ("pooled_self_ar","pooled_ridge","regional_fcm")}
    target=splits[held]
    fitted["target_local_fcm"]=fit({held:target["train"]},
                                   {held:target["validation"]},"target_local_fcm")
    rows=[]
    for day,x,y in target["test"]:
        if day<=max(m["validation_end"] for m in fitted.values()):
            raise ValueError("test overlaps fitting/validation")
        forecasts={m:forecast(f,x) for m,f in fitted.items()}
        for j,c in enumerate(CONCEPTS):
            row=dict(site_id=held,date=day,concept=c,actual=y[j],previous=x[j],
                     persistence=x[j])
            for m,(p,clipped,outside) in forecasts.items():
                row[m]=p[j]
                row[m+"_output_clipped"]=clipped[j]
                row[m+"_input_outside_3sd"]=outside[j]
            rows.append(row)
    return fitted,rows


def metrics(rows):
    result=[]
    for site in sorted({r["site_id"] for r in rows})+["all_sites"]:
        for c in CONCEPTS:
            selected=[r for r in rows if r["concept"]==c and
                      (site=="all_sites" or r["site_id"]==site)]
            # Same test dates per site required in the CLI; thus equal row
            # and equal site weighting coincide in the aggregate.
            for m in MODELS:
                errors=[r[m]-r["actual"] for r in selected]
                result.append(dict(site_id=site,concept=c,model=m,
                    n=len(errors),mae=mean(map(abs,errors)),
                    rmse=sqrt(mean(e*e for e in errors)),bias=mean(errors),
                    n_output_clipped=sum(r.get(m+"_output_clipped",False) for r in selected),
                    n_input_outside_3sd=sum(r.get(m+"_input_outside_3sd",False) for r in selected)))
    return result


def paired_block(rows, baseline, block=7, draws=2000, seed=20261126):
    """Date-synchronous moving blocks; keep every site on a sampled date.

    Input one concept, one or more sites, same dates per site. Refuse gaps
    that would leave any date outside the available full-length blocks.
    Estimates conditional temporal variability, not new-site uncertainty.
    """
    if baseline not in BASELINES or block<1 or draws<1:
        raise ValueError("invalid bootstrap specification")
    days=sorted({r["date"] for r in rows})
    sites={r["site_id"] for r in rows}
    by={}
    for r in rows:
        k=r["date"],r["site_id"]
        if k in by:
            raise ValueError("duplicate paired observation")
        by[k]=abs(r["regional_fcm"]-r["actual"])-abs(r[baseline]-r["actual"])
    if len(by)!=len(days)*len(sites) or len({r["concept"] for r in rows})!=1:
        raise ValueError("requires matched dates and one concept")
    values=[mean(by[d,s] for s in sorted(sites)) for d in days]
    dates=[date.fromisoformat(d) for d in days]
    starts=[i for i in range(len(days)-block+1)
            if dates[i+block-1]-dates[i]==timedelta(days=block-1)]
    if not starts or set(i for s in starts for i in range(s,s+block))!=set(range(len(days))):
        raise ValueError("insufficient contiguous block support")
    rng=Random(seed)
    estimates=[]
    for _ in range(draws):
        sample=[]
        while len(sample)<len(values):
            i=rng.choice(starts)
            sample.extend(values[i:i+block])
        estimates.append(mean(sample[:len(values)]))
    estimates.sort()
    def quantile(p):
        i=p*(len(estimates)-1)
        lo=int(i)
        return estimates[lo]+(i-lo)*(estimates[min(lo+1,len(estimates)-1)]-estimates[lo])
    return dict(delta_mae=mean(values),ci_low=quantile(.025),ci_high=quantile(.975),
                n_dates=len(days),n_sites=len(sites),block_days=block,
                n_available_blocks=len(starts),draws=draws,seed=seed)
