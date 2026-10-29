import importlib.util
from pathlib import Path
import pytest

path = Path(__file__).parents[1] / 'scripts/diagnostics/priority3_audit.py'
spec = importlib.util.spec_from_file_location('priority3_audit', path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_metrics_and_degenerate_auc():
    records = [{'fixed': a, 'mean_li_displacement_A': b}
               for a, b in [(1., .1), (2., .3), (3., 1.)]]
    result = mod.evaluate(records, 'fixed')
    assert result['rho'] == pytest.approx(1.)
    assert result['auc'] == pytest.approx(1.)
    assert mod.evaluate(records[:2], 'fixed')['auc'] is None
