<script lang="ts">
  // Ein Vorschlag (BF-69): Haken, Umschlag, Titel und Autor, Gründe als knappe Zeilen, "auch" für eine zweite Kategorie,
  // Sicherheit, Annehmen und Ablehnen
  import { zahl } from "../../../lib/format";
  import Haekchen from "../../../lib/teile/Haekchen.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Umschlag from "../../../lib/teile/Umschlag.svelte";
  import type { Katalogvorschlag } from "../../../lib/typen";
  import { auchText, einordnen, grundzeilen } from "./einordnung.svelte";

  let { vorschlag }: { vorschlag: Katalogvorschlag } = $props();

  let zeilen = $derived(grundzeilen(vorschlag));
  let arbeitet = $derived(einordnen.arbeitet.has(vorschlag.id));
  let auchAn = $derived(einordnen.auch.has(vorschlag.id));
</script>

<div class="vorschlagszeile platte" class:arbeitet>
  <span class="wahl"><Haekchen name="{vorschlag.buch.title} auswählen" an={einordnen.angehakt.has(vorschlag.id)} gesperrt={arbeitet} onwahl={(an) => einordnen.hake(vorschlag.id, an)} /></span>
  <a class="bild" href="/book/{vorschlag.buch.id}" title="{vorschlag.buch.title} öffnen"><Umschlag buch={vorschlag.buch} /></a>
  <span class="titel"><b title={vorschlag.buch.title}>{vorschlag.buch.title}</b><small>{vorschlag.buch.author}</small></span>
  <span class="grund">
    {#each zeilen as z, n (n)}<span><Symbol name={z.symbol} /><span>{z.text}</span></span>{/each}
    {#each vorschlag.auch as a (a.id)}
      <button type="button" class="auch" aria-pressed={auchAn} title={auchAn ? "Geht beim Annehmen mit" : "Beim Annehmen mitnehmen"} onclick={() => einordnen.schalteAuch(vorschlag.id)}><Symbol name={auchAn ? "check" : "plus"} /><span>{auchText(a)}</span></button>
    {/each}
  </span>
  <span class="sicher zahl">{zahl(vorschlag.sicherheit)} %</span>
  <span class="reihe tun">
    <Knopf text="Annehmen" symbol="check" nur klein frei laeuft={arbeitet} onclick={() => void einordnen.annehmen([vorschlag.id])} />
    <Knopf text="Ablehnen" symbol="xmark" nur klein frei gesperrt={arbeitet} onclick={() => void einordnen.ablehnen([vorschlag.id])} />
  </span>
</div>
