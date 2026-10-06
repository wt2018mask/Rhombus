"""Canonical visible structure-hash semantics for B4 blind execution."""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from rudeus.science.contracts import Record, require_hash


EXECUTION_STRUCTURE_BINDING_VERSION = "known-material-b4-execution-structure-binding-v1"


@dataclass(frozen=True, kw_only=True)
class ExecutionStructureComponent(Record):
    label: str
    structure_hash: str
    weight_numerator: int | None = None
    weight_denominator: int | None = None

    def validate(self):
        super().validate()
        if not self.label:
            raise ValueError("execution structure component requires label")
        require_hash(self.structure_hash)
        if (self.weight_numerator is None) != (self.weight_denominator is None):
            raise ValueError("execution structure weight requires numerator and denominator")
        if self.weight_numerator is not None:
            if self.weight_numerator <= 0 or self.weight_denominator <= 0:
                raise ValueError("execution structure weights must be positive")

    @property
    def weight(self) -> Fraction | None:
        if self.weight_numerator is None:
            return None
        return Fraction(self.weight_numerator, self.weight_denominator)


@dataclass(frozen=True, kw_only=True)
class ExecutionStructureBinding(Record):
    binding_version: str
    mode: str
    components: tuple[ExecutionStructureComponent, ...]
    weighting_assumption: str | None = None

    def validate(self):
        super().validate()
        if self.binding_version != EXECUTION_STRUCTURE_BINDING_VERSION:
            raise ValueError("unsupported execution-structure binding version")
        if self.mode not in {"DIRECT", "PHASE_SET", "ENSEMBLE"}:
            raise ValueError("unsupported execution-structure binding mode")
        if not self.components:
            raise ValueError("execution-structure binding requires components")
        labels = tuple(item.label for item in self.components)
        if len(set(labels)) != len(labels):
            raise ValueError("execution-structure component labels must be unique")
        if labels != tuple(sorted(labels)):
            raise ValueError("execution-structure components must be sorted by label")

        weights = tuple(item.weight for item in self.components)
        if self.mode == "DIRECT":
            if len(self.components) != 1 or any(weight is not None for weight in weights):
                raise ValueError("DIRECT binding requires one unweighted component")
            if self.weighting_assumption is not None:
                raise ValueError("DIRECT binding cannot declare weighting assumption")
        elif self.mode == "PHASE_SET":
            if len(self.components) < 2 or any(weight is not None for weight in weights):
                raise ValueError("PHASE_SET requires multiple unweighted components")
            if self.weighting_assumption is not None:
                raise ValueError("PHASE_SET cannot declare weighting assumption")
        else:
            if len(self.components) < 2 or any(weight is None for weight in weights):
                raise ValueError("ENSEMBLE requires multiple weighted components")
            if sum(weights, Fraction(0, 1)) != 1:
                raise ValueError("ENSEMBLE component weights must sum exactly to one")
            if not self.weighting_assumption:
                raise ValueError("ENSEMBLE requires explicit weighting assumption")

    @property
    def visible_structure_hash(self) -> str:
        if self.mode == "DIRECT":
            return self.components[0].structure_hash
        return self.content_hash
