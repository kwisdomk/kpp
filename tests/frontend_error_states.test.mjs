import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import Module, { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import test from "node:test";
import ts from "typescript";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { accessErrorForStatus, errorForPath, errorStates, isWorkspaceRole } from "../src/errorStates.ts";

// Render the actual TSX with installed React. No browser or backend is simulated.
function loadComponent(relativePath, overrides = {}) {
  const filename = fileURLToPath(new URL(relativePath, import.meta.url));
  const source = readFileSync(filename, "utf8")
    .replace("import.meta.env.VITE_API_BASE_URL", '"http://localhost:8080/api/v1"');
  const compiled = ts.transpileModule(source, {
    compilerOptions: { jsx: ts.JsxEmit.ReactJSX, module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023 },
  }).outputText;
  const loaded = new Module(filename);
  const localRequire = createRequire(filename);
  loaded.require = (name) => {
    if (Object.hasOwn(overrides, name)) return overrides[name];
    if (name.endsWith(".css")) return {};
    if (name.endsWith("errorStates")) return localRequire(`${name}.ts`);
    return localRequire(name);
  };
  loaded._compile(compiled, filename);
  return loaded.exports.default;
}

const ErrorPage = loadComponent("../src/components/ErrorPage.tsx");

test("existing entry paths remain valid, including trailing slashes", () => {
  for (const path of ["/", "/login", "/chat", "/chat/", "/login/"]) assert.equal(errorForPath(path), null);
});

test("unknown nested URLs have a not-found view rather than opening the workspace", () => {
  for (const path of ["/404", "/missing", "/sources/private-record", "/chat/unrecognized"]) {
    assert.equal(errorForPath(path), "not_found");
  }
});

test("permission, missing-role and expired-session URLs remain distinct", () => {
  assert.equal(errorForPath("/access-denied"), "forbidden");
  assert.equal(errorForPath("/403/"), "forbidden");
  assert.equal(errorForPath("/role-required"), "role_required");
  assert.equal(errorForPath("/session-expired"), "session_expired");
});

test("resource 404 and recoverable media/server failures do not imply permission denial", () => {
  assert.equal(accessErrorForStatus(401), "session_expired");
  assert.equal(accessErrorForStatus(403), "forbidden");
  for (const status of [404, 413, 415, 422, 429, 500, 503]) assert.equal(accessErrorForStatus(status), null);
});

test("only the two supported server roles select a workspace", () => {
  assert.equal(isWorkspaceRole("customer"), true);
  assert.equal(isWorkspaceRole("engineer"), true);
  for (const role of [undefined, null, "", "admin", "Engineer", { role: "engineer" }]) {
    assert.equal(isWorkspaceRole(role), false);
  }
});

test("all recovery views render one heading, a status note and an internal recovery link", () => {
  for (const kind of Object.keys(errorStates)) {
    const markup = renderToStaticMarkup(React.createElement(ErrorPage, { kind }));
    assert.equal((markup.match(/<h1\b/g) || []).length, 1);
    assert.match(markup, /aria-labelledby="recovery-heading"/);
    assert.match(markup, /aria-label="Workspace status"/);
    assert.match(markup, /href="\/(?:login)?"/);
    assert.doesNotMatch(markup, /wisdom@|kOS|clearance|Choose your workspace|Request access/);
  }
});

test("permission recovery exposes no protected resource or role-escalation control", () => {
  const markup = renderToStaticMarkup(React.createElement(ErrorPage, { kind: "forbidden", onSignIn() {} }));
  assert.match(markup, /Use another account/);
  assert.doesNotMatch(markup, /Select a role|Become an engineer|restricted service manual|supplier cost/);
});

test("a saved client engineer role cannot render protected workspace before server verification", () => {
  const savedWindow = globalThis.window;
  const savedStorage = Object.getOwnPropertyDescriptor(globalThis, "localStorage");
  try {
    globalThis.window = { location: { pathname: "/" } };
    Object.defineProperty(globalThis, "localStorage", { configurable: true, value: {
      getItem(key) {
        if (key === "ai-interface-session") return JSON.stringify({ token: "test-only-token", expiresAt: Date.now() + 60000 });
        if (key === "ai-interface-role") return "engineer";
        return null;
      },
      removeItem() {},
    } });
    const App = loadComponent("../src/App.tsx", { "./components/ErrorPage": { default: ErrorPage }, "./media": {} });
    const markup = renderToStaticMarkup(React.createElement(App));
    assert.match(markup, /Checking your workspace/);
    assert.doesNotMatch(markup, /dashboard-sidebar|Choose your workspace|Engineer workspace/);
  } finally {
    if (savedWindow === undefined) delete globalThis.window;
    else globalThis.window = savedWindow;
    if (savedStorage === undefined) delete globalThis.localStorage;
    else Object.defineProperty(globalThis, "localStorage", savedStorage);
  }
});
