"""0186 original journal 25C-total gate: hostile source alterations and no pseudo-N."""
import xml.etree.ElementTree as ET
import pytest
import numpy as np
from scripts.science import obelix_solo_oxide_primary_0186 as m

def make_xml(before="2.32 × 10−4 and 7.14 × 10−4",
             after_ta="2.32 × 10−4 to 2.86 × 10−4",
             after_ga="7.14 × 10−4 to 3.29 × 10−4"):
    filler="".join("<p>Author original 25 C EIS XRD pellet interface bulk grain experimental context.</p>" for _ in range(16))
    xml=f'<article><front><article-meta><article-id pub-id-type="doi">{m.SOURCE_DOI}</article-id><article-id pub-id-type="pmc">12315797</article-id></article-meta></front><body>{filler}<p>Ta0.5 Li6.5La3Zr1.5Ta0.5O12 and Ga0.2 Li6.4Ga0.2La3Zr2O12 were measured at 25 C.</p><p>We calculated total conductivity from the combined bulk and grain resistance pellet EIS.</p><p>The room-temperature ionic conductivities calculated using the total solid electrolyte resistance were {before} S cm−1 for Ta- and Ga-LLZO, respectively.</p><p>Ta-LLZO exhibited a moderate increase in ionic conductivity from {after_ta} S cm−1 at room temperature following alloy contact.</p><p>Conversely, Ga-LLZO demonstrated a substantial decrease in conductivity from {after_ga} S cm−1 at room temperature.</p></body></article>'
    return xml.encode()

def test_genuine_two_chemistry_single_paper_gate():
    s=m.parse_original_jats(make_xml())
    assert s["measurement_temperature_C"]==25
    assert s["transport_endpoint"]=="AUTHOR_TOTAL_IONIC_CONDUCTIVITY_S_PER_CM"
    assert s["nominal_chemistries"]==2 and s["distinct_original_papers"]==1
    assert not s["same_individual_diffraction_EIS_pellet_verified"]
    assert len(m.FORMULAS)==2 and len(m.MODELS)==4

def test_mutated_original_source_and_exponents_fail_closed():
    for a in (make_xml(before="2.32 × 10−3 and 7.14 × 10−4"),
              make_xml(after_ta="2.32 × 10−4 to 2.86 × 10−5"),
              make_xml(after_ga="7.14 × 10−4 to 3.29 × 10−5"),
              make_xml().replace(b"10.1039/d5ra03917g",b"10.1039/other")):
        with pytest.raises(ValueError):m.parse_original_jats(a)
    with pytest.raises(ValueError):m.parse_original_jats(b"<!DOCTYPE x><article/>")
    with pytest.raises(ValueError):m.parse_original_jats(b"<article>broken")

def test_pristine_vs_contact_nominal_composition_is_same_input_but_different_target():
    from scripts.science.obelix_real_grouped_oof_0146 import _composition
    from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
    assert all(_family_proxy(_composition(x)[1])=="O_ONLY" for x in m.FORMULAS)
    assert m.POST_LI_SI_CONTACT[0]>m.PRISTINE[0]
    assert m.POST_LI_SI_CONTACT[1]<m.PRISTINE[1]
    log_delta=np.abs(np.log10(m.POST_LI_SI_CONTACT)-np.log10(m.PRISTINE))
    floor=float(np.sum(log_delta)/4)
    assert floor>0.09
    for p in np.linspace(-10,0,27):
        mean_mae=np.mean(np.abs(np.array([p,p])-np.log10([m.PRISTINE[0],m.POST_LI_SI_CONTACT[0]])))
        assert mean_mae+1e-10>=log_delta[0]/2

def test_unseen_TEST_not_decoded_by_source_graph():
    class Guard(dict):
        def get(self,key,default=None):
            if key!="official_split":raise AssertionError("official TEST leaked")
            return super().get(key,default)
    source=[Guard(official_split="TEST") for _ in range(121)]
    source += [dict(official_split="TRAIN",source_entry_id="r"+str(i),
                    reported_composition="Li6.5La3Zr1.5Ta0.5O12" if i==1 else "Li4PO4",
                    reference_dois=["10.1234/a"+str(i)]) for i in range(478)]
    source_ids=("r0","r1","r2")
    with pytest.raises(ValueError,match="graph mismatch"):
        m.components_to_embargo(source,source_ids,("wrong","wrong","wrong"))
    # Correct source grouping must quarantine the matching component.
    keep,groups,matched=m.components_to_embargo(source,source_ids,source_ids)
    assert keep.tolist()==[True,False,True] and groups==1 and matched==1
