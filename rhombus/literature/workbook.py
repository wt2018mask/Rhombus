"""Offline, fixed-source MOESM5 inspection; no Excel execution or label promotion."""
from __future__ import annotations

import argparse
import collections
import hashlib
import io
import json
import math
import re
import struct
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from . import supplement as source

ARCHIVE_SHA256 = '9d0965de5b45ae0185046a855fb3774596e670128a9a870c71224032a9fa53ed'
ARCHIVE_BYTES = 51_596_476
FILENAME = '41467_2026_74887_MOESM5_ESM.xlsb'
WORKBOOK_SHA256 = '6c084f536b2e02b902319f9570c9a9ffc7c9a40fbbdaa4c9dee3061d6da905f5'
WORKBOOK_BYTES = 9_068_841
MAX_WORKBOOK_BYTES = 16 * 1024 * 1024
RELEVANT = {'Fig 3a EIS', 'Fig3b DRT', 'Fig3c activation energy',
            'Fig2a SPS sintering ', 'FigS1 LLZO density', 'FigS3c SPS sintering'}


def cell_address(row, column):
    letters = ''
    while column:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters + str(row)


def verify_workbook_member(archive, jats):
    """Authenticate retained bytes, JATS MOESM5 membership and both ZIP layers."""
    source.authenticate_article(jats)
    root = ET.fromstring(jats)
    media = root.findall(".//supplementary-material[@id='MOESM5']/media")
    if (len(media) != 1 or media[0].get('{http://www.w3.org/1999/xlink}href') != FILENAME
            or ''.join(media[0].itertext()).strip() != 'Source data'):
        raise ValueError('MOESM5 JATS membership mismatch')
    archive = Path(archive)
    if (archive.stat().st_size != ARCHIVE_BYTES or
            hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256):
        raise ValueError('original archive size/hash mismatch')
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if len(members) > 100 or sum(x.file_size for x in members) > 128 * 1024 * 1024:
            raise ValueError('archive expansion budget exceeded')
        matches = [m for m in members if m.filename == FILENAME]
        if len(matches) != 1 or matches[0].file_size != WORKBOOK_BYTES:
            raise ValueError('missing/ambiguous exact MOESM5 member')
        if bundle.testzip() is not None:
            raise ValueError('archive CRC failure')
        raw = bundle.read(matches[0])
    if len(raw) > MAX_WORKBOOK_BYTES or hashlib.sha256(raw).hexdigest() != WORKBOOK_SHA256:
        raise ValueError('MOESM5 size/hash mismatch')
    with zipfile.ZipFile(io.BytesIO(raw)) as book:
        members = book.infolist()
        if len(members) > 200 or sum(x.file_size for x in members) > 64 * 1024 * 1024:
            raise ValueError('workbook expansion budget exceeded')
        if book.testzip() is not None:
            raise ValueError('workbook CRC failure')
    return raw


def _records(raw):
    """BIFF12 headers, preserving record payloads including formula tokens.

    IDs use the pyxlsb representation (continuation bits retained); length uses
    7-bit groups. No expressions, external connections or macros are evaluated.
    """
    stream = io.BytesIO(raw)
    while stream.tell() < len(raw):
        offset = stream.tell()
        record_id = length = 0
        for i in range(4):
            byte = stream.read(1)
            if not byte: raise ValueError('truncated BIFF12 record ID')
            byte = byte[0]; record_id |= byte << (8*i)
            if not byte & 128: break
        else: raise ValueError('excessive BIFF12 record ID')
        for i in range(4):
            byte = stream.read(1)
            if not byte: raise ValueError('truncated BIFF12 record length')
            byte = byte[0]; length |= (byte & 127) << (7*i)
            if not byte & 128: break
        else: raise ValueError('excessive BIFF12 record length')
        data = stream.read(length)
        if len(data) != length: raise ValueError('truncated BIFF12 record body')
        yield record_id, offset, data


def inspect_workbook(raw):
    """Scan every nonempty cell, all formula records, headers and package parts.

    The canonical cell digest is SHA256 over ordered JSON [A1-address,value]
    lines, UTF-8 ensure_ascii=False, compact separators. The raw file is pinned.
    """
    from pyxlsb import open_workbook
    if len(raw) > MAX_WORKBOOK_BYTES or hashlib.sha256(raw).hexdigest() != WORKBOOK_SHA256:
        raise ValueError('unreviewed workbook bytes')
    inventories, selected = [], {}
    with zipfile.ZipFile(io.BytesIO(raw)) as package, open_workbook(io.BytesIO(raw)) as book:
        part_hashes = {m.filename: hashlib.sha256(package.read(m)).hexdigest()
                       for m in package.infolist()}
        defined_names = []
        for kind, offset, data in _records(package.read('xl/workbook.bin')):
            if kind == 39:  # BrtName: keep the original binary expression, not a guessed formula.
                count = struct.unpack_from('<I', data, 9)[0]
                defined_names.append({'name':data[13:13+2*count].decode('utf-16le'),
                                      'offset':offset,'raw_record_hex':data.hex()})
        for index, name in enumerate(book.sheets, 1):
            part = f'xl/worksheets/sheet{index}.bin'
            formulas, counts, row = [], collections.Counter(), None
            for kind, offset, data in _records(package.read(part)):
                counts[kind] += 1
                if kind == 0: row = struct.unpack_from('<I',data)[0] + 1
                if kind in (8,9,10,11):
                    formulas.append({'cell':cell_address(row,struct.unpack_from('<I',data)[0]+1),
                                     'record_type':kind,'offset':offset,'raw_record_hex':data.hex()})
            digest = hashlib.sha256(); count = 0; labels = {}; headers = {}; cells = {}
            with book.get_sheet(index) as sheet:
                dimension = sheet.dimension._asdict()
                if dimension['h'] * dimension['w'] > 5_000_000:
                    raise ValueError('worksheet cell budget exceeded')
                for values in sheet.rows(sparse=True):
                    for cell in values:
                        if cell.v is None: continue
                        address = cell_address(cell.r+1,cell.c+1); count += 1
                        digest.update((json.dumps([address,cell.v],ensure_ascii=False,
                                                   separators=(',',':'),allow_nan=False)+'\n').encode())
                        if name in RELEVANT: cells[address] = cell.v
                        if cell.r < 3: headers[address] = cell.v
                        if isinstance(cell.v,str):
                            try: float(cell.v)
                            except ValueError:
                                if cell.v not in labels:
                                    labels[cell.v] = {'text':cell.v,'first_cell':address,'count':0}
                                labels[cell.v]['count'] += 1
            inventories.append({'sheet':name,'part':part,'dimension':dimension,
                                'nonempty_cells':count,'cells_sha256':digest.hexdigest(),
                                'part_sha256':part_hashes[part], 'headers':headers,
                                'annotations_and_labels':list(labels.values()),
                                'cell_formula_records':formulas,'record_counts':dict(counts)})
            if name in RELEVANT: selected[name] = cells
    return {'workbook_sha256':WORKBOOK_SHA256,'sheets':inventories,
            'package_part_sha256':part_hashes,'defined_names':defined_names,
            'relevant_cells':selected, 'external_refresh_executed':False}


def extract_eis_evidence(cells):
    """Bind original measured/fitted plot pairs by exact source header/cell keys."""
    rows = []
    for start, sample in [(1,'S-LLZO'),(5,'SF-LLZO'),(9,'Annealed SF-LLZO')]:
        if cells.get(cell_address(1,start)) != sample:
            raise ValueError('incorrect EIS sample mapping')
        for delta, role in [(0,'tested'),(2,'Fitted')]:
            col = start + delta
            if (cells.get(cell_address(2,col)) != role
                    or cells.get(cell_address(3,col)) != 'Z’ (KΩ)'
                    or cells.get(cell_address(3,col+1)) != '-Z’’ (KΩ)'):
                raise ValueError('EIS role/unit header mismatch')
            for r in range(4,211):
                addresses = [cell_address(r,c) for c in (col,col+1)]
                values = [cells.get(c) for c in addresses]
                if all(v in (None,'--') for v in values): continue
                try: numeric = [float(v) for v in values]
                except (ValueError,TypeError): raise ValueError('incomplete EIS coordinate pair')
                if not all(math.isfinite(v) for v in numeric): raise ValueError('nonfinite EIS coordinate')
                rows.append({'doi':source.DOI,'source_sha256':WORKBOOK_SHA256,
                             'sheet':'Fig 3a EIS','cells':addresses,'sample':sample,
                             'series_role':role,'source_values':values,'unit':'KΩ',
                             'observable_type':'COMPLEX_IMPEDANCE_COORDINATES',
                             'specimen_id':None,'measurement_temperature_C':25,
                             'temperature_evidence':'JATS Par17/Fig.3a caption, Par36',
                             'geometry':None,'resistance_component':None,
                             'conductivity_S_cm':None,
                             'qualification':'EXPLORATORY' if role=='tested' else 'REJECTED',
                             'reasons':['NO_SPECIMEN_GEOMETRY_JOIN','NO_COMPONENT_TO_TOTAL_JOIN',
                                        'NO_SPECIMEN_ID_OR_REPLICATE_JOIN',
                                        'WORKBOOK_KOHM_VS_FIGURE_KOHM_CM_UNRESOLVED'] if role=='tested'
                                       else ['FITTED_CURVE_NOT_AN_INDEPENDENT_MEASUREMENT']})
    return rows


def assess_conductivity_join(row):
    """Fixed-source admission: unknown geometry/components cannot yield labels.

    Even added plausible geometry, renamed specimens or claimed replicates cannot
    override missing original-source attestations. This DOI review admits none.
    """
    if (row.get('source_sha256') != WORKBOOK_SHA256 or row.get('sheet') != 'Fig 3a EIS'
            or row.get('observable_type') != 'COMPLEX_IMPEDANCE_COORDINATES'
            or row.get('unit') != 'KΩ' or row.get('series_role') != 'tested'):
        return {'qualification':'REJECTED','reason':'UNSUPPORTED_SOURCE_OBSERVABLE_OR_UNITS'}
    if any(row.get(key) is not None for key in ('specimen_id','geometry','resistance_component',
                                               'replicate_id','conductivity_S_cm')):
        return {'qualification':'REJECTED','reason':'UNSUPPORTED_SPECIMEN_COMPONENT_GEOMETRY_OR_REPLICATE_MAPPING'}
    return {'qualification':'EXPLORATORY','reason':'ORIGINAL_CONDUCTIVITY_JOIN_UNRESOLVED'}


def verify_eis_rows(rows, original_cells):
    """Reject relabeling or value swaps against the original keyed cell extract."""
    expected = extract_eis_evidence(original_cells)
    if rows != expected:
        raise ValueError('EIS evidence differs from original keyed workbook cells')
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,required=True)
    parser.add_argument('--jats',type=Path,required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args = parser.parse_args()
    raw = verify_workbook_member(args.archive,args.jats.read_bytes())
    inventory = inspect_workbook(raw)
    evidence = extract_eis_evidence(inventory['relevant_cells']['Fig 3a EIS'])
    args.output_dir.mkdir()
    for name, data in [('inventory.json',inventory),('eis-evidence.json',evidence)]:
        (args.output_dir/name).write_text(json.dumps(data,indent=2,ensure_ascii=False,allow_nan=False)+'\n')
    print(json.dumps({'sheets':len(inventory['sheets']),'eis_coordinate_pairs':len(evidence),
                      'new_strict_qualified_doi_groups':0,'new_strict_manufacturing_comparisons':0,
                      'scientific_verdict':'INCONCLUSIVE','network_requests':0}))


if __name__ == '__main__':
    main()
