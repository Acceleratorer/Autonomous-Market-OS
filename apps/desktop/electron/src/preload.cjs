"use strict";

const { contextBridge } = require("electron");

contextBridge.exposeInMainWorld("marketOsShell", Object.freeze({
  version: "u6.3",
  readOnly: true,
}));
