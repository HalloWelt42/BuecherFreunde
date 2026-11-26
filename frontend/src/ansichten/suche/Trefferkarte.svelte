<script lang="ts">
  // Rahmen eines Treffers: Umschlag, Titel, Auszug, rechts Art und Sprung. Ein Klick daneben zeigt das Buch in der Vorschau.
  import type { Snippet } from "svelte";
  import { holeBuch } from "../../lib/api/books";
  import { schale } from "../../lib/stand/schale.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Umschlag from "../../lib/teile/Umschlag.svelte";
  import { kontext } from "../../lib/stand/kontextmenue.svelte";
  import { buchmenue } from "../bibliothek/buchmenue";

  let { buch, titel, autor, ort, symbol, ton, wort, children, knopf }: { buch: number; titel: string; autor: string; ort: string; symbol: string; ton: "gut" | "info"; wort: string; children: Snippet; knopf: Snippet } = $props();

  async function zeige(e: MouseEvent) {
    if (!schale.mitVorschau || (e.target as Element).closest("a, button")) return;
    try {
      wahl.waehle(await holeBuch(buch));
    } catch {
      // die Vorschau bleibt beim bisherigen Buch
    }
  }
</script>

<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<article class="treffer platte" class:gewaehlt={schale.mitVorschau && wahl.buch?.id === buch} onclick={zeige} use:kontext={buchmenue(buch)}>
  <a href="/book/{buch}" aria-label={titel} tabindex="-1"><Umschlag buch={{ id: buch, title: titel, author: autor }} /></a>
  <div class="mitte">
    <h3><a href="/book/{buch}">{titel}</a></h3>
    <p class="leise">{[autor, ort].filter(Boolean).join(", ")}</p>
    {@render children()}
  </div>
  <div class="rechts"><span class="marke-text {ton}"><Symbol name={symbol} />{wort}</span>{@render knopf()}</div>
</article>

<style>
  .mitte {
    min-width: 0;
    overflow-wrap: anywhere;
  }
  h3 a {
    color: inherit;
    text-decoration: none;
  }
  h3 a:hover {
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .rechts {
    display: flex;
    flex-direction: column;
    align-items: stretch;
    gap: 0.5rem;
  }
  .gewaehlt {
    box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--messing) 55%, transparent);
  }
</style>
