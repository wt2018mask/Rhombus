"""0173: source-bound MACE-MPA-0 author-stated TRAIN / VALID split leads.

Retrieve the actual upstream GitHub author replies, NOT the datasets.
The cited archive/folder URLs are valuable provenance *leads*, not the
checkpoint-selected individual-frame/hash/preprocessing audit required for
RT-P0-02. No download of MPTrj/sAlex, no certification, no blind overlap test.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

SCHEMA="rhombus-0173-mace-mpa0-upstream-author-split-disclosure-v1"
REPO="ACEsuit/mace-foundations"
AUTHOR="ilyes319"
COMMENT_IDS=(3244634298,3291737675)
MAX_COMMENT_BYTES=64_000
DATASET_LINKS={
    "sAlex_training":"https://dl.fbaipublicfiles.com/opencatalystproject/data/omat/241018/sAlex/train.tar.gz",
    "MPTrj_training":"https://drive.google.com/drive/folders/12RsjlEtSlBldhoQVJapfC9lIFZwpnVk6?usp=drive_link",
    "sAlex_validation":"https://dl.fbaipublicfiles.com/opencatalystproject/data/omat/241018/sAlex/val.tar.gz",
    "MPTrj_validation":"https://drive.google.com/drive/folders/10atLHo2VJyTcb9JqL8SjHZIornPntUh-?usp=sharing",
}
SCRIPT="https://github.com/ACEsuit/mace-foundations/blob/main/mace_omat/mace-omat-medium.sh"


def parse_comments(comments: list[dict]) -> dict:
    if not isinstance(comments,list) or len(comments)!=2:
        raise ValueError("both distinct original upstream author comments required")
    identifiers=set()
    output=[]
    for c in comments:
        if not isinstance(c,dict) or set(("id","user","issue_url","html_url","body","created_at"))-set(c):
            raise ValueError("unidentified upstream issue comment")
        id=c["id"]
        if type(id) is not int or id not in COMMENT_IDS or id in identifiers:
            raise ValueError("wrong/duplicate comment ID")
        identifiers.add(id)
        issue=42 if id==COMMENT_IDS[0] else 29
        api_issue=f"https://api.github.com/repos/{REPO}/issues/{issue}"
        public=f"https://github.com/{REPO}/issues/{issue}#issuecomment-{id}"
        if (not isinstance(c["user"],dict) or
            c["user"].get("login")!=AUTHOR or
            c["issue_url"]!=api_issue or c["html_url"]!=public):
            raise ValueError("original publisher author and exact issue origin mismatch")
        body=c["body"]
        if not isinstance(body,str) or len(body)>12_000 or not body:
            raise ValueError("invalid author text")
        if not isinstance(c["created_at"],str) or not re.fullmatch(
            r"20\d\d-\d\d-\d\dT\d\d:\d\d:\d\dZ",c["created_at"]):
            raise ValueError("original source timestamp not present")
        output.append({
            "comment_id":id,"original_author_GitHub_login":AUTHOR,
            "source_issue_number":issue,"source_public_url":public,
            "source_created_at":c["created_at"],
            "exact_author_body_sha256":hashlib.sha256(body.encode()).hexdigest(),
        })
    index={c["id"]:c["body"] for c in comments}
    a=index[COMMENT_IDS[0]]
    b=index[COMMENT_IDS[1]]
    # No cross-project leakage: MATPES/OMAT discussion follows a separate
    # explicit model section in issue #42.
    if "For the MACE-MPA-0 we used the following data:" not in a:
        raise ValueError("source did not explicitly bind splits to MPA-0")
    section=a.split("For the MACE-MPA-0 we used the following data:",1)[1]
    section=section.split("For the MACE-MATPES-PBE-0:",1)[0]
    expected_train=("training is the combination of sAlex here: "
                    +DATASET_LINKS["sAlex_training"]+" and MPtraj training set from here: "
                    +DATASET_LINKS["MPTrj_training"])
    expected_valid=("the validation set is the sAlex valid set from here: "
                    +DATASET_LINKS["sAlex_validation"]+" and the Mptraj valid: "
                    +DATASET_LINKS["MPTrj_validation"])
    if not (expected_train in section and expected_valid in section and
            section.index(expected_train)<section.index(expected_valid)):
        raise ValueError("upstream author train/validation split identifiers altered")
    if ("MPA model is the same input as: "+SCRIPT not in b or
        "replace the omat data is the sAlex + Mptraj dataset" not in b):
        raise ValueError("author training script scope/required substitution missing")
    return {
        "schema_version":SCHEMA,
        "original_official_repository":REPO,
        "original_comment_author":AUTHOR,
        "independent_author_comments_verified":2,
        "author_comment_receipts":sorted(output,key=lambda x:x["comment_id"]),
        "MACE_MPA0_author_stated_source_training_validation_URLs":DATASET_LINKS,
        "author_stated_training_script_template":SCRIPT,
        "training_script_requires_OMAT_replacement_with_sAlex_and_MPTrj":True,
        "original_upstream_author_disclosure_observed":True,
        "source_hosted_archive_full_bytes_downloaded":False,
        "MPTrj_and_sAlex_exact_selected_frame_ids_attested":False,
        "original_archive_SHA256_and_sizes_rehashed":False,
        "checkpoint_to_preprocess_and_energy_labels_audited":False,
        "original_author_comment_is_not_independently_signed_training_manifest":True,
        "comment_source_does_not_cryptographically_prove_dataset_bytes_used":True,
        "full_exact_model_training_lineage_independent_ACCEPTED":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED",
        "scientific_GO":False,
        "next_action":"0174-P0-02 retrieve/bind actual archive manifests, hashes, full selected-frame membership through authorized source without large speculative Kaggle",
    }


def official_comment_headers():
    """Read-only official GitHub token, kept out of receipts/logs and other hosts."""
    headers={
        "User-Agent":"Rhombus-0173-official-provider-origin-audit",
        "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
    }
    token=os.environ.get("GITHUB_TOKEN","").strip()
    if token:
        # Only this exact hardcoded api.github.com original author endpoint uses it.
        headers["Authorization"]="Bearer "+token
    return headers


def fetch_author_comment(comment_id: int) -> dict:
    if type(comment_id) is not int or comment_id not in COMMENT_IDS:
        raise ValueError("unapproved upstream source comment ID")
    url=f"https://api.github.com/repos/{REPO}/issues/comments/{comment_id}"
    request=Request(url,headers=official_comment_headers())
    with urlopen(request,timeout=35) as response:
        dest=urlsplit(response.geturl())
        src=urlsplit(url)
        if (dest.scheme,dest.hostname,dest.path)!=(src.scheme,src.hostname,src.path):
            raise ValueError("original authenticated GitHub source redirected")
        raw=response.read(MAX_COMMENT_BYTES+1)
    if len(raw)>MAX_COMMENT_BYTES or not raw.startswith(b"{"):
        raise ValueError("official source comment body too large/wrong content")
    try:
        return json.loads(raw,parse_constant=lambda z: (_ for _ in ()).throw(ValueError(z)),
                          object_pairs_hook=strict_pairs)
    except (ValueError,UnicodeDecodeError,TypeError) as exc:
        raise ValueError("malformed official origin JSON") from exc


def strict_pairs(items):
    d={}
    for k,v in items:
        if k in d:raise ValueError("ambiguous duplicate source metadata field")
        d[k]=v
    return d


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--live-author-source",action="store_true")
    ap.add_argument("--output-dir",type=Path,required=True)
    args=ap.parse_args()
    if not args.live_author_source:ap.error("explicit real publisher GitHub fetch required")
    out=args.output_dir.resolve()
    if out.exists():ap.error("append-only output: require new directory")
    result=parse_comments([fetch_author_comment(i) for i in COMMENT_IDS])
    out.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix=".rhombus-0173-",dir=out.parent))
    try:
        (staging/"upstream_mace_training_splits_0173.json").write_text(
            json.dumps(result,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n",
            encoding="utf-8")
        if out.exists():raise ValueError("output collision")
        staging.rename(out)
    finally:
        if staging.exists():shutil.rmtree(staging)
    print("0173_ACTUAL_UPSTREAM_AUTHOR_TRAIN_VALID_SOURCE_POINTERS_PASS")
    print(json.dumps({"source_author":result["original_comment_author"],
                       "source_comments":result["independent_author_comments_verified"],
                       "P0_02":result["P0_02"],
                       "scientific_GO":result["scientific_GO"]},sort_keys=True))


if __name__=="__main__":
    main()
