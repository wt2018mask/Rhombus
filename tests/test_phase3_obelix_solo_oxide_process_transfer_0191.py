"""0191 hostile original process-data tests; no TEST label reading or target leakage."""
import numpy as np
import pytest
from scripts.science import obelix_solo_oxide_process_transfer_0191 as m

def test_strict_author_sintering_cell():
    assert m.process_cell("1100 °C × 20 h")== (1100,1200)
    assert m.process_cell("1200 °C × 30 min")== (1200,30)
    for value in ("1200°C", "1200 °C x 30 min followed by 1100 C",
                  "1200 °C x 30 days", "1400 °C x 30 min", "1200 °C x NaN min"):
        with pytest.raises(ValueError):m.process_cell(value)

def test_feature_time_and_temperature_only():
    row=("DOI","state","Li6La3Zr2O12",1200,60,1e-4)
    assert np.allclose(m.features([row]),np.array([[0.5,0.0]]))
    for row in [("DOI","bad","Li6La3Zr2O12",1200,0,1e-4),
                ("DOI","bad","Li6La3Zr2O12",float("nan"),60,1e-4)]:
        with pytest.raises(ValueError):m.features([row])

def test_leave_one_complete_original_paper_out_and_active_process_fitting():
    a=[("pA",f"a{i}","Li6La3Zr2O12",t,mn,y) for i,(t,mn,y) in enumerate(zip(
        [1100,1150,1200,1210,1220],[1200,1200,1200,900,600],
        [1e-5,2e-5,4e-5,8e-5,1e-4]))]
    b=[("pB",f"b{i}","Li6La3Zr2O12",t,mn,y) for i,(t,mn,y) in enumerate(zip(
        [1200,1200,1150,1100,1100],[60,30,60,60,360],
        [2e-4,5e-4,4e-4,1e-5,3e-5]))]
    scores=m.fold(a,b,{"pA":-4.0,"pB":-4.0})
    assert scores["test_DOI"]=="pB"
    assert scores["models"]["O_ONLY_RF"]["top1_abstained"]
    assert not scores["models"]["TRAIN_DOI_PROCESS_RIDGE"]["top1_abstained"]
    with pytest.raises(ValueError):m.fold(a,a,{"pA":-4.0})
    polluted=list(a);polluted[0]=("pB",)+polluted[0][1:]
    with pytest.raises(ValueError):m.fold(polluted,b,{"pA":-4.0,"pB":-4.0})

def test_frozen_2018_2020_original_process_descriptors():
    assert m.S18[0]==("LLZALO-1",1100,1200)
    assert m.S18[3]==("LLZALO-4",1210,900)
    assert m.S20[1]==("SL2",1200,30)
    assert m.S20[4]==("SL5",1100,360)
    assert m.ALPHA==1.0 and len(m.S18)==len(m.S20)==5

def test_original_2018_table1_to_table3_link_and_tamper():
    from scripts.science.obelix_solo_oxide_five_doi_0188 import S18,T18
    root=('<article><front><article-meta><article-id pub-id-type="doi">'+m.DOI18+
          '</article-id><article-id pub-id-type="pmc">9079727</article-id></article-meta></front>'
          '<body><p>Li6.4Al0.2La3Zr2O12 25 C measurement</p></body><floats-group>'
          '<table-wrap><caption><p>Summary of sample denotation, sintering conditions and compositions</p></caption><table>'
          '<tr><th>Sample denotation</th><th>Sintering conditions</th></tr>')
    root+=''.join(f'<tr><td>{name}</td><td>{temp} °C × {duration//60} h</td></tr>'
                  for name,temp,duration in m.S18)
    root+=('</table></table-wrap><table-wrap><caption><p>Other results</p></caption><table>'
           '<tr><td>Any</td></tr></table></table-wrap>'
           '<table-wrap><caption><p>Summary of ionic conductivity data</p></caption><table>'
           '<tr><th>Sample</th><th>total conductivity</th><th>bulk conductivity</th></tr>')
    root+=''.join(f'<tr><td>{n}</td><td>{v:.8e}</td><td>1e-4</td></tr>' for n,v in zip(S18,T18))
    blob=(root+'</table></table-wrap></floats-group></article>').encode()
    rows,_=m.original_process_2018(blob)
    assert len(rows)==5 and rows[3][3:5]==(1210,900)
    with pytest.raises(ValueError):
        m.original_process_2018(blob.replace(b"1100",b"1300"))

def test_original_2020_table2_process_source_tamper():
    from scripts.science.obelix_solo_oxide_jats_three_doi_0187 import COND2020
    table='<table-wrap><label>Table 2.</label><caption><p>Total ionic conductivity at 25 C and sintering condition</p></caption><table>'
    table+='<tr><th>Sample Name</th><th>Sintering Condition</th><th>Total Ionic Conductivity (10-4 S cm-1)</th></tr>'
    table+=''.join(f'<tr><td>{name}</td><td>{temp} °C × {minutes} min</td><td>{v}</td></tr>'
                   for (name,temp,minutes),v in zip(m.S20,COND2020))
    xml=(f'<article><front><article-meta><article-id pub-id-type="doi">{m.DOI20}</article-id>'
         f'<article-id pub-id-type="pmc">{m.PMCS[2][3:]}</article-id></article-meta></front>'
         f'<body><p>Li6.6La3Zr1.6Nb0.4O12 total conductivity sintering.</p></body><floats-group>{table}</table></table-wrap></floats-group></article>').encode()
    rows,_ = m.original_process_2020(xml)
    assert len(rows)==5 and rows[4][4]==360
    # Process-to-conductivity pairing must refuse a mutated furnace setting.
    with pytest.raises(ValueError):
        m.original_process_2020(xml.replace(b"1200",b"1300",1))
