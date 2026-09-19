import numpy as np

from ase.calculators.calculator import Calculator

import rudeus.mlip.p2 as p2


class ZeroCalc(Calculator):
    implemented_properties = ["energy", "free_energy", "forces"]

    def calculate(self, atoms=None, properties=None, system_changes=None):
        super().calculate(atoms, properties, system_changes)
        n = len(atoms)
        self.results = {
            "energy": 0.0,
            "free_energy": 0.0,
            "forces": np.zeros((n, 3)),
        }


class FakeLangevin:
    def __init__(self, atoms, **kwargs):
        self.atoms = atoms
        self._attachments = []

    def attach(self, function, interval=1, *args, **kwargs):
        self._attachments.append((function, int(interval)))

    def run(self, steps):
        # Mirror the relevant ASE observer behavior: initial observers run
        # before the first MD step, then interval observers run after steps.
        if steps <= 0:
            return

        for function, interval in self._attachments:
            if interval == 1:
                function()

        for step in range(1, int(steps) + 1):
            # Construct a deterministic >3 A MIC displacement at sample 10.
            if step == 10:
                self.atoms.positions[0, 0] += 4.0

            for function, interval in self._attachments:
                if step % interval == 0:
                    function()


def test_explosive_step_stops_current_dynamics_run(monkeypatch):
    monkeypatch.setattr(p2, "Langevin", FakeLangevin)

    from pymatgen.core import Lattice, Structure

    structure = Structure(
        Lattice.cubic(10.0),
        ["Li", "Cl"],
        [[0, 0, 0], [0.5, 0.5, 0.5]],
    ).as_dict()

    protocol = dict(p2.P2_PROTOCOL_DEFAULTS)
    protocol["equil_steps"] = 20
    protocol["production_steps"] = 0
    protocol["sample_interval_steps"] = 10

    record = p2.run_nvt(
        structure,
        ZeroCalc(),
        protocol,
        seed=7,
        batch_id="abort-test",
    )

    assert record["completed"] is False
    assert record["termination_note"] == "explosive-step"
    assert record["production_steps"] == 0

    # The initial sample and the first explosive sample are retained, but
    # the second half of the 20-step equilibration must not execute.
    assert [f["md_step"] for f in record["frames"]] == [0, 10]
    assert record["frames"][-1]["step_jump_A"] > 3.0
