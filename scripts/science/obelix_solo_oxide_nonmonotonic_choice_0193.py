"""0193: retrospective, unauthenticated trivial-heuristic diagnostic.

This does NOT invent another experimental paper or consume original TEST labels.
Caller-provided source fields are assertions, not authenticated publication
evidence. Diagnostic eligibility never constitutes source admission.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

SCHEMA="rhombus-0193-nonmonotonic-choice-diagnostic-v2"
SOURCES=(
    {"doi":"10.1039/c8ra01329b","exact_25C":True,"process_type":"numeric_sintering",
     "temp_C":[1100,1150,1200,1210,1220],"best_sample":"LLZALO-4",
     "sample_names":["LLZALO-1","LLZALO-2","LLZALO-3","LLZALO-4","LLZALO-5"],
     "evidence":"0191 original RSC 2018 Table1 and Table3"},
    {"doi":"10.3390/ma13030560","exact_25C":True,"process_type":"numeric_sintering",
     "temp_C":[1200,1200,1150,1100,1100],"best_sample":"SL2",
     "sample_names":["SL1","SL2","SL3","SL4","SL5"],
     "evidence":"0191 original Materials 2020 Table2"},
    {"doi":"10.1021/acsomega.2c06544","exact_25C":False,"process_type":"numeric_sintering",
     "temp_C":[1050,1100]*5,"best_sample":None,"sample_names":[],
     "evidence":"0192 original ACS 2022 room-temperature not exact 25C; five paired conditions"},
)
def classify(source):
    if not isinstance(source.get("exact_25C"),bool):
        raise ValueError("exact-temperature status must be authenticated")
    if not source["exact_25C"]:
        return {"doi":source["doi"],"admitted":False,"diagnostic_eligible":False,"source_authentication":"NOT_PERFORMED","reason":"NOT_EXACT_25C",
                "nonmonotonic":None,"trivial_hotter_top1_correct":None}
    if source.get("process_type")!="numeric_sintering":
        return {"doi":source["doi"],"admitted":False,"diagnostic_eligible":False,"source_authentication":"NOT_PERFORMED","reason":"INCOMPATIBLE_PROCESS",
                "nonmonotonic":None,"trivial_hotter_top1_correct":None}
    names=source["sample_names"];temps=source["temp_C"];best=source["best_sample"]
    if len(names)<2 or len(names)!=len(temps) or len(set(names))!=len(names) or best not in names:
        raise ValueError("missing or ambiguous source-verified condition pairing")
    if any(type(t) not in (int,float) or not 900<=t<=1400 for t in temps):
        raise ValueError("untrusted sintering temperature")
    highest=max(temps)
    # An always-hotter rule is only unambiguously wrong if ALL maximum-T
    # conditions differ from the observed best; ties cannot be scored as wins.
    best_temp=temps[names.index(best)]
    hotter_wrong=best_temp<highest
    return {"doi":source["doi"],"admitted":False,"diagnostic_eligible":True,
            "source_authentication":"NOT_PERFORMED","reason":"CALLER_ASSERTED_EXACT_25C",
            "nonmonotonic":hotter_wrong,
            "trivial_hotter_top1_correct":False if hotter_wrong else
                 (True if temps.count(highest)==1 else None),
            "max_temperature_C":highest,"observed_best_temperature_C":best_temp}

def report(sources=SOURCES):
    rows=[classify(x) for x in sources]
    admitted=[x for x in rows if x["diagnostic_eligible"]]
    challenging=[x for x in admitted if x["nonmonotonic"]]
    return {"schema_version":SCHEMA,"evidence_status":"DIAGNOSTIC_ONLY",
            "source_authentication":"NOT_PERFORMED","sources":rows,
            "historical_assertions_provenance":"HISTORICAL_RECORD_NOT_RECOMPUTED_FROM_INPUT",
            "caller_asserted_exact_25C_diagnostic_count":len(admitted),
            "diagnostic_nonmonotonic_source_count":len(challenging),
            "diagnostic_nonmonotonic_source_DOIs":[x["doi"] for x in challenging],
            "new_independent_unexposed_DOIs":0,
            "0191_RSC_process_model_wrong_choice":True,
            "0192_RT_trivial_hotter_heuristic_wins_all_five_pairs":True,
            "source_heldout_nonmonotonic_benchmark_qualified":False,
            "verdict":"INCONCLUSIVE",
            "scientific_GO":False,"production_enabled":False,
            "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
            "next_action":"0194-SOLO-O_ONLY-NEW_EXACT_25C_NONMONOTONIC_DOI_SOURCE"}
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--output",type=Path,required=True)
    args=p.parse_args()
    d=report()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    if args.output.exists():raise ValueError("refuse to overwrite prior science evidence")
    args.output.write_text(json.dumps(d,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print("0193_NONMONOTONIC_DIAGNOSTIC_ONLY",json.dumps(d,sort_keys=True))
if __name__=="__main__":main()
