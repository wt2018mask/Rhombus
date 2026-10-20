"""0194 author-source identity, counterexample and applicability tests."""
import pytest
from scripts.science import obelix_solo_oxide_author_te_hotpress_0194 as m

def fixture(values=None,doi=m.DOI,header="Total ionic conductivity σ (25 °C) [S cm−1]"):
    v=m.AUTHOR if values is None else values
    rows=""
    for i,t in enumerate(m.TEMPS):
        cells="".join("<td>"+f"{x:.2e}".replace("e-","x10-")+"</td>" for x in v[i])
        rows+=f"<tr><td>{t} °C</td>{cells}</tr>"
    return (f'<html><head><meta name="citation_doi" content="{doi}"/></head><body>'
        '<h1>Hexavalent Ions Insertion in Garnet</h1>'
        '<p>Authors Campanella, Zhu, Girard: total ionic conductivity of hot-pressed samples.</p>'
        f'<table><caption>Original Table 2. {header}</caption>'
        '<tr><th>Temperature</th><th>Te0.1</th><th>Te0.25</th><th>Te0.375</th>'
        '<th>Te0.5</th><th>Al-LLZO</th><th>Ta-LLZO</th></tr>'
        +rows+'</table></body></html>').encode()

def test_author_18_conditions_and_650C_nonmonotonic_counterexample():
    d=m.evaluate(m.original_html(fixture()))
    assert d["author_conditions"]==18 and d["nominal_series_count"]==6
    assert d["nonmonotonic_series"]==["Te0.1"]
    assert d["always_hottest_successes"]==5
    assert d["always_hottest_failures"]==1
    assert d["rows"][0]["best_source_temp_C"]==650
    assert d["rows"][0]["25C_TOTAL_S_cm"][2]==pytest.approx(1.45e-5)

def test_first_party_DOI_and_target_temperature_required():
    for kw in ({"doi":"10.1002/wrong"},{"header":"Total ionic conductivity σ (30 °C) [S cm−1]"},
               {"header":"Total ionic conductivity σ (25 °C) [mS cm−1]"}):
        with pytest.raises(ValueError):m.original_html(fixture(**kw))

def test_mutation_and_double_table_must_fail():
    v=[list(row) for row in m.AUTHOR]
    v[1][0]=1.11e-5
    with pytest.raises(ValueError):m.original_html(fixture(values=v))
    with pytest.raises(ValueError):m.original_html(fixture().replace(b"650",b"680"))
    f=fixture()
    duplicate=f.replace(b"</body>",f[f.find(b"<table>"):f.find(b"</table>")+8]+b"</body>")
    with pytest.raises(ValueError):m.original_html(duplicate)

def test_invalid_scientific_notation_rejected():
    assert m.conductivity("1,76×10−5")==pytest.approx(1.76e-5)
    for cell in ("NaN","1.76 mS/cm","1.76e5","1.76x10-5 noise","0","-1"):
        with pytest.raises(ValueError):m.conductivity(cell)

def test_physical_science_NO_GO_and_0191_outside_domain():
    d=m.evaluate(m.original_html(fixture()))
    assert not d["0191_process_model_compatible"]
    assert d["0191_model_route_abstentions"]==6
    assert not d["model_choice_outperformance_proven"]
    assert d["original_OBELiX_official_TEST_121_unread"]
    assert not d["scientific_GO"] and not d["production_enabled"]
    assert all(d[k]=="BLOCKED" for k in ("P0_01","P0_02","P0_03"))


def test_publisher_http_denial_default_is_fail_closed(monkeypatch,tmp_path):
    def publisher_unavailable():
        raise m.PublisherUnavailable("publisher original HTML inaccessible HTTP 403")
    monkeypatch.setattr(m,"fetch_publisher",publisher_unavailable)
    with pytest.raises(ValueError,match="inaccessible"):
        m.run(tmp_path/"strict.json")
    assert not (tmp_path/"strict.json").exists()

def test_frozen_author_diagnostic_distinguishes_unverified_from_live(monkeypatch,tmp_path):
    def publisher_unavailable():
        raise m.PublisherUnavailable("publisher original HTML inaccessible HTTP 403")
    monkeypatch.setattr(m,"fetch_publisher",publisher_unavailable)
    d=m.run(tmp_path/"retrospective.json",allow_unverified_frozen_diagnostic=True)
    assert (tmp_path/"retrospective.json").exists()
    assert d["author_conditions"]==18
    assert d["first_party_html_sha256"] is None
    assert d["publisher_live_source_verified"] is False
    assert d["source_unavailable_diagnostic_only"] is True
    assert d["original_source_admission"]=="BLOCKED_PUBLISHER_ACCESS"
    assert not d["scientific_GO"] and not d["production_enabled"]

def test_valid_original_fixture_has_authentic_source_sha():
    d=m.evaluate(m.original_html(fixture()))
    assert d["publisher_live_source_verified"]
    assert d["original_source_admission"]=="SOURCE_VERIFIED"
    assert len(d["first_party_html_sha256"])==64


def test_availability_probe_never_claims_authentication_for_unavailable_wiley(monkeypatch,tmp_path):
    def unavailable():
        raise m.PublisherUnavailable("HTTP_403; HTTP_403")
    monkeypatch.setattr(m,"fetch_publisher",unavailable)
    d=m.probe_publisher_availability(tmp_path/"availability.json")
    assert d["availability"]=="UNAVAILABLE"
    assert not d["publisher_live_source_verified"]
    assert d["first_party_html_sha256"] is None
    assert d["original_source_admission"]=="BLOCKED_PUBLISHER_ACCESS"


def test_availability_probe_does_not_mask_received_source_validation_failure(monkeypatch,tmp_path):
    def invalid():
        raise ValueError("original Table2 value mutated")
    monkeypatch.setattr(m,"fetch_publisher",invalid)
    with pytest.raises(ValueError,match="mutated"):
        m.probe_publisher_availability(tmp_path/"invalid.json")
    assert not (tmp_path/"invalid.json").exists()


def test_received_invalid_source_never_falls_back(monkeypatch,tmp_path):
    import io
    calls=[]
    def invalid_source(*args,**kwargs):
        calls.append(args[0].full_url)
        return io.BytesIO(fixture(doi="10.1002/wrong"))
    monkeypatch.setattr(m.urllib.request,"urlopen",invalid_source)
    with pytest.raises(ValueError,match="DOI and authors"):
        m.run(tmp_path/"invalid.json",allow_unverified_frozen_diagnostic=True)
    assert len(calls)==1
    assert not (tmp_path/"invalid.json").exists()


def test_access_denial_then_changed_values_is_hard_failure(monkeypatch,tmp_path):
    import io
    from urllib.error import HTTPError
    values=[list(row) for row in m.AUTHOR]
    values[1][0]=1.11e-5
    calls=[]
    def source(*args,**kwargs):
        calls.append(args[0].full_url)
        if len(calls)==1:
            raise HTTPError(calls[-1],403,"Forbidden",{},None)
        return io.BytesIO(fixture(values=values))
    monkeypatch.setattr(m.urllib.request,"urlopen",source)
    with pytest.raises(ValueError,match="mutated"):
        m.run(tmp_path/"changed.json",allow_unverified_frozen_diagnostic=True)
    assert len(calls)==2
    assert not (tmp_path/"changed.json").exists()


def test_actual_http_denials_only_allow_explicit_diagnostic(monkeypatch,tmp_path):
    from urllib.error import HTTPError
    def denied(req,**kwargs):
        raise HTTPError(req.full_url,403,"Forbidden",{},None)
    monkeypatch.setattr(m.urllib.request,"urlopen",denied)
    with pytest.raises(m.PublisherUnavailable,match="HTTP_403"):
        m.run(tmp_path/"strict.json")
    assert not (tmp_path/"strict.json").exists()
    d=m.run(tmp_path/"diagnostic.json",allow_unverified_frozen_diagnostic=True)
    assert d["original_source_admission"]=="BLOCKED_PUBLISHER_ACCESS"
    assert d["first_party_html_sha256"] is None


@pytest.mark.parametrize("kind",["tls","unexpected"])
def test_trust_or_programming_failures_never_become_diagnostics(monkeypatch,tmp_path,kind):
    import ssl
    from urllib.error import URLError
    exc=(URLError(ssl.SSLCertVerificationError("invalid certificate"))
         if kind=="tls" else RuntimeError("parser programming failure"))
    def broken(*args,**kwargs):
        raise exc
    monkeypatch.setattr(m.urllib.request,"urlopen",broken)
    with pytest.raises(type(exc)):
        m.run(tmp_path/"broken.json",allow_unverified_frozen_diagnostic=True)
    assert not (tmp_path/"broken.json").exists()
