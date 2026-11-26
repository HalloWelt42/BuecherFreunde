<script lang="ts">
  // Taste an einer Codestelle (BF-29, Entwurf ausfuehren.html): messingfarben, wo der Code beginnt, mit dem Zeichen der
  // Sprache und der Vorprüfung als Punkt (grün: läuft für sich, sonst "Auszug" mit kurzem Grund). Ein späterer Teil nach
  // einem Seitenwechsel trägt die kleine Marke "Fortsetzung von S. n" und öffnet dasselbe Listing.
  import { SPRACHNAMEN, SPRACHSYMBOLE, istCodesprache, type Codestelle } from "../../lib/api/ausfuehren";
  import Symbol from "../../lib/teile/Symbol.svelte";

  let { stelle, weiterVon = "", fest = false, onoeffne }: { stelle: Codestelle; weiterVon?: string; fest?: boolean; onoeffne: () => void } = $props();

  let sprache = $derived(istCodesprache(stelle.sprache) ? stelle.sprache : "python");
  let v = $derived(stelle.vorpruefung);
  let auszug = $derived(v?.stand === "auszug");
  let punkt = $derived(v?.stand === "laeuft" ? "gut" : auszug ? "warn" : "");
  let pruefung = $derived(v?.stand === "laeuft" ? "Läuft für sich" : auszug ? `Auszug: ${v?.grund || "braucht mehr als dieses Listing"}${v?.fehlt.length ? ` (fehlt: ${v.fehlt.join(", ")})` : ""}` : "Noch nicht vorgeprüft");
  let wo = $derived([stelle.datei || stelle.titel, SPRACHNAMEN[sprache]].filter(Boolean).join(", "));
</script>

{#if weiterVon}
  <button type="button" class="codetaste weiter" class:fest title="Fortsetzung von Seite {weiterVon}, Listing ausführen" onclick={onoeffne}><Symbol name="arrow-turn-up" />Fortsetzung von S. {weiterVon}<Symbol name="play" /></button>
{:else}
  <button type="button" class="codetaste" class:fest title="Listing ausführen: {wo}. {pruefung}" onclick={onoeffne}>
    <Symbol name="play" />Ausführen<span class="spr" title={SPRACHNAMEN[sprache]}><Symbol name={SPRACHSYMBOLE[sprache]} art="brands" />{#if auszug}<span class="auszug">Auszug</span>{/if}</span><span class="led {punkt}" title={pruefung}></span>
  </button>
{/if}
