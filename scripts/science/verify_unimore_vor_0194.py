"""Verify the institutional publisher-VOR copy for the 0194 article.

The institution record, its declared open license and the downloaded PDF are
independent provenance checks. This route never substitutes a transcription
or a PDF hash for a DOI-bound and complete source.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import re
import subprocess
import tempfile
import unicodedata
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject

DOI = "10.1002/cssc.202300399"
RECORD_URL = "https://iris.unimore.it/handle/11380/1328508"
PDF_URL = ("https://iris.unimore.it/retrieve/500e772d-e2c5-4d6d-88e5-14f53ce47ac1/"
           "ChemSusChem%20-%202023%20-%20Campanella%20-%20Hexavalent%20Ions%20Insertion%20"
           "in%20Garnet%20Li7La3Zr2O12%20Toward%20a%20Low%20Temperature%20Densification.pdf")
PDF_HANDLE = "500e772d-e2c5-4d6d-88e5-14f53ce47ac1"
EXPECTED_PDF_SHA256 = "871e6ff252cce27799e8e2bf5455667bdaf6dc639dde2875ad57a4ecce5fc58b"
MATH_FONT_SHA256 = "fb461586ef77c2a8b671ad21ab047e64897e85248985057cd0224224a368b234"
MATH_CMAP_SHA256 = "811e6119c3c4b775c4cf72e88b052723a29c9aaecea8b65607e85d93b287ba82"
# Actual code-0 contour from the pinned embedded TeX math-symbol font. It is
# a horizontal minus with rounded caps, obtained by decoding the Type1 program
# (Actions 39357413171), independently of conductivity coefficients/exponents.
SOURCE_MINUS_OUTLINE = [
    ("moveTo",((112,271),)),
    ("curveTo",((106,271),(84,271),(84,251))),
    ("curveTo",((84,229),(104,229),(112,229))),
    ("lineTo",((663,229),)),
    ("curveTo",((671,229),(691,229),(691,251))),
    ("curveTo",((691,271),(669,271),(663,271))),
    ("closePath",()),
]
MAX_RECORD_BYTES = 4 * 1024 * 1024
MAX_PDF_BYTES = 40 * 1024 * 1024
EXPECTED = (
    1.21e-5, 2.95e-5, 1.61e-5, 2.33e-5, 3.88e-8, 2.64e-7,
    1.76e-5, 4.64e-5, 3.27e-5, 4.24e-5, 1.04e-7, 2.29e-6,
    1.45e-5, 5.15e-5, 4.66e-5, 4.83e-5, 3.05e-7, 6.70e-6,
)
SERIES = ("Te0.1", "Te0.25", "Te0.375", "Te0.5", "Al-LLZO", "Ta-LLZO")
TEMPERATURES = (600, 650, 700)
SCIENTIFIC_VALUE = re.compile(
    r"(?<![\d.,])(\d+(?:[.,]\d+)?)\s*(?:×|x|\*)\s*10\s*\^?\s*\(?\s*(-\d+)\s*\)?")
SERIES_LABEL = re.compile(r"(?<![\w.])(?:te0\.375|te0\.25|te0\.1|te0\.5|al-llzo|ta-llzo)(?![\w.])")



class _RecordParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text: list[str] = []
        self.links: list[str] = []

    def handle_data(self, data: str) -> None:
        self.text.append(data)

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        for name in ("href", "content"):
            value = values.get(name)
            if value:
                self.links.append(value)


def _normalized(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    for char in ("−", "–", "—", "‑"):
        value = value.replace(char, "-")
    return re.sub(r"\s+", " ", value)


def document_license(record_html: bytes, pdf_text: str) -> dict:
    """Read rights only from the selected file row and publisher notice."""
    html = record_html.decode("utf-8", errors="replace")
    rows = [row for row in re.findall(r"<tr\b[^>]*>.*?</tr\s*>", html, re.I|re.S)
            if PDF_HANDLE in row]
    if len(rows) != 1:
        raise ValueError("one file-specific institutional metadata row is required")
    row = rows[0]
    parser = _RecordParser()
    parser.feed(row)
    text = _normalized(" ".join(parser.text))
    if not any(version in text for version in ("version of record", "published version",
            "publisher version", "vor - versione pubblicata dall'editore")):
        raise ValueError("selected institutional file is not declared publisher VOR")
    if "creative-commons" not in text and "creative commons" not in text:
        raise ValueError("selected institutional file has no Creative Commons rights label")
    # IRIS supplies this file's URI in AJAX data bound to license_<UUID>.
    # Do not execute the script or read repository-wide footer defaults.
    if f"license_{PDF_HANDLE}" not in row:
        raise ValueError("license metadata is not bound to the selected file handle")
    if not re.search(r"\$\(\s*['\"]#license_"+re.escape(PDF_HANDLE)+r"['\"]\s*\)\.html",row):
        raise ValueError("file licenseUri is not applied to the selected license element")
    uris = re.findall(r"\blicenseUri\s*:\s*['\"]([^'\"]+)['\"]", row)
    if len(uris) != 1:
        raise ValueError("file-specific licenseUri must be unique and explicit")
    raw_uri = uris[0]
    parsed = urlsplit(raw_uri)
    if (parsed.scheme not in ("http", "https") or parsed.hostname != "creativecommons.org"
            or parsed.username or parsed.password or parsed.port or parsed.query or parsed.fragment):
        raise ValueError("file-specific Creative Commons URI is invalid")
    canonical_uri = "https://creativecommons.org" + parsed.path.rstrip("/") + "/"
    if canonical_uri != "https://creativecommons.org/licenses/by/4.0/":
        raise ValueError("file-specific license differs from this publisher VOR's Attribution license")
    notice = re.search(r"this is an open access article under the terms of the creative commons attribution "
                       r"license, which permits use, distribution and reproduction in any medium, "
                       r"provided the original work is properly cited[.]", pdf_text)
    if notice is None:
        raise ValueError("publisher PDF's document-specific Attribution and citation notice is missing")
    return {"scope":"SELECTED_FILE_METADATA_AND_PUBLISHER_NOTICE",
            "institutional_file_handle":PDF_HANDLE,
            "institutional_label":"[IR] creative-commons",
            "institutional_raw_uri":raw_uri,"canonical_uri":canonical_uri,
            "representation":"licenseUri AJAX data in selected file's table row",
            "pdf_notice":notice[0],"pdf_license_family":"Creative Commons Attribution",
            "pdf_license_version":None,"institutional_license_version":"4.0",
            "uncertainties":["The PDF notice states the Attribution family without a version; "
                             "version 4.0 is declared by the institution's file-specific metadata."],
            "repository_default_policy_used":False,
            "redistribution_authorization":"CONDITIONAL_ON_CITATION_OF_ORIGINAL_WORK",
            "raw_pdf_redistributed":False}


def parse_table_layout(layout: str) -> list[dict]:
    """Bind extracted cells to explicit column labels and row temperatures."""
    lines = [_normalized(line).strip() for line in layout.splitlines()]
    captions = [i for i, line in enumerate(lines) if re.match(r"table\s*2\b", line)]
    if len(captions) != 1:
        raise ValueError("one unambiguous Table 2 caption is required")
    preceding = " ".join(lines[max(0,captions[0]-40):captions[0]+1])
    lines = lines[captions[0]:captions[0]+70]
    end = next((i for i, line in enumerate(lines[1:], 1)
                if re.match(r"table\s*3\b", line)), len(lines))
    lines = lines[:end]
    headers = [(i, SERIES_LABEL.findall(line)) for i, line in enumerate(lines)
               if len(SERIES_LABEL.findall(line)) == 6]
    if len(headers) != 1:
        raise ValueError("Table 2 must expose all six column labels on one header row")
    header_index, labels = headers[0]
    if len(set(labels)) != 6 or set(labels) != {x.lower() for x in SERIES}:
        raise ValueError("Table 2 series header changed")
    context = " ".join(lines[:header_index+1])
    if ("conductivity" not in context
            or re.search(r"\b25\s*°?\s*c\b", context) is None):
        raise ValueError("Table 2 conductivity at 25 C must be explicit")
    if "total ionic conductivity" not in preceding:
        raise ValueError("Table 2 must be bound to the preceding total-ionic-conductivity context")
    if re.search(r"\bs\s*cm\s*-\s*1\b|\bs\s*/\s*cm\b", context) is None:
        raise ValueError("Table 2 must use S/cm conductivity units")
    if re.search(r"\bms\s*(?:cm|/)", context):
        raise ValueError("Table 2 milli-Siemens units are incompatible")
    rows = {}
    for line in lines[header_index+1:]:
        row = re.match(r"^(\d{3,4})\s*°?\s*c\b(.*)", line)
        if row is None:
            continue
        temperature = int(row[1])
        if temperature not in TEMPERATURES or temperature in rows:
            raise ValueError("Table 2 temperature changed or duplicated")
        tokens = SCIENTIFIC_VALUE.findall(row[2])
        if len(tokens) != 6:
            raise ValueError("Table 2 row must contain six complete scientific values")
        rows[temperature] = dict(zip(labels, (float(c.replace(",", "."))*10**int(e) for c,e in tokens)))
    if set(rows) != set(TEMPERATURES):
        raise ValueError("Table 2 is missing a temperature row")
    mapping = []
    for row_index, temperature in enumerate(TEMPERATURES):
        for column_index, series in enumerate(SERIES):
            actual = rows[temperature][series.lower()]
            expected = EXPECTED[row_index*6+column_index]
            if not math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-18):
                raise ValueError(f"Table 2 mapping differs at {series}, {temperature} C")
            mapping.append({"nominal_series":series,"hot_press_temperature_C":temperature,
                            "total_ionic_conductivity_S_cm":actual,
                            "author_reported_target_temperature_C":25})
    return mapping


class _SameInstitutionRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlsplit(newurl)
        if (parsed.scheme != "https" or parsed.hostname != "iris.unimore.it"
                or parsed.username or parsed.password or parsed.port not in (None, 443)):
            raise ValueError("institutional source redirected outside its pinned host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url: str, limit: int, accept: str) -> tuple[bytes, str, int]:
    opener = build_opener(_SameInstitutionRedirects())
    with opener.open(Request(url, headers={"Accept": accept,
            "User-Agent": "Rhombus-source-verification/1.0"}), timeout=45) as response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname != "iris.unimore.it":
            raise ValueError("final institutional source host mismatch")
        length = response.headers.get("Content-Length")
        if length is not None and int(length) > limit:
            raise ValueError("institutional source exceeds byte bound")
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError("institutional source exceeds byte bound")
        return data, response.headers.get("Content-Type", ""), len(data)


def extract_layout(pdf: bytes) -> str:
    """Use native PDF text coordinates, never OCR or expected-value filling."""
    with tempfile.TemporaryDirectory(prefix="rhombus-vor-") as directory:
        path = Path(directory) / "source.pdf"
        path.write_bytes(pdf)
        result = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", "-nopgbrk", str(path), "-"],
                                check=True, capture_output=True, timeout=45)
    if len(result.stdout) > 2*1024*1024:
        raise ValueError("extracted PDF text exceeds audit bound")
    return result.stdout.decode("utf-8", errors="strict")


def type1_outline(data: bytes, length1: int, length2: int):
    """Wrap the unchanged PDF Type1 segments in a standard PFB container."""
    from fontTools.t1Lib import T1Font
    from fontTools.misc import psLib, psCharStrings, eexec
    from fontTools.pens.recordingPen import RecordingPen
    if not 0 < length1 < len(data) or not 0 < length2 <= len(data)-length1:
        raise ValueError("invalid embedded Type1 segment lengths")
    segments = [(1,data[:length1]),(2,data[length1:length1+length2])]
    if length1+length2 < len(data):
        segments.append((1,data[length1+length2:]))
    pfb = b"".join(b"\x80"+bytes([kind])+len(chunk).to_bytes(4,"little")+chunk
                   for kind,chunk in segments)+b"\x80\x03"
    with tempfile.TemporaryDirectory(prefix="rhombus-font-") as directory:
        path = Path(directory)/"source.pfb"
        path.write_bytes(pfb)
        program = T1Font(str(path),kind="PFB")
        # A Type1 font may omit Subrs when it uses none. FontTools' generic
        # T1Font.parse requires that optional key; preserve the standard empty
        # default while using its PostScript parser and charstring decoder.
        font = psLib.suckfont(program.data, "ascii")
        private = font["Private"]
        len_iv = private.get("lenIV",4)
        if not isinstance(len_iv,int) or not 0 <= len_iv <= 32:
            raise ValueError("unsupported Type1 charstring prefix")
        subrs = []
        for raw in private.get("Subrs",[]):
            decrypted,_ = eexec.decrypt(raw,4330)
            subrs.append(psCharStrings.T1CharString(decrypted[len_iv:],subrs=subrs))
        glyph = font["Encoding"][0]
        decrypted,_ = eexec.decrypt(font["CharStrings"][glyph],4330)
        charstring = psCharStrings.T1CharString(decrypted[len_iv:],subrs=subrs)
        pen = RecordingPen()
        charstring.draw(pen)
    return glyph, pen.value


def horizontal_bar_bounds(outline):
    """Require a proved horizontal bar; no OCR or scientific-value inference."""
    if outline == SOURCE_MINUS_OUTLINE:
        return [84,229,691,271]
    operations = [op for op,_ in outline]
    if (operations.count("moveTo") != 1 or operations.count("closePath") != 1
            or operations[0] != "moveTo" or operations[-1] != "closePath"
            or any(op not in ("moveTo","lineTo","closePath") for op in operations)):
        raise ValueError("unmapped math glyph is not a single closed horizontal bar")
    points = [tuple(point) for op,args in outline if op != "closePath" for point in args]
    if points and points[-1] == points[0]:points.pop()
    xs = sorted({p[0] for p in points});ys = sorted({p[1] for p in points})
    if (len(points) != 4 or len(xs) != 2 or len(ys) != 2
            or set(points) != {(x,y) for x in xs for y in ys}
            or any(a[0]!=b[0] and a[1]!=b[1] for a,b in zip(points,points[1:]+points[:1]))
            or not 0 < ys[1]-ys[0] < (xs[1]-xs[0])/5):
        raise ValueError("unmapped math glyph does not have a horizontal minus-bar outline")
    return [xs[0],ys[0],xs[1],ys[1]]


def recover_math_unicode(reader, original: bytes):
    """Repair only the pinned font's proven code-0 minus in an extraction copy."""
    proofs = []
    seen = set()
    for page in reader.pages:
        resources = page.get("/Resources",{}) if hasattr(page,"get") else {}
        resources = resources.get_object() if hasattr(resources,"get_object") else resources
        fonts = resources.get("/Font",{})
        fonts = fonts.get_object() if hasattr(fonts,"get_object") else fonts
        for reference in fonts.values():
            font = reference.get_object()
            if str(font.get("/BaseFont")) != "/TeX_CM_Maths_Symbols" or id(font) in seen:continue
            seen.add(id(font))
            if str(font.get("/Subtype")) != "/Type1" or font.get("/Encoding") is not None:
                raise ValueError("source math font encoding changed")
            stream = font["/FontDescriptor"].get_object()["/FontFile"].get_object()
            data = stream.get_data()
            if hashlib.sha256(data).hexdigest() != MATH_FONT_SHA256:
                raise ValueError("source embedded math font changed")
            glyph,outline = type1_outline(data,int(stream["/Length1"]),int(stream["/Length2"]))
            if glyph != "C0":raise ValueError("source math code-0 glyph changed")
            try:
                bounds = horizontal_bar_bounds(outline)
            except ValueError as exc:
                raise ValueError("source code-0 outline requires audit: "+json.dumps(outline)) from exc
            cmap = font["/ToUnicode"].get_object().get_data()
            if hashlib.sha256(cmap).hexdigest() != MATH_CMAP_SHA256:
                raise ValueError("source math Unicode map changed")
            proofs.append({"font":"TeX_CM_Maths_Symbols","encoded_byte":0,"glyph":glyph,
                "intrinsic_encoding_source":"embedded Type1 program /Encoding[0]",
                "embedded_font_sha256":MATH_FONT_SHA256,"original_cmap_sha256":MATH_CMAP_SHA256,
                "original_unicode":"UNMAPPED_NUL","extraction_unicode":"U+2212",
                "glyph_outline":outline,"horizontal_bar_bounds":bounds,
                "basis":"audited horizontal minus contour in the source math-symbol font; no expected numbers used"})
    if not proofs:return original,[]
    writer = PdfWriter(clone_from=reader)
    changed = set()
    for page in writer.pages:
        resources = page.get("/Resources",{})
        resources = resources.get_object() if hasattr(resources,"get_object") else resources
        fonts = resources.get("/Font",{})
        fonts = fonts.get_object() if hasattr(fonts,"get_object") else fonts
        for reference in fonts.values():
            font = reference.get_object()
            if str(font.get("/BaseFont")) != "/TeX_CM_Maths_Symbols" or id(font) in changed:continue
            changed.add(id(font))
            old = font["/ToUnicode"].get_object().get_data()
            if hashlib.sha256(old).hexdigest() != MATH_CMAP_SHA256 or old.count(b"endcmap") != 1:
                raise ValueError("ambiguous source Unicode repair target")
            replacement = DecodedStreamObject()
            replacement.set_data(old.replace(b"endcmap",b"1 beginbfchar\n<00> <2212>\nendbfchar\nendcmap"))
            font[NameObject("/ToUnicode")] = writer._add_object(replacement)
    if len(changed) != len(proofs):raise ValueError("Unicode repair target count changed")
    output = io.BytesIO();writer.write(output)
    return output.getvalue(),proofs


def inspect_source(record: bytes, pdf: bytes) -> None:
    """Emit bounded, public-source excerpts for auditing, never raw PDF bytes."""
    def notice(kind, payload):
        message = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
        message = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::notice title=0194 {kind}::{message}", flush=True)

    notice("download identity", {"pdf_sha256": hashlib.sha256(pdf).hexdigest(),
        "pdf_bytes": len(pdf), "record_sha256": hashlib.sha256(record).hexdigest(),
        "status": "DOWNLOADED_NOT_YET_VERIFIED"})
    html = record.decode("utf-8", errors="replace")
    matches = list(re.finditer(r"creative", html, re.I))
    selected = matches[:3] + matches[-1:]
    notice("record license evidence", [re.sub(r"\s+", " ",
        html[max(0,m.start()-450):m.end()+650]) for m in selected])
    reader = PdfReader(io.BytesIO(pdf), strict=True)
    rights_reported = False
    for index, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        if "1,21" in text and "2,95" in text:
            fonts = {}
            def inspect_glyphs(chunk, _cm, _tm, font, _size):
                if "\x00" not in chunk or font is None:
                    return
                key = str(font.get("/BaseFont"))
                if key in fonts:
                    return
                encoding = font.get("/Encoding")
                encoding = encoding.get_object() if hasattr(encoding,"get_object") else encoding
                cmap = font.get("/ToUnicode")
                cmap = cmap.get_object().get_data().decode("latin-1") if cmap else ""
                descriptor = font.get("/FontDescriptor")
                descriptor = descriptor.get_object() if descriptor else {}
                embedded = {}
                for kind in ("/FontFile", "/FontFile2", "/FontFile3"):
                    if kind in descriptor:
                        data = descriptor[kind].get_object().get_data()
                        embedded = {"kind":kind,"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),
                                    "intrinsic_encoding_zero":None}
                        if kind == "/FontFile":
                            stream = descriptor[kind].get_object()
                            try:
                                glyph, outline = type1_outline(data,int(stream["/Length1"]),int(stream["/Length2"]))
                                embedded["intrinsic_encoding_zero"] = glyph
                                embedded["zero_glyph_outline"] = outline
                            except Exception as exc:
                                embedded["outline_diagnostic_error"] = type(exc).__name__+":"+str(exc)[:180]
                fonts[key] = {"subtype":str(font.get("/Subtype")),
                    "encoding":str(encoding)[:200],"to_unicode_sha256":hashlib.sha256(cmap.encode()).hexdigest(),
                    "font_descriptor_keys":list(descriptor),"embedded":embedded,
                    "character_codes":[ord(c) for c in chunk[:40]]}
            page.extract_text(visitor_text=inspect_glyphs)
            notice("PDF exponent font mapping", fonts)
            start = re.search(r"Table\s*2", text, re.I)
            if start:
                notice("PDF original character table", {"page":index+1,
                    "text":text[start.start():start.start()+2100]})
            notice("PDF original exponent characters", [m[0] for m in
                list(re.finditer(r"\d[,\.]\d\d.{0,14}", text))[:20]])
        match = re.search(r"open access article", text, re.I)
        if match and not rights_reported:
            notice("PDF document rights", {"page":index+1,
                "text":text[max(0,match.start()-100):match.end()+650]})
            rights_reported = True
    layout = extract_layout(pdf)
    for i, match in enumerate(list(re.finditer(r"Table\s*2", layout, re.I))[:4]):
        section = layout[max(0,match.start()-100):match.start()+2600]
        notice(f"PDF native Table 2 candidate {i}", {"text":section})


def verify(record_html: bytes, pdf_bytes: bytes, pdf_reader=PdfReader,
           layout_extractor=extract_layout) -> dict:
    if not isinstance(record_html, bytes) or not 20 < len(record_html) <= MAX_RECORD_BYTES:
        raise ValueError("invalid or oversized institutional record")
    if not isinstance(pdf_bytes, bytes) or not 1000 < len(pdf_bytes) <= MAX_PDF_BYTES:
        raise ValueError("invalid or oversized VOR PDF")
    if not pdf_bytes.startswith(b"%PDF-"):
        raise ValueError("institutional file is not a PDF")

    parser = _RecordParser()
    parser.feed(record_html.decode("utf-8", errors="replace"))
    record_text = _normalized(" ".join(parser.text + parser.links))
    if DOI not in record_text:
        raise ValueError("institutional record does not bind the exact article DOI")
    if "1328508" not in record_text or PDF_HANDLE not in record_text:
        raise ValueError("institutional record does not bind the selected VOR file")
    pdf_digest = hashlib.sha256(pdf_bytes).hexdigest()
    if pdf_digest != EXPECTED_PDF_SHA256:
        raise ValueError("institutional PDF differs from the observed source-byte SHA-256")

    reader = pdf_reader(io.BytesIO(pdf_bytes), strict=True)
    if reader.is_encrypted:
        raise ValueError("VOR PDF is encrypted")
    if not 1 <= len(reader.pages) <= 80:
        raise ValueError("VOR PDF page count is outside bounds")
    extraction_copy, glyph_repairs = recover_math_unicode(reader, pdf_bytes)
    layout = layout_extractor(extraction_copy)
    pdf_text = _normalized(layout)
    required_identity = (DOI, "hexavalent ions insertion", "campanella", "zhu", "girard")
    missing = [term for term in required_identity if term not in pdf_text]
    if missing:
        raise ValueError("PDF article identity is incomplete: " + ",".join(missing))
    if "wiley" not in pdf_text and "chemsuschem" not in pdf_text:
        raise ValueError("PDF does not identify the publisher or journal")

    # The notice is in a two-column page. Plain reading order preserves its
    # sentence; physical layout is reserved for the scientific table cells.
    rights_text = _normalized("\n".join(page.extract_text() or "" for page in reader.pages))
    rights = document_license(record_html, rights_text)
    rights["pdf_notice_extraction"] = "pypdf plain reading order from the original PDF bytes"
    if not any(term in pdf_text for term in ("hot press", "hot-press")) or "56 mpa" not in pdf_text:
        raise ValueError("PDF does not identify hot-press manufacturing conditions")
    mapping = parse_table_layout(layout)

    return {
        "schema_version": "rhombus-0194-unimore-institutional-vor-verification-v2",
        "verification_status": "VERIFIED",
        "source_authenticity_status": "AUTHENTICATED_INSTITUTIONAL_PUBLISHER_VOR",
        "qualifies_0194_original_source": True,
        "doi": DOI,
        "source_route": "INSTITUTIONAL_VERSION_OF_RECORD",
        "record_url": RECORD_URL,
        "pdf_url": PDF_URL,
        "institution_host": "iris.unimore.it",
        "institution": "Universita degli Studi di Modena e Reggio Emilia",
        "record_sha256": hashlib.sha256(record_html).hexdigest(),
        "record_exact_doi_match": True,
        "record_binds_exact_pdf_handle": True,
        "record_identifies_publisher_version": True,
        "license_uri": rights["canonical_uri"],
        "license_evidence": rights,
        "pdf_title_author_doi_match": True,
        "pdf_page_count": len(reader.pages),
        "pdf_byte_count": len(pdf_bytes),
        "pdf_sha256": pdf_digest,
        "pdf_text_extraction": "Poppler pdftotext -layout -enc UTF-8 -nopgbrk; no OCR",
        "unicode_extraction_repairs": glyph_repairs,
        "extraction_copy_sha256": hashlib.sha256(extraction_copy).hexdigest(),
        "pdf_layout_sha256": hashlib.sha256(layout.encode("utf-8")).hexdigest(),
        "table_2_all_18_values_exact_match": True,
        "table_2_condition_count": len(mapping),
        "table_mapping": mapping,
        "independent_publication_count": 1,
        "nominal_series_count": 6,
        "independent_experimental_specimens_verified": 0,
        "single_directly_measured_25C_EIS_label_unattested": True,
        "table_2_conductivity_target_temperature_C": 25,
        "manufacturing_route": "HOT_PRESS_56_MPA",
        "live_wiley_html_verified": False,
        "scientific_GO": False,
        "production_enabled": False,
        "official_OBELiX_TEST_121_read": False,
        "P0_01": "BLOCKED", "P0_02": "BLOCKED", "P0_03": "BLOCKED",
    }


def run(output: Path, inspect=False) -> dict:
    if output.exists():
        raise ValueError("refuse to overwrite prior source receipt")
    record, _, _ = _fetch(RECORD_URL, MAX_RECORD_BYTES, "text/html")
    pdf, content_type, _ = _fetch(PDF_URL, MAX_PDF_BYTES, "application/pdf")
    if "pdf" not in content_type.casefold() and not pdf.startswith(b"%PDF-"):
        raise ValueError("institutional VOR endpoint did not return PDF content")
    if inspect:
        inspect_source(record, pdf)
    receipt = verify(record, pdf)
    version = subprocess.run(["pdftotext", "-v"], check=True, capture_output=True, text=True)
    receipt["pdf_text_extractor_version"] = (version.stderr or version.stdout).splitlines()[0]
    receipt["font_decoder_version"] = __import__("fontTools").__version__
    receipt["verification_execution"] = {
        "github_run_id":os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),
        "source_code_head":os.environ.get("RHOMBUS_HEAD_SHA",os.environ.get("GITHUB_SHA")),
        "checkout_commit":subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip()}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", required=True, type=Path)
    cli.add_argument("--inspect-source", action="store_true")
    args = cli.parse_args()
    try:
        result = run(args.output, args.inspect_source)
    except Exception as exc:
        message=(type(exc).__name__+": "+str(exc)[:700]).replace("%","%25").replace("\r","%0D").replace("\n","%0A")
        print("::error title=0194 source verification failed::"+message,flush=True)
        raise
    packed=json.dumps(result,sort_keys=True,separators=(",",":"),ensure_ascii=True)
    parts=[packed[i:i+1700] for i in range(0,len(packed),1700)]
    if len(parts)>8:raise ValueError("verified receipt exceeds annotation bound")
    for index,part in enumerate(parts):
        message=json.dumps(part).replace("%","%25")
        print(f"::notice title=0194 verified receipt {index+1} of {len(parts)}::{message}",flush=True)
    print("0194_INSTITUTIONAL_VOR_SOURCE_VERIFIED", json.dumps(result, sort_keys=True))
