<script lang="ts">
  import { rueckfrage } from "../stand/rueckfrage.svelte";
  import Fenster from "./Fenster.svelte";
  import Haekchen from "./Haekchen.svelte";
  import Knopf from "./Knopf.svelte";
</script>

{#if rueckfrage.offen}
  {@const f = rueckfrage.offen}
  <Fenster titel={f.titel} breite={f.liste ? "32rem" : "28rem"} onschliessen={() => rueckfrage.antworte(false)}>
    {#if f.text}<p>{f.text}</p>{/if}
    {#if f.folgen?.length}<ul class="folgen">{#each f.folgen as folge (folge)}<li>{folge}</li>{/each}</ul>{/if}
    {#if f.liste?.eintraege.length}
      <div class="feld">
        {#if f.liste.titel}<span class="pfad">{f.liste.titel}</span>{/if}
        <ul class="mulde dateiliste">{#each f.liste.eintraege as eintrag, n (n)}<li class="pfad">{eintrag}</li>{/each}</ul>
      </div>
    {/if}
    {#if f.wahl}{@const wahl = f.wahl}<Haekchen text={wahl.text} an={wahl.an} onwahl={(an) => wahl.onwahl(an)} />{/if}
    {#snippet fuss()}
      <span class="schiebt reihe">
        <Knopf text={f.nein ?? "Abbrechen"} onclick={() => rueckfrage.antworte(false)} />
        <Knopf text={f.ja} symbol={f.symbol ?? "trash"} klasse={f.gefahr === false ? "" : "gefahr"} haupt={f.gefahr === false} onclick={() => rueckfrage.antworte(true)} />
      </span>
    {/snippet}
  </Fenster>
{/if}
