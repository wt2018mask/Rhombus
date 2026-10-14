"""0172 independent primary paper source and falsification tests."""
import pytest
from scripts.science import independent_lab_specimen_0172 as m


def article(doi=m.DOI, pmc="12435569", sigma240="7.2 × 10−4",
            sigma250="1.5 × 10−3", c="25", label="total impedance",
            methods="510 MPa", structure="XRD, Raman and 31P NMR"):
    paras=[
        "Li7P3S11 powder sample series S-240 and S-250 was studied in ethyl propionate.",
        "Li7P3S11 original comparison of S-240 and S-250 results.",
        "The structure was characterized using "+structure+".",
        "Samples were prepared and heat treated at 240 and 250 C for S-240 and S-250.",
        "The electrical conductivity of a pellet prepared by uniaxially cold-pressing approximately 200 mg of powder at "+methods+" was measured using alternating-current impedance spectroscopy.",
        "The impedance of S-240 and S-250 was measured.",
        "The temperature-dependent ionic conductivities of S-240 and S-250 were calculated from the "+label+" values and are plotted in Fig. 5b.",
        "The ionic conductivities of S-240 and S-250 at "+c+" °C are "+sigma240+" and "+sigma250+" S cm−1, respectively.",
        "The NMR and XRD patterns showed characteristic phases of Li7P3S11.",
        "Raman and 31P NMR were examined for S-240 and S-250."
    ]
    xml="<article><front><article-meta><article-id pub-id-type='doi'>"+doi+"</article-id><article-id pub-id-type='pmc'>"+pmc+"</article-id></article-meta></front><body>"
    xml+="".join("<p>"+p+"</p>" for p in paras)
    return (xml+"</body></article>").encode()


def test_batch_level_not_physical_individual_acceptance():
    a=m.parse_primary_jats(article())
    assert a["conductivity_measurement_temperature_C"]==25
    assert a["source_batch_labels_count"]==2
    assert a["transport_observable"]=="CONDUCTIVITY_FROM_TOTAL_IMPEDANCE"
    assert a["original_25C_sigma_Scm_series_ratio"]==2.083333333
    assert a["same_individual_pellet_used_for_EIS_and_diffraction_proven"] is False
    assert a["physically_authenticated_individual_pellets"]==0
    assert a["independent_new_SEALED_materials_enrolled"]==0
    assert a["scientific_GO"] is False
    assert all(a[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))


@pytest.mark.parametrize("changes",[
    {"doi":"10.1039/d5ra05281f"}, {"pmc":"12435568"},
    {"sigma240":"7.2 × 10−3"}, {"sigma250":"1.5 × 10−4"},
    {"c":"20"},{"label":"bulk resistance"},
    {"methods":"410 MPa"},{"structure":"XRD only"},
])
def test_misleading_original_scientific_source_drifts_fail_closed(changes):
    with pytest.raises(ValueError):
        m.parse_primary_jats(article(**changes))


def test_wrong_paper_or_unsupported_doctype_and_xml_entity_rejected():
    for raw in (
        b'<html><p>Li7P3S11</p></html>',
        b'<!DOCTYPE article SYSTEM "remote.dtd">'+article(),
        b'<!ENTITY x SYSTEM "http://evil.test">'+article(),
        article()[:-12],
    ):
        with pytest.raises(ValueError):
            m.parse_primary_jats(raw)


def test_sample_claim_not_inferred_from_matching_two_batch_names():
    d=m.parse_primary_jats(article())
    assert d["series_labels_are_powder_batches_not_independent_materials"]
    assert d["numeric_per_pellet_thickness_electrode_area_certified"] is False
    assert d["supplement_file_contents_reviewed"] is False
    assert d["new_original_study_published_before_protocol"] is True
    assert d["admission"]=="BATCH_CONTEXT_ONLY_PELLET_LEVEL_UNATTESTED"
