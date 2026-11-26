"""Small, explicitly bounded linear-threshold dynamic FCM with holdout checks.

For train-only standardized concepts z, predicts next observed day with
z[t+1] = clip(intercept + z[t] @ W, -3, 3).
Signed predictive weights in [-1,1] are regularized, NOT causal claims.
No interpolation, no pooled site identity, no test-time parameter fitting.
"""
from datetime import date
from math import sqrt,isfinite
from statistics import mean
from .panels import numeric

class NotReadyError(ValueError):
    pass

ALPHAS=(0.1,1.0,10.0,50.0)
EVAL_COLS=["concept","n_test_pairs","fcm_mae","fcm_rmse","self_ar_mae",
           "persistence_mae","train_climatology_mae","fcm_vs_persistence_mae_delta",
           "fcm_vs_self_ar_mae_delta","test_target_mean","unit_note"]
EDGE_COLS=["source_concept","target_concept","weight","sign","edge_kind","interpretation"]


def solve(matrix, vector):
    """Gaussian elimination with pivoting; small regularized normal equations."""
    n=len(vector)
    rows=[list(a)+[b] for a,b in zip(matrix,vector)]
    for col in range(n):
        pivot=max(range(col,n),key=lambda k:abs(rows[k][col]))
        if abs(rows[pivot][col])<1e-12:
            raise NotReadyError("singular model system even after regularization")
        rows[col],rows[pivot]=rows[pivot],rows[col]
        div=rows[col][col]
        rows[col]=[v/div for v in rows[col]]
        for i in range(n):
            if i==col: continue
            mult=rows[i][col]
            rows[i]=[x-mult*y for x,y in zip(rows[i],rows[col])]
    return [r[-1] for r in rows]


def ridge(xs,ys,alpha):
    """Intercept unpenalized, all directed edges subject to ridge penalty."""
    if alpha<=0: raise ValueError("ridge penalty must be positive")
    n=len(xs)
    d=len(xs[0])
    m=len(ys[0])
    A=[[0.0]*(d+1) for _ in range(d+1)]
    for x in xs:
        phi=[1.0]+list(x)
        for i in range(d+1):
            for j in range(d+1):
                A[i][j]+=phi[i]*phi[j]
    for i in range(1,d+1): A[i][i]+=alpha
    # Bound coefficients to FCM-style signed [-1,+1] *before* validation.
    B=[]
    for target in range(m):
        rhs=[sum(([1.0]+list(x))[i]*y[target] for x,y in zip(xs,ys))
             for i in range(d+1)]
        coeff=solve(A,rhs)
        B.append([coeff[0]]+[max(-1.0,min(1.0,x)) for x in coeff[1:]])
    return B


def predict(weights,x):
    return [max(-3.0,min(3.0,w[0]+sum(a*b for a,b in zip(x,w[1:]))))
            for w in weights]


def mae(pred,actual):
    return mean(abs(p-a) for p,a in zip(pred,actual))


def _metrics(pred,actual):
    n=len(pred)
    return {"mae":mae(pred,actual),
            "rmse":sqrt(sum((p-a)**2 for p,a in zip(pred,actual))/n)}


def build_pairs(rows,concepts):
    if len(concepts)<2 or len(set(concepts))!=len(concepts):
        raise NotReadyError("at least two unique concepts required for an FCM")
    sorted_rows=sorted(rows,key=lambda r:r["date"])
    dates=set()
    clean=[]
    site_ids={r.get("site_id") for r in sorted_rows}
    if len(site_ids)!=1:
        raise NotReadyError("no cross-site model fitting without verified connectivity")
    for r in sorted_rows:
        day=date.fromisoformat(r["date"])
        if day in dates: raise NotReadyError("duplicate panel day")
        dates.add(day)
        v=[numeric(r.get(c)) for c in concepts]
        if any(x is None for x in v):
            raise NotReadyError("panel contains missing/nonfinite concept; no imputation")
        clean.append((day,v))
    pairs=[]
    for (d0,x),(d1,y) in zip(clean,clean[1:]):
        if (d1-d0).days==1:
            pairs.append((d1.isoformat(),x,y))
    return pairs


def fit_preview(rows,concepts,min_pairs=79):
    pairs=build_pairs(rows,concepts)
    n=len(pairs)
    if n<min_pairs:
        raise NotReadyError(f"{n} consecutive complete pairs; require >= {min_pairs}")
    ntrain=int(n*.6)
    nval=int(n*.2)
    if ntrain<35 or nval<15 or n-ntrain-nval<15:
        raise NotReadyError("insufficient chronological train/validation/test pairs")
    train,val,test=pairs[:ntrain],pairs[ntrain:ntrain+nval],pairs[ntrain+nval:]
    # Fit standardization on training PREVIOUS states alone, never test rows.
    d=len(concepts)
    means=[mean(p[1][j] for p in train) for j in range(d)]
    scales=[sqrt(mean((p[1][j]-means[j])**2 for p in train)) for j in range(d)]
    if any(s<=1e-10 for s in scales):
        raise NotReadyError("constant concept in training period; cannot fit FCM")
    def normalized(chunk):
        return ([[ (p[1][j]-means[j])/scales[j] for j in range(d)] for p in chunk],
                [[ (p[2][j]-means[j])/scales[j] for j in range(d)] for p in chunk])
    tx,ty=normalized(train)
    vx,vy=normalized(val)
    ex,ey=normalized(test)
    best=None
    for alpha in ALPHAS:
        weights=ridge(tx,ty,alpha)
        candidate=[predict(weights,x) for x in vx]
        loss=mean(mae([p[j] for p in candidate],[y[j] for y in vy])
                  for j in range(d))
        if best is None or loss<best[0]:
            best=(loss,alpha,weights)
    _,chosen,weights=best
    # Independent AR(1) per concept is a more meaningful baseline than
    # persistence when dynamics are smooth and self-autocorrelated.
    ar=[]
    self_ar_alphas=[]
    for j in range(d):
        # Give the simple AR(1) baseline its OWN chronological validation
        # tuning. Reusing the FCM-selected alpha would bias this comparison.
        choices=[]
        for candidate_alpha in ALPHAS:
            fitted=ridge([[x[j]] for x in tx],[[y[j]] for y in ty],
                         candidate_alpha)[0]
            val_forecast=[predict([fitted],[x[j]])[0] for x in vx]
            val_loss=mae(val_forecast,[y[j] for y in vy])
            choices.append((val_loss,candidate_alpha,fitted))
        _,best_ar_alpha,coeff=min(choices,key=lambda x:(x[0],x[1]))
        self_ar_alphas.append(best_ar_alpha)
        ar.append(coeff)
    fcm=[predict(weights,x) for x in ex]
    self_ar=[[predict([ar[j]],[x[j]])[0] for j in range(d)] for x in ex]
    persistence=ex
    train_means=[mean(y[j] for y in ty) for j in range(d)]
    evaluation=[]
    predictions=[]
    for j,concept in enumerate(concepts):
        actual_raw=[y[j]*scales[j]+means[j] for y in ey]
        fcm_raw=[y[j]*scales[j]+means[j] for y in fcm]
        ar_raw=[y[j]*scales[j]+means[j] for y in self_ar]
        pers_raw=[y[j]*scales[j]+means[j] for y in persistence]
        clim_raw=[train_means[j]*scales[j]+means[j]]*len(ey)
        metrics=_metrics(fcm_raw,actual_raw)
        ar_err=mae(ar_raw,actual_raw)
        pers_err=mae(pers_raw,actual_raw)
        evaluation.append(dict(concept=concept,n_test_pairs=len(test),
            fcm_mae=round(metrics["mae"],6),fcm_rmse=round(metrics["rmse"],6),
            self_ar_mae=round(ar_err,6),persistence_mae=round(pers_err,6),
            train_climatology_mae=round(mae(clim_raw,actual_raw),6),
            fcm_vs_persistence_mae_delta=round(metrics["mae"]-pers_err,6),
            fcm_vs_self_ar_mae_delta=round(metrics["mae"]-ar_err,6),
            test_target_mean=round(mean(actual_raw),6),
            unit_note="native source unit; verify in panel plan"))
        for i,p in enumerate(test):
            predictions.append(dict(date=p[0],concept=concept,
                actual=actual_raw[i],fcm=fcm_raw[i],
                self_ar=ar_raw[i],persistence=pers_raw[i]))
    edges=[]
    for target,j in enumerate(concepts):
        for source,i in enumerate(concepts):
            w=weights[target][source+1]
            # Store concept NAMES, not loop indices: fcm_figures.network_svg
            # looks edges up by name in a name-keyed point dictionary.
            edges.append(dict(source_concept=i,target_concept=j,
                weight=round(w,6),sign="positive" if w>0 else
                "negative" if w<0 else "zero",
                edge_kind="self_memory" if source==target else "cross_concept",
                interpretation="held-out predictive association; NOT demonstrated causality"))
    # Explicit forward recursion (no future observation inputs): illustrative,
    # not measured skill or an intervention effect.
    last=max(rows,key=lambda r:r["date"])
    state=[(numeric(last[c])-means[j])/scales[j] for j,c in enumerate(concepts)]
    roll=[]
    for step in range(1,8):
        state=predict(weights,state)
        for j,concept in enumerate(concepts):
            roll.append(dict(step=step,concept=concept,
                             simulated_value=state[j]*scales[j]+means[j]))
    return {
        "concepts":concepts,"n_pairs":n,"train_pairs":len(train),
        "validation_pairs":len(val),"test_pairs":len(test),
        "train_start":train[0][0],"train_end":train[-1][0],
        "validation_start":val[0][0],"validation_end":val[-1][0],
        "test_start":test[0][0],"test_end":test[-1][0],
        "normalization_mean":means,"normalization_scale":scales,
        "ridge_alpha":chosen,"self_ar_alphas":self_ar_alphas,
        "intercepts":[w[0] for w in weights],
        "matrix_source_to_target":[[weights[j][i+1] for j in range(d)] for i in range(d)],
        "evaluation":evaluation,"predictions":predictions,"edges":edges,
        "rollout":roll,
        "method":"train-standardized ridge, signed clipped FCM weights, "
                 "bounded linear-threshold activation, chronological holdout",
        "forecast_type":"one-day-ahead prediction conditioned on observed previous-day state",
        "limitations":"predictive associations not causal effects; daily mean and "
                      "one site only; test result not an operational risk estimate",
    }
