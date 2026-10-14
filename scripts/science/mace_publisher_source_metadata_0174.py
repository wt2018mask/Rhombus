"""0174 primary publisher sAlex split metadata + immutable MACE template audit.

Real publicly reported sAlex archive split COUNTS are NOT counts of selected
MACE-MPA-0 training frames. An upstream author-stated location is NOT actual
training membership or full raw archive identity. This module requests only
a bounded, revision-pinned small publisher README and a pinned Git blob;
NO multi-GB archives, data frames, model weights, secret material IDs or GPU.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import json
import re
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request,urlopen

from scripts.science import mace_author_training_splits_0173 as prior

SCHEMA="rhombus-0174-mpa0-primary-publisher-split-metadata-and-template-v1"
HF_REV="1c0584ba87467241ca2231eb55ce94e3686f452d"
README="https://huggingface.co/datasets/facebook/OMAT24/raw/"+HF_REV+"/README.md"
BLOB_SHA="68f58cd4076e8aaadee94b672cc4b019e9fbc046"
GITHUB_BLOB="https://api.github.com/repos/ACEsuit/mace-foundations/git/blobs/"+BLOB_SHA
SPLIT_COUNTS={"sAlex_training":10447765,"sAlex_validation":553218}
MAX_BYTES=160000
MAX_SCRIPT=20000


def parse_meta(primary_readme: bytes, git_blob: dict, authors: dict) -> dict:
    """Strict original-source observations, no scientific authentication."""
    if not isinstance(primary_readme,bytes) or not 100<len(primary_readme)<=MAX_BYTES:
        raise ValueError("invalid publisher metadata size")
    if b"\x00" in primary_readme:
        raise ValueError("binary dataset not an original source README")
    try:
        txt=primary_readme.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("invalid publisher UTF-8") from exc
    if not ("### sAlex Dataset" in txt and
            "sAlex was created by removing structures matched in WBM" in txt):
        raise ValueError("publisher original sAlex methods/split context missing")
    only=txt.split("### sAlex Dataset",1)[1].split("## How to read the data",1)[0]
    pattern=r"^\|\s*sAlex\s*\|\s*(train|val)\s*\|\s*([0-9,]+)\s*\|\s*\[([^]]+)\]\((https://[^)]+)\)\s*\|\s*$"
    raw=re.findall(pattern,only,re.M)
    if len(raw)!=2 or len({v[0] for v in raw})!=2:
        raise ValueError("exactly two original sAlex publisher split rows required")
    pub={}
    for split,n,display,url in raw:
        field="sAlex_training" if split=="train" else "sAlex_validation"
        if (n!=f"{SPLIT_COUNTS[field]:,}" or
            display!=("train.tar.gz" if split=="train" else "val.tar.gz") or
            url!=prior.DATASET_LINKS[field]):
            raise ValueError("sAlex split count or upstream author URL mismatch")
        pub[field]=int(n.replace(",",""))
    if pub!=SPLIT_COUNTS or not isinstance(authors,dict):
        raise ValueError("incomplete publisher split")
    if (authors.get("original_comment_author")!=prior.AUTHOR
        or authors.get("independent_author_comments_verified")!=2
        or authors.get("MACE_MPA0_author_stated_source_training_validation_URLs")
           !=prior.DATASET_LINKS):
        raise ValueError("missing separately verified upstream author split source")

    if not isinstance(git_blob,dict) or (git_blob.get("sha")!=BLOB_SHA
        or git_blob.get("encoding")!="base64" or
        type(git_blob.get("size")) is not int
        or not 50<=git_blob["size"]<=MAX_SCRIPT
        or not isinstance(git_blob.get("content"),str)):
        raise ValueError("GitHub pinned script Git blob metadata invalid")
    try:
        script=base64.b64decode(re.sub(r"\s+","",git_blob["content"]),validate=True)
    except (ValueError,base64.binascii.Error) as exc:
        raise ValueError("invalid binary original Git blob encoding") from exc
    gitsha=hashlib.sha1(b"blob "+str(len(script)).encode()+b"\0"+script).hexdigest()
    if len(script)!=git_blob["size"] or gitsha!=BLOB_SHA:
        raise ValueError("Git blob bytes not cryptographically content-bound")
    try:
        script_text=script.decode("utf-8")
    except UnicodeError as exc:
        raise ValueError("non-UTF8 original training template") from exc
    # This IS an OMAT command template, not an observed MPA0 training run.
    must=(
        '--name="mace-omat-medium"',
        '--train_file="/train/all_data"',
        '--valid_file="/val/all_data"',
        '--energy_key=\'energy\'',
        '--forces_key=\'forces\'',
        '--stress_key=\'stress\'',
        '--energy_weight=1',
        '--forces_weight=10',
        '--compute_stress=True',
        '--stress_weight=10',
        '--default_dtype="float64"',
    )
    if not all(token in script_text for token in must):
        raise ValueError("original pinned OMAT template method/label keys altered")
    return {
        "schema_version":SCHEMA,
        "original_publisher_huggingface_revision":HF_REV,
        "original_publisher_README_URL":README,
        "observed_publisher_README_full_byte_SHA256":hashlib.sha256(primary_readme).hexdigest(),
        "meta_reported_sAlex_train_records_NOT_checkpoint_selected":pub["sAlex_training"],
        "meta_reported_sAlex_valid_records_NOT_checkpoint_selected":pub["sAlex_validation"],
        "data_row_counts_from_publisher_are_NOT_MACE_MPA0_training_selection":True,
        "sAlex_pub_archive_links_match_MPA0_developer_author_statement":True,
        "WBM_matched_structures_removed_as_author_reported_for_sAlex":True,
        "MPtrj_original_author_split_URLs_only":True,
        "MPTrj_original_training_archive_bytes_observed":False,
        "original_MACE_upstream_template_blob_sha1":BLOB_SHA,
        "original_MACE_upstream_template_blob_SHA256":hashlib.sha256(script).hexdigest(),
        "template_contains_energy_forces_stress_keys":True,
        "template_explicitly_named_OMAT_not_historical_MPA_training_receipt":True,
        "training_template_can_change_with_other_MPA_data_rules":True,
        "sAlex_training_archive_downloaded":False,
        "sAlex_validation_archive_downloaded":False,
        "source_archive_SHA256_independently_computed":False,
        "dataset_selected_frame_ids_for_exact_MACE_checkpoint_authenticated":False,
        "historic_training_script_execution_attested":False,
        "energy_label_source_to_checkpoint_binding_attested":False,
        "independent_evaluation_material_overlap_audited":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_GO":False,
        "evidence_level":"TWO_PUBLIC_PUBLISHER_METADATA_SOURCES_NOT_TRAINING_FRAME_MEMBERSHIP"
    }


def small_official_read(url: str,max_size: int,content_type: str) -> bytes:
    request=Request(url,headers={
        "User-Agent":"Rhombus-0174-bounded-original-metadata-evidence",
        "Accept":content_type,
    })
    with urlopen(request,timeout=40) as response:
        initial=urlsplit(url);final=urlsplit(response.geturl())
        if (final.scheme,final.netloc,final.path)!=(initial.scheme,initial.netloc,initial.path):
            raise ValueError("original publisher source URL redirect not permitted")
        data=response.read(max_size+1)
    if not data or len(data)>max_size:
        raise ValueError("unexpected publisher response exceeds bounded read")
    return data


def run_original() -> dict:
    author=prior.parse_comments([
        prior.fetch_author_comment(cid) for cid in prior.COMMENT_IDS])
    readme=small_official_read(README,MAX_BYTES,"text/plain")
    raw=small_official_read(GITHUB_BLOB,MAX_BYTES,"application/vnd.github+json")
    try:
        blob=json.loads(raw,object_pairs_hook=prior.strict_pairs,
                        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    except (TypeError,ValueError,UnicodeDecodeError) as exc:
        raise ValueError("invalid original pinned GitHub blob JSON") from exc
    return parse_meta(readme,blob,author)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--live-publisher",action="store_true")
    parser.add_argument("--output-dir",type=Path,required=True)
    args=parser.parse_args()
    if not args.live_publisher:parser.error("explicit source-bounded publisher metadata verification required")
    out=args.output_dir.resolve()
    if out.exists():parser.error("new output directory required")
    result=run_original()
    out.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix=".rhombus-0174-",dir=out.parent))
    try:
        (temp/"actual_upstream_source_metadata_0174.json").write_text(
            json.dumps(result,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n",
            encoding="utf-8")
        if out.exists():raise ValueError("no replacement of scientific evidence")
        temp.rename(out)
    finally:
        if temp.exists():shutil.rmtree(temp)
    print("0174_TWO_PRIMARY_ORIGINAL_SOURCE_METADATA_BOUNDARY_PASS")
    print(json.dumps({
        "public_sAlex_train_records_NOT_model_selected":
            result["meta_reported_sAlex_train_records_NOT_checkpoint_selected"],
        "public_sAlex_validation_records_NOT_model_selected":
            result["meta_reported_sAlex_valid_records_NOT_checkpoint_selected"],
        "P0_02":result["P0_02"],
        "scientific_GO":result["scientific_GO"]},sort_keys=True))


if __name__=="__main__":
    main()
