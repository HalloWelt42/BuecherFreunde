<script lang="ts">
  import type { Component } from "svelte";
  import { route, matchRoute, handleLinkClick } from "./lib/router.svelte";
  import { hasToken, oeffneInhalte, onAuthError, beiTokenWechsel } from "./lib/api/client";
  import { fassungVerfolgen, vielleichtNeuLaden } from "./lib/fassung.svelte";
  import { filter } from "./lib/stand/filter.svelte";
  import { schale } from "./lib/stand/schale.svelte";
  import Kulisse from "./lib/schale/Kulisse.svelte";
  import Schale from "./lib/schale/Schale.svelte";
  import Fassungsband from "./lib/schale/Fassungsband.svelte";
  import Meldungen from "./lib/teile/Meldungen.svelte";
  import Rueckfrage from "./lib/teile/Rueckfrage.svelte";
  import Anmeldung from "./ansichten/anmeldung/Anmeldung.svelte";
  import Autoren from "./ansichten/autoren/Autoren.svelte";
  import Autorenseite from "./ansichten/autoren/Autorenseite.svelte";
  import Bibliothek from "./ansichten/bibliothek/Bibliothek.svelte";
  import Buchseite from "./ansichten/buch/Buchseite.svelte";
  import Danke from "./ansichten/danke/Danke.svelte";
  import Einstellungen from "./ansichten/einstellungen/Einstellungen.svelte";
  import Hinzufuegen from "./ansichten/hinzu/Hinzufuegen.svelte";
  import Leser from "./ansichten/leser/Leser.svelte";
  import Sammlung from "./ansichten/sammlung/Sammlung.svelte";
  import Suche from "./ansichten/suche/Suche.svelte";
  import Unbekannt from "./ansichten/Unbekannt.svelte";

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
    { muster: "/book/:id", ansicht: Buchseite },
    { muster: "/authors", ansicht: Autoren },
    { muster: "/author/:id", ansicht: Autorenseite },
    { muster: "/search", ansicht: Suche, vorschau: true },
    { muster: "/collection/:id", ansicht: Sammlung, vorschau: true },
    { muster: "/import", ansicht: Hinzufuegen },
    { muster: "/settings/*", ansicht: Einstellungen },
    { muster: "/settings", ansicht: Einstellungen },
    { muster: "/danke", ansicht: Danke },
  ];

  let angemeldet = $state(hasToken());
  /** Erst wenn Bilder und Ereignisströme lesen dürfen, kommt die Bibliothek auf den Schirm. */
  let offen = $state(false);
  if (hasToken()) void oeffneInhalte().then(() => (offen = true));

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
    <Schale mitVorschau={!!ziel.vorschau} mitLeiste={!ziel.ohneLeiste}>
      {#key schluessel}<ziel.ansicht params={ziel.params} />{/key}
    </Schale>
  {:else if !angemeldet}
    <Anmeldung onerfolg={nachAnmeldung} />
  {/if}
  <Fassungsband />
  <Meldungen />
  <Rueckfrage />
</div>
