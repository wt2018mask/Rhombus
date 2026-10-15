"""0177 original Zenodo research dataset identity and anti-pellet-promotion."""
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import pytest
from scripts.science import independent_lab_original_workbooks_0177 as m

def sample_record():
    return {"id":m.RECORD_ID,"files":[
        {"key":key,"checksum":"md5:"+v["md5"],
         "size":10_000_000,
         "links":{"content":
           "https://zenodo.org/api/records/17816356/files/"+
           key.replace(" ","%20")+"/content"}}
        for key,v in m.SOURCES.items()]}

def test_original_two_file_publication_manifest_and_host():
    r=m.parse_record(sample_record())
    assert len(r)==2
    assert all(x["original_content_url"].startswith(
        "https://zenodo.org/api/records/17816356/files/") for x in r)

@pytest.mark.parametrize("mutate",[
    lambda r:r.update(id=17816357),
    lambda r:r["files"][0].update(checksum="md5:"+"0"*32),
    lambda r:r["files"][0].update(size=10**12),
    lambda r:r["files"][0]["links"].update(content="https://evil.com/data.xlsx"),
    lambda r:r["files"].append(r["files"][0]),
])
def test_wrong_dataset_file_spoof_and_md5_rejected(mutate):
    r=sample_record();mutate(r)
    with pytest.raises(ValueError):m.parse_record(r)

def test_xlsx_sheet_metadata_is_not_same_sample_join():
    wb=b'<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheets><sheet name="Sample A XRD"/><sheet name="Sample A EIS"/></sheets></workbook>'
    with TemporaryDirectory() as folder:
        path=Path(folder)/"real-source.xlsx"
        with ZipFile(path,"w") as z:
            z.writestr("[Content_Types].xml","text")
            z.writestr("xl/workbook.xml",wb)
        r=m.inspect_workbook(path)
    assert r["sheet_count"]==2
    assert r["sheet_name_modality_candidates"]["XRD"]==["Sample A XRD"]
    assert r["sheet_name_modality_candidates"]["EIS"]==["Sample A EIS"]
    assert r["same_individual_pellet_link_identified_from_sheet_names"] is False
    assert r["source_raw_cells_or_specimen_level_identifiers_opened"] is False

def test_zip_duplicate_members_and_fake_paths_rejected():
    with TemporaryDirectory() as folder:
        path=Path(folder)/"source.xlsx"
        with ZipFile(path,"w") as z:
            z.writestr("[Content_Types].xml","a")
            z.writestr("xl/workbook.xml","<bad/>")
        with pytest.raises(ValueError):m.inspect_workbook(path)

def test_modality_title_names_alone_are_not_accepted_pellet_ids():
    assert m.classify_title("LiOPA EIS curves")==["EIS"]
    assert m.classify_title("XRD of materials")==["XRD"]
    assert m.classify_title("Fig 2a")==[]
    with pytest.raises(ValueError):m.assert_source_url("https://zenodo.org.evil.test/api/records/17816356")
