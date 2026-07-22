"""SQLite persistence with migrations, WAL, recovery, and bounded writes."""

from __future__ import annotations

import csv
import io
import json
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator
from uuid import uuid4

from .models import GameIdentity, TimerSnapshot, TimerState

CURRENT_DB_SCHEMA = 2

MIGRATIONS: dict[int, str] = {
    1: """
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            day_key TEXT NOT NULL,
            app_id TEXT,
            app_name TEXT NOT NULL,
            source TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 1.0,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            duration_seconds REAL NOT NULL DEFAULT 0,
            reason TEXT,
            last_checkpoint_at TEXT NOT NULL,
            metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_sessions_one_open
            ON sessions((1)) WHERE ended_at IS NULL;
        CREATE INDEX IF NOT EXISTS idx_sessions_day ON sessions(day_key, started_at);
        CREATE INDEX IF NOT EXISTS idx_sessions_app ON sessions(app_id, started_at);

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            occurred_at TEXT NOT NULL,
            event_type TEXT NOT NULL,
            session_id TEXT,
            app_id TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_events_time ON events(occurred_at);

        CREATE TABLE IF NOT EXISTS daily_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day_key TEXT NOT NULL,
            seconds INTEGER NOT NULL,
            reason TEXT NOT NULL,
            granted_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_adjustments_day ON daily_adjustments(day_key);

        CREATE TABLE IF NOT EXISTS timer_state (
            singleton INTEGER PRIMARY KEY CHECK(singleton = 1),
            generation TEXT,
            state TEXT NOT NULL,
            configured_seconds INTEGER NOT NULL,
            remaining_seconds REAL NOT NULL,
            action TEXT NOT NULL,
            started_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS notification_marks (
            scope TEXT NOT NULL,
            scope_key TEXT NOT NULL,
            threshold_seconds INTEGER NOT NULL,
            emitted_at TEXT NOT NULL,
            PRIMARY KEY(scope, scope_key, threshold_seconds)
        );

        CREATE TABLE IF NOT EXISTS runtime_state (
            key TEXT PRIMARY KEY,
            value_json TEXT NOT NULL
        );
    """,
    2: """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
        INSERT OR IGNORE INTO schema_migrations(version, applied_at)
            VALUES (1, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'));
    """,
}


class DatabaseError(RuntimeError):
    """Persistent storage could not be initialized safely."""


def utc_iso(value: datetime | None = None) -> str:
    current = value or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    return current.astimezone(UTC).isoformat()


class Storage:
    def __init__(self, path: Path, *, backup_count: int = 3):
        self.path = path
        self.backup_count = max(0, min(int(backup_count), 20))
        self._connection: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        self.recovery_note: str | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise DatabaseError("database is not open")
        return self._connection

    def open(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self._connect()
            check = self.connection.execute("PRAGMA quick_check").fetchone()
            if not check or check[0] != "ok":
                raise sqlite3.DatabaseError(f"quick_check returned {check!r}")
            self._migrate()
        except sqlite3.DatabaseError as exc:
            self.close()
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
            quarantine = self.path.with_name(f"guardian.corrupt-{stamp}.db")
            try:
                if self.path.exists():
                    shutil.move(self.path, quarantine)
                for suffix in ("-wal", "-shm"):
                    sidecar = Path(str(self.path) + suffix)
                    if sidecar.exists():
                        shutil.move(sidecar, Path(str(quarantine) + suffix))
            except OSError as move_error:
                raise DatabaseError(f"database corrupt and could not be quarantined: {move_error}") from exc
            self.recovery_note = f"corrupt database quarantined as {quarantine.name}: {exc}"
            self._connect()
            self._migrate()

    def _connect(self) -> None:
        self._connection = sqlite3.connect(
            self.path,
            timeout=5.0,
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=NORMAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA busy_timeout=5000")
        try:
            self.path.chmod(0o600)
        except OSError:
            pass

    def close(self) -> None:
        if self._connection is not None:
            try:
                self._connection.execute("PRAGMA wal_checkpoint(PASSIVE)")
            except sqlite3.Error:
                pass
            self._connection.close()
            self._connection = None

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            conn = self.connection
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except Exception:
                conn.execute("ROLLBACK")
                raise
            else:
                conn.execute("COMMIT")

    def _migrate(self) -> None:
        current = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
        if current > CURRENT_DB_SCHEMA:
            raise DatabaseError(
                f"database schema {current} is newer than supported {CURRENT_DB_SCHEMA}"
            )
        if 0 < current < CURRENT_DB_SCHEMA and self.path.exists() and self.path.stat().st_size:
            self._backup_before_migration(current)
        for version in range(current + 1, CURRENT_DB_SCHEMA + 1):
            # sqlite3.executescript() controls its own transaction boundary, so include
            # BEGIN/COMMIT in the script rather than nesting it in transaction().
            script = "BEGIN IMMEDIATE;\n" + MIGRATIONS[version]
            if version >= 2:
                applied = utc_iso().replace("'", "''")
                script += (
                    "\nINSERT OR REPLACE INTO schema_migrations(version, applied_at) "
                    f"VALUES ({version}, '{applied}');"
                )
            script += f"\nPRAGMA user_version={version};\nCOMMIT;"
            with self._lock:
                try:
                    self.connection.executescript(script)
                except Exception:
                    if self.connection.in_transaction:
                        self.connection.execute("ROLLBACK")
                    raise

    def _backup_before_migration(self, version: int) -> None:
        if self.backup_count == 0:
            return
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        backup = self.path.with_name(f"guardian.pre-v{version}-migration-{stamp}.db")
        try:
            target = sqlite3.connect(backup)
            self.connection.backup(target)
            target.close()
            backup.chmod(0o600)
            backups = sorted(
                self.path.parent.glob("guardian.pre-v*-migration-*.db"),
                key=lambda item: item.stat().st_mtime_ns,
                reverse=True,
            )
            for obsolete in backups[self.backup_count :]:
                obsolete.unlink(missing_ok=True)
        except (sqlite3.Error, OSError):
            backup.unlink(missing_ok=True)

    def record_event(
        self,
        event_type: str,
        occurred_at: datetime,
        payload: dict[str, Any] | None = None,
        *,
        session_id: str | None = None,
        app_id: str | None = None,
    ) -> int:
        encoded = json.dumps(payload or {}, sort_keys=True, separators=(",", ":"))
        with self._lock:
            cursor = self.connection.execute(
                "INSERT INTO events(occurred_at,event_type,session_id,app_id,payload_json) "
                "VALUES (?,?,?,?,?)",
                (utc_iso(occurred_at), event_type, session_id, app_id, encoded),
            )
            return int(cursor.lastrowid)

    def open_session(self, day_key: str, game: GameIdentity, started_at: datetime) -> str:
        session_id = str(uuid4())
        with self.transaction() as conn:
            existing = conn.execute("SELECT id FROM sessions WHERE ended_at IS NULL").fetchone()
            if existing:
                raise DatabaseError(f"an open session already exists: {existing['id']}")
            conn.execute(
                "INSERT INTO sessions(id,day_key,app_id,app_name,source,confidence,started_at,"
                "last_checkpoint_at,metadata_json) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    session_id,
                    day_key,
                    game.app_id,
                    game.name,
                    game.source,
                    game.confidence,
                    utc_iso(started_at),
                    utc_iso(started_at),
                    json.dumps({"pids": list(game.pids), "instance_id": game.instance_id}),
                ),
            )
            conn.execute(
                "INSERT INTO events(occurred_at,event_type,session_id,app_id,payload_json) "
                "VALUES (?,?,?,?,?)",
                (utc_iso(started_at), "game_started", session_id, game.app_id, json.dumps(game.to_dict())),
            )
        return session_id

    def checkpoint_session(self, session_id: str, duration_seconds: float, when: datetime) -> None:
        with self._lock:
            cursor = self.connection.execute(
                "UPDATE sessions SET duration_seconds=?, last_checkpoint_at=? "
                "WHERE id=? AND ended_at IS NULL",
                (max(0.0, duration_seconds), utc_iso(when), session_id),
            )
            if cursor.rowcount != 1:
                raise DatabaseError("cannot checkpoint a session that is not open")

    def close_session(
        self,
        session_id: str,
        duration_seconds: float,
        ended_at: datetime,
        reason: str,
    ) -> None:
        with self.transaction() as conn:
            row = conn.execute(
                "SELECT app_id FROM sessions WHERE id=? AND ended_at IS NULL", (session_id,)
            ).fetchone()
            if not row:
                return
            conn.execute(
                "UPDATE sessions SET ended_at=?, duration_seconds=?, reason=?, last_checkpoint_at=? "
                "WHERE id=?",
                (utc_iso(ended_at), max(0.0, duration_seconds), reason, utc_iso(ended_at), session_id),
            )
            conn.execute(
                "INSERT INTO events(occurred_at,event_type,session_id,app_id,payload_json) "
                "VALUES (?,?,?,?,?)",
                (
                    utc_iso(ended_at),
                    "game_stopped",
                    session_id,
                    row["app_id"],
                    json.dumps({"reason": reason, "duration_seconds": int(duration_seconds)}),
                ),
            )

    def rotate_session_day(
        self,
        session_id: str,
        duration_seconds: float,
        boundary: datetime,
        new_day_key: str,
        game: GameIdentity,
    ) -> str:
        self.close_session(session_id, duration_seconds, boundary, "daily_reset")
        return self.open_session(new_day_key, game, boundary)

    def recover_open_session(self, when: datetime) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM sessions WHERE ended_at IS NULL LIMIT 1"
        ).fetchone()
        if not row:
            return None
        payload = dict(row)
        self.close_session(
            row["id"],
            float(row["duration_seconds"]),
            when,
            "service_restart_recovery",
        )
        return payload

    def usage_for_day(self, day_key: str) -> float:
        row = self.connection.execute(
            "SELECT COALESCE(SUM(duration_seconds),0) AS total FROM sessions WHERE day_key=?",
            (day_key,),
        ).fetchone()
        return float(row["total"])

    def adjustment_for_day(self, day_key: str) -> int:
        row = self.connection.execute(
            "SELECT COALESCE(SUM(seconds),0) AS total FROM daily_adjustments WHERE day_key=?",
            (day_key,),
        ).fetchone()
        return int(row["total"])

    def grant_adjustment(self, day_key: str, seconds: int, reason: str, when: datetime) -> int:
        if not -86400 <= seconds <= 86400:
            raise ValueError("adjustment must be between -24h and +24h")
        with self._lock:
            cursor = self.connection.execute(
                "INSERT INTO daily_adjustments(day_key,seconds,reason,granted_at) VALUES (?,?,?,?)",
                (day_key, seconds, reason[:200], utc_iso(when)),
            )
            adjustment_id = int(cursor.lastrowid)
        self.record_event(
            "time_adjustment",
            when,
            {"day_key": day_key, "seconds": seconds, "reason": reason[:200]},
        )
        return adjustment_id

    def list_adjustments(
        self, day_key: str | None = None, limit: int | None = 100
    ) -> list[dict[str, Any]]:
        bounded = None if limit is None else max(1, min(limit, 1000))
        where = " WHERE day_key=?" if day_key else ""
        sql = f"SELECT * FROM daily_adjustments{where} ORDER BY granted_at DESC"
        params: tuple[Any, ...] = (day_key,) if day_key else ()
        if bounded is not None:
            sql += " LIMIT ?"
            params += (bounded,)
        rows = self.connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def save_timer(self, timer: TimerSnapshot) -> None:
        with self._lock:
            self.connection.execute(
                "INSERT INTO timer_state(singleton,generation,state,configured_seconds,remaining_seconds,"
                "action,started_at,updated_at) VALUES (1,?,?,?,?,?,?,?) "
                "ON CONFLICT(singleton) DO UPDATE SET generation=excluded.generation,state=excluded.state,"
                "configured_seconds=excluded.configured_seconds,remaining_seconds=excluded.remaining_seconds,"
                "action=excluded.action,started_at=excluded.started_at,updated_at=excluded.updated_at",
                (
                    timer.generation,
                    timer.state.value,
                    timer.configured_seconds,
                    max(0.0, timer.remaining_seconds),
                    timer.action,
                    timer.started_at,
                    timer.updated_at,
                ),
            )

    def load_timer(self) -> TimerSnapshot:
        row = self.connection.execute("SELECT * FROM timer_state WHERE singleton=1").fetchone()
        if not row:
            return TimerSnapshot()
        try:
            state = TimerState(row["state"])
        except ValueError:
            state = TimerState.IDLE
        return TimerSnapshot(
            state=state,
            generation=row["generation"],
            configured_seconds=int(row["configured_seconds"]),
            remaining_seconds=float(row["remaining_seconds"]),
            action=row["action"],
            started_at=row["started_at"],
            updated_at=row["updated_at"],
        )

    def mark_notification(
        self, scope: str, scope_key: str, threshold_seconds: int, when: datetime
    ) -> bool:
        with self._lock:
            cursor = self.connection.execute(
                "INSERT OR IGNORE INTO notification_marks(scope,scope_key,threshold_seconds,emitted_at) "
                "VALUES (?,?,?,?)",
                (scope, scope_key, threshold_seconds, utc_iso(when)),
            )
            return cursor.rowcount == 1

    def clear_notification_scope(self, scope: str, scope_key: str) -> None:
        with self._lock:
            self.connection.execute(
                "DELETE FROM notification_marks WHERE scope=? AND scope_key=?", (scope, scope_key)
            )

    def notification_thresholds(self, scope: str, scope_key: str) -> set[int]:
        rows = self.connection.execute(
            "SELECT threshold_seconds FROM notification_marks WHERE scope=? AND scope_key=?",
            (scope, scope_key),
        ).fetchall()
        return {int(row["threshold_seconds"]) for row in rows}

    def list_sessions(
        self, limit: int | None = 100, day_key: str | None = None
    ) -> list[dict[str, Any]]:
        bounded = None if limit is None else max(1, min(limit, 1000))
        where = " WHERE day_key=?" if day_key else ""
        sql = f"SELECT * FROM sessions{where} ORDER BY started_at DESC"
        params: tuple[Any, ...] = (day_key,) if day_key else ()
        if bounded is not None:
            sql += " LIMIT ?"
            params += (bounded,)
        rows = self.connection.execute(sql, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["metadata"] = json.loads(item.pop("metadata_json"))
            except json.JSONDecodeError:
                item["metadata"] = {}
                item.pop("metadata_json", None)
            item["duration_seconds"] = int(round(item["duration_seconds"]))
            result.append(item)
        return result

    def list_events(self, limit: int | None = 100) -> list[dict[str, Any]]:
        sql = "SELECT * FROM events ORDER BY occurred_at DESC, id DESC"
        params: tuple[Any, ...] = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (max(1, min(limit, 1000)),)
        rows = self.connection.execute(sql, params).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            try:
                item["payload"] = json.loads(item.pop("payload_json"))
            except json.JSONDecodeError:
                item["payload"] = {}
                item.pop("payload_json", None)
            result.append(item)
        return result

    def daily_summary(self, start_day: date, days: int) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for offset in range(days):
            key = (start_day + timedelta(days=offset)).isoformat()
            rows = self.connection.execute(
                "SELECT app_id,app_name,SUM(duration_seconds) AS seconds,COUNT(*) AS sessions "
                "FROM sessions WHERE day_key=? GROUP BY app_id,app_name ORDER BY seconds DESC",
                (key,),
            ).fetchall()
            result.append(
                {
                    "day_key": key,
                    "total_seconds": int(sum(float(row["seconds"]) for row in rows)),
                    "adjustment_seconds": self.adjustment_for_day(key),
                    "apps": [
                        {
                            "app_id": row["app_id"],
                            "app_name": row["app_name"],
                            "seconds": int(row["seconds"]),
                            "sessions": int(row["sessions"]),
                        }
                        for row in rows
                    ],
                }
            )
        return result

    def weekly_summary(self, end_day: date) -> dict[str, Any]:
        start = end_day - timedelta(days=6)
        days = self.daily_summary(start, 7)
        return {
            "start_day": start.isoformat(),
            "end_day": end_day.isoformat(),
            "total_seconds": sum(day["total_seconds"] for day in days),
            "days": days,
        }

    def clear_history(self) -> None:
        with self.transaction() as conn:
            if conn.execute("SELECT 1 FROM sessions WHERE ended_at IS NULL").fetchone():
                raise DatabaseError("history cannot be cleared while a game session is active")
            conn.execute("DELETE FROM sessions")
            conn.execute("DELETE FROM events")
            conn.execute("DELETE FROM daily_adjustments")
            conn.execute("DELETE FROM notification_marks")

    def enforce_retention(self, retention_days: int, now: datetime) -> dict[str, int]:
        cutoff = utc_iso(now - timedelta(days=retention_days))
        with self.transaction() as conn:
            session_cursor = conn.execute(
                "DELETE FROM sessions WHERE ended_at IS NOT NULL AND ended_at < ?", (cutoff,)
            )
            event_cursor = conn.execute("DELETE FROM events WHERE occurred_at < ?", (cutoff,))
            adjustment_cursor = conn.execute(
                "DELETE FROM daily_adjustments WHERE granted_at < ?", (cutoff,)
            )
            notification_cursor = conn.execute(
                "DELETE FROM notification_marks WHERE emitted_at < ?", (cutoff,)
            )
        return {
            "sessions": session_cursor.rowcount,
            "events": event_cursor.rowcount,
            "adjustments": adjustment_cursor.rowcount,
            "notification_marks": notification_cursor.rowcount,
        }

    def export(self, format_name: str) -> str:
        sessions = self.list_sessions(limit=None)
        if format_name == "json":
            return json.dumps(
                {
                    "schema_version": 1,
                    "exported_at": utc_iso(),
                    "sessions": sessions,
                    "adjustments": self.list_adjustments(limit=None),
                    "events": self.list_events(limit=None),
                },
                indent=2,
                sort_keys=True,
            ) + "\n"
        if format_name == "csv":
            output = io.StringIO()
            fields = (
                "day_key",
                "app_id",
                "app_name",
                "started_at",
                "ended_at",
                "duration_seconds",
                "reason",
                "source",
            )
            writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(sessions)
            return output.getvalue()
        raise ValueError("format must be json or csv")

    def quick_check(self) -> str:
        return str(self.connection.execute("PRAGMA quick_check").fetchone()[0])

    def schema_version(self) -> int:
        return int(self.connection.execute("PRAGMA user_version").fetchone()[0])
