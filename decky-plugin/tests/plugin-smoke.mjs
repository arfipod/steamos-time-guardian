import { readFile } from "node:fs/promises";
import vm from "node:vm";

const source = await readFile(new URL("../dist/index.js", import.meta.url), "utf8");
if (!source.includes("SteamOS Time Guardian") || !source.includes("enforcement.close_requested")) {
  throw new Error("compiled plugin is missing required integration markers");
}
const transformed = source.replace(/export default function definePlugin/, "function definePlugin").replace(/\nexport \{[^}]+\};?\s*$/s, "");
const hooks = {
  createElement: (type, props, ...children) => ({ type, props: props ?? {}, children }),
  Fragment: "fragment",
  useCallback: (fn) => fn,
  useEffect: () => {},
  useMemo: (fn) => fn(),
  useState: (value) => [typeof value === "function" ? value() : value, () => {}],
};
const listener = () => {};
const runtime = {
  _version: 2,
  call: async () => ({}),
  addEventListener: () => listener,
  removeEventListener: () => {},
  toaster: { toast: () => ({}) },
  useQuickAccessVisible: () => false,
};
const sandbox = {
  console,
  setInterval: () => 1,
  clearInterval: () => {},
  setTimeout: () => 1,
  SP_REACT: hooks,
  DFL: {
    ButtonItem: "ButtonItem",
    DropdownItem: "DropdownItem",
    PanelSection: "PanelSection",
    PanelSectionRow: "PanelSectionRow",
    ToggleField: "ToggleField",
    Router: {},
    staticClasses: { Title: "title" },
  },
  SteamClient: { GameSessions: {}, Apps: {} },
  window: {
    __DECKY_SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED_deckyLoaderAPIInit: {
      connect: () => runtime,
    },
  },
};
vm.createContext(sandbox);
vm.runInContext(`${transformed}\nthis.__plugin = definePlugin();`, sandbox);
if (sandbox.__plugin?.name !== "SteamOS Time Guardian" || typeof sandbox.__plugin?.onDismount !== "function") {
  throw new Error("Decky plugin factory smoke test failed");
}
console.log("Decky plugin smoke test passed");
