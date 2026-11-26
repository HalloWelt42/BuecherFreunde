<script lang="ts">
  import type { Component } from "svelte";
  import { route, matchRoute, handleLinkClick } from "./lib/router.svelte";
  import { hasToken, oeffneInhalte, onAuthError, onProfilFehlt, beiTokenWechsel, beiProfilWechsel } from "./lib/api/client";
  import { fassungVerfolgen, vielleichtNeuLaden } from "./lib/fassung.svelte";
  import { anschluesse } from "./lib/stand/anschluesse.svelte";
  import { einrichtung } from "./lib/stand/einrichtung.svelte";
  import { familie } from "./lib/stand/familie.svelte";
  import { ich } from "./lib/stand/ich.svelte";
  import { filter } from "./lib/stand/filter.svelte";
  import { schale } from "./lib/stand/schale.svelte";
  import Kulisse from "./lib/schale/Kulisse.svelte";
  import Schale from "./lib/schale/Schale.svelte";
  import Netzband from "./lib/schale/Netzband.svelte";
  import Fassungsband from "./lib/schale/Fassungsband.svelte";
  import Meldungen from "./lib/teile/Meldungen.svelte";
  import Rueckfrage from "./lib/teile/Rueckfrage.svelte";
  import Zustand from "./lib/teile/Zustand.svelte";
  import Anmeldung from "./ansichten/anmeldung/Anmeldung.svelte";
  import Autoren from "./ansichten/autoren/Autoren.svelte";
  import Autorenseite from "./ansichten/autoren/Autorenseite.svelte";
  import Bibliothek from "./ansichten/bibliothek/Bibliothek.svelte";
  import Buchseite from "./ansichten/buch/Buchseite.svelte";
  import Danke from "./ansichten/danke/Danke.svelte";
  import Einrichtung from "./ansichten/einrichtung/Einrichtung.svelte";
  import Wartungsassistent from "./ansichten/einrichtung/Wartungsassistent.svelte";
  import Profilwahl from "./ansichten/familie/Profilwahl.svelte";
  import Kinderbereich from "./ansichten/kind/Kinderbereich.svelte";
  import { nutztKinderbereich } from "./lib/kind/ich";
  import Einstellungen from "./ansichten/einstellungen/Einstellungen.svelte";
  import Hinzufuegen from "./ansichten/hinzu/Hinzufuegen.svelte";
  import Vorschau from "./ansichten/hinzu/vorschau/Vorschau.svelte";
  import Leser from "./ansichten/leser/Leser.svelte";
  import Sammlung from "./ansichten/sammlung/Sammlung.svelte";
  import Suche from "./ansichten/suche/Suche.svelte";
  import Unbekannt from "./ansichten/Unbekannt.svelte";
  import Zuordnen from "./ansichten/zuordnen/Zuordnen.svelte";
  import Begriffsliste from "./ansichten/uebersetzung/Begriffsliste.svelte";
  import Lauf from "./ansichten/uebersetzung/Lauf.svelte";
  import Pruefbericht from "./ansichten/uebersetzung/Pruefbericht.svelte";

  interface Ziel {
    muster: string;
    // Ansichten ohne Bestandteile in der Adresse brauchen params nicht
    ansicht: Component<{ params: Record<string, string> }> | Component;
    vorschau?: boolean;
    ohneLeiste?: boolean;
  }

  const ziele: Ziel[] = [
    { muster: "/", ansicht: Bibliothek, vorschau: true },
    { muster: "/book/:id/read", ansicht: Leser, ohneLeiste: true },
    { muster: "/book/:id/read/:sprache", ansicht: Leser, ohneLeiste: true },
    { muster: "/book/:id/read/format/:format", ansicht: Leser, ohneLeiste: true },
    { muster: "/book/:id/material/:mid", ansicht: Leser, ohneLeiste: true },
    { muster: "/book/:id/uebersetzung", ansicht: Lauf },
    { muster: "/book/:id/pruefbericht", ansicht: Pruefbericht },
    { muster: "/book/:id/begriffe", ansicht: Begriffsliste },
    { muster: "/book/:id", ansicht: Buchseite },
    { muster: "/authors", ansicht: Autoren },
    { muster: "/author/:id", ansicht: Autorenseite },
    { muster: "/search", ansicht: Suche, vorschau: true },
    { muster: "/collection/:id", ansicht: Sammlung, vorschau: true },
    { muster: "/zuordnen/:art/:id", ansicht: Zuordnen },
    { muster: "/import", ansicht: Hinzufuegen },
    { muster: "/import/vorschau/:id", ansicht: Vorschau },
    { muster: "/settings/einrichtung", ansicht: Wartungsassistent },
    { muster: "/settings/*", ansicht: Einstellungen },
    { muster: "/settings", ansicht: Einstellungen },
    { muster: "/danke", ansicht: Danke },
  ];

  let angemeldet = $state(hasToken());
  /**
   * Erst wenn Bilder und Ereignisströme lesen dürfen, feststeht, was angeschlossen ist, und klar ist, wer liest (BF-78:
   * "Wer liest?" oder gleich das gemerkte Profil), kommt die Bibliothek auf den Schirm.
   */
  let offen = $state(false);
  // Vor der Anmeldung fragt die Seite, ob eine neue Installation den Assistenten zeigt (BF-82); dann kommt er statt der Anmeldung
  if (hasToken()) void Promise.all([oeffneInhalte(), anschluesse.laden(), familie.starte(), einrichtung.laden()]).then(() => (offen = true));
  else void einrichtung.laden();

  let ziel = $derived.by(() => {
    for (const z of ziele) {
      const params = matchRoute(z.muster, route.path);
      if (params) return { ...z, params };
    }
    return { muster: "", ansicht: Unbekannt as Ziel["ansicht"], params: {}, vorschau: false, ohneLeiste: false };
  });

  // Die Einstellungen bleiben beim Wechsel des Reiters stehen
  let schluessel = $derived(ziel.muster.startsWith("/settings") ? "/settings" : route.path);

  filter.stelleWiederHer();

  onAuthError(() => (angemeldet = false));
  // Fehlt nur das Profil (abgelaufen, gelöscht, Gerät fest auf ein anderes), bleibt das Gerät angemeldet: neu wählen
  onProfilFehlt(() => familie.profilFehlt());

  // Nach der Anmeldung lädt die Seite an derselben Adresse neu: ein Verweis (etwa /book/12/read?page=38&q=Begriff)
  // öffnet danach genau diese Stelle
  function nachAnmeldung() {
    location.reload();
  }

  // In einem anderen Tab an- oder abgemeldet gilt auch hier
  beiTokenWechsel((token) => {
    if (token && !angemeldet) nachAnmeldung();
    else if (!token) angemeldet = false;
  });

  // Ein anderer Tab hat das Profil gewechselt: hier liest dann jemand anderes, nichts vom bisherigen Profil bleibt stehen
  beiProfilWechsel(() => location.reload());

  // Neue Fassung auf dem Server: von selbst neu laden (Start, Ortswechsel, Fenster wieder vorn)
  $effect(() => fassungVerfolgen());

  let letzterPfad = route.path;
  $effect(() => {
    if (route.path === letzterPfad) return;
    letzterPfad = route.path;
    schale.schliesseAlles();
    vielleichtNeuLaden("ortswechsel");
  });
</script>

<svelte:document onclick={handleLinkClick} />

<div class="app" bind:clientWidth={schale.breite}>
  <Kulisse />
  {#if angemeldet && offen}
    {#if familie.phase === "wahl"}
      <Profilwahl />
    {:else if familie.phase === "fehler"}
      <main class="familienfehler"><Zustand art="fehler" text={familie.fehler} onerneut={() => void familie.starte()} /></main>
    {:else if familie.phase === "bereit" && einrichtung.ersteinrichtung}
      <!-- Die Ersteinrichtung ist noch offen: der Assistent geht nach der Anmeldung am nächsten Schritt weiter -->
      <Einrichtung angemeldet />
    {:else if familie.phase === "bereit" && ich.jetzt && nutztKinderbereich(ich.jetzt)}
      <!-- Ein Kind sieht statt der Schale seinen eigenen, einfacheren Bereich -->
      <Kinderbereich ich={ich.jetzt} onverlassen={() => void familie.neuBeginnen()} />
    {:else if familie.phase === "bereit"}
      <Schale mitVorschau={!!ziel.vorschau} mitLeiste={!ziel.ohneLeiste}>
        {#key schluessel}<ziel.ansicht params={ziel.params} />{/key}
      </Schale>
    {/if}
  {:else if !angemeldet && einrichtung.geladen}
    {#if einrichtung.ersteinrichtung}<Einrichtung angemeldet={false} />{:else}<Anmeldung onerfolg={nachAnmeldung} />{/if}
  {/if}
  <Fassungsband />
  <Netzband />
  <Meldungen />
  <Rueckfrage />
</div>

<style>
  .familienfehler {
    position: relative;
    z-index: 1;
    height: 100%;
    display: grid;
    place-items: center;
    padding: 1rem;
    grid-template-columns: minmax(0, 28rem);
  }
</style>
