"""0166 scientific tests: real source table rows, unit conversion, no pellet inflation."""
import math
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
import pytest
from scripts.science import original_sulfide_measurement_table_0166 as o

def fixture(*,doi=o.ORIGINAL_DOI,cells=None,cap="Conductivities and activation energies of the argyrodite electrolytes. Green compacts pressed at 720 MPa were used."):
    rows=[
      ["HT temperature/°C","150","200","300","400","500","550"],
      ["Conductivity at 25 °C/mS cm−1","0.19","0.20","0.53","1.49","1.23","1.94"],
      ["Activation energy/kJ mol−1","42.3","40.3","38.3","31.2","27.7","34.9"],
    ]
    if cells is not None:rows=cells
    table="".join("<tr>"+"".join(f"<td>{escape(v)}</td>" for v in vals)+"</tr>" for vals in rows)
    xml=f"""<article><front><article-meta><article-id pub-id-type="doi">{doi}</article-id>
     <title-group><article-title>Quantitative analysis of crystallinity in an argyrodite sulfide-based solid electrolyte synthesized via solution processing</article-title></title-group></article-meta></front>
     <body><table-wrap><caption><p>{cap}</p></caption><table><tbody>{table}</tbody></table></table-wrap></body></article>"""
    return xml.encode("utf-8")


def test_six_real_source_measurements_are_PROCESSING_conditions_not_independent_specimens():
    out=o.extract_table(fixture())
    pts=out["six_original_public_process_condition_points"]
    assert len(pts)==6
    assert [v["heat_treatment_C_not_measurement_temperature"] for v in pts]==[150,200,300,400,500,550]
    assert [v["source_ionic_conductivity_mS_per_cm"] for v in pts]==[.19,.20,.53,1.49,1.23,1.94]
    assert [v["normalized_ionic_conductivity_S_per_cm"] for v in pts]==[.00019,.00020,.00053,.00149,.00123,.00194]
    assert [v["source_activation_energy_kJ_per_mol"] for v in pts]==[42.3,40.3,38.3,31.2,27.7,34.9]
    assert out["actual_quantitative_table_condition_rows"]==6
    assert out["actual_independent_qualified_materials"]==0
    assert out["scientific_GO"] is False
    assert all(v["original_measurement_temperature_C"]==25 for v in pts)
    assert all(v["green_compact_pressing_MPa"]==720 for v in pts)
    assert all(v["admitted_as_material_level_transport_truth"] is False for v in pts)


def test_reject_wrong_DOI_publisher_table_or_sample_method():
    with pytest.raises(ValueError,match="DOI"):
        o.extract_table(fixture(doi="10.9999/wrong"))
    with pytest.raises(ValueError,match="720 MPa"):
        o.extract_table(fixture(cap="Conductivities and activation energies, no preparation method"))
    with pytest.raises(ValueError,match="DTD/entity"):
        o.extract_table(b"<!DOCTYPE foo [ <!ENTITY trap 'fake'> ]>"+fixture())


def test_reject_missing_extra_duplicate_or_fake_numeric_measurements():
    bad=[
      ["HT temperature/°C","150","200","300","400","500","550"],
      ["Conductivity at 25 °C/mS cm−1","0.19","0.20","0.53","<1.49","1.23","1.94"],
      ["Activation energy/kJ mol−1","42.3","40.3","38.3","31.2","27.7","34.9"]]
    with pytest.raises(ValueError,match="source field"):
        o.extract_table(fixture(cells=bad))
    bad[1][4]="1.48"
    with pytest.raises(ValueError,match="drift"):
        o.extract_table(fixture(cells=bad))
    with pytest.raises(ValueError,match="not the expected three 6-condition rows"):
        o.extract_table(fixture(cells=bad[:2]))


def test_fail_if_processing_temperature_is_mislabeled_measurement_T():
    bad=[
      ["Measurement temperature/°C","150","200","300","400","500","550"],
      ["Conductivity at 25 °C/mS cm−1","0.19","0.20","0.53","1.49","1.23","1.94"],
      ["Activation energy/kJ mol−1","42.3","40.3","38.3","31.2","27.7","34.9"]]
    with pytest.raises(ValueError,match="measurement/processing type"):
        o.extract_table(fixture(cells=bad))
    bad[0][0]="HT temperature/°C"
    bad[1][0]="Conductivity at 90 °C/mS cm−1"
    with pytest.raises(ValueError,match="25 C"):
        o.extract_table(fixture(cells=bad))
