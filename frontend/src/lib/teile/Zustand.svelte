<script lang="ts">
  // Laden, Fehler, leer: eine Fläche für alle Ansichten
  import type { Snippet } from "svelte";
  import Symbol from "./Symbol.svelte";
  import Knopf from "./Knopf.svelte";
  let { art = "leer", text, onerneut = undefined, children = undefined }: { art?: "laedt" | "fehler" | "leer"; text: string; onerneut?: () => void; children?: Snippet } = $props();
  const zeichen = { laedt: "circle-notch", fehler: "triangle-exclamation", leer: "inbox" };
</script>

<div class="platte karte zustand" role={art === "fehler" ? "alert" : "status"}>
  <p class="reihe" class:marke-text={art === "fehler"} class:schlecht={art === "fehler"}><Symbol name={zeichen[art]} dreht={art === "laedt"} /><span>{text}</span></p>
  {#if onerneut || children}<div class="reihe">{#if onerneut}<Knopf text="Erneut versuchen" symbol="rotate-right" klein onclick={onerneut} />{/if}{@render children?.()}</div>{/if}
</div>
