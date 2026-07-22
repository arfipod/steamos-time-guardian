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
const VIEW_OPTIONS = [
  { data: "summary", label: "Summary" },
  { data: "timer", label: "Timer" },
  { data: "daily", label: "Daily limit" },
  { data: "weekly", label: "Weekly schedule" },
  { data: "history", label: "History" },
  { data: "settings", label: "Settings" },
  { data: "diagnostics", label: "Diagnostics" },
] as const;

type ViewName = (typeof VIEW_OPTIONS)[number]["data"];
type JsonObject = Record<string, any>;

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
  history: () => deckyApi.call<JsonObject>("history_list", 30),
  clearHistory: (confirmation: string) => deckyApi.call<JsonObject>("history_clear", confirmation),
  weekly: () => deckyApi.call<JsonObject>("weekly_summary"),
  diagnostics: () => deckyApi.call<JsonObject>("get_diagnostics"),
  heartbeat: () => deckyApi.call<JsonObject>("heartbeat"),
  reportForeground: (running: boolean, appId: string | null, name: string) =>
    deckyApi.call<JsonObject>("report_foreground", running, appId, name),
  reportLifetime: (appId: number, instanceId: number, running: boolean) =>
    deckyApi.call<JsonObject>("report_lifetime", appId, instanceId, running),
  reportEnforcement: (appId: string | null, success: boolean, detail: string) =>
    deckyApi.call<JsonObject>("report_enforcement", appId, success, detail),
};

function formatDuration(value: number | null | undefined): string {
  if (value === null) return "Unlimited";
  const total = Math.max(0, Math.floor(Number(value ?? 0)));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60);
  const seconds = total % 60;
  return hours > 0
    ? `${hours}h ${String(minutes).padStart(2, "0")}m`
    : `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

function currentSteamApp(): { running: boolean; appId: string | null; name: string } {
  const app = DFL.Router?.MainRunningApp;
  if (!app) return { running: false, appId: null, name: "" };
  return {
    running: true,
    appId: app.appid === undefined || app.appid === null ? null : String(app.appid),
    name: app.display_name || app.sort_as || `Steam App ${String(app.appid ?? "unknown")}`,
  };
}

async function reportCurrentForeground(): Promise<void> {
  const app = currentSteamApp();
  try {
    await backend.reportForeground(app.running, app.appId, app.name || "No foreground game");
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
  const [view, setView] = React.useState<ViewName>("summary");
  const [status, setStatus] = React.useState<JsonObject | null>(null);
  const [config, setConfig] = React.useState<JsonObject | null>(null);
  const [detail, setDetail] = React.useState<JsonObject | null>(null);
  const [error, setError] = React.useState<string>("");
  const [busy, setBusy] = React.useState(false);
  const [clearArmed, setClearArmed] = React.useState(false);
  const [forceArmed, setForceArmed] = React.useState(false);
  const [levelArmed, setLevelArmed] = React.useState<number | null>(null);
  const visible = deckyApi.useQuickAccessVisible ? deckyApi.useQuickAccessVisible() : true;

  const refresh = React.useCallback(async () => {
    try {
      const [nextStatus, nextConfig] = await Promise.all([backend.status(), backend.config()]);
      setStatus(nextStatus);
      setConfig(nextConfig);
      setError("");
      if (view === "history") setDetail(await backend.history());
      else if (view === "weekly") setDetail(await backend.weekly());
      else if (view === "diagnostics") setDetail(await backend.diagnostics());
      else setDetail(null);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : String(caught));
    }
  }, [view]);

  React.useEffect(() => {
    if (!visible) return;
    void backend.heartbeat();
    void reportCurrentForeground();
    void refresh();
    const interval = setInterval(() => {
      void backend.heartbeat();
      void reportCurrentForeground();
      void refresh();
    }, 5000);
    return () => clearInterval(interval);
  }, [visible, refresh]);

  React.useEffect(() => {
    setClearArmed(false);
    setForceArmed(false);
    setLevelArmed(null);
    if (visible) void refresh();
  }, [view, visible, refresh]);

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

  function summaryView(): JSX.Element {
    const nextWarning = status?.next_warning;
    return (
      <PanelSection title="Now">
        <ValueRow label="Played today" value={formatDuration(status?.played_today_seconds)} />
        <ValueRow label="Remaining today" value={formatDuration(status?.remaining_today_seconds)} />
        <ValueRow label="Game" value={game?.name ?? "None detected"} />
        <ValueRow label="Timer" value={`${timer.state ?? "unknown"} · ${formatDuration(timer.remaining_seconds)}`} />
        <ValueRow label="Restriction" value={`Level ${restriction.effective_level ?? 0} · ${restriction.reason ?? "none"}`} />
        <ValueRow
          label="Next warning"
          value={nextWarning ? `${String(nextWarning.scope)} in ${formatDuration(nextWarning.play_seconds_until)}` : "None"}
        />
        <ValueRow label="Next reset" value={formatDuration(status?.seconds_until_reset)} />
        {error ? <Notice danger>Daemon unavailable: {error}</Notice> : <Notice>Decky is optional. Tracking continues in the user daemon when this panel is closed.</Notice>}
      </PanelSection>
    );
  }

  function timerView(): JSX.Element {
    return (
      <PanelSection title="Session timer">
        <ValueRow label="State" value={String(timer.state ?? "idle")} />
        <ValueRow label="Remaining" value={formatDuration(timer.remaining_seconds)} />
        {timer.state === "idle" || timer.state === "expired" ? (
          <PanelSectionRow><ButtonItem disabled={busy || (restriction.effective_level ?? 0) >= 1} onClick={() => void act(() => backend.startTimer(30))}>Start 30 minutes</ButtonItem></PanelSectionRow>
        ) : null}
        {timer.state === "running" ? <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(backend.pauseTimer)}>Pause</ButtonItem></PanelSectionRow> : null}
        {timer.state === "paused" ? <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(backend.resumeTimer)}>Resume</ButtonItem></PanelSectionRow> : null}
        {timer.state !== "idle" ? <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(() => backend.adjustTimer(300))}>Add 5 minutes</ButtonItem></PanelSectionRow> : null}
        {timer.state !== "idle" ? <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(() => backend.adjustTimer(-300))}>Remove 5 minutes</ButtonItem></PanelSectionRow> : null}
        {timer.state !== "idle" ? <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(backend.cancelTimer)}>Cancel timer</ButtonItem></PanelSectionRow> : null}
      </PanelSection>
    );
  }

  function dailyView(): JSX.Element {
    return (
      <PanelSection title="Daily allowance">
        <ValueRow label="Accounting day" value={String(status?.day_key ?? "-")} />
        <ValueRow label="Limit" value={formatDuration(status?.daily_limit_seconds)} />
        <ValueRow label="Exceptional time" value={formatDuration(status?.daily_adjustment_seconds)} />
        <ValueRow label="Played" value={formatDuration(status?.played_today_seconds)} />
        <ValueRow label="Remaining" value={formatDuration(status?.remaining_today_seconds)} />
        <ValueRow label="Allowed period" value={status?.within_allowed_period ? "Yes" : "No"} />
        <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void act(() => backend.grantTime(15, "Decky exceptional time"))}>Grant 15 minutes today</ButtonItem></PanelSectionRow>
      </PanelSection>
    );
  }

  function weeklyView(): JSX.Element {
    const weekly = config?.daily_limits?.weekly ?? {};
    const choices = [30, 60, 90, 120, 180, 0];
    const cycle = (day: string): void => {
      const entry = weekly[day] ?? { minutes: 120, unlimited: false };
      const current = entry.unlimited ? 0 : Number(entry.minutes);
      const index = Math.max(0, choices.indexOf(current));
      const next = choices[(index + 1) % choices.length] ?? 120;
      void act(() => backend.updateConfig({ daily_limits: { weekly: { [day]: { minutes: next || 120, unlimited: next === 0 } } } }));
    };
    return (
      <PanelSection title="Weekly schedule">
        {WEEKDAYS.map((day) => {
          const entry = weekly[day];
          const label = entry?.unlimited ? "Unlimited" : `${entry?.minutes ?? 0} min`;
          return <PanelSectionRow key={day}><ButtonItem disabled={busy} onClick={() => cycle(day)}>{day.slice(0, 3).toUpperCase()}: {label}</ButtonItem></PanelSectionRow>;
        })}
        <Notice>Press a day to cycle common limits. Detailed allowed periods remain editable in Desktop Mode.</Notice>
      </PanelSection>
    );
  }

  function historyView(): JSX.Element {
    const sessions = detail?.sessions ?? [];
    return (
      <PanelSection title="Recent history">
        {sessions.length === 0 ? <Notice>No completed sessions yet.</Notice> : sessions.slice(0, 10).map((session: JsonObject) => (
          <ValueRow key={session.id} label={`${session.day_key} · ${session.app_name}`} value={formatDuration(session.duration_seconds)} />
        ))}
        <PanelSectionRow>
          <ButtonItem
            disabled={busy}
            onClick={() => {
              if (!clearArmed) setClearArmed(true);
              else void act(() => backend.clearHistory("PURGE_HISTORY")).then(() => setClearArmed(false));
            }}
          >
            {clearArmed ? "Confirm: erase all history" : "Erase history…"}
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    );
  }

  function settingsView(): JSX.Element {
    const configured = Number(config?.restriction?.level ?? 0);
    const forceEnabled = Boolean(config?.restriction?.force_kill_enabled);
    const targetLevel = (configured + 1) % 4;
    return (
      <PanelSection title="Settings">
        <ValueRow label="Restriction level" value={String(configured)} />
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
              ? `Confirm restriction level ${targetLevel}`
              : `Set restriction level ${targetLevel}`}
          </ButtonItem>
        </PanelSectionRow>
        <ToggleField
          label="Desktop notifications"
          checked={Boolean(config?.warnings?.native_desktop_notifications)}
          onChange={(checked: boolean) => void act(() => backend.updateConfig({ warnings: { native_desktop_notifications: checked } }))}
        />
        <ValueRow label="Forced termination" value={forceEnabled ? "Enabled" : "Disabled"} />
        <PanelSectionRow>
          <ButtonItem
            disabled={busy}
            onClick={() => {
              if (forceEnabled) void act(() => backend.updateConfig({ restriction: { force_kill_enabled: false } }));
              else if (!forceArmed) setForceArmed(true);
              else void act(() => backend.updateConfig({ restriction: { force_kill_enabled: true } })).then(() => setForceArmed(false));
            }}
          >
            {forceEnabled ? "Disable forced termination" : forceArmed ? "Confirm enabling SIGKILL fallback" : "Enable forced termination…"}
          </ButtonItem>
        </PanelSectionRow>
        <Notice danger>Local restrictions can be bypassed by the device owner. Level 3 never blocks Desktop Mode, power controls, or recovery access.</Notice>
      </PanelSection>
    );
  }

  function diagnosticsView(): JSX.Element {
    return (
      <PanelSection title="Status and diagnostics">
        <ValueRow label="Daemon" value={error ? "Unavailable" : "Connected"} />
        <ValueRow label="Version" value={String(detail?.project_version ?? "-")} />
        <ValueRow label="Detector" value={String(detail?.detector ?? "-")} />
        <ValueRow label="Database" value={String(detail?.database?.quick_check ?? "-")} />
        <ValueRow label="DB schema" value={String(detail?.database?.schema_version ?? "-")} />
        <ValueRow label="Native notifications" value={detail?.native_notifications?.notify_send_available ? "Available" : "Unavailable"} />
        <PanelSectionRow><ButtonItem disabled={busy} onClick={() => void refresh()}>Refresh diagnostics</ButtonItem></PanelSectionRow>
        {error ? <Notice danger>{error}</Notice> : null}
      </PanelSection>
    );
  }

  const content = view === "summary" ? summaryView()
    : view === "timer" ? timerView()
    : view === "daily" ? dailyView()
    : view === "weekly" ? weeklyView()
    : view === "history" ? historyView()
    : view === "settings" ? settingsView()
    : diagnosticsView();

  return (
    <div style={{ minWidth: 0 }}>
      <PanelSection title="View">
        <DropdownItem
          label="Time Guardian"
          rgOptions={VIEW_OPTIONS}
          selectedOption={view}
          onChange={(option: { data: ViewName }) => setView(option.data)}
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
    let detail = "SteamClient.Apps.TerminateApp unavailable";
    try {
      if (appId && SteamClient.Apps?.TerminateApp) {
        SteamClient.Apps.TerminateApp(appId, true);
        success = true;
        detail = "Steam close requested";
      }
    } catch (error) {
      detail = error instanceof Error ? error.message : String(error);
    }
    void backend.reportEnforcement(appId, success, detail);
    deckyApi.toaster.toast({ title: "Play time exhausted", body: detail, critical: true, duration: 10000, playSound: true });
  }
  if (event.kind === "restriction.activated" && event.payload?.persistent_notice_required) {
    const level = Number(event.payload?.level ?? 0);
    const reason = String(event.payload?.reason ?? "limit").replace(/_/g, " ");
    deckyApi.toaster.toast({
      title: "Play is currently restricted",
      body: `Reason: ${reason}. Restriction level ${level} is active.`,
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
