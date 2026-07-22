const React = SP_REACT;
const {
  ButtonItem,
  DropdownItem,
  PanelSection,
  PanelSectionRow,
  ToggleField,
  staticClasses,
} = DFL;

const PLUGIN_NAME = "SteamOS Time Guardian";
const WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"] as const;
const VIEW_NAMES = ["summary", "timer", "daily", "weekly", "activity", "settings", "diagnostics"] as const;
type ViewName = (typeof VIEW_NAMES)[number];
type Language = "en" | "es";
type JsonObject = Record<string, any>;

const UI_TEXT: Record<Language, Record<string, string>> = {
  en: {
    summary: "Summary", timer: "Timer", daily: "Daily limit", weekly: "Weekly schedule", activity: "Activity", settings: "Settings", diagnostics: "Diagnostics",
    now: "Now", playedToday: "Played today", remainingToday: "Remaining today", game: "Game", noneDetected: "None detected", restriction: "Restriction", nextWarning: "Next warning", nextReset: "Next reset",
    daemonUnavailable: "Daemon unavailable: {{error}}", deckyOptional: "Decky is optional. Tracking continues in the user daemon when this panel is closed.",
    sessionTimer: "Session timer", state: "State", remaining: "Remaining", start30: "Start 30 minutes", pause: "Pause", resume: "Resume", add5: "Add 5 minutes", remove5: "Remove 5 minutes", cancelTimer: "Cancel timer",
    dailyAllowance: "Daily allowance", accountingDay: "Accounting day", limit: "Limit", exceptionalTime: "Exceptional time", played: "Played", allowedPeriod: "Allowed period", grant15: "Grant 15 minutes today",
    yes: "Yes", no: "No", unlimited: "Unlimited", idle: "idle", running: "running", paused: "paused", expired: "expired", unknown: "unknown", noGame: "No games yet", noActivity: "No activity yet",
    steamApp: "Steam app {{appId}}", noForegroundGame: "No foreground game",
    dailyScope: "daily", timerScope: "timer", reasonNone: "none", dailyLimitReason: "daily limit", timerExpiredReason: "timer expired", outsideAllowedPeriodReason: "outside allowed period",
    weeklyHint: "Press a day to cycle common limits. Detailed allowed periods remain editable in Desktop Mode.",
    last7Days: "Last 7 days", dailyAverage: "Daily average", topGame: "Top game", peakTime: "Peak time", refreshActivity: "Refresh activity", loadingActivity: "Loading activity…", whenYouPlay: "When you play", darkerMeans: "Darker means more time. The hourly map records from this version onward.", heatmapStarts: "The hourly map starts collecting with this version. Your totals and games still include saved history.", topGames: "Top games", noGamesPeriod: "No games in this period.", recentSessions: "Recent sessions", noCompletedSessions: "No completed sessions yet.", confirmEraseHistory: "Confirm: erase all history", eraseHistory: "Erase history…",
    restrictionLevel: "Restriction level", confirmRestrictionLevel: "Confirm restriction level {{level}}", setRestrictionLevel: "Set restriction level {{level}}", language: "Language", desktopNotifications: "Desktop notifications", forcedTermination: "Forced termination", enabled: "Enabled", disabled: "Disabled", disableForcedTermination: "Disable forced termination", confirmForceKill: "Confirm enabling SIGKILL fallback", enableForcedTermination: "Enable forced termination…", ownerNotice: "Local restrictions can be bypassed by the device owner. Level 3 never blocks Desktop Mode, power controls, or recovery access.",
    statusDiagnostics: "Status and diagnostics", daemon: "Daemon", connected: "Connected", unavailable: "Unavailable", version: "Version", detector: "Detector", database: "Database", dbSchema: "DB schema", nativeNotifications: "Native notifications", available: "Available", refreshDiagnostics: "Refresh diagnostics", view: "View",
    terminateUnavailable: "SteamClient.Apps.TerminateApp unavailable", steamCloseRequested: "Steam close requested", playTimeExhausted: "Play time exhausted", playRestricted: "Play is currently restricted", restrictionActive: "Reason: {{reason}}. Restriction level {{level}} is active.",
  },
  es: {
    summary: "Resumen", timer: "Temporizador", daily: "Límite diario", weekly: "Horario semanal", activity: "Actividad", settings: "Ajustes", diagnostics: "Diagnóstico",
    now: "Ahora", playedToday: "Jugado hoy", remainingToday: "Resta hoy", game: "Juego", noneDetected: "No detectado", restriction: "Restricción", nextWarning: "Próximo aviso", nextReset: "Próximo reinicio",
    daemonUnavailable: "Daemon no disponible: {{error}}", deckyOptional: "Decky es opcional. El seguimiento continúa en el daemon de usuario al cerrar este panel.",
    sessionTimer: "Temporizador de sesión", state: "Estado", remaining: "Restante", start30: "Iniciar 30 minutos", pause: "Pausar", resume: "Reanudar", add5: "Añadir 5 minutos", remove5: "Quitar 5 minutos", cancelTimer: "Cancelar temporizador",
    dailyAllowance: "Tiempo diario", accountingDay: "Día contable", limit: "Límite", exceptionalTime: "Tiempo excepcional", played: "Jugado", allowedPeriod: "Horario permitido", grant15: "Conceder 15 minutos hoy",
    yes: "Sí", no: "No", unlimited: "Sin límite", idle: "inactivo", running: "en marcha", paused: "en pausa", expired: "agotado", unknown: "desconocido", noGame: "Aún no hay juegos", noActivity: "Aún no hay actividad",
    steamApp: "Aplicación de Steam {{appId}}", noForegroundGame: "No hay juego en primer plano",
    dailyScope: "diario", timerScope: "temporizador", reasonNone: "ninguna", dailyLimitReason: "límite diario", timerExpiredReason: "temporizador agotado", outsideAllowedPeriodReason: "fuera del horario permitido",
    weeklyHint: "Pulsa un día para recorrer límites habituales. Los horarios permitidos detallados se editan en el modo escritorio.",
    last7Days: "Últimos 7 días", dailyAverage: "Media diaria", topGame: "Juego principal", peakTime: "Hora punta", refreshActivity: "Actualizar actividad", loadingActivity: "Cargando actividad…", whenYouPlay: "Cuándo juegas", darkerMeans: "Más oscuro significa más tiempo. El mapa horario registra desde esta versión.", heatmapStarts: "El mapa horario empieza a recopilar con esta versión. Los totales y juegos incluyen el historial guardado.", topGames: "Juegos principales", noGamesPeriod: "No hay juegos en este periodo.", recentSessions: "Sesiones recientes", noCompletedSessions: "Aún no hay sesiones terminadas.", confirmEraseHistory: "Confirmar: borrar todo el historial", eraseHistory: "Borrar historial…",
    restrictionLevel: "Nivel de restricción", confirmRestrictionLevel: "Confirmar nivel de restricción {{level}}", setRestrictionLevel: "Establecer nivel de restricción {{level}}", language: "Idioma", desktopNotifications: "Notificaciones de escritorio", forcedTermination: "Terminación forzada", enabled: "Activada", disabled: "Desactivada", disableForcedTermination: "Desactivar terminación forzada", confirmForceKill: "Confirmar activación de SIGKILL", enableForcedTermination: "Activar terminación forzada…", ownerNotice: "El propietario del dispositivo puede omitir las restricciones locales. El nivel 3 nunca bloquea el modo escritorio, los controles de energía ni la recuperación.",
    statusDiagnostics: "Estado y diagnóstico", daemon: "Daemon", connected: "Conectado", unavailable: "No disponible", version: "Versión", detector: "Detector", database: "Base de datos", dbSchema: "Esquema de BD", nativeNotifications: "Notificaciones nativas", available: "Disponible", refreshDiagnostics: "Actualizar diagnóstico", view: "Vista",
    terminateUnavailable: "SteamClient.Apps.TerminateApp no está disponible", steamCloseRequested: "Se ha solicitado el cierre en Steam", playTimeExhausted: "Tiempo de juego agotado", playRestricted: "El juego está restringido", restrictionActive: "Motivo: {{reason}}. El nivel de restricción {{level}} está activo.",
  },
};
let uiLanguage: Language = "en";

function toLanguage(value: unknown): Language {
  return value === "es" ? "es" : "en";
}

function t(key: string, values: Record<string, string | number> = {}, selected: Language = uiLanguage): string {
  let text = UI_TEXT[selected][key] ?? UI_TEXT.en[key] ?? key;
  for (const [name, value] of Object.entries(values)) text = text.split(`{{${name}}}`).join(String(value));
  return text;
}

function viewOptions(selected: Language) {
  return VIEW_NAMES.map((data) => ({ data, label: t(data, {}, selected) }));
}

const ACTIVITY_BUCKET_LABELS = ["00–04", "04–08", "08–12", "12–16", "16–20", "20–24"];
let rememberedView: ViewName = "summary";

function connectRuntime(): DeckyRuntimeApi {
  const connector = window.__DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit;
  if (!connector) throw new Error("Decky Loader API is unavailable");
  try {
    return connector.connect(2, PLUGIN_NAME);
  } catch {
    return connector.connect(1, PLUGIN_NAME);
  }
}

const deckyApi = connectRuntime();
const backend = {
  status: () => deckyApi.call<JsonObject>("get_status"),
  config: () => deckyApi.call<JsonObject>("get_config"),
  updateConfig: (patch: JsonObject) => deckyApi.call<JsonObject>("update_config", patch),
  startTimer: (minutes: number, action?: string) => action === undefined
    ? deckyApi.call<JsonObject>("timer_start", minutes)
    : deckyApi.call<JsonObject>("timer_start", minutes, action),
  pauseTimer: () => deckyApi.call<JsonObject>("timer_pause"),
  resumeTimer: () => deckyApi.call<JsonObject>("timer_resume"),
  cancelTimer: () => deckyApi.call<JsonObject>("timer_cancel"),
  adjustTimer: (seconds: number) => deckyApi.call<JsonObject>("timer_adjust", seconds),
  grantTime: (minutes: number, reason: string) => deckyApi.call<JsonObject>("daily_grant", minutes, reason),
  activity: () => deckyApi.call<JsonObject>("activity_summary", 7),
  clearHistory: (confirmation: string) => deckyApi.call<JsonObject>("history_clear", confirmation),
  diagnostics: () => deckyApi.call<JsonObject>("get_diagnostics"),
  heartbeat: () => deckyApi.call<JsonObject>("heartbeat"),
  reportForeground: (running: boolean, appId: string | null, name: string) =>
    deckyApi.call<JsonObject>("report_foreground", running, appId, name),
  reportLifetime: (appId: number, instanceId: number, running: boolean) =>
    deckyApi.call<JsonObject>("report_lifetime", appId, instanceId, running),
  reportEnforcement: (appId: string | null, success: boolean, detail: string) =>
    deckyApi.call<JsonObject>("report_enforcement", appId, success, detail),
};

function formatDuration(value: number | null | undefined, selected: Language = uiLanguage): string {
  if (value === null) return t("unlimited", {}, selected);
  const total = Math.max(0, Math.floor(Number(value ?? 0)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  return hours > 0
    ? `${hours}h ${String(minutes).padStart(2, "0")}${selected === "es" ? "min" : "m"}`
    : `${minutes}${selected === "es" ? "min" : "m"} ${String(seconds).padStart(2, "0")}s`;
}

function formatCompactDuration(value: number | null | undefined, selected: Language = uiLanguage): string {
  const total = Math.max(0, Math.floor(Number(value ?? 0)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  if (hours > 0) return minutes > 0 ? `${hours}h${minutes}` : `${hours}h`;
  return `${minutes}${selected === "es" ? "min" : "m"}`;
}

function currentSteamApp(): { running: boolean; appId: string | null; name: string } {
  const app = DFL.Router?.MainRunningApp;
  if (!app) return { running: false, appId: null, name: "" };
  return {
    running: true,
    appId: app.appid === undefined || app.appid === null ? null : String(app.appid),
    name: app.display_name || app.sort_as || t("steamApp", { appId: String(app.appid ?? t("unknown")) }),
  };
}

function selectedView(value: unknown): ViewName | null {
  const raw = typeof value === "string"
    ? value
    : value && typeof value === "object"
      ? (value as JsonObject).data ?? (value as JsonObject).value
      : null;
  if (typeof raw !== "string") return null;
  return VIEW_NAMES.find((name) => name === raw || t(name, {}, "en") === raw || t(name, {}, "es") === raw) ?? null;
}

function languageFromSelection(value: unknown): Language {
  const raw = typeof value === "string"
    ? value
    : value && typeof value === "object"
      ? (value as JsonObject).data ?? (value as JsonObject).value
      : null;
  return toLanguage(raw);
}

function displayTimerState(value: unknown): string {
  return t(["idle", "running", "paused", "expired"].includes(String(value)) ? String(value) : "unknown");
}

function displayScope(value: unknown): string {
  return value === "daily" ? t("dailyScope") : value === "timer" ? t("timerScope") : t("noneDetected");
}

function displayReason(value: unknown): string {
  const reasons: Record<string, string> = {
    none: "reasonNone",
    daily_limit: "dailyLimitReason",
    timer_expired: "timerExpiredReason",
    outside_allowed_period: "outsideAllowedPeriodReason",
  };
  return t(reasons[String(value)] ?? "reasonNone");
}

function formatActivityDay(value: string): string {
  const parts = value.split("-");
  return parts.length === 3 ? `${parts[2]}/${parts[1]}` : value;
}

function activityCellColor(seconds: number, unavailable: boolean): string {
  if (unavailable) return "rgba(255, 255, 255, 0.05)";
  if (seconds <= 0) return "rgba(255, 255, 255, 0.08)";
  if (seconds < 30 * 60) return "rgba(102, 192, 244, 0.3)";
  if (seconds < 60 * 60) return "rgba(102, 192, 244, 0.48)";
  if (seconds < 2 * 60 * 60) return "rgba(102, 192, 244, 0.68)";
  return "rgba(102, 192, 244, 0.9)";
}

async function reportCurrentForeground(): Promise<void> {
  const app = currentSteamApp();
  try {
    await backend.reportForeground(app.running, app.appId, app.name || t("noForegroundGame"));
  } catch (error) {
    console.warn("Time Guardian could not report foreground app", error);
  }
}

function ValueRow({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <PanelSectionRow>
      <div style={{ display: "flex", justifyContent: "space-between", gap: "12px", width: "100%", fontSize: "16px" }}>
        <span style={{ opacity: 0.78 }}>{label}</span>
        <strong style={{ textAlign: "right" }}>{value}</strong>
      </div>
    </PanelSectionRow>
  );
}

function Notice({ children, danger = false }: { children?: any; danger?: boolean }): JSX.Element {
  return (
    <PanelSectionRow>
      <div
        style={{
          width: "100%",
          padding: "10px 12px",
          borderRadius: "6px",
          background: danger ? "rgba(214, 69, 69, 0.22)" : "rgba(102, 192, 244, 0.13)",
          lineHeight: 1.35,
        }}
      >
        {children}
      </div>
    </PanelSectionRow>
  );
}

function GuardianPanel(): JSX.Element {
  const [view, setViewState] = React.useState<ViewName>(() => rememberedView);
  const [status, setStatus] = React.useState<JsonObject | null>(null);
  const [config, setConfig] = React.useState<JsonObject | null>(null);
  const [detail, setDetail] = React.useState<JsonObject | null>(null);
  const [activity, setActivity] = React.useState<JsonObject | null>(null);
  const [error, setError] = React.useState<string>("");
  const [busy, setBusy] = React.useState(false);
  const [clearArmed, setClearArmed] = React.useState(false);
  const [forceArmed, setForceArmed] = React.useState(false);
  const [levelArmed, setLevelArmed] = React.useState<number | null>(null);
  const visible = deckyApi.useQuickAccessVisible ? deckyApi.useQuickAccessVisible() : true;

  const setView = React.useCallback((nextView: ViewName) => {
    rememberedView = nextView;
    setViewState(nextView);
  }, []);

  const refreshCore = React.useCallback(async () => {
    try {
      const [nextStatus, nextConfig] = await Promise.all([backend.status(), backend.config()]);
      setStatus(nextStatus);
      setConfig(nextConfig);
      uiLanguage = toLanguage(nextConfig.language);
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }, []);

  const refreshDetail = React.useCallback(async (target: ViewName) => {
    try {
      if (target === "activity") setActivity(await backend.activity());
      else if (target === "diagnostics") setDetail(await backend.diagnostics());
      else setDetail(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }, []);

  const refresh = React.useCallback(async () => {
    await refreshCore();
    await refreshDetail(view);
  }, [refreshCore, refreshDetail, view]);

  React.useEffect(() => {
    if (!visible) return;
    void backend.heartbeat();
    void reportCurrentForeground();
    void refreshCore();
    const interval = setInterval(() => {
      void backend.heartbeat();
      void reportCurrentForeground();
      void refreshCore();
    }, 5000);
    return () => clearInterval(interval);
  }, [visible, refreshCore]);

  React.useEffect(() => {
    setClearArmed(false);
    setForceArmed(false);
    setLevelArmed(null);
    if (visible) void refreshDetail(view);
  }, [view, visible, refreshDetail]);

  const act = React.useCallback(async (operation: () => Promise<JsonObject>) => {
    setBusy(true);
    try {
      await operation();
      await refresh();
      setError("");
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    } finally {
      setBusy(false);
    }
  }, [refresh]);

  const game = status?.game;
  const timer = status?.timer ?? {};
  const restriction = status?.restriction ?? {};
  const selectedLanguage = toLanguage(config?.language);

  function summaryView(): JSX.Element {
    const nextWarning = status?.next_warning;
    return (
      <PanelSection title={t("now")}>
        <ValueRow label={t("playedToday")} value={formatDuration(status?.played_today_seconds)} />
        <ValueRow label={t("remainingToday")} value={formatDuration(status?.remaining_today_seconds)} />
        <ValueRow label={t("game")} value={game?.name ?? t("noneDetected")} />
        <ValueRow label={t("timer")} value={`${displayTimerState(timer.state)} · ${formatDuration(timer.remaining_seconds)}`} />
        <ValueRow label={t("restriction")} value={`${t("restrictionLevel")} ${restriction.effective_level ?? 0} · ${displayReason(restriction.reason)}`} />
        <ValueRow
          label={t("nextWarning")}
          value={nextWarning ? `${displayScope(nextWarning.scope)} · ${formatDuration(nextWarning.play_seconds_until)}` : t("noneDetected")}
        />
        <ValueRow label={t("nextReset")} value={formatDuration(status?.seconds_until_reset)} />
        {error ? <Notice danger>{t("daemonUnavailable", { error })}</Notice> : <Notice>{t("deckyOptional")}</Notice>}
      </PanelSection>
    );
  }

  function timerView(): JSX.Element {
    return (
      <PanelSection title={t("sessionTimer")}>
        <ValueRow label={t("state")} value={displayTimerState(timer.state)} />
        <ValueRow label={t("remaining")} value={formatDuration(timer.remaining_seconds)} />
        {timer.state === "idle" || timer.state === "expired" ? (
          <PanelSectionRow><ButtonItem disabled={busy || (restriction.effective_level ?? 0) >= 1} onClick={() => void act(() => backend.startTimer(30))}>{t("start30")}</ButtonItem></PanelSectionRow>
        ) : null}
        {timer.state === "running" ? <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(backend.pauseTimer)}>{t("pause")}</ButtonItem></PanelSectionRow> : null}
        {timer.state === "paused" ? <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(backend.resumeTimer)}>{t("resume")}</ButtonItem></PanelSectionRow> : null}
        {timer.state !== "idle" ? <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(() => backend.adjustTimer(300))}>{t("add5")}</ButtonItem></PanelSectionRow> : null}
        {timer.state !== "idle" ? <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(() => backend.adjustTimer(-300))}>{t("remove5")}</ButtonItem></PanelSectionRow> : null}
        {timer.state !== "idle" ? <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(backend.cancelTimer)}>{t("cancelTimer")}</ButtonItem></PanelSectionRow> : null}
      </PanelSection>
    );
  }

  function dailyView(): JSX.Element {
    return (
      <PanelSection title={t("dailyAllowance")}>
        <ValueRow label={t("accountingDay")} value={String(status?.day_key ?? "-")} />
        <ValueRow label={t("limit")} value={formatDuration(status?.daily_limit_seconds)} />
        <ValueRow label={t("exceptionalTime")} value={formatDuration(status?.daily_adjustment_seconds)} />
        <ValueRow label={t("played")} value={formatDuration(status?.played_today_seconds)} />
        <ValueRow label={t("remaining")} value={formatDuration(status?.remaining_today_seconds)} />
        <ValueRow label={t("allowedPeriod")} value={status?.within_allowed_period ? t("yes") : t("no")} />
        <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(() => backend.grantTime(15, t("grant15")))}>{t("grant15")}</ButtonItem></PanelSectionRow>
      </PanelSection>
    );
  }

  function weeklyView(): JSX.Element {
    const weekly = config?.daily_limits?.weekly ?? {};
    const choices = [30, 45, 60, 90, 120, 180, 0];
    const cycle = (day: string): void => {
      const entry = weekly[day] ?? { minutes: 120, unlimited: false };
      const current = entry.unlimited ? 0 : Number(entry.minutes);
      const index = Math.max(0, choices.indexOf(current));
      const next = choices[(index + 1) % choices.length] ?? 120;
      void act(() => backend.updateConfig({ daily_limits: { weekly: { [day]: { minutes: next || 120, unlimited: next === 0 } } } }));
    };
    return (
      <PanelSection title={t("weekly")}>
        {WEEKDAYS.map((day) => {
          const entry = weekly[day];
          const label = entry?.unlimited ? t("unlimited") : `${entry?.minutes ?? 0} ${selectedLanguage === "es" ? "min" : "min"}`;
          const weekday = new Intl.DateTimeFormat(selectedLanguage, { weekday: "short" }).format(
            new Date(Date.UTC(2026, 6, 20 + WEEKDAYS.indexOf(day))),
          );
          return <PanelSectionRow key={day}><ButtonItem disabled={busy} onClick={() => cycle(day)}>{weekday.toUpperCase()}: {label}</ButtonItem></PanelSectionRow>;
        })}
        <Notice>{t("weeklyHint")}</Notice>
      </PanelSection>
    );
  }

  function activityView(): JSX.Element {
    const days = activity?.days ?? [];
    const games = activity?.top_games ?? [];
    const sessions = activity?.recent_sessions ?? [];
    const heatmap = activity?.heatmap ?? {};
    const heatmapDays = heatmap.days ?? days.map((day: JsonObject) => ({ ...day, buckets: [] }));
    const peak = activity?.peak;
    const dailyAverage = days.length > 0 ? Number(activity?.total_seconds ?? 0) / days.length : 0;
    const heatmapHasData = heatmapDays.some((day: JsonObject) =>
      (day.buckets ?? []).some((seconds: number) => Number(seconds) > 0),
    );
    const peakLabel = peak
      ? `${ACTIVITY_BUCKET_LABELS[Number(peak.bucket_index)] ?? "-"} · ${formatActivityDay(String(peak.day_key))}`
      : t("noActivity");

    return (
      <>
        <PanelSection title={t("activity")}>
          {!activity ? <Notice>{t("loadingActivity")}</Notice> : <>
            <ValueRow label={t("last7Days")} value={formatDuration(activity.total_seconds)} />
            <ValueRow label={t("dailyAverage")} value={formatDuration(dailyAverage)} />
            <ValueRow label={t("topGame")} value={games[0] ? String(games[0].app_name) : t("noGame")} />
            <ValueRow label={t("peakTime")} value={peakLabel} />
            <PanelSectionRow>
              <ButtonItem disabled={busy} onClick={() => void refresh()}>{t("refreshActivity")}</ButtonItem>
            </PanelSectionRow>
          </>}
          {error ? <Notice danger>{error}</Notice> : null}
        </PanelSection>
        {activity ? <PanelSection title={t("whenYouPlay")}>
          <PanelSectionRow>
            <div style={{ display: "grid", gridTemplateColumns: "48px repeat(7, minmax(0, 1fr))", gap: "4px", width: "100%" }}>
              <span />
              {heatmapDays.map((day: JsonObject) => <strong key={`header-${String(day.day_key)}`} style={{ fontSize: "11px", textAlign: "center" }}>{formatActivityDay(String(day.day_key))}</strong>)}
              {ACTIVITY_BUCKET_LABELS.map((label, bucketIndex) => <React.Fragment key={label}>
                <span style={{ alignSelf: "center", fontSize: "11px", opacity: 0.75 }}>{label}</span>
                {heatmapDays.map((day: JsonObject) => {
                  const seconds = Number(day.buckets?.[bucketIndex] ?? 0);
                  return <div
                    key={`${String(day.day_key)}-${bucketIndex}`}
                    aria-label={`${String(day.day_key)} ${label}: ${formatDuration(seconds)}`}
                    style={{
                      minHeight: "16px",
                      borderRadius: "3px",
                      background: activityCellColor(seconds, !heatmapHasData),
                    }}
                  />;
                })}
              </React.Fragment>)}
            </div>
          </PanelSectionRow>
          <PanelSectionRow>
            <div style={{ width: "100%", display: "grid", gridTemplateColumns: "48px repeat(7, minmax(0, 1fr))", gap: "4px", fontSize: "11px", opacity: 0.75 }}>
              <span />
              {heatmapDays.map((day: JsonObject) => <span key={`total-${String(day.day_key)}`} style={{ textAlign: "center" }}>{formatCompactDuration(day.total_seconds)}</span>)}
            </div>
          </PanelSectionRow>
          <Notice>{heatmapHasData ? t("darkerMeans") : t("heatmapStarts")}</Notice>
        </PanelSection> : null}
        {activity ? <PanelSection title={t("topGames")}>
          {games.length === 0 ? <Notice>{t("noGamesPeriod")}</Notice> : games.map((game: JsonObject, index: number) => (
            <ValueRow key={`${String(game.app_id ?? game.app_name)}-${index}`} label={`${index + 1}. ${String(game.app_name)}`} value={formatDuration(game.seconds)} />
          ))}
        </PanelSection> : null}
        {activity ? <PanelSection title={t("recentSessions")}>
          {sessions.length === 0 ? <Notice>{t("noCompletedSessions")}</Notice> : sessions.map((session: JsonObject) => (
            <ValueRow key={session.id} label={`${String(session.day_key)} · ${String(session.app_name)}`} value={formatDuration(session.duration_seconds)} />
          ))}
          <PanelSectionRow>
            <ButtonItem
              disabled={busy}
              onClick={() => {
                if (!clearArmed) setClearArmed(true);
                else void act(() => backend.clearHistory("PURGE_HISTORY")).then(() => setClearArmed(false));
              }}
            >
              {clearArmed ? t("confirmEraseHistory") : t("eraseHistory")}
            </ButtonItem>
          </PanelSectionRow>
        </PanelSection> : null}
      </>
    );
  }

  function settingsView(): JSX.Element {
    const configured = Number(config?.restriction?.level ?? 0);
    const forceEnabled = Boolean(config?.restriction?.force_kill_enabled);
    const targetLevel = (configured + 1) % 4;
    return (
      <PanelSection title={t("settings")}>
        <DropdownItem
          label={t("language")}
          rgOptions={[{ data: "en", label: "English" }, { data: "es", label: "Español" }]}
          selectedOption={selectedLanguage}
          onChange={(value: unknown) => {
            const next = languageFromSelection(value);
            void act(() => backend.updateConfig({ language: next }));
          }}
        />
        <ValueRow label={t("restrictionLevel")} value={String(configured)} />
        <PanelSectionRow>
          <ButtonItem
            disabled={busy}
            onClick={() => {
              if (targetLevel >= 2 && levelArmed !== targetLevel) {
                setLevelArmed(targetLevel);
                return;
              }
              void act(() => backend.updateConfig({ restriction: { level: targetLevel } })).then(() => setLevelArmed(null));
            }}
          >
            {targetLevel >= 2 && levelArmed === targetLevel
              ? t("confirmRestrictionLevel", { level: targetLevel })
              : t("setRestrictionLevel", { level: targetLevel })}
          </ButtonItem>
        </PanelSectionRow>
        <ToggleField
          label={t("desktopNotifications")}
          checked={Boolean(config?.warnings?.native_desktop_notifications)}
          onChange={(checked: boolean) => void act(() => backend.updateConfig({ warnings: { native_desktop_notifications: checked } }))}
        />
        <ValueRow label={t("forcedTermination")} value={forceEnabled ? t("enabled") : t("disabled")} />
        <PanelSectionRow>
          <ButtonItem
            disabled={busy}
            onClick={() => {
              if (forceEnabled) void act(() => backend.updateConfig({ restriction: { force_kill_enabled: false } }));
              else if (!forceArmed) setForceArmed(true);
              else void act(() => backend.updateConfig({ restriction: { force_kill_enabled: true } })).then(() => setForceArmed(false));
            }}
          >
            {forceEnabled ? t("disableForcedTermination") : forceArmed ? t("confirmForceKill") : t("enableForcedTermination")}
          </ButtonItem>
        </PanelSectionRow>
        <Notice danger>{t("ownerNotice")}</Notice>
      </PanelSection>
    );
  }

  function diagnosticsView(): JSX.Element {
    return (
      <PanelSection title={t("statusDiagnostics")}>
        <ValueRow label={t("daemon")} value={error ? t("unavailable") : t("connected")} />
        <ValueRow label={t("version")} value={String(detail?.project_version ?? "-")} />
        <ValueRow label={t("detector")} value={String(detail?.detector ?? "-")} />
        <ValueRow label={t("database")} value={String(detail?.database?.quick_check ?? "-")} />
        <ValueRow label={t("dbSchema")} value={String(detail?.database?.schema_version ?? "-")} />
        <ValueRow label={t("nativeNotifications")} value={detail?.native_notifications?.notify_send_available ? t("available") : t("unavailable")} />
        <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void refresh()}>{t("refreshDiagnostics")}</ButtonItem></PanelSectionRow>
        {error ? <Notice danger>{error}</Notice> : null}
      </PanelSection>
    );
  }

  const content = view === "summary" ? summaryView()
    : view === "timer" ? timerView()
    : view === "daily" ? dailyView()
    : view === "weekly" ? weeklyView()
    : view === "activity" ? activityView()
    : view === "settings" ? settingsView()
    : view === "diagnostics" ? diagnosticsView()
    : summaryView();

  return (
    <div style={{ minWidth: 0 }}>
      <PanelSection title={t("view")}>
        <DropdownItem
          label="Time Guardian"
          rgOptions={viewOptions(selectedLanguage)}
          selectedOption={view}
          onChange={(option: unknown) => {
            const nextView = selectedView(option);
            if (nextView) setView(nextView);
          }}
        />
      </PanelSection>
      {content}
    </div>
  );
}

function toastGuardianEvent(event: JsonObject): void {
  if (event.kind === "notification.warning") {
    const payload = event.payload ?? {};
    deckyApi.toaster.toast({
      title: payload.title ?? PLUGIN_NAME,
      body: payload.body ?? "",
      duration: payload.persistent ? 15000 : 7000,
      expiration: payload.persistent ? 24 * 60 * 60 * 1000 : 60 * 60 * 1000,
      critical: payload.urgency === "critical",
      playSound: true,
      showToast: true,
    });
  }
  if (event.kind === "enforcement.close_requested") {
    const appId = event.payload?.game?.app_id ? String(event.payload.game.app_id) : null;
    let success = false;
    let detail = t("terminateUnavailable");
    try {
      if (appId && SteamClient.Apps?.TerminateApp) {
        SteamClient.Apps.TerminateApp(appId, true);
        success = true;
        detail = t("steamCloseRequested");
      }
    } catch (error) {
      detail = error instanceof Error ? error.message : String(error);
    }
    void backend.reportEnforcement(appId, success, detail);
    deckyApi.toaster.toast({ title: t("playTimeExhausted"), body: detail, critical: true, duration: 10000, playSound: true });
  }
  if (event.kind === "restriction.activated" && event.payload?.persistent_notice_required) {
    const level = Number(event.payload?.level ?? 0);
    const reason = String(event.payload?.reason ?? "limit").replace(/_/g, " ");
    deckyApi.toaster.toast({
      title: t("playRestricted"),
      body: t("restrictionActive", { reason: displayReason(reason.replace(/ /g, "_")), level }),
      critical: true,
      duration: 15000,
      expiration: 24 * 60 * 60 * 1000,
      playSound: true,
      showToast: true,
    });
  }
}

export default function definePlugin(): JsonObject {
  const eventListener = deckyApi.addEventListener("guardian_event", (event: JsonObject) => toastGuardianEvent(event));
  let lifetimeRegistration: { unregister?: () => void; Unregister?: () => void } | undefined;
  try {
    lifetimeRegistration = SteamClient.GameSessions?.RegisterForAppLifetimeNotifications?.((notification) => {
      void backend.reportLifetime(notification.unAppID, notification.nInstanceID, notification.bRunning);
      setTimeout(() => void reportCurrentForeground(), 750);
    });
  } catch (error) {
    console.warn("Time Guardian lifetime listener unavailable", error);
  }
  void backend.heartbeat();
  void reportCurrentForeground();
  return {
    name: PLUGIN_NAME,
    titleView: <div className={staticClasses?.Title}>SteamOS Time Guardian</div>,
    content: <GuardianPanel />,
    icon: <span style={{ fontSize: "20px" }}>⏱</span>,
    onDismount(): void {
      deckyApi.removeEventListener("guardian_event", eventListener);
      lifetimeRegistration?.unregister?.();
      lifetimeRegistration?.Unregister?.();
    },
  };
}
