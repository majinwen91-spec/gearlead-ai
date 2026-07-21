from __future__ import annotations

from pathlib import Path

import pytest

from gearlead.database import initialize_database


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "test_gearlead.db"
    initialize_database(path, force_seed=True)
    return path


@pytest.fixture()
def keyboard_inquiry() -> str:
    return (
        "We are Nordlicht Gaming GmbH, a distributor based in Germany. "
        "Contact sales@nordlicht-gaming.de and visit https://nordlicht-gaming.de. "
        "We need 500 units of a 75% tri-mode mechanical keyboard with gasket mount, "
        "hot-swappable PCB, PBT keycaps and ISO-DE layout, CE certification, custom logo "
        "and retail packaging. Please quote for delivery by October 15."
    )

