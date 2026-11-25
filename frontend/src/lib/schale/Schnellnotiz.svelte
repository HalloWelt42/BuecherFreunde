<script lang="ts">
  import { anzahl } from "../format";
  import { melde } from "../stand/meldungen.svelte";
  import { notizblock } from "../stand/notizblock.svelte";
  import { frage } from "../stand/rueckfrage.svelte";
  import { schale } from "../stand/schale.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Schwebefenster from "../teile/Schwebefenster.svelte";

  async function kopiere() {
    await navigator.clipboard.writeText(notizblock.text);
    melde.gut("Kopiert");
  }

  async function leere() {
    if (!notizblock.text.trim()) return;
    const ja = await frage({ titel: "Schnellnotiz leeren?", folgen: [`${anzahl(notizblock.woerter, "Wort geht", "Wörter gehen")} verloren.`], ja: "Leeren" });
    if (ja) notizblock.text = "";
  }
</script>

<Schwebefenster merkname="bf-schnellnotiz-pos" titel="Schnellnotiz" symbol="note-sticky" klasse="notizblock" onschliessen={() => (schale.notizOffen = false)}>
  {#snippet zusatz()}{#if notizblock.woerter}<span class="leise zahl">{anzahl(notizblock.woerter, "Wort", "Wörter")}</span>{/if}{/snippet}
  {#snippet knoepfe()}
    <Knopf text="Alles kopieren" symbol="copy" nur klein frei onclick={kopiere} />
    <Knopf text="Leeren" symbol="trash-can" nur klein frei onclick={leere} />
  {/snippet}
  <textarea id="schnellnotiz" aria-label="Notiz" placeholder="Hier schreiben, gemerkt in diesem Browser" spellcheck="false" bind:value={notizblock.text}></textarea>
</Schwebefenster>
