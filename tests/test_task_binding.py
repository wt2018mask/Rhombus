"""Adversarial full-TaskSpec binding through the real publication path."""
import copy
from dataclasses import replace

import pytest

from rudeus.execution.contracts import TaskSpec, ExecutionError
from rudeus.science.contracts import digest
from rudeus.science.evidence import EvidenceStore, validate_request
from tests.test_evidence import fixture


@pytest.mark.parametrize("field", ["provenance", "resource_requirements", "retry_policy"])
@pytest.mark.parametrize("pair", ["AA", "AB", "BA"])
def test_full_task_binding_rejects_same_id_substitution(tmp_path, field, pair):
    request, _ = fixture(tmp_path/"source")
    a = replace(TaskSpec.from_dict(request["task"]), provenance={"evidence_hash": digest("A")})
    b = replace(a, **{field: {"evidence_hash": digest("B")} if field == "provenance" else {"changed": True}})
    assert a.task_id == b.task_id
    assert a.content_hash != b.content_hash
    tasks = {"A": a, "B": b}
    request["task"] = tasks[pair[1]].to_dict()
    request["attempts"][0]["task_content_hash"] = tasks[pair[0]].content_hash
    store = EvidenceStore(tmp_path/"archive")
    reader = lambda manifest: (tmp_path/"source"/manifest.durable_locator).read_bytes()
    if pair == "AA":
        validate_request(request, reader)
        manifest = store.publish(request, source_root=tmp_path/"source")
        assert store.verify(manifest.logical_hash)["provenance"]["task"] == a.to_dict()
        reordered = copy.deepcopy(request)
        reordered["task"] = dict(reversed(list(request["task"].items())))
        assert store.publish(reordered, source_root=tmp_path/"source") == manifest
    else:
        for operation in (lambda: validate_request(request, reader),
                          lambda: store.publish(request, source_root=tmp_path/"source")):
            with pytest.raises(ExecutionError, match="full TaskSpec") as failure:
                operation()
            assert failure.value.failure_class.value == "INTEGRITY"
        assert not list(store.root.rglob("*"))


@pytest.mark.parametrize("binding", [None, "absent", "invalid"])
def test_missing_or_invalid_binding_cannot_publish(tmp_path, binding):
    request, _ = fixture(tmp_path/"source")
    if binding == "absent":
        del request["attempts"][0]["task_content_hash"]
    else:
        request["attempts"][0]["task_content_hash"] = binding
    store = EvidenceStore(tmp_path/"archive")
    with pytest.raises(ExecutionError) as failure:
        store.publish(request, source_root=tmp_path/"source")
    assert failure.value.failure_class.value == "INTEGRITY"
    assert not list(store.root.rglob("*"))
