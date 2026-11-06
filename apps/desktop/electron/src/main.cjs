"use strict";

const path = require("node:path");
const { app, BrowserWindow, dialog } = require("electron");
const {
  LocalRuntime,
  isAllowedLoopbackUrl,
} = require("./runtime.cjs");

const runtime = new LocalRuntime();
let mainWindow = null;
let quitting = false;

function createWindow() {
  const nextPort = runtime.nextPort;
  const allowedOrigin = `http://127.0.0.1:${nextPort}`;
  const window = new BrowserWindow({
    width: 1440,
    height: 960,
    minWidth: 320,
    minHeight: 480,
    show: false,
    backgroundColor: "#0b1117",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      webSecurity: true,
      devTools: false,
    },
  });

  const isAllowed = (url) => isAllowedLoopbackUrl(url, nextPort);
  window.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  window.webContents.on("will-navigate", (event, url) => {
    if (!isAllowed(url)) event.preventDefault();
  });
  window.webContents.on("will-redirect", (event, url) => {
    if (!isAllowed(url)) event.preventDefault();
  });
  window.once("ready-to-show", () => window.show());
  window.loadURL(`${allowedOrigin}/overview`);
  mainWindow = window;
}

async function stopAndQuit(exitCode = 0) {
  if (quitting) return;
  quitting = true;
  await runtime.stop();
  if (exitCode === 0) app.quit();
  else app.exit(exitCode);
}

app.whenReady().then(async () => {
  try {
    await runtime.start();
    createWindow();
  } catch (error) {
    const detail = error instanceof Error
      ? error.message
      : String(error);
    await dialog.showMessageBox({
      type: "error",
      title: "Market OS unavailable",
      message: "The local read-only services could not start.",
      detail: `${detail}\n\nThe shell uses loopback-only services. Close any conflicting local ports or set MARKET_OS_API_PORT and MARKET_OS_NEXT_PORT, then try again.`,
    });
    await stopAndQuit(1);
  }
});

app.on("window-all-closed", () => {
  void stopAndQuit(0);
});

app.on("before-quit", (event) => {
  if (quitting) return;
  event.preventDefault();
  void stopAndQuit(0);
});

process.on("SIGINT", () => { void stopAndQuit(0); });
process.on("SIGTERM", () => { void stopAndQuit(0); });

module.exports = { createWindow, stopAndQuit };
