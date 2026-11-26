<script lang="ts">
  // Der wieder geöffnete Assistent in der Bühne (Einstellungen, Wartung): dieselben Schritte wie "Neu beginnen" ohne Konto.
  // Er merkt nur vor; übernommen wird am Ende, was angehakt ist.
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import { navigate } from "../../lib/router.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import Schritte from "./Schritte.svelte";

  $effect(() => void einrichtung.laden());

  async function oeffne() {
    await einrichtung.oeffne();
    navigate("/settings/einrichtung", true);
  }
</script>

<div class="werkzeug">
  <Knopf text="Wartung" symbol="arrow-left" klein href="/settings/wartung" />
  <h1>Einrichtung</h1>
  <span class="leise">ändert nur, was du bestätigst</span>
</div>
{#if einrichtung.wartung}
  <Schritte angemeldet />
{:else}
  <div class="inhalt rollen">
    {#if einrichtung.geladen}
      <Zustand text="Der Assistent ist gerade nicht geöffnet.">
        <Knopf text="Assistent öffnen" symbol="wand-magic-sparkles" klein gesperrt={einrichtung.arbeitet} onclick={() => void einrichtung.tu(oeffne, "Nicht geöffnet")} />
      </Zustand>
    {:else}
      <Zustand art="laedt" text="Einrichtung wird geholt" />
    {/if}
  </div>
{/if}
