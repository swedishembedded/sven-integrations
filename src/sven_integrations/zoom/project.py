"""Zoom meeting configuration model — dataclass-based."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Participant:
    """A meeting participant with a role."""

    email: str
    name: str
    role: str = "attendee"  # "host" | "co-host" | "attendee"

    def to_dict(self) -> dict[str, Any]:
        return {"email": self.email, "name": self.name, "role": self.role}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Participant":
        return cls(
            email=str(d["email"]),
            name=str(d["name"]),
            role=str(d.get("role", "attendee")),
        )


@dataclass
class ZoomMeetingConfig:
    """Configuration for a Zoom meeting."""

    meeting_id: str | None = None
    topic: str = "New Meeting"
    host_email: str = ""
    duration_minutes: int = 60
    timezone: str = "UTC"
    passcode: str = ""
    waiting_room: bool = True
    recording_enabled: bool = False
    participants: list[Participant] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Serialisation

    def to_dict(self) -> dict[str, Any]:
        return {
            "meeting_id": self.meeting_id,
            "topic": self.topic,
            "host_email": self.host_email,
            "duration_minutes": self.duration_minutes,
            "timezone": self.timezone,
            "passcode": self.passcode,
            "waiting_room": self.waiting_room,
            "recording_enabled": self.recording_enabled,
            "participants": [p.to_dict() for p in self.participants],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ZoomMeetingConfig":
        cfg = cls(
            meeting_id=d.get("meeting_id"),
            topic=str(d.get("topic", "New Meeting")),
            host_email=str(d.get("host_email", "")),
            duration_minutes=int(d.get("duration_minutes", 60)),
            timezone=str(d.get("timezone", "UTC")),
            passcode=str(d.get("passcode", "")),
            waiting_room=bool(d.get("waiting_room", True)),
            recording_enabled=bool(d.get("recording_enabled", False)),
        )
        cfg.participants = [Participant.from_dict(p) for p in d.get("participants", [])]
        return cfg

    # ------------------------------------------------------------------
    # Validation

    def validate(self) -> list[str]:
        """Return a list of validation error strings (empty = valid)."""
        errors: list[str] = []

        if not self.topic.strip():
            errors.append("topic must not be empty")

        if not self.host_email.strip():
            errors.append("host_email must not be empty")
        elif "@" not in self.host_email:
            errors.append(f"host_email '{self.host_email}' is not a valid email address")

        if self.duration_minutes <= 0:
            errors.append(f"duration_minutes must be > 0 (got {self.duration_minutes})")

        valid_roles = {"host", "co-host", "attendee"}
        for p in self.participants:
            if not p.email.strip():
                errors.append(f"participant '{p.name}' has no email address")
            elif "@" not in p.email:
                errors.append(f"participant email '{p.email}' is not valid")
            if p.role not in valid_roles:
                errors.append(
                    f"participant '{p.name}' has invalid role '{p.role}'; "
                    f"must be one of {sorted(valid_roles)}"
                )

        return errors
