"""0175 anti-spoof / truncation / model false-go tests."""
import hashlib
import ast
from pathlib import Path
import io
import pytest
from scripts.science import mace_checkpoint_binary_0175 as m

def release():
    return {"tag_name":"mace_mpa_0","draft":False,"prerelease":False,
        "assets":[{"name":m.MODEL,"id":m.ASSET_ID,"size":m.MODEL_SIZE,
                   "state":"uploaded","browser_download_url":m.MODEL_URL}]}

class MemoryResponse:
    status=200
    def __init__(self,raw,head=None,url=m.MODEL_URL):
        self.buf=io.BytesIO(raw)
        self.headers={} if head is None else {"Content-Length":head}
        self.url=url
    def geturl(self):
        return self.url
    def read(self,n):
        return self.buf.read(n)

def test_true_release_identity_and_complete_real_binary_contract():
    assert m.verify_release(release())["public_asset_size"]==79_462_305
    data=b"tiny model test file"
    valid=hashlib.sha256(data).hexdigest()
    observed=m.hash_full_stream(MemoryResponse(data,str(len(data))),
                                size=len(data),expected_digest=valid)
    assert observed["hash_scope"]=="FULL_FILE"
    assert observed["model_weights_retained"] is False
    assert observed["observed_byte_length"]==len(data)

@pytest.mark.parametrize("edit",[
    lambda d:d.update(tag_name="bad"),
    lambda d:d.update(prerelease=True),
    lambda d:d["assets"][0].update(id=m.ASSET_ID+1),
    lambda d:d["assets"][0].update(size=m.MODEL_SIZE-1),
    lambda d:d["assets"][0].update(state="deleted"),
    lambda d:d["assets"][0].update(browser_download_url="https://evil.invalid/weights"),
    lambda d:d["assets"].append(d["assets"][0].copy()),
])
def test_publisher_release_spoof_and_id_drift_rejected(edit):
    d=release()
    edit(d)
    with pytest.raises(ValueError):
        m.verify_release(d)

@pytest.mark.parametrize("data,size,head,wrong",[
    (b"abc",3,"3",True),
    (b"abc",4,None,False),
    (b"abcd",3,None,False),
    (b"abc",3,"4",False),
])
def test_model_hash_truncation_and_wrong_digest_fail_closed(data,size,head,wrong):
    expected=hashlib.sha256(b"other" if wrong else data).hexdigest()
    with pytest.raises(ValueError):
        m.hash_full_stream(MemoryResponse(data,head),size=size,expected_digest=expected)

def test_no_external_redirect_or_duplicate_json_keys():
    for url in ("http://github.com/m","https://evil.com/x",
                "https://github.com.attacker.test/file",
                "https://user:pass@github.com/path"):
        with pytest.raises(ValueError):
            m.require_source_url(url,m.CDN_HOSTS)
    with pytest.raises(ValueError):
        m.no_duplicate_fields([("sha","a"),("sha","b")])


def test_digest_and_name_against_frozen_original_publisher_contract():
    source=Path(__file__).resolve().parents[1]/"rhombus"/"domain"/"mpa0_publisher_digest.py"
    assignments={}
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(node,ast.Assign) and len(node.targets)==1 and isinstance(node.targets[0],ast.Name):
            if node.targets[0].id in ("PUBLIC_SHA256","MODEL"):
                assignments[node.targets[0].id]=ast.literal_eval(node.value)
    assert assignments == {"PUBLIC_SHA256":m.PUBLIC_SHA256,"MODEL":m.MODEL}
