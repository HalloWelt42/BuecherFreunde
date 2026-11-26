<script lang="ts">
  // "Wer liest?" (BF-78, Entwurf kinder-4 Abschnitt 1): große Bilder statt Namenslisten, unten die Katze auf ihrem eigenen
  // Platz. Ein Tipp wählt; Erwachsene geben danach ihre PIN im Zahlenfeld ein, Kinder ihre Bild-PIN, ein Profil ohne PIN
  // öffnet sofort. Auf einem gebundenen Gerät steht nur das Kind da, bis die Eltern es mit ihrer PIN öffnen. Die Verwaltung
  // kommt über das Konto des Geräts auch ohne ihre PIN hinein.
  import "@fontsource/andika/400.css";
  import "@fontsource/andika/700.css";
  import { untrack } from "svelte";
  import { ApiError } from "../../lib/api/client";
  import type { Familie, Nachweis, Profil } from "../../lib/api/familie";
  import Katze from "../../lib/kind/Katze.svelte";
  import { darstellung, wahlen } from "../../lib/stand/darstellung.svelte";
  import { familie } from "../../lib/stand/familie.svelte";
  import Profilbild from "../../lib/teile/Profilbild.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Bildpinfeld from "../../lib/teile/Bildpinfeld.svelte";
  import Zahlenfeld from "../../lib/teile/Zahlenfeld.svelte";
  import PinVergessen from "./PinVergessen.svelte";

  let profile = $derived(familie.waehlbar);
  let gewaehlt = $state<Profil | null>(untrack(() => (familie.waehlbar.length === 1 ? familie.waehlbar[0] : null)));
  /** Bleibt nur ein Profil zur Wahl (die offene Wahl eines gebundenen Geräts lief ab), steht es gleich da */
  $effect(() => {
    if (profile.length === 1 && !untrack(() => gewaehlt)) gewaehlt = profile[0];
  });
  let vergessen = $state(false);
  let mitKatze = $derived(profile.some((p) => p.rolle === "kind"));
  let laeuft = $state(false);
  let versuch = $state(0);
  let fehler = $state("");
  /** Zu viele Versuche: der Server lässt warten */
  let wartet = $state(false);
  let darstellungOffen = $state(false);

  function tippe(p: Profil) {
    fehler = "";
    wartet = false;
    if (!p.hat_pin && !p.hat_bild_pin) void pruefe(p, {});
    else gewaehlt = p;
  }

  async function pruefe(p: Profil, nachweis: Nachweis) {
    laeuft = true;
    fehler = "";
    wartet = false;
    try {
      await familie.waehle(p.id, nachweis);
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
      wartet = e instanceof ApiError && e.status === 429;
      versuch += 1;
      // Etwa die offene Wahl eines gebundenen Geräts ist vorbei: was zur Wahl steht, kommt neu
      void familie.laden().catch(() => undefined);
    } finally {
      laeuft = false;
    }
  }

  function zurueck() {
    gewaehlt = null;
    fehler = "";
    wartet = false;
  }

  /** Ohne PIN öffnet das Profil sofort */
  async function ohnePin(p: Profil, f: Familie) {
    vergessen = false;
    await familie.laden(f);
    await pruefe(p, {});
  }
</script>

<main class="wer-liest" aria-label="Wer liest?">
  <header class="kopfzeile">
    {#if gewaehlt}
      <span class="wer"><Profilbild profil={gewaehlt} groesse="2.75rem" /><span class="wername">{gewaehlt.name}</span></span>
    {:else}
      <h1 class="wer">Wer liest?</h1>
    {/if}
    <span class="rechts">
      <button type="button" class="rund" aria-label="Darstellung" title="Darstellung" aria-expanded={darstellungOffen} onclick={() => (darstellungOffen = !darstellungOffen)}><Symbol name="circle-half-stroke" /></button>
      {#if gewaehlt && profile.length > 1}<button type="button" class="rund" aria-label="Zurück zur Profilwahl" title="Zurück zur Profilwahl" onclick={zurueck}><Symbol name="arrow-left" /></button>{/if}
    </span>
  </header>

  {#if darstellungOffen}
    <div class="darstellung">
      <div class="feld">Licht<Segment name="Licht" werte={wahlen.thema} wert={darstellung.thema} onwahl={(w) => (darstellung.thema = w)} /></div>
      <div class="feld">Schrift<Segment name="Schriftgröße" werte={wahlen.schrift} wert={darstellung.schrift} onwahl={(w) => (darstellung.schrift = w)} /></div>
    </div>
  {/if}

  <div class="mitte rollen">
    <div class="innen">
      {#if !gewaehlt}
        <div class="personen">
          {#each profile as p (p.id)}
            <button type="button" class="person" aria-label="{p.name}{p.hat_bild_pin ? ', mit Bild-PIN' : p.hat_pin ? ', mit PIN' : ''}" disabled={laeuft} onclick={() => tippe(p)}>
              <Profilbild profil={p} groesse="var(--bild)" />
              <span class="name">{p.name}</span>
              {#if p.hat_bild_pin}<small><Symbol name="shapes" />Bild-PIN</small>{:else if p.hat_pin}<small><Symbol name="lock" />PIN</small>{/if}
            </button>
          {/each}
        </div>
      {:else if gewaehlt.hat_bild_pin}
        {@const p = gewaehlt}
        <Bildpinfeld zugang={familie.zugang} name="Bild-PIN von {p.name}" gesperrt={laeuft || wartet} {versuch} onvoll={(bild_pin) => void pruefe(p, { bild_pin })} />
      {:else}
        {@const p = gewaehlt}
        <Zahlenfeld zugang={familie.zugang} name="PIN von {p.name}" gesperrt={laeuft || wartet} {versuch} onfertig={(pin) => void pruefe(p, { pin })} />
      {/if}
      {#if fehler && (wartet || gewaehlt?.rolle !== "kind")}
        <p class="fehlerzeile" role="alert"><Symbol name={wartet ? "hourglass-half" : "circle-xmark"} />{fehler}</p>
      {/if}
    </div>
  </div>

  {#if !gewaehlt && mitKatze}
    <!-- Die Katze hat ihren eigenen Platz unten rechts, ihre Nennung steht darunter (Entwurf Runde 4) -->
    <footer class="fuss katzenplatz"><Katze name="" groesse="7.5rem" /></footer>
  {:else if gewaehlt?.rolle === "verwaltung" && gewaehlt.hat_pin}
    <footer class="fuss"><button type="button" class="leise-taste" onclick={() => (vergessen = true)}>PIN vergessen</button></footer>
  {/if}
</main>

{#if vergessen && gewaehlt}
  {@const p = gewaehlt}
  <PinVergessen profil={p} onfertig={(f) => void ohnePin(p, f)} onschliessen={() => (vergessen = false)} />
{/if}

<style>
  /* Farben und Schrift wie der Kinderbereich im Entwurf: warmes Papier, große Flächen, Kinderschrift */
  .wer-liest {
    --k-grund: #fbf6ea;
    --k-flaeche: #ffffff;
    --k-tinte: #2b2a33;
    --k-leise: #6b6873;
    --k-linie: #e6dcc6;
    --k-haupt: #2f6fb3;
    --pin-flaeche: var(--k-flaeche);
    --pin-tinte: var(--k-tinte);
    --pin-linie: var(--k-linie);
    --pin-haupt: var(--k-haupt);
    --pin-ecke: 1rem;
    --pin-abstand: 1.5rem;
    --bild: 7.5rem;
    position: relative;
    z-index: 1;
    height: 100%;
    display: flex;
    flex-direction: column;
    background: var(--k-grund);
    color: var(--k-tinte);
    font-family: Andika, "Atkinson Hyperlegible", var(--schrift);
    container-type: inline-size;
  }
  :global(:root[data-theme="dark"]) .wer-liest {
    --k-grund: #1e2328;
    --k-flaeche: #2a3036;
    --k-tinte: #f1ede4;
    --k-leise: #b6b2aa;
    --k-linie: #3a424a;
    --k-haupt: #6fa6e0;
  }
  .kopfzeile {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: calc(1rem + env(safe-area-inset-top, 0px)) max(1.5rem, env(safe-area-inset-right, 0px)) 1rem max(1.5rem, env(safe-area-inset-left, 0px));
  }
  .wer {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 1.75rem;
    font-weight: 700;
    min-width: 0;
  }
  .wername {
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  h1.wer {
    font-size: 2.125rem;
  }
  .rechts {
    margin-left: auto;
    display: flex;
    gap: 0.75rem;
  }
  .rund {
    width: 3.25rem;
    height: 3.25rem;
    border-radius: 50%;
    display: grid;
    place-items: center;
    flex: none;
    color: var(--k-leise);
    font-size: 1.375rem;
    border: 0.1875rem solid var(--k-linie);
  }
  .rund[aria-expanded="true"] {
    color: var(--k-tinte);
    border-color: var(--k-haupt);
  }
  .darstellung {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    padding: 0 1.5rem 1rem;
    font-family: var(--schrift);
  }
  .darstellung .feld {
    color: var(--k-leise);
  }
  /* Mittig, solange es passt; wird es höher als der Schirm (große Schrift), rollt es von oben an */
  .mitte {
    /* Drei Tasten nebeneinander passen immer, auch mit großer Schrift am Telefon */
    --pin-taste: min(5.5rem, calc((100cqi - 3rem) / 3.4));
    flex: 1;
    display: flex;
    flex-direction: column;
    padding: 1rem 1.5rem;
  }
  .innen {
    margin-block: auto;
    display: grid;
    justify-items: center;
    gap: 1.5rem;
  }
  /* Gleich breite Kacheln, mittig umbrechend */
  .personen {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 2rem 1.5rem;
    max-width: 60rem;
  }
  .person {
    width: 10rem;
    display: grid;
    justify-items: center;
    align-content: start;
    gap: 0.625rem;
    padding: 0.5rem 0;
    border-radius: 1rem;
    color: inherit;
    font-family: inherit;
  }
  .person :global(.profilbild) {
    box-shadow: 0 0.375rem 0 rgb(0 0 0 / 0.15);
  }
  .person:active:not(:disabled) :global(.profilbild) {
    transform: translateY(0.25rem);
    box-shadow: 0 0.125rem 0 rgb(0 0 0 / 0.15);
  }
  .name {
    font-size: 1.5rem;
    font-weight: 700;
    line-height: 1.2;
    max-width: 100%;
    overflow-wrap: anywhere;
  }
  small {
    display: flex;
    align-items: center;
    gap: 0.375rem;
    font-size: 1rem;
    color: var(--k-leise);
  }
  .fuss {
    display: flex;
    justify-content: center;
    padding: 0 max(1.5rem, env(safe-area-inset-right, 0px)) calc(1rem + env(safe-area-inset-bottom, 0px)) max(1.5rem, env(safe-area-inset-left, 0px));
  }
  .fuss.katzenplatz {
    justify-content: flex-end;
  }
  .leise-taste {
    min-height: 2.75rem;
    padding: 0 1rem;
    border-radius: 99px;
    color: var(--k-leise);
    font-family: var(--schrift);
    font-size: 1rem;
    text-decoration: underline;
    text-decoration-color: var(--k-linie);
    text-underline-offset: 4px;
  }
  .leise-taste:hover {
    color: var(--k-tinte);
  }
  .fehlerzeile {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    max-width: 30rem;
    color: var(--schlecht);
    font-family: var(--schrift);
    font-size: 1rem;
    text-align: center;
  }
  /* Nach der Breite des Schirms; die Fläche selbst ist der Behälter, gemessen wird für alles darin */
  @container (min-width: 60rem) {
    .mitte {
      --bild: 9.5rem;
    }
    .person {
      width: 12rem;
    }
  }
  @container (max-width: 26rem) {
    .mitte {
      --bild: 6rem;
    }
    .person {
      width: 8.5rem;
    }
    .kopfzeile {
      padding-inline: 1rem;
      gap: 0.5rem;
    }
    .wer {
      font-size: 1.375rem;
    }
    h1.wer {
      font-size: 1.75rem;
    }
    .rechts {
      gap: 0.5rem;
    }
    .rund {
      width: 2.75rem;
      height: 2.75rem;
      font-size: 1.125rem;
    }
  }
</style>
