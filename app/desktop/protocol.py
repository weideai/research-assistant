"""Versioned metadata for the in-process desktop bridge contract."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


PROTOCOL_VERSION = 1
MIN_COMPATIBLE_PROTOCOL = 1
MAX_COMPATIBLE_PROTOCOL = 1

CAPABILITIES = (
    "ai.changesets",
    "records.batch_export",
    "zotero.jobs",
)

DEPRECATED_COMMANDS = {
    "record.export_batch": {
        "replacement": "record.export.batch",
        "remove_in_protocol": 2,
    },
}


def build_app_info(app_info: Mapping[str, Any], commands: Mapping[str, Any]) -> dict[str, Any]:
    """Attach stable protocol discovery metadata to runtime application info."""

    result = dict(app_info)
    result.update(
        {
            "protocol_version": PROTOCOL_VERSION,
            "protocol_compatibility": {
                "minimum": MIN_COMPATIBLE_PROTOCOL,
                "maximum": MAX_COMPATIBLE_PROTOCOL,
            },
            "capabilities": list(CAPABILITIES),
            "commands": sorted(commands),
            "deprecated_commands": DEPRECATED_COMMANDS,
        }
    )
    return result
