"""pytest — Zoom harness core tests."""

from __future__ import annotations

import json
import unittest.mock as mock
import urllib.error
import urllib.request

import pytest

from sven_integrations.zoom.core import auth as auth_mod
from sven_integrations.zoom.core import meetings as meet_mod
from sven_integrations.zoom.core import participants as part_mod
from sven_integrations.zoom.project import Participant, ZoomMeetingConfig
from sven_integrations.zoom.session import ZoomSession

# ---------------------------------------------------------------------------
# ZoomMeetingConfig validation


def make_valid_config(**overrides: object) -> ZoomMeetingConfig:
    cfg = ZoomMeetingConfig(
        topic="Weekly Sync",
        host_email="host@example.com",
        duration_minutes=60,
        timezone="America/New_York",
        passcode="secret",
        waiting_room=True,
        recording_enabled=False,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def test_valid_config_no_errors() -> None:
    cfg = make_valid_config()
    assert cfg.validate() == []


def test_missing_topic() -> None:
    cfg = make_valid_config(topic="   ")
    errors = cfg.validate()
    assert any("topic" in e for e in errors)


def test_missing_host_email() -> None:
    cfg = make_valid_config(host_email="")
    errors = cfg.validate()
    assert any("host_email" in e for e in errors)


def test_invalid_host_email() -> None:
    cfg = make_valid_config(host_email="notanemail")
    errors = cfg.validate()
    assert any("host_email" in e for e in errors)


def test_invalid_duration() -> None:
    cfg = make_valid_config(duration_minutes=0)
    errors = cfg.validate()
    assert any("duration" in e for e in errors)


def test_to_dict_round_trip() -> None:
    cfg = make_valid_config()
    d = cfg.to_dict()
    cfg2 = ZoomMeetingConfig.from_dict(d)
    assert cfg2.topic == cfg.topic
    assert cfg2.host_email == cfg.host_email
    assert cfg2.duration_minutes == cfg.duration_minutes
    assert cfg2.waiting_room == cfg.waiting_room


# ---------------------------------------------------------------------------
# Participant model


def test_participant_defaults() -> None:
    p = Participant(email="alice@example.com", name="Alice")
    assert p.role == "attendee"


def test_participant_valid_role() -> None:
    for role in ("host", "co-host", "attendee"):
        cfg = make_valid_config()
        cfg.participants = [Participant(email="a@example.com", name="A", role=role)]
        assert cfg.validate() == []


def test_participant_invalid_role() -> None:
    cfg = make_valid_config()
    cfg.participants = [Participant(email="a@example.com", name="A", role="spectator")]
    errors = cfg.validate()
    assert any("invalid role" in e for e in errors)


def test_participant_missing_email() -> None:
    cfg = make_valid_config()
    cfg.participants = [Participant(email="", name="Bob")]
    errors = cfg.validate()
    assert any("no email" in e for e in errors)


def test_participant_invalid_email() -> None:
    cfg = make_valid_config()
    cfg.participants = [Participant(email="bademail", name="Bob")]
    errors = cfg.validate()
    assert any("not valid" in e for e in errors)


def test_participant_to_dict_round_trip() -> None:
    p = Participant(email="b@example.com", name="Bob", role="co-host")
    d = p.to_dict()
    p2 = Participant.from_dict(d)
    assert p2.email == p.email
    assert p2.role == p.role


# ---------------------------------------------------------------------------
# Auth URL building


def test_build_oauth_url_basic() -> None:
    url = auth_mod.build_oauth_url("client_id_123", "http://localhost:4199/callback")
    assert "zoom.us/oauth/authorize" in url
    assert "client_id=client_id_123" in url
    assert "response_type=code" in url


def test_build_oauth_url_with_state() -> None:
    url = auth_mod.build_oauth_url("cid", "http://localhost:4199/cb", state="random_state")
    assert "state=random_state" in url


def test_build_oauth_url_contains_redirect_uri() -> None:
    url = auth_mod.build_oauth_url("cid", "http://localhost:4199/callback")
    assert "redirect_uri=" in url


# ---------------------------------------------------------------------------
# Meeting URL helpers


def test_join_meeting_url_basic() -> None:
    url = meet_mod.join_meeting_url("123456789")
    assert url == "https://zoom.us/j/123456789"


def test_join_meeting_url_with_passcode() -> None:
    url = meet_mod.join_meeting_url("123456789", passcode="secret")
    assert "pwd=secret" in url


def test_start_meeting_url_basic() -> None:
    url = meet_mod.start_meeting_url("987654321")
    assert url == "https://zoom.us/s/987654321"


def test_start_meeting_url_with_passcode() -> None:
    url = meet_mod.start_meeting_url("987654321", passcode="pass123")
    assert "pwd=pass123" in url


# ---------------------------------------------------------------------------
# ZoomSession auth storage (no network)


def test_session_set_and_check_token(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SVEN_INTEGRATIONS_STATE_DIR", str(tmp_path))
    sess = ZoomSession("test_auth")
    assert not sess.is_authenticated()
    sess.set_token("tok123", 3600, refresh_token="ref456")
    assert sess.is_authenticated()
    assert sess.oauth_token == "tok123"
    assert sess.get_refresh_token() == "ref456"


def test_session_token_expiry(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SVEN_INTEGRATIONS_STATE_DIR", str(tmp_path))
    sess = ZoomSession("test_expiry")
    sess.set_token("tok_short", expires_in_seconds=0)
    # Token is immediately expired
    assert not sess.is_authenticated()


def test_session_clear_auth(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SVEN_INTEGRATIONS_STATE_DIR", str(tmp_path))
    sess = ZoomSession("test_clear")
    sess.set_token("tok", 3600)
    assert sess.is_authenticated()
    sess.clear_auth()
    assert not sess.is_authenticated()
    assert sess.oauth_token is None


def test_session_harness_name() -> None:
    assert ZoomSession.harness == "zoom"


# ---------------------------------------------------------------------------
# Mock API: create_meeting


def _make_mock_response(body: dict) -> mock.MagicMock:
    resp_mock = mock.MagicMock()
    resp_mock.read.return_value = json.dumps(body).encode()
    resp_mock.__enter__ = mock.MagicMock(return_value=resp_mock)
    resp_mock.__exit__ = mock.MagicMock(return_value=False)
    return resp_mock


@pytest.fixture()
def mock_zoom_api(monkeypatch):
    """Patch urllib.request.urlopen to return predictable responses."""
    responses: list[dict] = []

    def fake_urlopen(req, timeout=30):
        if responses:
            return _make_mock_response(responses.pop(0))
        return _make_mock_response({})

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return responses


def test_create_meeting_mock(mock_zoom_api) -> None:
    mock_zoom_api.append({
        "id": 123456789,
        "topic": "Weekly Sync",
        "type": 2,
        "duration": 60,
    })
    cfg = make_valid_config()
    result = meet_mod.create_meeting("fake_token", "me", cfg)
    assert result["id"] == 123456789
    assert result["topic"] == "Weekly Sync"


def test_create_meeting_invalid_config() -> None:
    cfg = make_valid_config(topic="", host_email="")
    with pytest.raises(ValueError):
        meet_mod.create_meeting("tok", "me", cfg)


def test_get_meeting_mock(mock_zoom_api) -> None:
    mock_zoom_api.append({"id": 111, "topic": "Demo"})
    result = meet_mod.get_meeting("fake_token", "111")
    assert result["topic"] == "Demo"


def test_list_meetings_mock(mock_zoom_api) -> None:
    mock_zoom_api.append({
        "meetings": [
            {"id": 1, "topic": "A"},
            {"id": 2, "topic": "B"},
        ]
    })
    result = meet_mod.list_meetings("fake_token", "me")
    assert len(result) == 2


# ---------------------------------------------------------------------------
# RegistrantInfo dataclass tests


class TestRegistrantInfo:
    def test_defaults(self) -> None:
        reg = part_mod.RegistrantInfo(
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
        )
        assert reg.status == "pending"
        assert reg.email == "alice@example.com"

    def test_to_dict(self) -> None:
        reg = part_mod.RegistrantInfo(
            email="bob@example.com",
            first_name="Bob",
            last_name="Jones",
            status="approved",
        )
        d = reg.to_dict()
        assert d["email"] == "bob@example.com"
        assert d["status"] == "approved"

    def test_from_dict(self) -> None:
        d = {"email": "carol@x.com", "first_name": "Carol", "last_name": "Lee", "status": "denied"}
        reg = part_mod.RegistrantInfo.from_dict(d)
        assert reg.last_name == "Lee"
        assert reg.status == "denied"

    def test_roundtrip(self) -> None:
        reg = part_mod.RegistrantInfo("a@b.com", "A", "B", "approved")
        reg2 = part_mod.RegistrantInfo.from_dict(reg.to_dict())
        assert reg2.email == reg.email
        assert reg2.status == reg.status


# ---------------------------------------------------------------------------
# list_registrants mock test


def _make_zoom_response(payload: dict) -> mock.MagicMock:
    """Build a mock urlopen context-manager returning JSON *payload*."""
    raw = json.dumps(payload).encode("utf-8")
    resp = mock.MagicMock()
    resp.read.return_value = raw
    resp.__enter__ = mock.MagicMock(return_value=resp)
    resp.__exit__ = mock.MagicMock(return_value=False)
    return resp


class TestListRegistrants:
    def test_list_registrants_mock(self) -> None:
        payload = {
            "registrants": [
                {"email": "a@b.com", "first_name": "A", "last_name": "B", "status": "approved"},
                {"email": "c@d.com", "first_name": "C", "last_name": "D", "status": "approved"},
            ],
            "next_page_token": "",
        }
        with mock.patch("urllib.request.urlopen", return_value=_make_zoom_response(payload)):
            result = part_mod.list_registrants("tok", "123456")
        assert len(result) == 2
        assert result[0]["email"] == "a@b.com"

    def test_add_registrant_mock(self) -> None:
        payload = {"registrant_id": "REG001", "join_url": "https://zoom.us/j/123"}
        with mock.patch("urllib.request.urlopen", return_value=_make_zoom_response(payload)):
            result = part_mod.add_registrant("tok", "123", "alice@x.com", "Alice", "Smith")
        assert result["registrant_id"] == "REG001"


# ---------------------------------------------------------------------------
# add_batch_registrants tests


class TestBatchRegistrants:
    def test_batch_add(self) -> None:
        payload = {"registrant_id": "R1", "join_url": "https://zoom.us/j/1"}
        registrants = [
            {"email": "a@b.com", "first_name": "A", "last_name": "B"},
            {"email": "c@d.com", "first_name": "C", "last_name": "D"},
        ]
        with mock.patch("urllib.request.urlopen", return_value=_make_zoom_response(payload)):
            result = part_mod.add_batch_registrants("tok", "123", registrants)
        assert result["total"] == 2
        assert len(result["added"]) == 2
        assert result["errors"] == []

    def test_batch_add_with_error(self) -> None:
        """If one registrant fails, errors list captures it."""
        call_count = 0

        def side_effect(req, timeout=30):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return _make_zoom_response({"registrant_id": "R1"})
            exc = urllib.error.HTTPError("url", 400, "Bad Request", {}, None)
            exc.read = lambda: b'{"message": "Invalid email"}'
            raise exc

        registrants = [
            {"email": "good@b.com", "first_name": "G", "last_name": "O"},
            {"email": "bad", "first_name": "B", "last_name": "A"},
        ]
        with mock.patch("urllib.request.urlopen", side_effect=side_effect):
            result = part_mod.add_batch_registrants("tok", "123", registrants)
        assert len(result["added"]) == 1
        assert len(result["errors"]) == 1
