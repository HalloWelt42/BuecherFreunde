<script lang="ts">
  import { anschluesse } from "../stand/anschluesse.svelte";
  import type { Snippet } from "svelte";
  import { bestand } from "../stand/bestand.svelte";
  import { annahme } from "../stand/annahme.svelte";
  import { auftraege } from "../stand/auftraege.svelte";
  import { schale } from "../stand/schale.svelte";
  import { verbindungen } from "../stand/verbindungen.svelte";
  import { werkarten } from "../stand/werkarten.svelte";
  import Auftraege from "./Auftraege.svelte";
  import Darstellungswahl from "./Darstellungswahl.svelte";
  import Konto from "./Konto.svelte";
  import Kopf from "./Kopf.svelte";
  import Leiste from "./Leiste.svelte";
  import { gespraech } from "../stand/gespraech.svelte";
  import { nachschlag } from "../stand/nachschlag.svelte";
  import Assistentenfenster from "./Assistentenfenster.svelte";
  import Nachschlagefenster from "./Nachschlagefenster.svelte";
  import Schnellnotiz from "./Schnellnotiz.svelte";
  import Kontextmenue from "../teile/Kontextmenue.svelte";
  import { kontextmenue } from "../stand/kontextmenue.svelte";
  import { ausfuehren } from "../stand/ausfuehren.svelte";
  // Editor und Debugger kommen erst, wenn jemand ausführt (BF-29); ohne Anschluss nie
  const ausfuehrfenster = () => import("./Ausfuehrfenster.svelte");
  import Schwebefeld from "./Schwebefeld.svelte";
  import Tafel from "./Tafel.svelte";
  import Vorschau from "./Vorschau.svelte";

  let { mitVorschau, mitLeiste, children }: { mitVorschau: boolean; mitLeiste: boolean; children: Snippet } = $props();

  $effect(() => {
    void bestand.laden();
    void annahme.starte();
    auftraege.starte();
    werkarten.starte();
    verbindungen.starte();
    return () => {
      annahme.halte();
      auftraege.halte();
      werkarten.halte();
      verbindungen.halte();
    };
  });

  $effect(() => {
    const ab = () => schale.vollbildAbgleichen();
    document.addEventListener("fullscreenchange", ab);
    document.addEventListener("webkitfullscreenchange", ab);
    return () => {
      document.removeEventListener("fullscreenchange", ab);
      document.removeEventListener("webkitfullscreenchange", ab);
    };
  });
</script>

<div class="schale" class:ohne-leiste={schale.leisteZu || !mitLeiste} class:ohne-vorschau={!mitVorschau} class:leiste-offen={schale.leisteOffen} class:vollbild={schale.vollbild}>
  <Kopf />
  <Leiste />
  <main class="buehne glas klar">{@render children()}</main>
  {#if mitVorschau && schale.mitVorschau}<Vorschau />{/if}
  <Tafel />
</div>

{#if schale.offen === "auftraege"}
  <Schwebefeld titel="Aufträge" breite="27rem"><Auftraege /></Schwebefeld>
{:else if schale.offen === "darstellung"}
  <Schwebefeld titel="Darstellung"><Darstellungswahl /><p class="leise hinweis">Die Regalwand entsteht aus den Farben der eigenen Umschläge. Eigene Hintergrundbilder stehen unter Einstellungen, Darstellung.</p></Schwebefeld>
{:else if schale.offen === "konto"}
  <Schwebefeld titel={anschluesse.jetzt.anmeldung === "kellerwolke" ? "Angemeldet mit der Kellerwolke" : "Konto"} breite="18rem"><Konto /></Schwebefeld>
{/if}
{#if schale.notizOffen}<Schnellnotiz />{/if}
{#if kontextmenue.offen}{#key kontextmenue.offen}<Kontextmenue />{/key}{/if}
{#if nachschlag.offen}<Nachschlagefenster />{/if}
{#if gespraech.offen}<Assistentenfenster />{/if}
{#if ausfuehren.offen && anschluesse.jetzt.ausfuehren}{#await ausfuehrfenster() then { default: Fenster }}<Fenster />{/await}{/if}

<style>
  .hinweis {
    padding-top: 0.75rem;
  }
</style>
