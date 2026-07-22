declare const SP_REACT: {
  createElement: (...args: any[]) => any;
  Fragment: any;
  useCallback: <T extends (...args: any[]) => any>(callback: T, dependencies: readonly any[]) => T;
  useEffect: (effect: () => void | (() => void), dependencies?: readonly any[]) => void;
  useMemo: <T>(factory: () => T, dependencies: readonly any[]) => T;
  useState: <T>(initial: T | (() => T)) => [T, (value: T | ((previous: T) => T)) => void];
};

declare const DFL: {
  ButtonItem: any;
  DropdownItem: any;
  PanelSection: any;
  PanelSectionRow: any;
  ToggleField: any;
  Router?: {
    MainRunningApp?: {
      appid?: string | number;
      display_name?: string;
      sort_as?: string;
    };
  };
  staticClasses?: Record<string, string>;
};

declare const SteamClient: {
  GameSessions?: {
    RegisterForAppLifetimeNotifications?: (
      callback: (notification: { unAppID: number; nInstanceID: number; bRunning: boolean }) => void,
    ) => { unregister?: () => void; Unregister?: () => void };
  };
  Apps?: {
    TerminateApp?: (appId: string, confirmed: boolean) => void;
  };
};

declare interface Window {
  __DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit?: {
    connect: (version: number, pluginName: string) => DeckyRuntimeApi;
  };
}

declare interface DeckyRuntimeApi {
  _version?: number;
  call: <T = unknown>(route: string, ...args: any[]) => Promise<T>;
  addEventListener: (event: string, callback: (...args: any[]) => void) => (...args: any[]) => void;
  removeEventListener: (event: string, callback: (...args: any[]) => void) => void;
  toaster: {
    toast: (data: Record<string, any>) => { dismiss?: () => void };
  };
  useQuickAccessVisible?: () => boolean;
}

declare namespace JSX {
  interface IntrinsicElements {
    [elementName: string]: any;
  }
  interface Element {}
  interface ElementChildrenAttribute { children: {}; }
  interface IntrinsicAttributes { key?: any; }
}
