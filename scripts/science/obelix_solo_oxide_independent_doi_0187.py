"""0187: two original DOI O_ONLY 25C TOTAL single-garnet source-group diagnostic.

Fetch genuine 2025 RSC JATS and a different-laboratory primary archived Elsevier
article PDF. Keep only the three single-composition reference EIS observations
from the new paper: mixed co-sintered bi-layer devices are never mapped onto
one chemical formula. TWO source papers are not an independent-power claim.
"""
from __future__ import annotations
import argparse,hashlib,json,math,re,tempfile,unicodedata
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen
import numpy as np
from rhombus.qualification.obelix_benchmark_intake import SOURCE_COMMIT,build_obelix_benchmark_intake,_json_bytes
from scripts.science.obelix_real_grouped_oof_0146 import _composition,run_official_original_oof
from scripts.science.obelix_rf_mlp_frozen_group_oof_0147 import RF_PARAMS
from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
from scripts.science.obelix_solo_family_specialists_0184 import RIDGE_ALPHA
from scripts.science.obelix_solo_oxide_primary_0186 import (
    ORIGINAL_JATS,get_original,FORMULAS as PAPER0186_FORMULAS,
    PRISTINE as PAPER0186_PRISTINE,SOURCE_DOI as PAPER0186_DOI,
    components_to_embargo,
)
from scripts.science.obelix_solo_oxide_external_0185 import doi

SCHEMA="rhombus-0187-solo-original-two-DOI-25C-TOTAL-LLZO-v1"
NEW_DOI="10.1016/j.jeurceramsoc.2024.116936"
NEW_PDF="https://juser.fz-juelich.de/record/1035145/files/1-s2.0-S0955221924008094-main.pdf"
MAX_PDF_BYTES=10_000_000
NEW_GA="Li6.4Ga0.2La3Zr2O12"
NEW_TA="Li6.45Al0.05La3Zr1.6Ta0.4O12"
# Fixed single-phase reference states, NOT two-layer heterogeneous composites.
NEW_REFERENCE_ROWS=(
    ("GA_REFERENCE",NEW_GA,1.70e-3),
    ("TA_0PCT_LI_EXCESS",NEW_TA,7.53e-4),
    ("TA_10PCT_LI_EXCESS",NEW_TA,6.69e-4),
)
# Excluded co-sintered two-material composite conductivities. MUST be present
# in the original table but never converted to one nominal formula.
NEW_COMPOSITE_EXCLUDED=(1.60e-5,6.22e-5)
MODELS=("POOLED_RF","O_ONLY_RF","O_ONLY_RIDGE","O_ONLY_TRAIN_MEAN")


def norm(s):
    s=unicodedata.normalize("NFKC",s)
    for a,b in (("\u2212","-"),("\u2010","-"),("\u2011","-"),("\u2013","-"),
                ("\u2014","-"),("\u00ad",""),("\u2060",""),("\u00d7","x"),
                ("\u2218","o"),("\u200b",""),("\x02","")):
        s=s.replace(a,b)
    return re.sub(r"\s+"," ",s).strip()

def no_spaces(s):
    return re.sub(r"[^a-z0-9.]","",norm(s).lower())

def verify_pdf_text(pages):
    """Strong primary SOURCE/context and table unit/row-order bound checks."""
    if not isinstance(pages,(list,tuple)) or len(pages)!=7:
        raise ValueError("publisher paper must have exactly seven PDF pages")
    if not all(isinstance(x,str) and x.strip() for x in pages):
        raise ValueError("truncated primary PDF page")
    cover=norm(pages[0]).lower()
    if (NEW_DOI not in cover or
        "ga-ion migration during co-sintering" not in cover or
        "scheld" not in cover or "journal of the european ceramic society" not in cover):
        raise ValueError("original DOI/title/author identity mismatch")
    methods=norm(" ".join(pages[1:3])).lower()
    compact=no_spaces(" ".join(pages[1:3]))
    if (no_spaces(NEW_GA.lower()) not in compact or
        no_spaces(NEW_TA.lower()) not in compact):
        raise ValueError("nominal single-material Ga/Ta composition not authenticated")
    if not re.search(r"eis\s*measurements",methods):
        raise ValueError("original EIS measurement methods not found")
    if not re.search(r"at\s+25\s*(?:o|°|degrees)?\s*c",methods):
        raise ValueError("must measure at 25C rather than infer room temperature")
    table=norm(pages[5]).lower()
    if "table 2" not in table:
        raise ValueError("original publisher table 2 unavailable")
    table=table[table.index("table 2"):]
    if ("total ionic conductivity" not in table or
        not re.search(r"measured\s+at\s+25\s*(?:o|°|degrees)?\s*c",table)):
        raise ValueError("source table is not 25C TOTAL ionic conductivity")
    # Row/number pairing is kept in publisher table order: not an image-digitization.
    expected=(
        (r"llzo\s*:\s*ga",r"1\.70\s*[x*]\s*10\s*-\s*3"),
        (r"llzo\s*:\s*ta\s*0\s*%\s*li\s*excess",r"7\.53\s*[x*]\s*10\s*-\s*4"),
        (r"llzo\s*:\s*ta\s*10\s*%\s*li\s*excess",r"6\.69\s*[x*]\s*10\s*-\s*4"),
        (r"llzo\s*:\s*ga\s*\|\s*llzo\s*:\s*ta\s*0\s*%\s*li\s*excess",r"1\.60\s*[x*]\s*10\s*-\s*5"),
        (r"llzo\s*:\s*ga\s*\|\s*llzo\s*:\s*ta\s*10\s*%\s*li\s*excess",r"6\.22\s*[x*]\s*10\s*-\s*5"),
    )
    spans=[]
    for label,qty in expected:
        m=re.search(label+r"\s+"+qty,table)
        if not m:raise ValueError("missing or mispaired original Table 2 reference/composite quantity "+label)
        spans.append(m.start())
    if spans!=sorted(spans) or len(set(spans))!=5:
        raise ValueError("source table ordering inconsistent")
    return {
        "DOI":NEW_DOI,"original_publisher_article_title_validated":True,
        "original_pdf_seven_pages_verified":True,
        "table":"Table 2","temperature_C":25,
        "endpoint":"AUTHOR_TOTAL_IONIC_CONDUCTIVITY_S_CM",
        "single_material_reference_rows":3,
        "heterogeneous_two_layer_composite_rows_EXCLUDED":2,
        "nominal_Ga_formula":NEW_GA,"nominal_Ta_formula":NEW_TA,
        "external_independent_DOI_vs_0186":NEW_DOI!=PAPER0186_DOI,
        "same_physical_pellet_XRD_EIS_identity_authenticated":False,
    }

def primary_pdf():
    import fitz
    req=Request(NEW_PDF,headers={"Accept":"application/pdf",
                 "User-Agent":"Rhombus-0187-public-original-research-evidence"})
    with urlopen(req,timeout=45) as resp:
        final=urlsplit(resp.geturl())
        target=urlsplit(NEW_PDF)
        if (final.scheme,final.hostname,final.path)!=(target.scheme,target.hostname,target.path):
            raise ValueError("original deposit redirect identity mismatch")
        body=resp.read(MAX_PDF_BYTES+1)
    if len(body)>MAX_PDF_BYTES or not body.startswith(b"%PDF-"):
        raise ValueError("external author PDF invalid or over budget")
    with fitz.open(stream=body,filetype="pdf") as pdf:
        if pdf.page_count!=7:raise ValueError("author pdf pages drift")
        pages=[p.get_text("text",sort=True) for p in pdf]
    report=verify_pdf_text(pages)
    report["original_pdf_SHA256"]=hashlib.sha256(body).hexdigest()
    return report

def extended_train_embargo(records,arrays):
    """Preserve original 0186 transitive group and quarantine new DOI/formula."""
    mask,prior_count,prior_match=components_to_embargo(
        records,arrays["source_ids"],arrays["groups"])
    new_reduced=_composition(NEW_TA)[0]
    # The 0186 group parser already proves all TRAIN source components.
    # If the new nominal Ta has already been seen in TRAIN, fail closed:
    # no claim of outside-source validation from an unembargoed group.
    contaminated=0
    for v in records:
        if v.get("official_split")=="TEST":
            continue  # Never read original TEST fields.
        if v.get("official_split")!="TRAIN":
            raise ValueError("invalid OBELiX split")
        raw=v.get("reported_composition")
        parsed=_composition(raw)
        if (parsed and parsed[0]==new_reduced) or NEW_DOI in [doi(d) for d in v.get("reference_dois",[])]:
            contaminated+=1
    if contaminated:
        raise ValueError("new original DOI/nominal formula overlaps existing TRAIN; must implement full-group embargo before scoring")
    return mask,prior_count,prior_match,contaminated

def score_two_papers(prior,arrays,records,old,new):
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    if (prior["original_upstream_commit"]!=SOURCE_COMMIT or
        prior["original_source_train_count"]!=478 or
        prior["original_official_test_reserved_unread"]!=121 or
        prior["original_raw_censored_upper_bounds_excluded"]!=29 or
        prior["scientific_qualification_authorized"] is not False):
        raise ValueError("original TRAIN verification drift")
    if old.get("original_doi")!=PAPER0186_DOI or old.get("measurement_temperature_C")!=25:
        raise ValueError("first paper 25C measurement identity missing")
    if new["DOI"]==old["original_doi"] or new["temperature_C"]!=25:
        raise ValueError("source independent DOI and exact measurement temperature required")
    mask,removed,prior_match,contaminated=extended_train_embargo(records,arrays)
    x=np.asarray(arrays["x"]);y=np.asarray(arrays["y"])
    if x.shape!=(449,118) or y.shape!=(449,) or len(mask)!=len(y):
        raise ValueError("official TRAIN population drift")
    train_idx=np.where(mask)[0]
    oxide_idx=np.array([i for i in train_idx if _family_proxy(x[i])=="O_ONLY"],dtype=int)
    if len(train_idx)<300 or len(oxide_idx)<100:
        raise ValueError("too few eligible original TRAIN records")
    # Two DOI source groups (2 observations in old, 3 in new).
    labels=(
        (PAPER0186_DOI,"TA0186_PRISTINE",PAPER0186_FORMULAS[0],PAPER0186_PRISTINE[0]),
        (PAPER0186_DOI,"GA0186_PRISTINE",PAPER0186_FORMULAS[1],PAPER0186_PRISTINE[1]),
        (NEW_DOI,NEW_REFERENCE_ROWS[0][0],NEW_REFERENCE_ROWS[0][1],NEW_REFERENCE_ROWS[0][2]),
        (NEW_DOI,NEW_REFERENCE_ROWS[1][0],NEW_REFERENCE_ROWS[1][1],NEW_REFERENCE_ROWS[1][2]),
        (NEW_DOI,NEW_REFERENCE_ROWS[2][0],NEW_REFERENCE_ROWS[2][1],NEW_REFERENCE_ROWS[2][2]),
    )
    features=np.asarray([_composition(v[2])[1] for v in labels])
    if any(_family_proxy(f)!="O_ONLY" for f in features):
        raise ValueError("unexpected non-oxide target")
    rf=RandomForestRegressor(**RF_PARAMS).fit(x[train_idx],y[train_idx])
    orf=RandomForestRegressor(**RF_PARAMS).fit(x[oxide_idx],y[oxide_idx])
    ridge=make_pipeline(StandardScaler(),Ridge(alpha=RIDGE_ALPHA)).fit(x[oxide_idx],y[oxide_idx])
    truth=np.log10(np.asarray([v[3] for v in labels],dtype=float))
    predictions={
        "POOLED_RF":rf.predict(features),
        "O_ONLY_RF":orf.predict(features),
        "O_ONLY_RIDGE":ridge.predict(features),
        "O_ONLY_TRAIN_MEAN":np.full(len(labels),float(y[oxide_idx].mean())),
    }
    vals={}
    for name,pred in predictions.items():
        if len(pred)!=5 or not np.isfinite(pred).all():
            raise ValueError("numeric external score invalid")
        err=np.abs(pred-truth)
        p1=float(err[:2].mean())
        p2=float(err[2:].mean())
        vals[name]={
            "row_MAE_log10":round(float(err.mean()),8),
            "equal_independent_paper_macro_MAE_log10":round((p1+p2)/2,8),
            "first_DOI_two_records_MAE_log10":round(p1,8),
            "second_DOI_three_single_material_references_MAE_log10":round(p2,8),
            "second_DOI_mixed_layer_records_scored":0,
        }
    return {
        "schema_version":SCHEMA,
        "original_primary_authentication":[old,new],
        "source_DOI_groups":[PAPER0186_DOI,NEW_DOI],
        "independent_publisher_papers":2,
        "lab_groups_claimed":2,
        "source_values_published_before_this_protocol":True,
        "not_strict_prospective_blind":True,
        "measurement_temperature_C":25,
        "measurement_type":"AUTHOR_TOTAL_IONIC_CONDUCTIVITY",
        "source_0186_reference_rows":2,
        "source_0187_single_material_reference_rows":3,
        "source_0187_heterogeneous_two_layer_composite_EXCLUDED":2,
        "cross_paper_duplicate_nominal_Ga_formula_linked_to_one_material_key":True,
        "different_nominal_formulas_total":3,
        "second_paper_Ta_Li_excess_conditions_share_nominal_composition":True,
        "two_paper_group_bootstrap_forbidden":True,
        "equal_paper_macro_insufficient_for_statistical_significance":True,
        "original_OBELIX_TRAIN":478,
        "original_OBELIX_numeric_TRAIN":449,
        "original_OBELIX_TEST_reserved_UNREAD":121,
        "original_OBELIX_TEST_field_decode_performed":False,
        "source_group_TRAIN_embargo_existing_0186":removed,
        "source_0186_TRAIN_identity_direct_matches":prior_match,
        "source_0187_TRAIN_identity_direct_matches":contaminated,
        "actual_train_rows_after_embargo":len(train_idx),
        "actual_O_ONLY_train_rows_after_embargo":len(oxide_idx),
        "frozen_models":list(MODELS),
        "source_independent_paper_macro_results":vals,
        "two_paper_group_robust_success":False,
        "research_candidate_only_NOT_production_or_physical_GO":True,
        "newly_authenticated_same_specimen_XRD_EIS_pellets":0,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "production_O_ONLY_router_enabled":False,
        "scientific_EXTERNAL_GO":False,
        "next_action":"0188-SOLO-O_ONLY-LARGER-INDEPENDENT-SOURCE-GROUP-SCORING",
    }

def run(obelix,output):
    original=obelix.resolve(strict=True)
    if output.exists() or original in output.resolve().parents:raise ValueError("immutable output/source separated")
    with tempfile.TemporaryDirectory(prefix="rhombus-0187-") as tmp:
        prior,arrays=run_official_original_oof(original,Path(tmp)/"original",return_internal=True)
        records,_=build_obelix_benchmark_intake(original,expected_commit=SOURCE_COMMIT)
        old=get_original()
        new=primary_pdf()
        result=score_two_papers(prior,arrays,records,old,new)
    output.mkdir(parents=True,exist_ok=False)
    (output/"0187_two_primary_DOI_O_ONLY_25C_total.json").write_bytes(_json_bytes(result)+b"\n")
    return result

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--original-obelix-checkout",type=Path,required=True)
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    v=run(a.original_obelix_checkout,a.output_dir)
    print("0187_SOLO_REAL_SECOND_PAPER_ORIGINAL_25C_TOTAL_DIAGNOSTIC_COMPLETE")
    print(json.dumps({"sources":v["source_DOI_groups"],"rows":5,
        "independent_DOI_groups":v["independent_publisher_papers"],
        "scores":v["source_independent_paper_macro_results"],
        "scientific_GO":False},sort_keys=True))
