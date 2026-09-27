"""Dashboard health is separate from database/API health and admission authority."""

import asyncio
from enum import StrEnum
from pathlib import Path

from omnis.core.web_assets import WebAssets
from omnis.modules.instance.domain import InstanceStatus
from omnis.transport.control_probe import control_available


class DashboardReason(StrEnum):
    ASSETS_UNAVAILABLE = "ASSETS_UNAVAILABLE"
    CONTROL_UNAVAILABLE = "CONTROL_UNAVAILABLE"


async def dashboard_reason(
    assets: WebAssets, directory: Path | None, status: InstanceStatus
) -> DashboardReason | None:
    if await asyncio.to_thread(assets.load) is None:
        return DashboardReason.ASSETS_UNAVAILABLE
    if not await control_available(directory, status):
        return DashboardReason.CONTROL_UNAVAILABLE
    return None
