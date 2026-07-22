"""XDG-compliant path resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

APP_SLUG = "steamos-time-guardian"


@dataclass(frozen=True, slots=True)
class AppPaths:
    config_dir: Path
    data_dir: Path
    state_dir: Path
    runtime_dir: Path

    @property
    def config_file(self) -> Path:
        return self.config_dir / "config.json"

    @property
    def database_file(self) -> Path:
        return self.data_dir / "guardian.db"

    @property
    def log_file(self) -> Path:
        return self.state_dir / "guardian.jsonl"

    @property
    def socket_file(self) -> Path:
        return self.runtime_dir / "control.sock"

    @property
    def support_dir(self) -> Path:
        return self.state_dir / "support"

    @classmethod
    def from_environment(cls) -> "AppPaths":
        home = Path(os.environ.get("HOME", str(Path.home()))).expanduser()
        config_home = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        data_home = Path(os.environ.get("XDG_DATA_HOME", home / ".local/share"))
        state_home = Path(os.environ.get("XDG_STATE_HOME", home / ".local/state"))
        runtime_base = os.environ.get("XDG_RUNTIME_DIR")
        if runtime_base:
            runtime = Path(runtime_base) / APP_SLUG
        else:
            # Development fallback only. systemd/pam_systemd normally provides XDG_RUNTIME_DIR.
            runtime = Path(f"/tmp/{APP_SLUG}-{os.getuid()}")
        return cls(
            config_dir=config_home / APP_SLUG,
            data_dir=data_home / APP_SLUG,
            state_dir=state_home / APP_SLUG,
            runtime_dir=runtime,
        )

    def ensure(self) -> None:
        for path, mode in (
            (self.config_dir, 0o700),
            (self.data_dir, 0o700),
            (self.state_dir, 0o700),
            (self.runtime_dir, 0o700),
        ):
            path.mkdir(parents=True, exist_ok=True, mode=mode)
            try:
                path.chmod(mode)
            except OSError:
                pass
