import { readFile } from "node:fs/promises";
import vm from "node:vm";

const source = await readFile(new URL("../dist/index.js", import.meta.url), "utf8");
if (
  !source.includes("SteamOS Time Guardian")
  || !source.includes("enforcement.close_requested")
  || !source.includes("activity_summary")
  || !source.includes("Idioma")
  || !source.includes("Tiempo de juego agotado")
) {
  throw new Error("compiled plugin is missing required integration markers");
}
const transformed = source.replace(/export default function definePlugin/, "function definePlugin").replace(/\nexport \{[^}]+\};?\s*$/s, "");
const state = [];
let hookIndex = 0;
const hooks = {
  createElement: (type, props, ...children) => ({ type, props: props ?? {}, children }),
  Fragment: "fragment",
  useCallback: (fn) => fn,
  useEffect: () => {},
  useMemo: (fn) => fn(),
  useState: (value) => {
    const index = hookIndex;
    hookIndex += 1;
    if (!(index in state)) state[index] = typeof value === "function" ? value() : value;
    return [state[index], (next) => {
      state[index] = typeof next === "function" ? next(state[index]) : next;
    }];
  },
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

function renderPanel() {
  hookIndex = 0;
  return sandbox.__plugin.content.type(sandbox.__plugin.content.props);
}

function walk(node, predicate) {
  if (!node) return null;
  if (predicate(node)) return node;
  for (const child of node.children ?? []) {
    if (Array.isArray(child)) {
      for (const nested of child) {
        const found = walk(nested, predicate);
        if (found) return found;
      }
    } else {
      const found = walk(child, predicate);
      if (found) return found;
    }
  }
  return null;
}

let panel = renderPanel();
const dropdown = walk(panel, (node) => node.type === "DropdownItem");
if (!dropdown?.props?.onChange) throw new Error("view selector is missing");
dropdown.props.onChange("timer");
panel = renderPanel();
if (!walk(panel, (node) => node.type === "PanelSection" && node.props.title === "Session timer")) {
  throw new Error("view selector did not accept Decky's string option value");
}
const activityDropdown = walk(panel, (node) => node.type === "DropdownItem");
activityDropdown.props.onChange({ data: "activity" });
panel = renderPanel();
if (!walk(panel, (node) => node.type === "PanelSection" && node.props.title === "Activity")) {
  throw new Error("view selector did not accept an option object");
}
state.length = 0;
panel = renderPanel();
if (!walk(panel, (node) => node.type === "PanelSection" && node.props.title === "Activity")) {
  throw new Error("view selector did not preserve the selected view across a panel remount");
}
console.log("Decky plugin smoke test passed");
