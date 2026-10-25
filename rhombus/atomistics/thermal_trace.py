"""Versioned raw MD measurements and no-model numerical verification.

Digests establish byte identity, not provider authenticity. A trusted host must
pin the binding and digest; a receipt supplied by the producer is insufficient.
NVT mechanical energy is not a conserved quantity. No scientific gate changes.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

VERSION = "rhombus-thermal-trace-v1"
MAX_BYTES = 16 * 1024 * 1024
UNITS = {"time": "fs", "temperature": "K", "energy": "eV",
         "volume": "angstrom^3", "force": "eV/angstrom", "pressure": "GPa"}
IDENTITIES = {"task_id", "candidate_id", "source_sha256", "relaxed_structure_sha256",
              "model_sha256", "protocol_sha256", "source_commit", "runtime"}


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


def build_thermal_trace(record, binding, protocol):
    """Serialize measurements, never backfill old kinetic/total energies."""
    if record.get("thermal_trace_version") != VERSION:
        raise ValueError("original measured kinetic evidence is required")
    rows = []
    for f in record["frames"]:
        row = {"md_step": f["md_step"], "time_fs": f["md_step"] * record["timestep_fs"],
                     "phase": f["phase"], "temperature_K": f["temperature_K"],
                     "potential_energy_eV": f["energy_ev"],
                     "kinetic_energy_eV": f["kinetic_energy_eV"],
                     "mechanical_energy_eV": f["mechanical_energy_eV"],
                     "volume_A3": f["volume_A3"], "max_force_eV_A": f["max_force_ev_A"],
                     "pressure_GPa": f["pressure_GPa"]}
        # JSON has no NaN/Inf. Preserve their occurrence explicitly; null
        # is missing/invalid evidence, never a substituted measured value.
        invalid = [key for key, value in row.items()
                   if isinstance(value, (float, np.floating)) and not np.isfinite(value)]
        for key in invalid:
            row[key] = None
        row["invalid_measurements"] = invalid
        rows.append(row)
    return {"schema_version": VERSION, "units": UNITS, "binding": binding,
            "atom_count": len(record["species"]), "seed": record["seed"],
            "protocol": protocol, "thermostat_heat_eV": None,
            "thermostat_heat_status": "NOT_MEASURED",
            "termination": {"completed": record["completed"], "note": record["termination_note"],
                            "actual_completed_steps": record["actual_completed_steps"],
                            "numerical_abort": record.get("numerical_abort")}, "samples": rows}


def write_thermal_trace(directory, trace):
    """Exclusive content-addressed write; non-finite failure data stays in logs."""
    raw = canonical_bytes(trace)
    if len(raw) > MAX_BYTES:
        raise ValueError("thermal trace output limit exceeded")
    identity = sha256(raw)
    path = Path(directory) / (identity + ".thermal.json")
    with path.open("xb") as out:
        out.write(raw)
    if sha256(path.read_bytes()) != identity:
        raise ValueError("thermal trace read-back mismatch")
    return {"path": path.name, "sha256": identity, "size_bytes": len(raw)}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_thermal_trace(path, *, expected_sha256, expected_binding, expected_protocol):
    """Recompute diagnostics without ASE, torch or MACE. Never qualify physics.

    Incomplete/aborted records can be authenticated but cannot be COMPLETE.
    Missing scheduled samples, including a truncated complete trace, are errors.
    """
    path = Path(path)
    _require(not path.is_symlink() and path.stat().st_size <= MAX_BYTES, "unsafe trace path/size")
    raw = path.read_bytes()
    _require(sha256(raw) == expected_sha256, "thermal artifact digest mismatch")
    trace = json.loads(raw)
    _require(canonical_bytes(trace) == raw, "noncanonical thermal artifact")
    _require(trace.get("schema_version") == VERSION and trace.get("units") == UNITS, "trace version/units mismatch")
    binding = trace["binding"]
    _require(set(binding) == IDENTITIES and binding == expected_binding, "thermal ancestry mismatch")
    _require(trace["protocol"] == expected_protocol, "thermal protocol mismatch")
    _require(trace["thermostat_heat_eV"] is None and trace["thermostat_heat_status"] == "NOT_MEASURED", "unmeasured thermostat heat")
    p = trace["protocol"]
    dt, interval, equil, prod = (p[k] for k in ("timestep_fs", "sample_interval_steps", "equil_steps", "production_steps"))
    _require(isinstance(dt, (float, int)) and not isinstance(dt, bool) and np.isfinite(dt) and dt > 0, "invalid timestep")
    _require(all(type(n) is int and n >= 0 for n in (interval, equil, prod)) and interval > 0, "invalid step schedule")
    _require(p.get("thermostat") == "langevin", "unsupported thermal ensemble")
    _require(type(trace["seed"]) is int and trace["seed"] == p["base_seed"], "seed mismatch")
    term = trace["termination"]
    end = term["actual_completed_steps"]
    _require(type(end) is int and 0 <= end <= equil + prod, "invalid completed step")
    _require(type(term["completed"]) is bool, "invalid completion flag")
    if term["completed"]:
        _require(end == equil + prod and term["note"] is None and term["numerical_abort"] is None, "false complete termination")
    else:
        _require(bool(term["note"]), "partial termination needs a reason")
    rows = trace["samples"]
    steps = [r["md_step"] for r in rows]
    _require(all(type(n) is int for n in steps), "noninteger sample steps")
    expected_steps = list(range(0, end + 1, interval))
    # At least the last scheduled sample can be absent if a hook aborts
    # before sampling or the sampler itself failed. Never hide that gap.
    complete_sampling = steps == expected_steps
    if term["completed"]:
        _require(complete_sampling, "missing/duplicate/out-of-order/truncated samples")
    else:
        _require(steps == expected_steps[:len(steps)] and len(steps) >= len(expected_steps) - 1,
                 "invalid partial sample sequence")
    n_atoms = trace["atom_count"]
    _require(type(n_atoms) is int and n_atoms > 0, "invalid atom count")
    numeric = ("temperature_K", "potential_energy_eV", "kinetic_energy_eV", "mechanical_energy_eV",
               "volume_A3", "max_force_eV_A", "time_fs")
    for r in rows:
        _require(r["invalid_measurements"] == [], "non-finite measured sample retained; metrics rejected")
        _require(all(type(r[k]) in (int, float) and np.isfinite(r[k]) for k in numeric), "non-finite measurement")
        _require(r["pressure_GPa"] is None or (type(r["pressure_GPa"]) in (int, float) and np.isfinite(r["pressure_GPa"])), "invalid pressure")
        _require(r["phase"] == ("equil" if r["md_step"] <= equil else "production"), "phase/step mismatch")
        _require(np.isclose(r["time_fs"], r["md_step"] * dt, rtol=0, atol=1e-10), "physical timestamp mismatch")
        _require(r["temperature_K"] >= 0 and r["kinetic_energy_eV"] >= 0 and r["volume_A3"] > 0 and r["max_force_eV_A"] >= 0, "invalid measurement range")
        _require(np.isclose(r["mechanical_energy_eV"], r["potential_energy_eV"] + r["kinetic_energy_eV"], rtol=1e-12, atol=1e-9), "mechanical energy mismatch")
    production = [r for r in rows if r["phase"] == "production"]
    if not production:
        return {"operational_status": "PARTIAL", "sample_count": len(rows), "production_sample_count": 0,
                "sampling_complete": complete_sampling, "scientific_verdict": "INDETERMINATE"}
    times = np.array([r["time_fs"] for r in production]) / 1000
    temps = np.array([r["temperature_K"] for r in production])
    def trend(key, axis=times):
        return float(np.polyfit(axis - axis[0], [r[key] / n_atoms for r in production], 1)[0]) if len(production) >= 3 else None
    potentials = np.array([r["potential_energy_eV"] for r in production]) / n_atoms
    pressures = [r["pressure_GPa"] for r in production if r["pressure_GPa"] is not None]
    return {"operational_status": "COMPLETE" if term["completed"] else "PARTIAL",
            "sample_count": len(rows), "production_sample_count": len(production),
            "sampling_complete": complete_sampling, "production_time_ps": times.tolist(),
            "temp_mean_K": float(temps.mean()), "temp_std_K": float(temps.std(ddof=0)),
            "energy_mean_ev_per_atom": float(potentials.mean()),
            "energy_drift_ev_per_ps_per_atom": trend("potential_energy_eV"),
            "legacy_index_drift_ev_per_ps_per_atom": trend("potential_energy_eV", np.arange(len(production)) * interval * dt / 1000),
            "kinetic_energy_mean_eV_per_atom": float(np.mean([r["kinetic_energy_eV"] / n_atoms for r in production])),
            "mechanical_energy_trend_eV_per_ps_per_atom": trend("mechanical_energy_eV"),
            "mechanical_energy_span_eV_per_atom": float(np.ptp([r["mechanical_energy_eV"] / n_atoms for r in production])),
            "pressure_mean_GPa": float(np.mean(pressures)) if pressures else None,
            "pressure_std_GPa": float(np.std(pressures)) if pressures else None,
            "temperature_half_mean_difference_K": float(temps[len(temps)//2:].mean() - temps[:len(temps)//2].mean()) if len(temps) >= 4 else None,
            "interpretation": "NVT potential/mechanical energy trends are not conserved-energy or physical-instability verdicts",
            "stationarity": "NOT_ESTABLISHED", "transport_eligibility": "NOT_ESTABLISHED",
            "scientific_verdict": "INDETERMINATE", "provider_authenticity": "NOT_ESTABLISHED_BY_DIGEST"}
