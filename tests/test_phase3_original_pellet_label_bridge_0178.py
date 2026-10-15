"""0178 original Excel text/source identity is not an individual pellet join."""
import io
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile
import pytest
from scripts.science import original_pellet_label_bridge_0178 as s


def smallbook(*,duplicate=False,external=False):
    sheetnames=s.TARGETS
    workbook=f'<workbook xmlns="{s.NS[1:-1]}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'
    workbook+="".join(f'<sheet name="{name.replace("&","&amp;")}" r:id="rId{i+1}"/>' for i,name in enumerate(sheetnames))
    workbook+='</sheets></workbook>'
    relations='<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    relations+="".join('<Relationship Id="rId%d" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="%s"/>'%(
        i+1,"../evil.xml" if external else "worksheets/sheet%d.xml"%(i+1)) for i in range(4))
    relations+='</Relationships>'
    out=io.BytesIO()
    with ZipFile(out,'w') as z:
        z.writestr("[Content_Types].xml","text")
        z.writestr("xl/workbook.xml",workbook)
        z.writestr("xl/_rels/workbook.xml.rels",relations)
        z.writestr("xl/sharedStrings.xml",
           '<sst xmlns="%s"><si><t>Sample A</t></si><si><t>Sample B</t></si></sst>'%s.NS[1:-1])
        for i in range(4):
            data=f'<worksheet xmlns="{s.NS[1:-1]}"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is><t>Condition %d</t></is></c></row></sheetData></worksheet>'%i
            z.writestr("xl/worksheets/sheet%d.xml"%(i+1),data)
        if duplicate:z.writestr("xl/workbook.xml",workbook)
    out.seek(0)
    return out

def test_four_original_target_paths_and_actual_cells():
    with TemporaryDirectory() as tmp:
        f=Path(tmp)/"fixture.xlsx";f.write_bytes(smallbook().getvalue())
        with ZipFile(f) as z:
            mapping=s.parse_source_sheet_paths(z)
            strings=s.parse_shared_strings(z)
            contents={n:s.first_text_rows(z,p,strings) for n,p in mapping.items()}
        result=s.evaluate_original_labels(s.SOURCE_SHA256,contents)
    assert set(mapping)==set(s.TARGETS)
    assert result["exact_identical_literal_texts_across_XRD_and_EIS"]==["sample a"]
    assert result["same_physical_pellet_structure_EIS_traceable_source_ID_certified"] is False
    assert result["new_authenticated_individual_physical_materials"]==0
    assert result["scientific_GO"] is False
    assert all(result[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))

def test_external_worksheet_relationship_and_source_drift_rejected():
    with ZipFile(smallbook(external=True)) as z:
        with pytest.raises(ValueError):
            s.parse_source_sheet_paths(z)
    with pytest.raises(ValueError):
        s.evaluate_original_labels("0"*64,{})

def test_http_urls_numeric_and_emails_not_overreported():
    assert s._label("https://example.com/data")==None
    assert s._label("person@example.com")==None
    assert s._label("1.32e-02")==None
    assert s._label("XRD humidity")=="XRD humidity"
    with pytest.raises(ValueError):s._safe_rel_target("../../external.xml")

def test_real_source_original_sha_is_pinned_and_first_read_is_not_model_prediction():
    assert s.SOURCE_SHA256=="22640fa76a00d90626cfe8fc2f3d4fc20ee71c3f87aba865f064960f1e3cd05e"
    assert s.MAX_ROWS<=100
    assert s.MAX_COLUMNS<=64
