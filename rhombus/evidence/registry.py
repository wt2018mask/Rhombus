"""Builders for typed v2 identities from frozen legacy registries.

These helpers only bind identities when exact keys/hashes agree. Missing or
ambiguous registry information remains unresolved rather than inferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .identity import ModelIdentity, ModelLineage, ProtocolIdentity


@dataclass(frozen=True)
class LegacyCompatibilityContext:
    models_by_checkpoint_sha256: Mapping[str, ModelIdentity]
    lineages_by_model_id: Mapping[str, ModelLineage]
    protocols_by_id: Mapping[str, ProtocolIdentity]

    @classmethod
    def from_records(
        cls,
        *,
        model_domain_registry: Mapping[str, Any] | None = None,
        mlip_exposure_ledger: Mapping[str, Any] | None = None,
        transport_extension_authorization: Mapping[str, Any] | None = None,
    ) -> "LegacyCompatibilityContext":
        models: dict[str, ModelIdentity] = {}
        lineages: dict[str, ModelLineage] = {}
        protocols: dict[str, ProtocolIdentity] = {}

        if model_domain_registry is not None:
            entries = model_domain_registry.get("entries", [])
            if not isinstance(entries, list):
                raise ValueError("model domain registry entries must be a list")
            for entry in entries:
                if not isinstance(entry, Mapping):
                    raise ValueError("model domain registry entry must be an object")
                model_id = str(entry.get("model_id", "")).strip()
                checkpoint = str(entry.get("checkpoint_sha256", "")).strip()
                if not model_id or not checkpoint:
                    raise ValueError(
                        "model registry entries require model_id and checkpoint_sha256"
                    )
                identity = ModelIdentity(
                    model_id=model_id,
                    name=model_id,
                    checkpoint_sha256=checkpoint,
                    framework=(
                        str(entry["package_constraint"])
                        if entry.get("package_constraint")
                        else None
                    ),
                )
                previous = models.get(checkpoint)
                if previous is not None and previous != identity:
                    raise ValueError(
                        f"checkpoint {checkpoint} maps to conflicting model identities"
                    )
                models[checkpoint] = identity

        if mlip_exposure_ledger is not None:
            model_id = str(mlip_exposure_ledger.get("model_id", "")).strip()
            if not model_id:
                raise ValueError("MLIP exposure ledger requires model_id")
            training = mlip_exposure_ledger.get("training_datasets", [])
            if not isinstance(training, list):
                raise ValueError("training_datasets must be a list")
            constraints = mlip_exposure_ledger.get("interpretation_constraints", [])
            if not isinstance(constraints, list):
                raise ValueError("interpretation_constraints must be a list")
            lineages[model_id] = ModelLineage(
                model_id=model_id,
                training_source_ids=tuple(str(item) for item in training),
                notes=tuple(str(item) for item in constraints),
            )

        if transport_extension_authorization is not None:
            transition = transport_extension_authorization.get("transition")
            if not isinstance(transition, Mapping):
                raise ValueError(
                    "transport extension authorization requires transition object"
                )
            protocol_hash = str(transition.get("protocol_hash", "")).strip()
            protocol_version = str(
                transition.get("protocol_version", "")
            ).strip()
            capability = str(
                transport_extension_authorization.get("capability", "")
            ).strip()
            if not protocol_hash or not protocol_version or not capability:
                raise ValueError(
                    "transport extension authorization must identify capability, "
                    "protocol_hash, and protocol_version"
                )
            protocols[protocol_hash] = ProtocolIdentity(
                protocol_id=protocol_hash,
                capability=capability,
                version=protocol_version,
                config_hash=protocol_hash,
            )

        return cls(
            models_by_checkpoint_sha256=models,
            lineages_by_model_id=lineages,
            protocols_by_id=protocols,
        )

    def resolve_model(
        self, checkpoint_sha256: str | None
    ) -> tuple[ModelIdentity | None, ModelLineage | None]:
        if checkpoint_sha256 is None:
            return None, None
        identity = self.models_by_checkpoint_sha256.get(checkpoint_sha256)
        if identity is None:
            return None, None
        return identity, self.lineages_by_model_id.get(identity.model_id)

    def resolve_protocol(self, protocol_id: str | None) -> ProtocolIdentity | None:
        if protocol_id is None:
            return None
        return self.protocols_by_id.get(protocol_id)
