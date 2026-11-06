"""Keep shared mail settings and communication preferences out of local data."""

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from database import AgentCommunicationPreference, Campaign, CampaignDelivery
from services import agent_communications


@pytest.fixture(autouse=True)
def isolated_mail_state(tmp_path, monkeypatch):
    # Jobs read persisted overrides in addition to environment defaults. Each
    # test starts without the operator's real schedule or recipient overrides.
    monkeypatch.setenv("AUTOMATIC_MAILS_CONFIG_FILE", str(tmp_path / "mail-config.json"))
    engine = create_engine(f"sqlite:///{tmp_path / 'communication-preferences.db'}")
    for model in (AgentCommunicationPreference, Campaign, CampaignDelivery):
        model.__table__.create(engine)
    monkeypatch.setattr(agent_communications, "SessionLocal", sessionmaker(bind=engine))
    yield
    engine.dispose()
