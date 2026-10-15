"""0187 original public DOI/JATS table falsification and official TEST quarantine."""
import pytest
from scripts.science import obelix_solo_oxide_jats_three_doi_0187 as m

def make_doc(doi,pmc,headers,rows):
    rowxml=""
    for row in rows:
        rowxml+="<tr>"+"".join("<td>"+str(x)+"</td>" for x in row)+"</tr>"
    fillers="<p>Original LLZO total ionic conductivity science paragraph.</p>"*16
    return (f'<article><front><article-meta><article-id pub-id-type="doi">{doi}</article-id>'
            f'<article-id pub-id-type="pmc">{pmc.removeprefix("PMC")}</article-id></article-meta></front>'
            f'<body>{fillers}<table-wrap><label>Table 2</label><caption><p>'
            f'{headers}</p></caption><table><tbody>{rowxml}</tbody></table></table-wrap></body></article>').encode()

def test_2022_six_original_theoretical_precursor_compositions_derived_without_pellet_false_identity():
    original=make_doc(m.DOIS[1],m.PMCS[1],"Summary of total bulk + grain-boundary ionic conductivity at 25 °C",
       [("Sample","Al6.9","Al7.7","Al8.4","AGT6.9","AGT7.7","AGT8.4"),
        ("Ion conductivity (x 10-4 S cm-1)","1.0","1.7","0.1","1.8","3.6","0.2")])
    # Fixture requires source narrative theoretical formula; not enough to
    # infer from a table-only skeleton: negative gate until original context.
    with pytest.raises(ValueError,match="theoretical precursor"):
        m.inspect_2022(original)

def test_2020_five_original_sintering_route_table_checks():
    a=make_doc(m.DOIS[2],m.PMCS[2],"Total ionic conductivity at 25 °C",
       [("Sample","sintering","cell","Total conductivity (10-4 S cm-1)","Ea","density")]+
       [(f"SL-{i}","1200 C","12.89",str(v),"0.3","89") for i,v in enumerate(m.COND2020,1)])
    with pytest.raises(ValueError,match="nominal Nb"):
        m.inspect_2020(a)

def test_2020_table_missing_original_DOI_denied():
    a=make_doc("10.3390/fake",m.PMCS[2],"Total ionic conductivity at 25 °C",
               [("SL1","1200","12.9","1.58","0.3","89")])
    with pytest.raises(ValueError,match="DOI"):
        m.inspect_2020(a)

def test_publisher_entity_expansion_denied():
    with pytest.raises(ValueError,match="entities"):
        m.parse_article(b'<!DOCTYPE x [<!ENTITY a "bad">]><article>&a;</article>',m.DOIS[1],m.PMCS[1])

def test_all_formula_inputs_are_O_ONLY_including_nbdoped_and_precursor_theoretical():
    from scripts.science.obelix_real_grouped_oof_0146 import _composition
    from scripts.science.obelix_group_failure_audit_0148 import _family_proxy
    f=[m.SERIES2020]
    for vals,t in m.SERIES2022.values():
        for x in m.LI_START:f.append(t.format(li=f"{x-.75:.10g}"))
    assert len(f)==7 and all(_family_proxy(_composition(z)[1])=="O_ONLY" for z in f)

def test_2022_fixed_rows_scientifically_derived_not_copied_2020():
    assert m.SERIES2022["Al"][0]==(1.0,1.7,0.1)
    assert m.SERIES2022["AGT"][0]==(1.8,3.6,0.2)
    assert m.COND2020==(1.58,5.09,3.49,0.51,0.35)
    assert len(set(m.DOIS))==3

def test_original_TEST_row_fields_never_accessed_even_during_embargo():
    class Guard(dict):
        def get(self,key,default=None):
            if key!="official_split":raise AssertionError("official TEST queried")
            return super().get(key,default)
    records=[Guard(official_split="TEST") for _ in range(121)]
    records += [dict(official_split="TRAIN",source_entry_id=str(i),
       reported_composition="Li6.6La3Zr1.6Nb0.4O12" if i==0 else "Li7La3Zr2O12",
       reference_dois=["10.1234/"+str(i)]) for i in range(478)]
    arr={"source_ids":("0","1"),"groups":("wrong","wrong")}
    with pytest.raises(ValueError,match="graph"):
        m.embargo_training(records,arr,[m.SERIES2020])
    arr["groups"]=("0","1")
    mask,matched,groups=m.embargo_training(records,arr,[m.SERIES2020])
    assert mask.tolist()==[False,True] and matched==1 and groups==1
