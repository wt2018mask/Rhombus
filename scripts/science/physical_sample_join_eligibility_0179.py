"""0179: fail-closed experiment treatment vs SAME physical pellet identity audit.

The input is an explicitly derived, tiny, source-bounded 0178 receipt case:
- actual Zenodo XRD/EIS XLSX was independently rehashed in 0177+0178;
- literal public XRD/EIS cell labels and positions were observed;
- the author article describes group-level measurement methodology.
No row/table names, group overlaps, paper-wide die diameter or nominal
pellet thickness can prove an identical physical specimen identity.

This is an OFFLINE scientific falsifier, not a fictitious publisher signature.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

SCHEMA = "rhombus-0179-source-bounded-physical-join-case-v1"
EXPECTED_SOURCE_RECEIPT_SHA256="74b524eff113762913f0242c4788851d915102ba755a6bc64b9c7f7f9d86b492"
EXPECTED_SUPPORT_SHA256="22640fa76a00d90626cfe8fc2f3d4fc20ee71c3f87aba865f064960f1e3cd05e"
EXPECTED_DOI="10.1002/adma.202515013"
EXPECTED_OBS={
    "EIS S5":{"A3":"Pristine","M3":"2 Li-OPA"},
    "EIS humidity test S5":{"A1":"Pristine","O1":"2 Li-OPA"},
    "XRD & FTIR humid test S6":{"A3":"Pristine","E3":"2 Li-OPA"},
}
METHOD={"powder_mass_mg":80,"die_diameter_mm":9,"pressing_MPa":370,
        "external_measurement_pressure_MPa":20,"approx_thickness_mm":0.8,
        "electrochemical_instrument":"Biologic VSP-300",
        "frequency_range_Hz":[1,7000000],"ac_amplitude_mV":10,
        "conductivity_equation":"sigma = d/(R*A)",
        "reported_geometry_is_not_individual_pellet_measurement":True}


def audit(source:dict) -> dict:
    if not isinstance(source,dict) or source.get("schema_version")!=SCHEMA:
        raise ValueError("not original provenance scope")
    if (source.get("actual_0178_source_receipt_sha256")!=EXPECTED_SOURCE_RECEIPT_SHA256
        or source.get("actual_original_supporting_workbook_sha256")!=EXPECTED_SUPPORT_SHA256
        or source.get("article_DOI")!=EXPECTED_DOI):
        raise ValueError("actual independently observed original or author paper drift")
    if source.get("author_reported_EIS_method_not_pellet_specific")!=METHOD:
        raise ValueError("original EIS methodology drift")
    if source.get("author_reported_postmortem_XRD_humidity_conditions")!=[
        {"RH_percent":0.1,"temperature_C":25,"hours":12},
        {"RH_percent":9,"temperature_C":25,"hours":4}
    ]:
        raise ValueError("original author XRD humidity/time method drift")
    groups=source.get("actual_raw_source_text_groups")
    if not isinstance(groups,list) or len(groups)!=3:
        raise ValueError("three independently observed source label groups required")
    by_name={}
    for row in groups:
        if not isinstance(row,dict) or row.get("sheet") in by_name:
            raise ValueError("invalid/duplicate source sheet")
        name=row["sheet"]
        if name not in EXPECTED_OBS or row.get("source_cells")!=EXPECTED_OBS[name]:
            raise ValueError("original physical-context cell names/coordinates drift")
        if row.get("measurement")!=("XRD" if "XRD" in name else "EIS"):
            raise ValueError("original source modality drift")
        by_name[name]=row
    if set(by_name)!=set(EXPECTED_OBS):
        raise ValueError("required source EIS/XRD group not found")
    if (by_name["EIS S5"].get("exposure_hours")!=[] or
        by_name["EIS humidity test S5"].get("exposure_hours")!=[0,12,24] or
        by_name["XRD & FTIR humid test S6"].get("exposure_hours")!=[12,4]):
        raise ValueError("time mismatch in verified source groups")
    # Do not accept a claimed join in this public input: the independent
    # laboratory must separately provide a source-bound individually keyed
    # specimen protocol; the existing strict P0 gate handles real acceptance.
    required_false=(
        "lab_signed_pellet_EIS_XRD_join_received",
        "independent_external_evaluator_signed_roster_received",
        "individual_pellet_EIS_geometry_uncertainty_record_received",
    )
    if any(source.get(field) is not False for field in required_false):
        raise ValueError("unauthorized self-attested physical or steward evidence")
    if (source.get("validated_exact_eis_pellet_to_xrd_specimen_pairs")!=0
        or source.get("source_does_not_attest_individual_pellet_ids") is not True
        or source.get("raw_cross_source_label_duplicate_is_treatment_not_pellet") is not True
        or source.get("scientific_GO") is not False):
        raise ValueError("cannot promote a public treatment label to a physical pellet")
    return {
        "schema_version":"rhombus-0179-pellet-linkage-negative-decision-v1",
        "original_observation_artifact":source["actual_0178_artifact"],
        "original_cell_receipt_sha256":EXPECTED_SOURCE_RECEIPT_SHA256,
        "author_paper_DOI":EXPECTED_DOI,
        "matched_conditions_only":[
            {"treatment":"Pristine","original_XRD":"XRD & FTIR humid test S6:A3",
             "original_EIS":"EIS humidity test S5:A1","join_level":"TREATMENT_ONLY"},
            {"treatment":"2 Li-OPA","original_XRD":"XRD & FTIR humid test S6:E3",
             "original_EIS":"EIS humidity test S5:O1","join_level":"TREATMENT_ONLY"}
        ],
        "XRD_9_percent_RH_4h_has_exact_matching_EIS_exposure_time":False,
        "XRD_0p1_percent_RH_12h_has_EIS_12h_treatment_context_not_pellet_ID":True,
        "nominal_published_pellet_geometry_is_not_per_pellet_measurement":True,
        "source_specific_raw_XRD_EIS_individual_pellet_IDs":None,
        "independent_original_lab_signed_join_receipt":None,
        "unique_independently_attested_pellet_pairs":0,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_GO":False,
        "next_step":"Obtain original EIS pellet ID ↔ exact XRD preparation or pellet ID, source raw EIS fit+geometry+T+uncertainty and original controlled replicate map directly from the lab; independent blind stewardship separately required",
    }


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--input",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    b=args.input.read_bytes()
    if len(b)>30000:raise ValueError("unbounded derived experimental provenance case")
    obj=json.loads(b)
    result=audit(obj)
    target=args.output
    target.parent.mkdir(parents=True,exist_ok=True)
    if target.exists():raise ValueError("append-only scientific receipt collision")
    target.write_text(json.dumps(result,sort_keys=True,allow_nan=False,indent=2)+"\n",encoding="utf-8")
    print("0179_REAL_ORIGINAL_TREATMENT_OVERLAP_NOT_PELLET_JOIN_PASS")
    print(json.dumps({"treatment_overlap":[x["treatment"] for x in result["matched_conditions_only"]],
       "certified_pellet_pairs":0,"P0_03":result["P0_03"],"GO":result["scientific_GO"]},sort_keys=True))


if __name__=="__main__":
    main()
