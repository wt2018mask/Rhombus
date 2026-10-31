"""Instance-local ASE-style event accounting; NOT a scientific runner.

Counts get_property() requests and calculate() entries separately. Does not
load, call, or deserialize a model on installation. Does not intercept bypasses,
subprocess execution or internal torch forwards; counts are self-reported.
"""
from __future__ import annotations

from functools import wraps
from types import MethodType
from typing import Any


class CalculatorInstrumentError(ValueError):
    pass


_MISSING = object()


class _CalculatorHook:
    _MARKER = "_rhombus_0205_meter_hook_v1"

    def __init__(self, calculator: Any, meter: Any):
        self.calculator = calculator
        self.meter = meter
        self._saved: dict[str, Any] = {}
        self._installed = False

    def __enter__(self):
        calc = self.calculator
        d = getattr(calc, "__dict__", None)
        if isinstance(calc, type) or not isinstance(d, dict) or d.get(self._MARKER):
            raise CalculatorInstrumentError("CALCULATOR_NOT_PATCHABLE_OR_ALREADY_PATCHED")
        if any(not callable(getattr(calc, name, None)) for name in ("get_property", "calculate")):
            raise CalculatorInstrumentError("CALCULATOR_METHOD_MISSING")
        self._saved = {name: d.get(name, _MISSING)
                       for name in ("get_property", "calculate", self._MARKER)}
        original_property = calc.get_property
        original_calculate = calc.calculate
        meter = self.meter

        @wraps(original_property)
        def wrapped_property(_self, name, *args, **kwargs):
            try:
                if type(name) is not str:
                    raise CalculatorInstrumentError("PROPERTY_NAME_MUST_BE_STRING")
                kind = {"energy": "energy", "forces": "force"}.get(name)
                if kind is None:
                    raise CalculatorInstrumentError("PROPERTY_OUTSIDE_TIER_A_ACCOUNTING")
                meter.record_call(kind)
                return original_property(name, *args, **kwargs)
            except BaseException:
                meter.mark_calculator_fault()
                raise

        @wraps(original_calculate)
        def wrapped_calculate(_self, *args, **kwargs):
            try:
                meter.record_call("model_calculation")
                return original_calculate(*args, **kwargs)
            except BaseException:
                meter.mark_calculator_fault()
                raise

        try:
            d[self._MARKER] = True
            calc.get_property = MethodType(wrapped_property, calc)
            calc.calculate = MethodType(wrapped_calculate, calc)
        except BaseException:
            self._restore()
            raise
        self._installed = True
        return self

    def _restore(self):
        d = getattr(self.calculator, "__dict__", None)
        if not isinstance(d, dict):
            return
        for name, original in self._saved.items():
            if original is _MISSING:
                d.pop(name, None)
            else:
                d[name] = original

    def __exit__(self, exc_type, exc_value, traceback):
        self._restore()
        self._installed = False
        return False


def instrument_calculator_methods(*, calculator: Any, meter: Any) -> _CalculatorHook:
    """Create a no-execution hook; use inside an explicitly measured phase."""
    if not callable(getattr(meter, "record_call", None)):
        raise CalculatorInstrumentError("METER_RECORD_CALL_MISSING")
    if not callable(getattr(meter, "mark_calculator_fault", None)):
        raise CalculatorInstrumentError("METER_MARK_CALCULATOR_FAULT_MISSING")
    return _CalculatorHook(calculator, meter)
