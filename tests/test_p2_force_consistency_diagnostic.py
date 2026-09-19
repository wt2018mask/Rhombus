from rudeus.mlip.p2_force_consistency_diagnostic import _force_metrics


def test_force_metrics_identical():
    f = [[1.0, 0.0, 0.0], [0.0, 2.0, 0.0]]
    result = _force_metrics(f, f)
    assert result["max_abs_force_delta_eV_A"] == 0.0
    assert result["rms_force_delta_eV_A"] == 0.0
    assert result["max_relative_force_delta"] == 0.0


def test_force_metrics_reports_max_delta_atom():
    f32 = [[1.0, 0.0, 0.0], [0.0, 2.0, 0.0]]
    f64 = [[1.1, 0.0, 0.0], [0.0, 2.5, 0.0]]
    result = _force_metrics(f32, f64)
    assert result["max_delta_atom_index"] == 1
    assert result["max_abs_force_delta_eV_A"] == 0.5
    assert result["max_force_f32_atom_index"] == 1
    assert result["max_force_f64_atom_index"] == 1
