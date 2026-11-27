<script lang="ts">
  // Suchfeld im Kopf und am Telefon in der Werkzeugzeile. Es sucht in allen Büchern (Vorschläge beim Tippen, Verlauf im
  // leeren Feld) oder filtert als Schnellfilter die offene Liste; die Taste vorn schaltet um, je Gerät gemerkt
  import { untrack, type Snippet } from "svelte";
  import { vorschlaege, type Suchvorschlag as Vorschlag } from "../api/search";
  import { beiEsc } from "../flucht";
  import { vonGesamt, zahl } from "../format";
  import { navigate } from "../router.svelte";
  import { anschluesse } from "../stand/anschluesse.svelte";
  import { schnellfilter } from "../stand/schnellfilter.svelte";
  import { suche } from "../stand/suche.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Symbol from "../teile/Symbol.svelte";
  import Suchvorschlaege from "./Suchvorschlaege.svelte";

  let { id, klasse = "", children = undefined }: { id: string; klasse?: string; children?: Snippet } = $props();

  const AB_ZEICHEN = 2;
  const WARTE_MS = 300;
  let wort = $state("");
  let offen = $state(false);
  let formular = $state<HTMLFormElement>();
  let vorschlagsliste = $state<Vorschlag[]>([]);
  let gewaehlt = $state(-1);
  let uhr: ReturnType<typeof setTimeout> | undefined;

  let ziel = $derived(schnellfilter.ziel);
  let filtert = $derived(schnellfilter.filtert);
  let mitVerlauf = $derived(!filtert && wort.trim() === "");
  // Als Schnellfilter gibt es eine Zeile: in allen Büchern suchen
  let zeilen = $derived(filtert ? Number(wort.trim() !== "") : mitVerlauf ? suche.verlauf.length : vorschlagsliste.length);
  let zaehlung = $derived.by(() => {
    if (!filtert || !ziel?.wort || ziel.treffer === null) return "";
    return ziel.gesamt === null ? zahl(ziel.treffer) : vonGesamt(ziel.treffer, ziel.gesamt);
  });
  let umschalthinweis = $derived(!ziel ? "Sucht in allen Büchern. Filtern geht in Listen" : filtert ? "Filtert die Liste. Umschalten: in allen Büchern suchen" : "Sucht in allen Büchern. Umschalten: Liste filtern");

  // Das Feld zeigt, wonach gerade gesucht wird
  $effect(() => {
    if (suche.wort) wort = suche.wort;
  });

  // Als Schnellfilter zeigt es das Wort der offenen Ansicht, jede hat ihr eigenes; ohne Liste das der Suche
  $effect(() => {
    if (schnellfilter.art !== "filtern") return;
    const soll = schnellfilter.ziel ? schnellfilter.ziel.wort : suche.wort;
    untrack(() => {
      if (wort.trim() !== soll) wort = soll;
    });
  });

  $effect(() => {
    if (offen) return beiEsc(() => (offen = false));
  });

  function tippt() {
    clearTimeout(uhr);
    gewaehlt = -1;
    offen = true;
    if (filtert) {
      vorschlagsliste = [];
      schnellfilter.tippe(wort);
      return;
    }
    const frage = wort.trim();
    if (frage.length < AB_ZEICHEN) {
      vorschlagsliste = [];
      return;
    }
    uhr = setTimeout(async () => {
      try {
        const antwort = (await vorschlaege(frage)).vorschlaege ?? [];
        if (wort.trim() === frage) vorschlagsliste = antwort;
      } catch {
        vorschlagsliste = [];
      }
    }, WARTE_MS);
  }

  function sucheNach(begriff: string) {
    clearTimeout(uhr);
    offen = false;
    wort = begriff;
    suche.suche(begriff);
  }

  /** Aus dem Schnellfilter heraus: die Ansicht behält, was getippt ist, gesucht wird in allen Büchern */
  function ueberall() {
    const begriff = wort.trim();
    if (!begriff) return;
    schnellfilter.sofort(begriff);
    sucheNach(begriff);
  }

  function oeffne(v: Vorschlag) {
    suche.merke(wort);
    offen = false;
    navigate(`/book/${v.id}`);
  }

  function abschicken(e: SubmitEvent) {
    e.preventDefault();
    if (filtert) ueberall();
    else if (offen && gewaehlt >= 0 && mitVerlauf) sucheNach(suche.verlauf[gewaehlt]);
    else if (offen && gewaehlt >= 0) oeffne(vorschlagsliste[gewaehlt]);
    else sucheNach(wort);
  }

  function taste(e: KeyboardEvent) {
    if (e.key === "Escape" && filtert) {
      // Leeren und verlassen; die Ansicht zeigt wieder alles
      e.preventDefault();
      wort = "";
      offen = false;
      schnellfilter.sofort("");
      (e.currentTarget as HTMLInputElement).blur();
      return;
    }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    offen = true;
    gewaehlt = Math.max(-1, Math.min(zeilen - 1, gewaehlt + (e.key === "ArrowDown" ? 1 : -1)));
  }

  function leeren() {
    wort = "";
    if (filtert) schnellfilter.sofort("");
    else tippt();
    document.getElementById(id)?.focus();
  }

  function schalteArt() {
    clearTimeout(uhr);
    vorschlagsliste = [];
    gewaehlt = -1;
    schnellfilter.schalte();
    // Was im Feld steht, filtert gleich die Liste
    if (schnellfilter.filtert) schnellfilter.sofort(wort);
    document.getElementById(id)?.focus();
  }

  // Die Liste schließt, wenn der Fokus wirklich woandershin geht (Tab) oder jemand außerhalb tippt. Am iPhone bekommt ein
  // angetippter Knopf keinen Fokus: das Feld verliert ihn ohne Ziel, und schlösse die Liste dabei, wäre sie weg, bevor der Tipp
  // ankommt (BF-115). Ein Verlust ohne Ziel schließt darum nicht; das tut das Tippen außerhalb.
  function verlassen(e: FocusEvent) {
    const nach = e.relatedTarget as Node | null;
    if (nach && !(e.currentTarget as HTMLElement).contains(nach)) offen = false;
  }

  // Wer das Feld verlässt, nimmt die ausstehende Frage nach Vorschlägen mit
  $effect(() => () => clearTimeout(uhr));

  $effect(() => {
    if (!offen) return;
    const draussen = (e: PointerEvent) => {
      if (!formular?.contains(e.target as Node)) offen = false;
    };
    document.addEventListener("pointerdown", draussen, true);
    return () => document.removeEventListener("pointerdown", draussen, true);
  });
</script>

<form class="suche mulde {klasse}" role="search" bind:this={formular} onsubmit={abschicken} onfocusout={verlassen}>
  <Knopf text="Liste filtern" symbol={filtert ? "filter" : "magnifying-glass"} nur klein frei klasse="feldart" gedrueckt={filtert} gesperrt={!ziel} titel={umschalthinweis} onclick={schalteArt} />
  <input {id} type="search" bind:value={wort} placeholder={filtert && ziel ? ziel.hinweis : anschluesse.jetzt.bedeutung ? "Titel, Autor, Satz oder eine Frage" : "Titel, Autor oder Satz"} aria-label={filtert ? "Liste filtern" : "In allen Büchern suchen"} autocomplete="off" enterkeyhint="search" oninput={tippt} onkeydown={taste} onfocus={() => (offen = true)} />
  {#if zaehlung}<span class="zaehlung" role="status">{zaehlung}</span>{/if}
  {#if wort}<button type="button" class="leeren" aria-label={filtert ? "Filter leeren" : "Suchwort leeren"} title={filtert ? "Filter leeren" : "Suchwort leeren"} onclick={leeren}><Symbol name="xmark" /></button>{/if}
  {#if !filtert}{@render children?.()}{/if}
  {#if offen && zeilen}
    {#if filtert}
      <Suchvorschlaege verlauf={null} vorschlaege={[]} ueberall={wort.trim()} {gewaehlt} onsuche={ueberall} onoeffne={oeffne} />
    {:else}
      <Suchvorschlaege verlauf={mitVerlauf ? suche.verlauf : null} vorschlaege={vorschlagsliste} {gewaehlt} onsuche={sucheNach} onoeffne={oeffne} />
    {/if}
  {/if}
</form>

<style>
  .suche {
    position: relative;
    padding-left: 0.25rem;
  }
  .suche input::-webkit-search-cancel-button {
    display: none;
  }
  /* Umschalter und Leeren gleich groß, am Telefon griffiger */
  .suche :global(.feldart.knopf),
  .leeren {
    flex: none;
    width: 2rem;
    height: 2rem;
  }
  .suche :global(.feldart.knopf) {
    color: var(--tinte-2);
  }
  .suche :global(.feldart.knopf[aria-pressed="true"]) {
    color: var(--messing);
  }
  @container app (max-width: 720px) {
    .suche :global(.feldart.knopf),
    .leeren {
      width: 2.375rem;
      height: 2.375rem;
    }
  }
  .zaehlung {
    flex: none;
    font-size: 0.8125rem;
    color: var(--tinte-3);
    white-space: nowrap;
    font-variant-numeric: tabular-nums;
  }
  .leeren {
    display: grid;
    place-items: center;
    color: var(--tinte-3);
  }
</style>
