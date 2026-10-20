"""Fail-closed gates for the institutional VOR source-verification route."""
import hashlib

import pytest

from scripts.science import verify_unimore_vor_0194 as source

PDF_NOTICE = ("This is an open access article under the terms of the Creative Commons Attribution "
              "License, which permits use, distribution and reproduction in any medium, "
              "provided the original work is properly cited.")


def _file_record(uri="http://creativecommons.org/licenses/by/4.0/"):
    # Shape observed in IRIS's exact file row, not the repository footer.
    return (f'<table><tr><td>Open access VOR - Versione pubblicata dall\'editore '
            f'Licenza: [IR] creative-commons <span id="license_{source.PDF_HANDLE}"></span>'
            f'<script>data: {{license: \'standard\', licenseUri: \'{uri}\'}}; '
            f'$(\'#license_{source.PDF_HANDLE}\').html(data);</script></td></tr></table>').encode()


def test_document_license_reads_file_scoped_ajax_data_not_footer_default():
    rights = source.document_license(_file_record(), source._normalized(PDF_NOTICE))
    assert rights["canonical_uri"] == "https://creativecommons.org/licenses/by/4.0/"
    assert rights["pdf_license_version"] is None
    assert rights["institutional_license_version"] == "4.0"
    assert not rights["repository_default_policy_used"]


def test_repository_wide_cc_default_cannot_replace_file_metadata():
    global_default = b'<footer><a rel="license" href="https://creativecommons.org/licenses/by/4.0/">CC BY</a></footer>'
    with pytest.raises(ValueError, match="file-specific"):
        source.document_license(global_default, source._normalized(PDF_NOTICE))
    with pytest.raises(ValueError):
        source.document_license(_file_record("http://creativecommons.org/licenses/by-nc/4.0/")+global_default,
                                source._normalized(PDF_NOTICE))


def test_generic_oa_footer_is_not_the_publisher_document_license():
    with pytest.raises(ValueError, match="document-specific"):
        source.document_license(_file_record(), "OA articles are governed by the applicable Creative Commons License")


class _Page:
    def extract_text(self):
        return ("Hexavalent Ions Insertion in Garnet Li7La3Zr2O12 Toward a Low Temperature Densification\n"
                "Campanella Zhu Girard DOI 10.1002/cssc.202300399 ChemSusChem Wiley\n"
                + PDF_NOTICE + "\nHot-press conditions 56 MPa\n" + _table_layout())


class _Reader:
    def __init__(self, _stream, strict=True):
        assert strict
        self.is_encrypted = False
        self.pages = [_Page()]


def _record(*, doi=source.DOI, version="Version of Record", license_uri="https://creativecommons.org/licenses/by/4.0/"):
    row = _file_record(license_uri).decode().replace("VOR - Versione pubblicata dall'editore", version)
    return (f'<html><head><meta name="citation_doi" content="{doi}"></head>'
            f'<body>record 1328508 {row}</body></html>').encode()


def _pdf():
    return b"%PDF-1.7\n" + b"verified test fixture only " * 60


@pytest.fixture(autouse=True)
def fixture_pdf_pin(monkeypatch):
    monkeypatch.setattr(source, "EXPECTED_PDF_SHA256", hashlib.sha256(_pdf()).hexdigest())


def _verify(record, pdf, pdf_reader=_Reader):
    def layout_extractor(_raw):
        reader = pdf_reader(None, strict=True)
        return "\n".join(page.extract_text() for page in reader.pages)
    return source.verify(record, pdf, pdf_reader=pdf_reader, layout_extractor=layout_extractor)


def _table_layout():
    lines = ["Table 2. Total ionic conductivity at 25 °C (S cm-1).",
             "Temperature Te0.1 Te0.25 Te0.375 Te0.5 Al-LLZO Ta-LLZO"]
    for i, temperature in enumerate(source.TEMPERATURES):
        cells = "  ".join(f"{x:.2e}".replace("e-", " × 10^-")
                          for x in source.EXPECTED[6*i:6*i+6])
        lines.append(f"{temperature} °C  {cells}")
    return "\n".join(lines)


def test_table_mapping_uses_series_headers_and_temperature_rows():
    mapping = source.parse_table_layout(_table_layout())
    assert len(mapping) == 18
    lookup = {(r["nominal_series"],r["hot_press_temperature_C"]):r["total_ionic_conductivity_S_cm"]
              for r in mapping}
    assert lookup[("Te0.1",650)] == pytest.approx(1.76e-5)
    assert lookup[("Ta-LLZO",700)] == pytest.approx(6.70e-6)


def test_comma_decimal_notation_preserves_all_mappings():
    layout = _table_layout()
    import re
    layout = re.sub(r"(\d)\.(\d\d)(?= ×)",r"\1,\2",layout)
    assert source.parse_table_layout(layout) == source.parse_table_layout(_table_layout())
    separated_sign=layout.replace("^-","^ - ")
    assert source.parse_table_layout(separated_sign) == source.parse_table_layout(_table_layout())


def test_changed_pdf_bytes_fail_before_extraction():
    with pytest.raises(ValueError,match="SHA-256"):
        _verify(_record(), _pdf()+b"changed")


def test_unaudited_shapes_cannot_replace_the_source_math_minus():
    bar=[("moveTo",((10,200),)),("lineTo",((600,200),)),
         ("lineTo",((600,240),)),("lineTo",((10,240),)),("closePath",())]
    for changed in (bar,bar[:-1],[("curveTo",((10,200),(600,200),(600,240)))],
                    [(op,tuple((y,x) for x,y in args)) for op,args in bar]):
        with pytest.raises(ValueError):source.horizontal_bar_bounds(changed)


def test_actual_embedded_minus_rounded_caps_are_audited_exactly():
    assert source.horizontal_bar_bounds(source.SOURCE_MINUS_OUTLINE)==[84,229,691,271]
    changed=list(source.SOURCE_MINUS_OUTLINE)
    changed[1]=("curveTo",((106,271),(84,999),(84,251)))
    with pytest.raises(ValueError):source.horizontal_bar_bounds(changed)


@pytest.mark.parametrize("old,new",[("600 °C","610 °C"),("Te0.375","Te0.376"),
                                   ("S cm-1","mS cm-1")])
def test_temperature_series_and_unit_mutations_reject(old,new):
    with pytest.raises(ValueError):
        source.parse_table_layout(_table_layout().replace(old,new))


@pytest.mark.parametrize("left,right",[("1.21","2.95"),("1.21","1.76")])
def test_value_swaps_between_series_or_temperatures_reject(left,right):
    layout = _table_layout().replace(left,"SWAPPED",1).replace(right,left,1).replace("SWAPPED",right,1)
    with pytest.raises(ValueError,match="mapping differs"):
        source.parse_table_layout(layout)


def test_record_vor_license_and_all_18_values_make_separate_provenance_receipt():
    receipt = _verify(_record(), _pdf(), pdf_reader=_Reader)
    assert receipt["source_route"] == "INSTITUTIONAL_VERSION_OF_RECORD"
    assert receipt["live_wiley_html_verified"] is False
    assert receipt["record_exact_doi_match"]
    assert receipt["record_binds_exact_pdf_handle"]
    assert receipt["record_identifies_publisher_version"]
    assert receipt["table_2_condition_count"] == 18
    assert receipt["table_2_all_18_values_exact_match"]
    assert receipt["pdf_sha256"] == hashlib.sha256(_pdf()).hexdigest()
    assert not receipt["scientific_GO"] and not receipt["production_enabled"]
    assert all(receipt[k] == "BLOCKED" for k in ("P0_01", "P0_02", "P0_03"))


@pytest.mark.parametrize("record", [
    _record(doi="10.1002/wrong"),
    _record(version="Accepted Manuscript"),
    _record(license_uri="https://example.org/license"),
])
def test_wrong_doi_vor_status_or_license_is_rejected(record):
    with pytest.raises(ValueError):
        _verify(record, _pdf(), pdf_reader=_Reader)


def test_wrong_article_identity_is_rejected():
    class WrongArticleReader(_Reader):
        def __init__(self, stream, strict=True):
            super().__init__(stream, strict)
            self.pages = [type("Page", (), {"extract_text": lambda self: "unrelated text"})()]
    with pytest.raises(ValueError, match="article identity"):
        _verify(_record(), _pdf(), pdf_reader=WrongArticleReader)


@pytest.mark.parametrize("old,new",[(source.DOI,"10.1002/cssc.wrong"),("56 MPa","57 MPa")])
def test_pdf_doi_and_pressure_mutations_reject(old,new):
    class ChangedReader(_Reader):
        def __init__(self,stream,strict=True):
            super().__init__(stream,strict)
            self.pages=[_Page()]
            self.pages[0].extract_text=lambda:_Page().extract_text().replace(old,new)
    with pytest.raises(ValueError):
        _verify(_record(),_pdf(),pdf_reader=ChangedReader)


def test_incomplete_or_changed_table_fails_closed():
    class TruncatedTableReader(_Reader):
        def __init__(self, stream, strict=True):
            super().__init__(stream, strict)
            self.pages = [_Page()]
            self.pages[0].extract_text = lambda: _Page().extract_text().replace("6.70 × 10^-06", "", 1)
    with pytest.raises(ValueError, match="six complete scientific values"):
        _verify(_record(), _pdf(), pdf_reader=TruncatedTableReader)

    class ChangedTableReader(_Reader):
        def __init__(self, stream, strict=True):
            super().__init__(stream, strict)
            self.pages = [_Page()]
            self.pages[0].extract_text = lambda: _Page().extract_text().replace("1.21", "1.22", 1)
    with pytest.raises(ValueError, match="mapping differs"):
        _verify(_record(), _pdf(), pdf_reader=ChangedTableReader)


@pytest.mark.parametrize("payload", [b"not pdf", b"%PDF-1.7\nshort"])
def test_invalid_pdf_bytes_rejected(payload):
    with pytest.raises(ValueError):
        _verify(_record(), payload, pdf_reader=_Reader)
