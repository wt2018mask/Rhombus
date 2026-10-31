"""Offline contract tests; the optional ASE test uses a zero-energy dummy."""
from __future__ import annotations

import pytest
from rhombus.benchmark.tier_a_calculator_hook import (
    CalculatorInstrumentError, instrument_calculator_methods,
)
from rhombus.benchmark.tier_a_local_meter import LocalProcessMeter
from tests.test_tier_a_budget_contract_0204 import ready_draft


class FakeCalculator:
    def __init__(self):
        self.cache = None
        self.evaluations = 0

    def get_property(self, name):
        if self.cache is None:
            self.calculate()
        return self.cache[name]

    def calculate(self):
        self.evaluations += 1
        self.cache = {"energy": 0.0, "forces": [[0, 0, 0]]}


def _meter():
    draft = ready_draft()
    return LocalProcessMeter(
        draft, arm_id=draft["model_arms"][0]["arm_id"],
        edge_id=draft["edges"][0]["edge_id"],
    )


def test_calculate_count_is_not_property_request_count():
    meter, calc = _meter(), FakeCalculator()
    with meter.phase("endpoint_relax"):
        with instrument_calculator_methods(calculator=calc, meter=meter):
            assert calc.get_property("energy") == 0.0
            assert calc.get_property("forces") == [[0, 0, 0]]
            assert calc.get_property("energy") == 0.0
    result = meter.finish(status="NONCONVERGED")
    counts = result["receipt"]["total"]
    assert (counts["energy_requests"], counts["force_requests"],
            counts["model_evaluations"]) == (2, 1, 1)
    assert calc.evaluations == 1
    assert "get_property" not in calc.__dict__
    assert "calculate" not in calc.__dict__
    assert result["model_executed_by_meter"] is False


def test_swallowed_unsupported_property_does_not_become_success():
    meter, calc = _meter(), FakeCalculator()
    with meter.phase("endpoint_relax"):
        with instrument_calculator_methods(calculator=calc, meter=meter):
            with pytest.raises(CalculatorInstrumentError, match="PROPERTY_OUTSIDE"):
                calc.get_property("stress")
    with pytest.raises(ValueError, match="CANNOT_BECOME_SUCCESS"):
        meter.finish(status="CONVERGED", endpoint_max_force=0, neb_max_force=0)


def test_event_limit_failure_does_not_become_success(monkeypatch):
    import rhombus.benchmark.tier_a_local_meter as module
    monkeypatch.setattr(module, "MAX_LOCAL_EVENTS", 1)
    meter, calc = _meter(), FakeCalculator()
    with meter.phase("neb_optimize"):
        with instrument_calculator_methods(calculator=calc, meter=meter):
            with pytest.raises(ValueError, match="LOCAL_EVENT_BUDGET_EXCEEDED"):
                calc.get_property("energy")
    with pytest.raises(ValueError, match="CANNOT_BECOME_SUCCESS"):
        meter.finish(status="CONVERGED", endpoint_max_force=0, neb_max_force=0)


def test_ase_calculator_real_interface_no_mlip_execution():
    ase = pytest.importorskip("ase")
    from ase.calculators.calculator import Calculator, all_changes

    class InertCalculator(Calculator):
        implemented_properties = ["energy", "forces"]

        def __init__(self):
            super().__init__()
            self.count = 0

        def calculate(self, atoms=None, properties=("energy",), system_changes=all_changes):
            super().calculate(atoms, properties, system_changes)
            self.count += 1
            self.results["energy"] = 0.0
            self.results["forces"] = [[0.0, 0.0, 0.0] for _ in atoms]

    atoms = ase.Atoms("Li", positions=[[0, 0, 0]], cell=[5, 5, 5], pbc=True)
    atoms.calc = InertCalculator()
    meter = _meter()
    with meter.phase("endpoint_relax"):
        with instrument_calculator_methods(calculator=atoms.calc, meter=meter):
            assert atoms.get_potential_energy() == 0.0
            assert atoms.get_forces().shape == (1, 3)
            assert atoms.get_potential_energy() == 0.0
    result = meter.finish(status="NONCONVERGED")
    assert atoms.calc.count == 1
    assert result["receipt"]["total"]["model_evaluations"] == 1
