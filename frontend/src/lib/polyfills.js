/**
 * Polyfills fuer aeltere Browser (v.a. aelteres iPad/iOS-Safari).
 *
 * Dieses Modul wird in main.js als ALLERERSTES importiert, damit die
 * Polyfills aktiv sind, bevor App-Code oder Bibliotheken laufen.
 * Grundsatz: nichts entfernen, sondern Faehigkeiten nachruesten.
 */

// URL.parse (statische Methode) gibt es erst ab Safari 18.4 / Chrome 126.
// Aeltere iPads stuerzen sonst im Router ab ("URL.parse is not a function").
if (typeof URL.parse !== "function") {
  URL.parse = function (url, base) {
    try {
      return base === undefined || base === null
        ? new URL(url)
        : new URL(url, base);
    } catch {
      return null;
    }
  };
}

// Promise.withResolvers (benoetigt von pdfjs-dist v5+), nativ erst ab
// iOS/Safari 17.4 - ohne diesen Polyfill laesst sich kein PDF oeffnen.
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

// Map.getOrInsertComputed (benoetigt von pdfjs-dist v5.5+).
if (!Map.prototype.getOrInsertComputed) {
  Map.prototype.getOrInsertComputed = function (key, callbackFn) {
    if (this.has(key)) return this.get(key);
    const value = callbackFn(key);
    this.set(key, value);
    return value;
  };
}

// navigator.clipboard ist in unsicheren Kontexten (http statt https) und auf
// aelteren Browsern undefined. Da BuecherFreunde im lokalen Netz per http
// laeuft, wuerden sonst alle "Kopieren"-Buttons abstuerzen. Fallback ueber
// das alte execCommand("copy").
(function () {
  function legacyCopy(text) {
    return new Promise((resolve, reject) => {
      try {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.top = "-1000px";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.focus();
        ta.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(ta);
        ok ? resolve() : reject(new Error("Kopieren fehlgeschlagen"));
      } catch (e) {
        reject(e);
      }
    });
  }

  if (!navigator.clipboard || typeof navigator.clipboard.writeText !== "function") {
    try {
      Object.defineProperty(navigator, "clipboard", {
        configurable: true,
        value: { writeText: legacyCopy },
      });
    } catch {
      // Falls navigator.clipboard nicht definierbar ist, ignorieren wir es
      // still - die Buttons werfen dann hoechstens einen abgefangenen Fehler.
    }
  }
})();
