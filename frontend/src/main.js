// Polyfill: Map.getOrInsertComputed (benoetigt von pdfjs-dist v5.5+)
if (!Map.prototype.getOrInsertComputed) {
  Map.prototype.getOrInsertComputed = function (key, callbackFn) {
    if (this.has(key)) return this.get(key);
    const value = callbackFn(key);
    this.set(key, value);
    return value;
  };
}

// Polyfill: Promise.withResolvers (benoetigt von pdfjs-dist v5+, erst ab
// iOS/Safari 17.4 nativ vorhanden). Ohne diesen Polyfill laesst sich auf
// aelteren iPads kein PDF oeffnen.
if (typeof Promise.withResolvers !== "function") {
  Promise.withResolvers = function () {
    let resolve;
    let reject;
    const promise = new Promise((res, rej) => {
      resolve = res;
      reject = rej;
    });
    return { promise, resolve, reject };
  };
}

import "./app.css";
import App from "./App.svelte";
import { mount } from "svelte";

const app = mount(App, {
  target: document.getElementById("app"),
});

export default app;
