"""Zoom interactive REPL console."""

from __future__ import annotations

from ..shared import Console, Style
from .backend import ZoomApiBackend, ZoomApiError
from .core import auth as auth_mod
from .core import meetings as meet_mod
from .core import recordings as rec_mod
from .project import ZoomMeetingConfig
from .session import ZoomSession


class ZoomConsole(Console):
    """Interactive REPL for the Zoom harness."""

    harness_name = "zoom"
    intro_extra = "Commands: auth  meeting  recording  status  help  quit"

    def __init__(self, session_name: str = "default", **kwargs: object) -> None:
        super().__init__(session_name=session_name, **kwargs)
        self._sess = ZoomSession.open_or_create(session_name)
        self._api = ZoomApiBackend()

    # ------------------------------------------------------------------
    # Internal helpers

    def _token(self) -> str | None:
        if not self._sess.is_authenticated():
            self.failure("Not authenticated. Run: auth login --client-id ... --client-secret ...")
            return None
        return self._sess.oauth_token

    # ------------------------------------------------------------------
    # auth

    def do_auth(self, arg: str) -> None:
        """auth <login|status|logout> [args...]

        Examples:
          auth status
          auth login --client-id ID --client-secret SECRET --code CODE
          auth logout
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_auth.__doc__)
            return

        sub = parts[0]
        rest = parts[1:]

        if sub == "status":
            if self._sess.is_authenticated():
                self.success(f"Authenticated (expires: {self._sess.token_expiry})")
            else:
                self.failure("Not authenticated")

        elif sub == "logout":
            token = self._sess.oauth_token
            if token:
                try:
                    auth_mod.revoke_token(token)
                except ZoomApiError:
                    pass
            self._sess.clear_auth()
            self.success("Logged out")

        elif sub == "login":
            # Parse --client-id, --client-secret, --code from rest
            params: dict[str, str] = {}
            for part in rest:
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k.lstrip("-").replace("-", "_")] = v
            client_id = params.get("client_id", "")
            client_secret = params.get("client_secret", "")
            code = params.get("code", "")
            redirect_uri = params.get("redirect_uri", "http://localhost:4199/callback")
            if not client_id or not client_secret:
                self.failure("Usage: auth login --client-id=ID --client-secret=SECRET [--code=CODE]")
                return
            if not code:
                url = auth_mod.build_oauth_url(client_id, redirect_uri)
                print(Style.info(f"\n  Auth URL:\n  {url}\n"))
                print(Style.dim("  Re-run with --code=<code> after authorising in the browser."))
            else:
                try:
                    data = auth_mod.exchange_code(client_id, client_secret, code, redirect_uri)
                    self._sess.set_token(
                        data["access_token"],
                        float(data.get("expires_in", 3600)),
                        refresh_token=data.get("refresh_token", ""),
                    )
                    self.success("Authenticated successfully")
                except ZoomApiError as exc:
                    self.failure(str(exc))

        else:
            self.failure(f"Unknown sub-command: {sub}")

    # ------------------------------------------------------------------
    # meeting

    def do_meeting(self, arg: str) -> None:
        """meeting <create|list|get|delete|url> [args...]

        Examples:
          meeting list
          meeting create --topic="Weekly Sync" --duration=30
          meeting get --id=123456789
          meeting delete --id=123456789
          meeting url --id=123456789
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_meeting.__doc__)
            return

        sub = parts[0]
        rest = parts[1:]
        token = self._token()
        if token is None:
            return

        if sub == "list":
            try:
                meetings = meet_mod.list_meetings(token, "me")
                self.section(f"Meetings ({len(meetings)})")
                for m in meetings:
                    self.bullet(
                        f"{m.get('id')}  {Style.info(m.get('topic', ''))}  "
                        f"{m.get('start_time', '')}  {m.get('duration', '')}min"
                    )
                if not meetings:
                    print(Style.dim("  (none)"))
            except ZoomApiError as exc:
                self.failure(str(exc))

        elif sub == "get":
            params = _parse_kv(rest)
            mid = params.get("id", "")
            if not mid:
                self.failure("Usage: meeting get --id=<meeting_id>")
                return
            try:
                info = meet_mod.get_meeting(token, mid)
                self.section("Meeting Info")
                for k, v in info.items():
                    self.bullet(f"{k}: {v}")
            except ZoomApiError as exc:
                self.failure(str(exc))

        elif sub == "create":
            params = _parse_kv(rest)
            topic = params.get("topic", "New Meeting")
            duration = int(params.get("duration", "60"))
            cfg = ZoomMeetingConfig(
                topic=topic,
                host_email="me",
                duration_minutes=duration,
                timezone=params.get("timezone", "UTC"),
                passcode=params.get("passcode", ""),
            )
            try:
                result = meet_mod.create_meeting(token, "me", cfg)
                self.success(f"Meeting created: {result.get('id')}  topic={result.get('topic')}")
            except (ZoomApiError, ValueError) as exc:
                self.failure(str(exc))

        elif sub == "delete":
            params = _parse_kv(rest)
            mid = params.get("id", "")
            if not mid:
                self.failure("Usage: meeting delete --id=<meeting_id>")
                return
            try:
                meet_mod.delete_meeting(token, mid)
                self.success(f"Meeting {mid} deleted")
            except ZoomApiError as exc:
                self.failure(str(exc))

        elif sub == "url":
            params = _parse_kv(rest)
            mid = params.get("id", "")
            if not mid:
                self.failure("Usage: meeting url --id=<meeting_id>")
                return
            url = meet_mod.join_meeting_url(mid, params.get("passcode"))
            self.section("Join URL")
            print(f"  {Style.ok(url)}")

        else:
            self.failure(f"Unknown sub-command: {sub}")

    # ------------------------------------------------------------------
    # recording

    def do_recording(self, arg: str) -> None:
        """recording <list|download> [args...]

        Examples:
          recording list --from=2026-01-01 --to=2026-03-31
          recording download --meeting-id=123456789 --output=/tmp/recording.mp4
        """
        parts = self.parse_args(arg)
        if not parts:
            print(self.do_recording.__doc__)
            return

        sub = parts[0]
        rest = parts[1:]
        token = self._token()
        if token is None:
            return

        if sub == "list":
            params = _parse_kv(rest)
            from_d = params.get("from", "")
            to_d = params.get("to", "")
            if not from_d or not to_d:
                self.failure("Usage: recording list --from=YYYY-MM-DD --to=YYYY-MM-DD")
                return
            try:
                recs = rec_mod.list_recordings(token, "me", from_d, to_d)
                self.section(f"Recordings ({len(recs)} meetings)")
                for m in recs:
                    self.bullet(f"{m.get('id')}  {m.get('topic', '')}  {m.get('start_time', '')}")
            except ZoomApiError as exc:
                self.failure(str(exc))

        elif sub == "download":
            params = _parse_kv(rest)
            mid = params.get("meeting_id", "")
            output = params.get("output", "")
            if not mid or not output:
                self.failure("Usage: recording download --meeting-id=ID --output=PATH")
                return
            try:
                info = rec_mod.get_recording_info(token, mid)
                files = info.get("recording_files", [])
                if not files:
                    self.failure("No recording files found")
                    return
                path = rec_mod.download_recording(token, files[0]["download_url"], output)
                self.success(f"Downloaded to {path}")
            except ZoomApiError as exc:
                self.failure(str(exc))

        else:
            self.failure(f"Unknown sub-command: {sub}")

    # ------------------------------------------------------------------
    # status

    def do_status(self, _arg: str) -> None:
        """Show session and authentication status."""
        self.section("Session")
        self.bullet(f"name: {self._sess.name}")
        self.section("Authentication")
        if self._sess.is_authenticated():
            self.success(f"Authenticated (expires: {self._sess.token_expiry})")
        else:
            self.failure("Not authenticated")


# ---------------------------------------------------------------------------
# Helpers


def _parse_kv(args: list[str]) -> dict[str, str]:
    """Parse ['--key=value', '--other=val'] → {'key': 'value', 'other': 'val'}."""
    result: dict[str, str] = {}
    for part in args:
        stripped = part.lstrip("-")
        if "=" in stripped:
            k, v = stripped.split("=", 1)
            result[k.replace("-", "_")] = v
    return result
