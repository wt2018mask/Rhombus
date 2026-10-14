"""0175: Direct streaming SHA-256 of the original complete MACE-MPA-0 checkpoint.

Authenticating model bytes is NOT authenticating selected training frames.
Do not deserialize, run, retain or redistribute publisher model weights.
"""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
# Frozen published identity cross-checked against rhombus/domain/mpa0_publisher_digest.py
# by dedicated regression tests. Keep this source reader stdlib-only so no
# scientific package import or model unpickling happens on the audit runner.
MODEL="mace-mpa-0-medium.model"
PUBLIC_SHA256="75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638"

SCHEMA="rhombus-0175-upstream-real-model-complete-byte-hash-v1"
RELEASE_API="https://api.github.com/repos/ACEsuit/mace-foundations/releases/tags/mace_mpa_0"
MODEL_URL="https://github.com/ACEsuit/mace-foundations/releases/download/mace_mpa_0/mace-mpa-0-medium.model"
ASSET_ID=213937064
MODEL_SIZE=79_462_305
MAX_METADATA_BYTES=96000
CHUNK=1024*1024
CDN_HOSTS=frozenset(("github.com","release-assets.githubusercontent.com","objects.githubusercontent.com"))

def require_source_url(url, hosts):
    u=urlsplit(url)
    if u.scheme!="https" or u.hostname not in hosts or u.username or u.password or u.fragment:
        raise ValueError("unsafe original model release redirect")

class AllowPinnedGithubRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        require_source_url(newurl, CDN_HOSTS)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def no_duplicate_fields(pairs):
    result={}
    for k,v in pairs:
        if k in result:
            raise ValueError("duplicate release JSON key")
        result[k]=v
    return result

def verify_release(meta):
    if (not isinstance(meta,dict) or meta.get("tag_name")!="mace_mpa_0"
        or meta.get("draft") is not False or meta.get("prerelease") is not False):
        raise ValueError("not the official public original release")
    assets=meta.get("assets")
    if not isinstance(assets,list) or len(assets)>50:
        raise ValueError("ambiguous upstream asset inventory")
    hits=[a for a in assets if isinstance(a,dict) and a.get("name")==MODEL]
    if len(hits)!=1:
        raise ValueError("exact MACE-MPA-0 model asset must be unique")
    a=hits[0]
    if (type(a.get("id")) is not int or a["id"]!=ASSET_ID
        or type(a.get("size")) is not int or a["size"]!=MODEL_SIZE
        or a.get("browser_download_url")!=MODEL_URL
        or a.get("state")!="uploaded"):
        raise ValueError("upstream checkpoint release asset size/identity drift")
    return {"release_asset_id":ASSET_ID,"release_tag":"mace_mpa_0",
            "release_model_name":MODEL,"public_asset_size":MODEL_SIZE,
            "published_expected_SHA256":PUBLIC_SHA256,
            "official_release_digest_optional":a.get("digest")}

def hash_full_stream(response, *, size, expected_digest):
    if type(size) is not int or size<1 or not isinstance(expected_digest,str) or len(expected_digest)!=64:
        raise ValueError("invalid expected full source identity")
    if response.status!=200:
        raise ValueError("upstream did not return complete HTTP 200 model")
    require_source_url(response.geturl(), CDN_HOSTS)
    length=response.headers.get("Content-Length")
    if length is not None and (not length.isdigit() or int(length)!=size):
        raise ValueError("HTTP original full-file length disagrees with release inventory")
    digest=hashlib.sha256()
    count=0
    while True:
        data=response.read(CHUNK)
        if not data:
            break
        if not isinstance(data,bytes) or len(data)>CHUNK:
            raise ValueError("unbounded/nonbinary model stream")
        count+=len(data)
        if count>size:
            raise ValueError("extra original model bytes")
        digest.update(data)
    if count!=size or digest.hexdigest()!=expected_digest:
        raise ValueError("actual model full SHA256 / byte-length mismatch")
    return {"observed_SHA256":digest.hexdigest(),"observed_byte_length":count,
            "hash_scope":"FULL_FILE","method":"INDEPENDENT_GITHUB_ACTIONS_CPU_BYTE_STREAM",
            "model_weights_retained":False}

def original_release_execution():
    opener=build_opener(AllowPinnedGithubRedirect())
    with opener.open(Request(RELEASE_API,headers={
        "User-Agent":"Rhombus-0175-real-model-full-byte-audit",
        "Accept":"application/vnd.github+json"}),timeout=40) as response:
        require_source_url(response.geturl(),frozenset(("api.github.com",)))
        if response.status!=200:
            raise ValueError("official GitHub asset metadata unavailable")
        raw=response.read(MAX_METADATA_BYTES+1)
    if not raw or len(raw)>MAX_METADATA_BYTES:
        raise ValueError("unbounded or absent original GitHub release metadata")
    data=json.loads(raw,object_pairs_hook=no_duplicate_fields,
        parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    asset=verify_release(data)
    with opener.open(Request(MODEL_URL,headers={
        "User-Agent":"Rhombus-0175-one-shot-full-release-model-read",
        "Accept":"application/octet-stream"}),timeout=90) as response:
        observed=hash_full_stream(response,size=MODEL_SIZE,expected_digest=PUBLIC_SHA256)
    return {"schema_version":SCHEMA,"original_release":asset,
        "independent_full_binary_observation":observed,
        "whole_checkpoint_binary_SHA256_actually_measured":True,
        "checkpoint_binary_identity_not_checkpoint_training_lineage":True,
        "third_party_auditor_receipt_authenticated":False,
        "selected_MPtrj_training_frames_authenticated":False,
        "selected_sAlex_training_frames_authenticated":False,
        "source_dataset_complete_byte_hash_authenticated":False,
        "historical_checkpoint_energy_and_preprocessing_authenticated":False,
        "independent_eval_material_membership_audited":False,
        "P0_01":"BLOCKED","P0_02":"BLOCKED","P0_03":"BLOCKED","scientific_GO":False}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--real-original-complete-checkpoint",action="store_true")
    p.add_argument("--output-dir",type=Path,required=True)
    a=p.parse_args()
    if not a.real_original_complete_checkpoint:
        p.error("explicit entire original model source read required")
    dst=a.output_dir.resolve()
    if dst.exists() or dst.is_symlink():
        p.error("output directory must not exist")
    result=original_release_execution()
    dst.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix=".rhombus-0175-",dir=dst.parent))
    try:
        (temp/"full_checkpoint_digest_0175.json").write_text(
            json.dumps(result,sort_keys=True,allow_nan=False,separators=(",",":"))+"\n",
            encoding="utf-8")
        if dst.exists():
            raise ValueError("new output path collision")
        temp.rename(dst)
    finally:
        if temp.exists():
            shutil.rmtree(temp)
    print("0175_ACTUAL_COMPLETE_MACE_MPA0_MODEL_SHA256_PASS")
    print(json.dumps({"SHA256":result["independent_full_binary_observation"]["observed_SHA256"],
        "full_bytes":result["independent_full_binary_observation"]["observed_byte_length"],
        "P0_02":result["P0_02"],"scientific_GO":False},sort_keys=True))

if __name__=="__main__":
    main()
