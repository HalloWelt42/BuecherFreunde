// Polyfills fuer aeltere Browser MUESSEN als erstes laufen (vor allen
// anderen Imports und vor App-/Bibliotheks-Code).
import "./lib/polyfills.js";

import "./app.css";
import App from "./App.svelte";
import { mount } from "svelte";

const app = mount(App, {
  target: document.getElementById("app"),
});

export default app;
