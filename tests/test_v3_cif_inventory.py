"""Source inventory contract; research structures are not silently relabeled."""
from pathlib import Path
from scripts.benchmark.audit_v3_fixed_rmin import discover_cifs


def test_repository_has_seven_source_cifs_and_two_obelix_train_inputs():
    root=Path(__file__).resolve().parents[1]
    inventory=discover_cifs(root)
    source=[p for group,p in inventory if group=='SOURCE_OR_LITERATURE_CIF']
    obelix=[p for group,p in inventory if group.startswith('OBELIX_')]
    assert len(source)==7
    assert len(obelix)==2
    assert all(path.suffix=='.cif' and path.is_file() for _,path in inventory)
    assert len({path.resolve() for _,path in inventory})==9
