"""Small, dependency-free user-interface translations.

Machine-facing protocol values stay stable and English.  This module is only for text shown to a
person in the CLI, TUI, notifications, or a frontend adapter.
"""

from __future__ import annotations

from typing import Any, Literal

Language = Literal["en", "es"]


_TEXT: dict[Language, dict[str, str]] = {
    "en": {
        "unlimited": "Unlimited",
        "none": "None",
        "unknown": "unknown",
        "yes": "Yes",
        "no": "No",
        "idle": "idle",
        "running": "running",
        "paused": "paused",
        "expired": "expired",
        "inherit": "inherit",
        "notify_only": "notify only",
        "soft": "soft restriction",
        "close": "close game",
        "block": "block new games",
        "daily": "daily",
        "timer": "timer",
        "daily_limit": "daily limit",
        "timer_expired": "timer expired",
        "outside_allowed_period": "outside allowed period",
        "restriction_none": "none",
        "warning_exhausted_title": "Play time exhausted",
        "warning_exhausted_daily": "The configured daily allowance has been used.",
        "warning_exhausted_timer": "The configured timer allowance has been used.",
        "warning_remaining_title": "{minutes} {unit} remaining",
        "minute_one": "minute",
        "minute_many": "minutes",
        "warning_remaining_daily": "Daily allowance is nearing its limit.",
        "warning_remaining_timer": "Timer allowance is nearing its limit.",
        "service_error": "Service error: {message}",
        "action_failed": "Action failed: {message}",
        "summary": "Summary",
        "session_timer": "Session timer",
        "daily_limit_view": "Daily limit",
        "weekly": "Weekly",
        "history": "History",
        "settings": "Settings",
        "diagnostics": "Diagnostics",
        "played_today": "Played today",
        "remaining_today": "Remaining today",
        "detected_game": "Detected game",
        "game": "Game",
        "restriction": "Restriction",
        "level": "level",
        "next_warning": "Next warning",
        "next_reset": "Next reset",
        "state": "State",
        "remaining": "Remaining",
        "configured": "Configured",
        "action": "Action",
        "accounting_day": "Accounting day",
        "limit": "Limit",
        "exceptional_time": "Exceptional time",
        "played": "Played",
        "allowed_period": "Allowed period",
        "week": "Week",
        "total": "Total",
        "recent_sessions": "Recent sessions",
        "no_history": "No history",
        "configured_restriction_level": "Configured restriction level",
        "force_kill": "Force kill",
        "enabled": "enabled",
        "disabled": "disabled",
        "version": "Version",
        "python": "Python",
        "detector": "Detector",
        "database_quick_check": "Database quick_check",
        "database_schema": "DB schema",
        "decky_connected": "Decky connected",
        "notify_send": "notify-send",
        "session_type": "Session type",
        "detected_exit": "detected exit",
        "game_changed": "game changed",
        "daily_reset": "daily reset",
        "service_shutdown": "service shutdown",
        "footer": "←/→ change view · 1–7 jump · Q quit",
        "timer_controls": "S starts 30m · P pauses · R resumes · C cancels · +/- changes 5m",
        "grant_hint": "B grants 15 exceptional minutes for today.",
        "level_hint": "L cycles restriction levels 0–3.",
        "schedule_hint": "Edit the complete weekly schedule in config.json or with the CLI.",
        "timer_started": "30-minute timer started",
        "timer_paused": "Timer paused",
        "timer_resumed": "Timer resumed",
        "timer_cancelled": "Timer cancelled",
        "minutes_added": "Added 5 minutes",
        "minutes_removed": "Removed 5 minutes",
        "daily_time_added": "Added 15 minutes for today",
        "confirm_level": "Press L again to confirm restriction level {level}",
        "level_set": "Restriction level set to {level}",
        "local_guardian": "Local SteamOS play-time guardian",
        "show_status": "show current status",
        "open_tui": "open the Desktop Mode text UI",
        "print_json": "print machine-readable JSON",
        "override_socket": "override the Unix socket path",
        "override_language": "override the configured interface language",
        "run_daemon": "run the user daemon",
        "force_simulation": "force simulation detector",
        "no_foreground_log": "do not mirror JSON logs to stderr",
        "diagnose": "show a non-sensitive diagnostic snapshot",
        "config": "read or update configuration",
        "config_patch": "JSON object or @path/to/file.json",
        "manage_timer": "manage the session timer",
        "timer_action_help": "override timer.default_action for this timer",
        "bonus": "grant or remove exceptional daily time",
        "bonus_reason": "reason for the exceptional time",
        "history_command": "list, export, or clear history",
        "history_format": "export format",
        "history_output": "output file",
        "history_confirm": "confirm permanent history deletion",
        "summary_command": "daily or weekly summaries",
        "simulate": "emit a simulator event",
        "exported_history": "Exported {format} history to {path}",
    },
    "es": {
        "unlimited": "Sin límite",
        "none": "Ninguno",
        "unknown": "desconocido",
        "yes": "Sí",
        "no": "No",
        "idle": "inactivo",
        "running": "en marcha",
        "paused": "en pausa",
        "expired": "agotado",
        "inherit": "heredada",
        "notify_only": "solo avisar",
        "soft": "restricción suave",
        "close": "cerrar juego",
        "block": "bloquear juegos nuevos",
        "daily": "diario",
        "timer": "temporizador",
        "daily_limit": "límite diario",
        "timer_expired": "temporizador agotado",
        "outside_allowed_period": "fuera del horario permitido",
        "restriction_none": "ninguna",
        "warning_exhausted_title": "Tiempo de juego agotado",
        "warning_exhausted_daily": "Se ha agotado el tiempo diario configurado.",
        "warning_exhausted_timer": "Se ha agotado el tiempo del temporizador configurado.",
        "warning_remaining_title": "Queda {minutes} {unit}",
        "minute_one": "minuto",
        "minute_many": "minutos",
        "warning_remaining_daily": "El tiempo diario está cerca de su límite.",
        "warning_remaining_timer": "El temporizador está cerca de su límite.",
        "service_error": "Error del servicio: {message}",
        "action_failed": "La acción ha fallado: {message}",
        "summary": "Resumen",
        "session_timer": "Temporizador de sesión",
        "daily_limit_view": "Límite diario",
        "weekly": "Semanal",
        "history": "Historial",
        "settings": "Ajustes",
        "diagnostics": "Diagnóstico",
        "played_today": "Jugado hoy",
        "remaining_today": "Resta hoy",
        "detected_game": "Juego detectado",
        "game": "Juego",
        "restriction": "Restricción",
        "level": "nivel",
        "next_warning": "Próximo aviso",
        "next_reset": "Próximo reinicio",
        "state": "Estado",
        "remaining": "Restante",
        "configured": "Configurado",
        "action": "Acción",
        "accounting_day": "Día contable",
        "limit": "Límite",
        "exceptional_time": "Tiempo excepcional",
        "played": "Jugado",
        "allowed_period": "Horario permitido",
        "week": "Semana",
        "total": "Total",
        "recent_sessions": "Sesiones recientes",
        "no_history": "Sin historial",
        "configured_restriction_level": "Nivel de restricción configurado",
        "force_kill": "Cierre forzado",
        "enabled": "activado",
        "disabled": "desactivado",
        "version": "Versión",
        "python": "Python",
        "detector": "Detector",
        "database_quick_check": "Comprobación rápida de la base de datos",
        "database_schema": "Esquema de BD",
        "decky_connected": "Decky conectado",
        "notify_send": "notify-send",
        "session_type": "Tipo de sesión",
        "detected_exit": "salida detectada",
        "game_changed": "cambio de juego",
        "daily_reset": "reinicio diario",
        "service_shutdown": "apagado del servicio",
        "footer": "←/→ cambiar vista · 1–7 saltar · Q salir",
        "timer_controls": "S inicia 30 min · P pausa · R reanuda · C cancela · +/- cambia 5 min",
        "grant_hint": "B concede 15 minutos excepcionales para hoy.",
        "level_hint": "L cambia entre los niveles 0–3.",
        "schedule_hint": "Edita el horario semanal completo en config.json o con la CLI.",
        "timer_started": "Temporizador de 30 minutos iniciado",
        "timer_paused": "Temporizador en pausa",
        "timer_resumed": "Temporizador reanudado",
        "timer_cancelled": "Temporizador cancelado",
        "minutes_added": "Se han añadido 5 minutos",
        "minutes_removed": "Se han quitado 5 minutos",
        "daily_time_added": "Se han añadido 15 minutos para hoy",
        "confirm_level": "Pulsa L otra vez para confirmar el nivel de restricción {level}",
        "level_set": "Nivel de restricción establecido en {level}",
        "local_guardian": "Control local de tiempo de juego para SteamOS",
        "show_status": "mostrar el estado actual",
        "open_tui": "abrir la interfaz de texto del modo escritorio",
        "print_json": "mostrar JSON para máquinas",
        "override_socket": "anular la ruta del socket Unix",
        "override_language": "anular el idioma de interfaz configurado",
        "run_daemon": "ejecutar el daemon de usuario",
        "force_simulation": "forzar el detector de simulación",
        "no_foreground_log": "no duplicar los registros JSON en stderr",
        "diagnose": "mostrar un diagnóstico no sensible",
        "config": "leer o actualizar la configuración",
        "config_patch": "objeto JSON o @ruta/al/archivo.json",
        "manage_timer": "gestionar el temporizador de sesión",
        "timer_action_help": "anular timer.default_action para este temporizador",
        "bonus": "conceder o quitar tiempo diario excepcional",
        "bonus_reason": "motivo del tiempo excepcional",
        "history_command": "listar, exportar o borrar el historial",
        "history_format": "formato de exportación",
        "history_output": "archivo de salida",
        "history_confirm": "confirmar el borrado permanente del historial",
        "summary_command": "resúmenes diarios o semanales",
        "simulate": "emitir un evento de simulación",
        "exported_history": "Historial {format} exportado a {path}",
    },
}


def language(value: Any) -> Language:
    """Return a supported language without exposing config validation to callers."""
    return "es" if value == "es" else "en"


def tr(selected: str | None, key: str, **values: object) -> str:
    """Translate a stable UI key and interpolate its named values."""
    template = _TEXT[language(selected)].get(key, _TEXT["en"].get(key, key))
    return template.format(**values)


def format_duration(seconds: int | float | None, selected: str | None = "en") -> str:
    if seconds is None:
        return tr(selected, "unlimited")
    value = max(0, int(seconds))
    hours, remainder = divmod(value, 3600)
    minutes, secs = divmod(remainder, 60)
    minute_unit = "min" if language(selected) == "es" else "m"
    return f"{hours:d}h {minutes:02d}{minute_unit} {secs:02d}s" if hours else f"{minutes:d}{minute_unit} {secs:02d}s"


def display_timer_state(value: object, selected: str | None) -> str:
    return tr(selected, str(value) if value in {"idle", "running", "paused", "expired"} else "unknown")


def display_scope(value: object, selected: str | None) -> str:
    return tr(selected, str(value) if value in {"daily", "timer"} else "none")


def display_restriction_reason(value: object, selected: str | None) -> str:
    key = "restriction_none" if value == "none" else str(value)
    return tr(selected, key)


def display_timer_action(value: object, selected: str | None) -> str:
    key = str(value)
    return tr(selected, key if key in {"inherit", "notify_only", "soft", "close", "block"} else "unknown")


def display_session_reason(value: object, selected: str | None) -> str:
    key = str(value)
    return tr(
        selected,
        key if key in {"detected_exit", "game_changed", "daily_reset", "service_shutdown"} else "unknown",
    )
