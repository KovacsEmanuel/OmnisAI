import json
from uuid import uuid4

import pytest

from omnis.modules.instance.schemas import ControlRequest
from omnis.modules.runs.model_test_models import ModelTestControl, ModelTestRequest


def test_complete_new_command_frames_are_bounded() -> None:
    identity, command = str(uuid4()), str(uuid4())
    maximum = 9223372036854775807
    for payload in (
        {"action": "read", "operation_id": identity},
        {
            "action": "start",
            "operation_id": identity,
            "expected_selection_revision": maximum,
            "consent": True,
        },
        {
            "action": "cancel",
            "operation_id": identity,
            "command_id": command,
            "expected_state_revision": maximum,
        },
        {"action": "refresh", "command_id": command, "expected_selection_revision": maximum},
    ):
        value = ModelTestControl.model_validate({"op": "model_test", **payload})
        assert len(value.model_dump_json().encode()) <= 3600
        frame = (
            ControlRequest(version=1, capability="a" * 64, command=value).model_dump_json().encode()
            + b"\n"
        )
        assert len(frame) <= 4096
        assert json.loads(frame)["command"]["op"] == "model_test"


def test_no_caller_authority_or_coerced_consent() -> None:
    intent = {"operation_id": str(uuid4()), "expected_selection_revision": 1, "consent": True}
    ModelTestRequest.model_validate(intent)
    for consent in (False, 1, "true", None):
        with pytest.raises(ValueError):
            ModelTestRequest.model_validate({**intent, "consent": consent})
        with pytest.raises(ValueError):
            ModelTestControl.model_validate(
                {"op": "model_test", "action": "start", **intent, "consent": consent}
            )
    for field in ("secret", "epoch", "config_snapshot_ref", "prompt", "url", "scope_kind"):
        with pytest.raises(ValueError):
            ModelTestRequest.model_validate({**intent, field: "caller-data"})
