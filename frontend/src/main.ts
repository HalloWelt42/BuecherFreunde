// Nachrüstungen für ältere Browser zuerst, vor allem anderen Code
import "./lib/polyfills.js";

import "@fontsource/barlow/400.css";
import "@fontsource/barlow/500.css";
import "@fontsource/barlow/600.css";
import "@fontsource/barlow/700.css";
import "@fontsource/literata/400.css";
import "@fontsource/literata/400-italic.css";
import "@fontsource/literata/600.css";
import "@fontsource/literata/700.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/700.css";
import "@fortawesome/fontawesome-free/css/fontawesome.css";
import "@fortawesome/fontawesome-free/css/solid.css";
import "@fortawesome/fontawesome-free/css/brands.css";
import "./stil/index.css";

import { mount } from "svelte";
import App from "./App.svelte";
import { darstellung } from "./lib/stand/darstellung.svelte";

darstellung.anwenden();

// Hülle ohne Netz; nur über https und im gebauten Stand
if (import.meta.env.PROD && "serviceWorker" in navigator) addEventListener("load", () => void navigator.serviceWorker.register("/sw.js").catch(() => undefined));

export default mount(App, { target: document.getElementById("app")! });
