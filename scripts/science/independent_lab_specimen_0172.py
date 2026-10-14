"""0172: first-party full-text independent-lab physical specimen linkage audit.

Independent Tu/Phuc HCMUT 2025 RSC Advances Li7P3S11; PMC JATS is an
authoritative original article full-text deposit, NOT a confidential blind.
A powder *series* label S-250 does not establish a particular EIS pellet is
the same physical specimen as the XRD or NMR material. This audit never
manufactures a per-pellet ID, geometry, replicate or exact phase linkage.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import tempfile
import unicodedata
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

SCHEMA="rhombus-0172-independent-lab-jats-specimen-physical-linkage-v1"
DOI="10.1039/d5ra05281e"
PMCID="PMC12435569"
ORIGINAL_JATS="https://www.ebi.ac.uk/europepmc/webservices/rest/PMC12435569/fullTextXML"
MAX_XML_BYTES=7_000_000
ORIGINAL_SERIES=("S-240","S-250")
ORIGINAL_CONDUCTIVITY_SCM=(7.2e-4,1.5e-3)


def norm(text: str) -> str:
    text=unicodedata.normalize("NFKC",text)
    text=text.replace("\u2212","-").replace("\u2010","-").replace("\u2011","-")
    text=text.replace("\u00d7","x")
    text=re.sub(r"\s+"," ",text).strip()
    return text


def tag(node) -> str:
    return node.tag.split("}")[-1] if isinstance(node.tag,str) else ""


def _author_paragraphs(root) -> list[str]:
    return [norm("".join(node.itertext())) for node in root.iter()
            if tag(node)=="p" and norm("".join(node.itertext()))]


def parse_primary_jats(raw: bytes) -> dict:
    if not isinstance(raw,bytes) or len(raw)>MAX_XML_BYTES or not raw:
        raise ValueError("invalid original XML byte size")
    if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
        raise ValueError("unsupported JATS doctype/entity")
    try:
        root=ET.fromstring(raw)
    except ET.ParseError as exc:
        raise ValueError("original JATS XML is malformed") from exc
    if tag(root)!="article":
        raise ValueError("not original deposited journal article")
    ids={norm("".join(n.itertext())).lower()
         for n in root.iter() if tag(n)=="article-id"
         and n.attrib.get("pub-id-type","").lower()=="doi"}
    pmc={norm("".join(n.itertext())).upper().removeprefix("PMC")
         for n in root.iter() if tag(n)=="article-id"
         and n.attrib.get("pub-id-type","").lower() in ("pmc","pmcid")}
    if DOI not in ids or "12435569" not in pmc:
        raise ValueError("DOI/PMC article identity not both independently bound")
    paragraphs=_author_paragraphs(root)
    article_body=[n for n in root.iter() if tag(n)=="body"]
    if len(article_body)!=1:
        raise ValueError("unexpected article body count")
    body_paras=_author_paragraphs(article_body[0])
    if len(body_paras)<8:
        raise ValueError("too little original full-text to admit physical source")
    full=" ".join(body_paras)
    if not ("Li7P3S11" in norm(full).replace(" ","") or
            "Li7P3S11" in "".join(norm(full).split())):
        raise ValueError("wrong nominal chemical family")
    if not all(v in full for v in ORIGINAL_SERIES):
        raise ValueError("both named powder batches missing")
    if not (re.search(r"510\s*MPa",full,re.I) and
            re.search(r"200\s*mg",full,re.I) and
            "pellet" in full.lower() and
            ("impedance spectroscopy" in full.lower() or "impedance" in full.lower())):
        raise ValueError("source original pellet EIS and compaction evidence missing")
    if not any(
        ("XRD" in p or "X-ray diffraction" in p)
        and "Raman" in p
        and ("NMR" in p or "nuclear magnetic resonance" in p)
        for p in body_paras
    ):
        raise ValueError("original joined diffraction/Raman/NMR structural methods absent")
    # Search the single science paragraph in which BOTH series and actual
    # 25 °C conductivity numbers are authored. Do not borrow Table 1 comparison
    # values or abstract claims; treatment temperatures are not measured T.
    candidates=[]
    for p in body_paras:
        x=norm(p)
        if "ionic conductivities of S-240 and S-250 at 25" in x and "respectively" in x:
            candidates.append(x)
    if len(candidates)!=1:
        raise ValueError("unique originally published S-240/S-250 25C source paragraph missing")
    paragraph=candidates[0]
    if not re.search(r"7\.2\s*x\s*10\s*[-−]?\s*4",paragraph):
        raise ValueError("S-240 25C conductivity exponent altered")
    if not re.search(r"1\.5\s*x\s*10\s*[-−]?\s*3",paragraph):
        raise ValueError("S-250 25C conductivity exponent altered")
    if not re.search(r"S\s*cm\s*[-−]?\s*1",paragraph):
        raise ValueError("published conductivity dimension S/cm absent")
    if not any("total impedance" in p.lower() and
               "S-240" in p and "S-250" in p for p in body_paras):
        raise ValueError("total impedance/series measurement provenance missing")
    # Presence of S-250 in different characterization sections is a shared
    # powder/BATCH marker, not an individually joined physical EIS pellet ID.
    supplement=[]
    for n in root.iter():
        if tag(n) in ("supplementary-material","supp","ext-link"):
            name=norm(n.attrib.get("id","")+" "+n.attrib.get("href","")+
                      " "+n.attrib.get("{http://www.w3.org/1999/xlink}href",""))
            if tag(n)!="ext-link" or "supp" in name.lower():
                supplement.append(tag(n))
    return {
        "schema_version":SCHEMA,
        "DOI":DOI,
        "PMCID":PMCID,
        "source_repository":ORIGINAL_JATS,
        "source_jats_full_byte_sha256":hashlib.sha256(raw).hexdigest(),
        "source_full_article_body_paragraph_count":len(body_paras),
        "independent_new_publisher_laboratory":True,
        "nominal_chemistry":"Li7P3S11",
        "series_labels_are_powder_batches_not_independent_materials":True,
        "source_batch_labels_count":2,
        "processing_temperature_C_by_series":[240,250],
        "conductivity_measurement_temperature_C":25,
        "original_25C_sigma_Scm_series_ratio":round(
            ORIGINAL_CONDUCTIVITY_SCM[1]/ORIGINAL_CONDUCTIVITY_SCM[0],9),
        "original_25C_sigma_log10_series_difference":round(
            math.log10(ORIGINAL_CONDUCTIVITY_SCM[1]/ORIGINAL_CONDUCTIVITY_SCM[0]),9),
        "transport_observable":"CONDUCTIVITY_FROM_TOTAL_IMPEDANCE",
        "pellet_compaction_MPa_from_method":510,
        "pellet_mass_mg_approx_from_method":200,
        "xrd_raman_31P_NMR_source_methods_observed":True,
        "supplement_manifest_entries_seen_in_JATS":len(supplement),
        "supplement_file_contents_reviewed":False,
        "same_individual_pellet_used_for_EIS_and_diffraction_proven":False,
        "specimen_specific_CIF_phase_occupancy_certified":False,
        "numeric_per_pellet_thickness_electrode_area_certified":False,
        "individual_pellet_uncertainties_and_replicate_count_certified":False,
        "new_original_study_published_before_protocol":True,
        "independent_new_SEALED_materials_enrolled":0,
        "physically_authenticated_individual_pellets":0,
        "cross_chemistry_ML_prediction_generalization_claim":False,
        "source_same_paper_conditions_not_external_blind":True,
        "public_official_OBELIX_TEST_parsed":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_GO":False,
        "admission":"BATCH_CONTEXT_ONLY_PELLET_LEVEL_UNATTESTED",
    }


def fetch_real_primary() -> dict:
    req=Request(ORIGINAL_JATS,headers={
        "Accept":"application/xml, text/xml",
        "User-Agent":"Rhombus-0172-original-source-science-audit",
    })
    with urlopen(req,timeout=40) as response:
        destination=urlsplit(response.geturl())
        expected=urlsplit(ORIGINAL_JATS)
        if (destination.scheme,destination.hostname,destination.path)!=(
            expected.scheme,expected.hostname,expected.path):
            raise ValueError("primary-deposit identity redirect drift")
        data=response.read(MAX_XML_BYTES+1)
    return parse_primary_jats(data)


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--live-original",action="store_true")
    ap.add_argument("--output-dir",type=Path,required=True)
    args=ap.parse_args()
    if not args.live_original:ap.error("explicit real original JATS source execution required")
    out=args.output_dir.resolve()
    if out.exists():ap.error("new output dir required, prior artifacts immutable")
    result=fetch_real_primary()
    out.parent.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix=".rhombus-0172-",dir=out.parent))
    try:
        (stage/"independent_lab_0172.json").write_text(
            json.dumps(result,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n",
            encoding="utf-8",
        )
        if out.exists():raise ValueError("output overwritten during fetch")
        stage.rename(out)
    finally:
        if stage.exists():shutil.rmtree(stage)
    print("0172_DIFFERENT_LAB_REAL_ORIGINAL_BATCH_NOT_PELLET_GATE_PASS")
    print(json.dumps({k:result[k] for k in (
        "original_25C_sigma_Scm_series_ratio",
        "original_25C_sigma_log10_series_difference",
        "source_batch_labels_count",
        "physically_authenticated_individual_pellets",
        "admission","scientific_GO")},sort_keys=True))


if __name__=="__main__":
    main()
