<script lang="ts">
  // Suchfeld im Kopf und am Telefon in der Suche: Vorschläge beim Tippen, Verlauf im leeren Feld
  import type { Snippet } from "svelte";
  import { vorschlaege, type Suchvorschlag as Vorschlag } from "../api/search";
  import { beiEsc } from "../flucht";
  import { navigate } from "../router.svelte.js";
  import { suche } from "../stand/suche.svelte";
  import Symbol from "../teile/Symbol.svelte";
  import Suchvorschlaege from "./Suchvorschlaege.svelte";

  let { id, klasse = "", children = undefined }: { id: string; klasse?: string; children?: Snippet } = $props();

  const AB_ZEICHEN = 2;
  const WARTE_MS = 300;
  let wort = $state("");
  let offen = $state(false);
  let vorschlagsliste = $state<Vorschlag[]>([]);
  let gewaehlt = $state(-1);
  let uhr: ReturnType<typeof setTimeout> | undefined;

  let mitVerlauf = $derived(wort.trim() === "");
  let zeilen = $derived(mitVerlauf ? suche.verlauf.length : vorschlagsliste.length);

  // Das Feld zeigt, wonach gerade gesucht wird
  $effect(() => {
    if (suche.wort) wort = suche.wort;
  });

  $effect(() => {
    if (offen) return beiEsc(() => (offen = false));
  });

  function tippt() {
    clearTimeout(uhr);
    gewaehlt = -1;
    offen = true;
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

  function oeffne(v: Vorschlag) {
    suche.merke(wort);
    offen = false;
    navigate(`/book/${v.id}`);
  }

  function abschicken(e: SubmitEvent) {
    e.preventDefault();
    if (offen && gewaehlt >= 0 && mitVerlauf) sucheNach(suche.verlauf[gewaehlt]);
    else if (offen && gewaehlt >= 0) oeffne(vorschlagsliste[gewaehlt]);
    else sucheNach(wort);
  }

  function taste(e: KeyboardEvent) {
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    e.preventDefault();
    offen = true;
    gewaehlt = Math.max(-1, Math.min(zeilen - 1, gewaehlt + (e.key === "ArrowDown" ? 1 : -1)));
  }

  function verlassen(e: FocusEvent) {
    if (!(e.currentTarget as HTMLElement).contains(e.relatedTarget as Node | null)) offen = false;
  }
</script>

<form class="suche mulde {klasse}" role="search" onsubmit={abschicken} onfocusout={verlassen}>
  <Symbol name="magnifying-glass" />
  <input {id} type="search" bind:value={wort} placeholder="Titel, Autor, Satz oder eine Frage" aria-label="In allen Büchern suchen" autocomplete="off" enterkeyhint="search" oninput={tippt} onkeydown={taste} onfocus={() => (offen = true)} />
  {#if wort}<button type="button" class="leeren" aria-label="Suchwort leeren" title="Suchwort leeren" onclick={() => { wort = ""; tippt(); document.getElementById(id)?.focus(); }}><Symbol name="xmark" /></button>{/if}
  {@render children?.()}
  {#if offen && zeilen}
    <Suchvorschlaege verlauf={mitVerlauf ? suche.verlauf : null} vorschlaege={vorschlagsliste} {gewaehlt} onsuche={sucheNach} onoeffne={oeffne} />
  {/if}
</form>

<style>
  .suche {
    position: relative;
  }
  .suche input::-webkit-search-cancel-button {
    display: none;
  }
  .leeren {
    flex: none;
    width: 2rem;
    height: 2rem;
    display: grid;
    place-items: center;
    color: var(--tinte-3);
  }
</style>
