"""M10.4: typed research inference over frozen experts, never a deployed model.

Geography and subsystem taxonomy route requests; they do not create physical
connections. Only M10.3 validation-selected weights are used for mixtures.
"""
from datetime import date,timedelta
from math import isfinite,isclose
from statistics import mean
from visuals.hierarchy import classify
from .regional_fcm import CONCEPTS
from .residual_fcm import predict as residual_predict
from .m10_forcing import FEATURES


def finite(values):
    return all(isfinite(float(v)) for v in values)


def validate_station_model(model,concepts):
    n=len(concepts)
    if (n<2 or len(set(concepts))!=n or model["concepts"]!=concepts or
        len(model["matrix_source_to_target"])!=n or
        any(len(r)!=n or not finite(r) or any(abs(v)>1.000001 for v in r)
            for r in model["matrix_source_to_target"])):
        raise ValueError("invalid station model concept/matrix")
    for k in ("normalization_mean","normalization_scale","intercepts"):
        if len(model[k])!=n or not finite(model[k]):
            raise ValueError("invalid station scaler/intercepts")
    if any(s<=0 for s in model["normalization_scale"]):
        raise ValueError("invalid station scale")
    if not (model["train_start"]<=model["train_end"]<model["validation_start"]
            <=model["validation_end"]<model["test_start"]<=model["test_end"]):
        raise ValueError("invalid station chronology")


def station_predict(model,state):
    cs=model["concepts"]
    if any(c not in state for c in cs) or not finite([state[c] for c in cs]):
        raise ValueError("missing or invalid station state")
    mu,sd=model["normalization_mean"],model["normalization_scale"]
    z=[(float(state[c])-m)/s for c,m,s in zip(cs,mu,sd)]
    return {c:mu[j]+sd[j]*max(-3.,min(3.,model["intercepts"][j]+
                sum(z[i]*model["matrix_source_to_target"][i][j] for i in range(len(cs)))))
            for j,c in enumerate(cs)}


def validate_residual(model,sites,dim,train_end,val_end):
    if (model["fit_sites"]!=sorted(sites) or len(model["means"])!=dim or
        len(model["scales"])!=dim or len(model["delta_scales"])!=2 or
        len(model["weights"])!=2 or any(len(w)!=dim+1 for w in model["weights"]) or
        not finite(model["means"]+model["scales"]+model["delta_scales"]+
                   [v for w in model["weights"] for v in w]) or
        any(v<=0 for v in model["scales"]+model["delta_scales"]) or
        model["bounded"] is not True or
        any(abs(v)>1.000001 for w in model["weights"] for v in w[1:]) or
        not model["train_end"]<=train_end<model["validation_end"]<=val_end):
        raise ValueError("invalid residual fit identity, dimensions or chronology")


def validate_gate(weights,local):
    if len(weights)!=2 or any(len(w)!=3 or not finite(w) or
        any(v<0 or v>1 for v in w) or not isclose(sum(w),1.,abs_tol=1e-10) or
        (not local and w[2]!=0) for w in weights):
        raise ValueError("invalid convex mixture weights")


def validate_fold(site,fold,sites,train_end,val_end):
    donors=sorted(set(sites)-{site})
    validate_residual(fold["residual_regional"],donors,2,train_end,val_end)
    validate_residual(fold["residual_local"],[site],2,train_end,val_end)
    if fold["gate_validation_sites"]!={"zero_shot":donors,"adapted":[site]}:
        raise ValueError("invalid gate validation sites")
    validate_gate(fold["zero_shot_gate"],False)
    validate_gate(fold["adapted_gate"],True)
    for scope,f in fold["forcing"].items():
        if scope not in FEATURES or f["features"]!=list(FEATURES[scope]):
            raise ValueError("unexpected forcing scope")
        if f["status"]!="fitted":
            continue
        dim=2+len(f["features"])
        validate_residual(f["forced"],donors,dim,train_end,val_end)
        validate_gate(f["zero_shot_gate"],False)
        if "local_forced" in f:
            validate_residual(f["local_forced"],[site],dim,train_end,val_end)
            validate_gate(f["adapted_gate"],True)


def mix_components(fold,state,concept,mode,scope,forcing):
    """Return prediction and exact component weights, with explicit fallback."""
    if mode not in ("zero_shot","adapted") or scope not in ("unforced",*FEATURES):
        raise ValueError("invalid mixture policy")
    x=[float(state[c]) for c in CONCEPTS]
    if not finite(x):
        raise ValueError("nonfinite state")
    j=CONCEPTS.index(concept)
    use=scope
    f=fold["forcing"].get(scope,{})
    ready=(scope!="unforced" and f.get("status")=="fitted" and
           all(k in forcing and finite([forcing[k]]) for k in FEATURES[scope]) and
           (mode=="zero_shot" or "local_forced" in f))
    if ready:
        xx=x+[float(forcing[k]) for k in FEATURES[scope]]
        regional=residual_predict(f["forced"],xx)[j]
        local=residual_predict(f["local_forced"],xx)[j] if mode=="adapted" else None
        weights=f[mode+"_gate"][j]
    else:
        use="unforced"
        regional=residual_predict(fold["residual_regional"],x)[j]
        local=residual_predict(fold["residual_local"],x)[j] if mode=="adapted" else None
        weights=fold[mode+"_gate"][j]
    values=[x[j],regional,local]
    result=sum(w*v for w,v in zip(weights,values) if v is not None)
    return dict(prediction=result,scope_used=use,
                fallback_reason="forcing_missing_or_unfitted" if scope!=use else "",
                weights=dict(zip(("persistence","regional","local"),weights)),
                components=dict(zip(("persistence","regional","local"),values)))


class ResearchRouter:
    """Archive-only one-day inference; no test actual enters routing."""
    def __init__(self,stations,registry,models,folds,forcing,cohort):
        self.stations=stations
        self.registry=registry
        self.models=models
        self.folds=folds
        self.forcing=forcing
        self.cohort=cohort

    def infer(self,site,target_date,concept,policy="persistence",scope="unforced",
              expert_id=None,region=None):
        if policy not in ("persistence","station","category","subcategory",
                          "zero_shot","adapted","expert"):
            raise ValueError("unknown research policy")
        if scope not in ("unforced",*FEATURES):
            raise ValueError("unknown forcing scope")
        if policy not in ("zero_shot","adapted") and scope!="unforced":
            raise ValueError("forcing applies only to mixture policies")
        if (expert_id is None)!=(policy!="expert"):
            raise ValueError("expert policy requires explicit expert_id")
        if site not in self.stations:
            raise ValueError("unknown station; no transferable deployment expert")
        s=self.stations[site]
        d=date.fromisoformat(target_date)
        previous=(d-timedelta(days=1)).isoformat()
        if target_date not in s["allowed_dates"]:
            raise ValueError("target date outside archived research window")
        if previous not in s["states"] or concept not in s["units"]:
            raise ValueError("no previous-day observed state/concept; abstain")
        state=s["states"][previous]
        if concept not in state or not finite([state[concept]]):
            raise ValueError("missing previous-day observation; abstain")
        cat,sub=classify(concept)
        result=dict(site_id=site,target_date=target_date,issue_date=target_date,
                    state_date=previous,concept=concept,unit=s["units"][concept],
                    primary_region=s["primary_region"],category=cat,subcategory=sub,
                    requested_policy=policy,requested_scope=scope,
                    requested_region=region or "",
                    selected_expert="persistence:"+site,scope_used="unforced",
                    prediction=float(state[concept]),weights={"persistence":1.},
                    components={"persistence":float(state[concept])},
                    fallback_reason="",research_only=True,as_issued_verified=False)
        if policy=="persistence":
            return result
        if policy in ("zero_shot","adapted"):
            if region not in (None,self.cohort["region_screen"]):
                result["fallback_reason"]="no_regional_expert_for_requested_region"
                return result
            if (site not in self.folds or concept not in CONCEPTS or
                not self.cohort["validation_target_date_end"]<target_date<=self.cohort["end"]):
                result["fallback_reason"]="no_compatible_regional_holdout_expert"
                return result
            if any(c not in state for c in CONCEPTS):
                result["fallback_reason"]="missing_required_state"
                return result
            mix=mix_components(self.folds[site],state,concept,policy,scope,
                               self.forcing.get(target_date,{}))
            result.update(mix,selected_expert=f"mixture:{site}:{policy}:{mix['scope_used']}",
                          effective_region=self.cohort["region_screen"])
            return result
        if region not in (None,s["primary_region"]):
            result["fallback_reason"]="no_station_expert_for_requested_region"
            return result
        if policy=="expert":
            entry=self.registry.get(expert_id)
            if entry is None or entry["site_id"]!=site or entry["kind"]!="station_fcm":
                raise ValueError("explicit expert is not a station FCM for this site")
            candidates=[entry]
        else:
            level={"station":"dataset","category":"category","subcategory":"subcategory"}[policy]
            candidates=[e for e in self.registry.values() if e["kind"]=="station_fcm" and
                        e["site_id"]==site and e["level"]==level and
                        concept in e["concepts"] and (level=="dataset" or e["category"]==cat)
                        and (level!="subcategory" or e["subcategory"]==sub)]
        if len(candidates)>1:
            raise ValueError("ambiguous expert scope")
        if not candidates or concept not in candidates[0]["concepts"]:
            result["fallback_reason"]="no_fitted_station_scope"
            return result
        e=candidates[0]
        model=self.models[e["expert_id"]]
        if not model["test_start"]<=target_date<=model["test_end"]:
            result["fallback_reason"]="outside_station_holdout"
            return result
        if any(c not in state for c in model["concepts"]):
            result["fallback_reason"]="missing_required_state"
            return result
        v=station_predict(model,state)[concept]
        result.update(selected_expert=e["expert_id"],prediction=v,
                      weights={e["expert_id"]:1.},components={e["expert_id"]:v})
        return result
