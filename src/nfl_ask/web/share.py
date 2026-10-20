"""Share links: one answer, saved only when the visitor clicks Share, behind a private link
that stops working (and is deleted) after SHARE_HOURS.

What a share can contain, and who can read it:
- Only an answer this server rendered. The answer page carries the rendered answer and an
  HMAC of it (a ticket); /share stores the answer only if the HMAC matches. Nobody can post
  their own HTML and get a link to it on this site. The key is made fresh per process and
  never leaves it, so a ticket stops working when the server restarts (ask again to share).
- Shares live in their own schema (ask), which the model can't query: nfl_ask.query only
  runs SELECTs on tables in marts.
- A link is 128 random bits. Expired rows are deleted whenever a share is made or opened.
"""

import base64
import hashlib
import hmac
import re
import secrets
import zlib
from collections.abc import Callable
from datetime import datetime, timedelta

SHARE_HOURS = 24
MAX_TICKET_CHARS = 400_000  # a rendered answer is ~10-40 KB compressed; refuse anything absurd
TOKEN = re.compile(r"^[A-Za-z0-9_-]{22}$")  # secrets.token_urlsafe(16)


class Tickets:
    """Signs a rendered answer so /share can tell it came from this server, unchanged."""

    def __init__(self, key: bytes | None = None):
        self._key = key or secrets.token_bytes(32)

    def issue(self, html: str) -> tuple[str, str]:
        payload = base64.urlsafe_b64encode(zlib.compress(html.encode(), 9)).decode()
        return payload, self._sign(payload)

    def redeem(self, payload: str, signature: str) -> str | None:
        """The answer's HTML if the ticket is genuine, else None."""
        if not payload or len(payload) > MAX_TICKET_CHARS or not hmac.compare_digest(self._sign(payload), signature):
            return None
        try:
            return zlib.decompress(base64.urlsafe_b64decode(payload)).decode()
        except (ValueError, zlib.error):
            return None

    def _sign(self, payload: str) -> str:
        return hmac.new(self._key, payload.encode(), hashlib.sha256).hexdigest()


class MemoryShares:
    """Shares in a dict: for tests, and for running the site without a database."""

    def __init__(self):
        self.rows: dict[str, tuple[str, datetime]] = {}

    def save(self, html: str, now: datetime) -> tuple[str, datetime]:
        self.rows = {t: r for t, r in self.rows.items() if r[1] > now}
        token, expires = secrets.token_urlsafe(16), now + timedelta(hours=SHARE_HOURS)
        self.rows[token] = (html, expires)
        return token, expires

    def load(self, token: str, now: datetime) -> tuple[str, datetime] | None:
        row = self.rows.get(token)
        if row is None or row[1] <= now:
            self.rows.pop(token, None)
            return None
        return row


class PostgresShares:
    """Shares in the serving database, schema ask (out of the model's reach)."""

    def __init__(self, connect: Callable):
        self.connect = connect
        with connect() as conn:
            conn.execute("create schema if not exists ask")
            conn.execute(
                "create table if not exists ask.shares ("
                " token text primary key, html text not null,"
                " created_at timestamptz not null, expires_at timestamptz not null)"
            )

    def save(self, html: str, now: datetime) -> tuple[str, datetime]:
        token, expires = secrets.token_urlsafe(16), now + timedelta(hours=SHARE_HOURS)
        with self.connect() as conn:
            conn.execute("delete from ask.shares where expires_at <= %s", (now,))
            conn.execute("insert into ask.shares (token, html, created_at, expires_at) values (%s, %s, %s, %s)",
                         (token, html, now, expires))
        return token, expires

    def load(self, token: str, now: datetime) -> tuple[str, datetime] | None:
        with self.connect() as conn:
            conn.execute("delete from ask.shares where expires_at <= %s", (now,))
            row = conn.execute("select html, expires_at from ask.shares where token = %s", (token,)).fetchone()
        return (row[0], row[1]) if row else None
