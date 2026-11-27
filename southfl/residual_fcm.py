"""Persistence-anchored residual experts and validation-only convex blending."""
from math import sqrt,isfinite
from statistics import mean
from .fcm_model import ALPHAS, solve
from .regional_fcm import CONCEPTS, weighted_rows, fit as level_fit, forecast as level_forecast

GRID=(0.,.25,.5,.75,1.)
# Bounded delta is relative to training variation of changes, not levels.


def augment(groups,forcing,features):
    return {s:[(d,list(x)+[forcing[d][f] for f in features],y)
               for d,x,y in rows if d in forcing and all(f in forcing[d] for f in features)]
            for s,rows in groups.items()}


def adequate(tr,va):
    return bool(tr) and set(tr)==set(va) and all(len(tr[s])>=35 and len(va[s])>=15 for s in tr)


def predict(model,x):
    z=[(v-m)/sd for v,m,sd in zip(x,model["means"],model["scales"])]
    raw=[w[0]+sum(a*b for a,b in zip(w[1:],z)) for w in model["weights"]]
    delta=[max(-3.,min(3.,v)) for v in raw] if model["bounded"] else raw
    return [x[j]+delta[j]*model["delta_scales"][j] for j in range(2)]


def fit_residual(tr,va,bounded=True):
    if not adequate(tr,va):
        raise ValueError("insufficient residual train/validation")
    if max(p[0] for rows in tr.values() for p in rows)>=min(p[0] for rows in va.values() for p in rows):
        raise ValueError("overlapping training and validation")
    rows=weighted_rows(tr); val=weighted_rows(va); total=sum(w for _,_,w in rows)
    dim=len(rows[0][0])
    if any(len(x)!=dim or len(y)!=2 or not all(isfinite(v) for v in x+y)
           for x,y,_ in rows+val):
        raise ValueError("invalid residual inputs")
    mu=[sum(w*x[j] for x,y,w in rows)/total for j in range(dim)]
    sd=[sqrt(sum(w*(x[j]-mu[j])**2 for x,y,w in rows)/total) for j in range(dim)]
    if any(v<=1e-10 for v in sd):
        raise ValueError("constant residual feature")
    # Scale change by RMS (zero change is exactly zero; no centering).
    ds=[sqrt(sum(w*(y[j]-x[j])**2 for x,y,w in rows)/total) for j in range(2)]
    if any(v<=1e-10 for v in ds):
        raise ValueError("constant residual target")
    design=[([1.]+[(v-m)/s for v,m,s in zip(x,mu,sd)],[(y[j]-x[j])/ds[j] for j in range(2)],w)
            for x,y,w in rows]
    gram=[[sum(w*x[i]*x[j] for x,y,w in design) for j in range(dim+1)] for i in range(dim+1)]
    best=None
    for alpha in ALPHAS:
        matrix=[r[:] for r in gram]
        for j in range(1,dim+1):
            matrix[j][j]+=alpha
        weights=[]; clipped=0
        for j in range(2):
            w=solve(matrix,[sum(v*x[i]*y[j] for x,y,v in design) for i in range(dim+1)])
            c=[w[0]]+[max(-1.,min(1.,z)) for z in w[1:]] if bounded else w
            clipped+=sum(a!=b for a,b in zip(w,c))
            weights.append(c)
        model=dict(fit_sites=sorted(tr),means=mu,scales=sd,delta_scales=ds,
                   bounded=bounded,weights=weights,alpha=alpha,edge_clips=clipped,
                   train_pairs=sum(map(len,tr.values())),validation_pairs=sum(map(len,va.values())),
                   train_end=max(p[0] for rows in tr.values() for p in rows),
                   validation_end=max(p[0] for rows in va.values() for p in rows))
        loss=sum(w*mean(abs(a-b)/ds[j] for j,(a,b) in enumerate(zip(predict(model,x),y)))
                 for x,y,w in val)/sum(w for _,_,w in val)
        model["validation_scaled_mae"]=loss
        if best is None or (loss,alpha)<(best["validation_scaled_mae"],best["alpha"]):
            best=model
    return best


def gate_weights(rows):
    """Rows are (actual, persistence, regional, local or None, weight).
    Select each concept separately by validation native-unit MAE.
    Ties favor persistence, then regional; no test information.
    """
    if not rows:
        raise ValueError("empty gate validation")
    local=rows[0][3] is not None
    options=[(1-r-l,r,l) for r in GRID for l in (GRID if local else (0.,)) if r+l<=1]
    result=[]
    for j in range(2):
        def loss(w):
            return sum(q*abs(y[j]-w[0]*p[j]-w[1]*r[j]-w[2]*(l[j] if l is not None else 0.))
                       for y,p,r,l,q in rows)/sum(q for *_,q in rows)
        result.append(list(min(options,key=lambda w:(loss(w),-w[0],-w[1]))))
    return result


def blend(weights,x,regional,local=None):
    return [w[0]*x[j]+w[1]*regional[j]+w[2]*(local[j] if local is not None else 0.)
            for j,w in enumerate(weights)]


def fold(splits,held,forcing,feature_sets):
    donors={s:v for s,v in splits.items() if s!=held}
    tr={s:v["train"] for s,v in donors.items()}
    va={s:v["validation"] for s,v in donors.items()}
    lt={held:splits[held]["train"]}; lv={held:splits[held]["validation"]}
    if held in tr or held in va or len(tr)<2:
        raise ValueError("invalid spatial fold")
    level=level_fit(tr,va,"regional_fcm")
    unbounded=fit_residual(tr,va,False)
    regional=fit_residual(tr,va)
    local=fit_residual(lt,lv)
    zero=gate_weights([(y,x,predict(regional,x),None,w) for x,y,w in weighted_rows(va)])
    adapted=gate_weights([(y,x,predict(regional,x),predict(local,x),w)
                          for x,y,w in weighted_rows(lv)])
    metadata=dict(level=level,residual_unbounded=unbounded,residual_regional=regional,
                  residual_local=local,zero_shot_gate=zero,adapted_gate=adapted,
                  gate_validation_sites={"zero_shot":sorted(va),"adapted":[held]},
                  gate_validation_counts={"zero_shot":sum(map(len,va.values())),
                                          "adapted":len(lv[held])},forcing={})
    predictions=[]
    for d,x,y in splits[held]["test"]:
        bounded,_,_=level_forecast(level,x)
        linear=[sum(a*b for a,b in zip(w[1:],[(v-m)/s for v,m,s in zip(x,level["means"],level["scales"])]))+w[0]
                for w in level["coefficients_target_rows"]]
        linear=[z*s+m for z,s,m in zip(linear,level["scales"],level["means"])]
        r,l=predict(regional,x),predict(local,x)
        preds=dict(persistence=x,level_bounded=bounded,level_activation_ablation=linear,
                   residual_unbounded=predict(unbounded,x),residual_regional=r,residual_local=l,
                   zero_shot_blend=blend(zero,x,r),adapted_blend=blend(adapted,x,r,l))
        predictions.append((d,x,y,preds))
    # Same complete-case donor train/val and test for paired forcing ablation.
    for label,features in feature_sets.items():
        ft,fv=augment(tr,forcing,features),augment(va,forcing,features)
        flt,flv=augment(lt,forcing,features),augment(lv,forcing,features)
        counts={"donor_train":{s:len(v) for s,v in ft.items()},
                "donor_validation":{s:len(v) for s,v in fv.items()},
                "target_train":len(flt[held]),"target_validation":len(flv[held]),
                "target_test":sum(d in forcing and all(f in forcing[d] for f in features)
                                  for d,_,_,_ in predictions)}
        detail=dict(features=list(features),counts=counts,status="insufficient_train_or_validation")
        metadata["forcing"][label]=detail
        # Always emit full-date fallback policies, even when a fold cannot fit forcing.
        for _,_,_,preds in predictions:
            preds[label+"_zero_shot_fallback"]=preds["zero_shot_blend"]
            preds[label+"_adapted_fallback"]=preds["adapted_blend"]
        if not adequate(ft,fv):
            continue
        try:
            model=fit_residual(ft,fv)
            noforce=fit_residual({s:[(d,x[:2],y) for d,x,y in rows] for s,rows in ft.items()},
                                 {s:[(d,x[:2],y) for d,x,y in rows] for s,rows in fv.items()})
        except ValueError as exc:
            detail.update(status="not_fitted",reason=str(exc))
            continue
        detail.update(status="fitted",forced=model,matched_unforced=noforce)
        # Optional zero-shot gate on donor validation; target-history
        # adapted gate is separate and only fitted when local coverage suffices.
        fw=gate_weights([(y,x[:2],predict(model,x),None,w) for x,y,w in weighted_rows(fv)])
        detail["zero_shot_gate"]=fw
        lm=aw=None
        if adequate(flt,flv):
            try:
                lm=fit_residual(flt,flv)
                aw=gate_weights([(y,x[:2],predict(model,x),predict(lm,x),w)
                                 for x,y,w in weighted_rows(flv)])
                detail.update(local_forced=lm,adapted_gate=aw)
            except ValueError as exc:
                detail["adapted_reason"]=str(exc)
                lm=aw=None
        for d,x,y,preds in predictions:
            available=d in forcing and all(f in forcing[d] for f in features)
            if available:
                xx=x+[forcing[d][f] for f in features]
                rp=predict(model,xx)
                preds[label+"_forced"]=rp
                preds[label+"_matched_unforced"]=predict(noforce,x)
                preds[label+"_zero_shot_matched"]=blend(fw,x,rp)
                if lm is not None:
                    preds[label+"_adapted_matched"]=blend(aw,x,rp,predict(lm,xx))
            # All-date operational-style policy, explicitly fallback rather
            # than dropping missing forcing days; archive availability unknown.
            preds[label+"_zero_shot_fallback"]=(preds.get(label+"_zero_shot_matched")
                                               or preds["zero_shot_blend"])
            if lm is not None:
                preds[label+"_adapted_fallback"]=(preds.get(label+"_adapted_matched")
                                                 or preds["adapted_blend"])
    rows=[]
    for d,x,y,preds in predictions:
        for name,values in preds.items():
            for j,c in enumerate(CONCEPTS):
                rows.append(dict(site_id=held,date=d,concept=c,model=name,actual=y[j],
                                 previous=x[j],prediction=values[j]))
    return metadata,rows
