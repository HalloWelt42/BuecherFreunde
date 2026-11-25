<script lang="ts">
  // Licht, Glas, Dahinter, Schrift: im Feld unter dem Kopf und in den Einstellungen
  import { darstellung, wahlen } from "../stand/darstellung.svelte";
  import { hintergrund } from "../stand/hintergrund.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Segment from "../teile/Segment.svelte";
</script>

<div class="wahl">
  <div class="feld">Licht<Segment name="Licht" werte={wahlen.thema} wert={darstellung.thema} onwahl={(w) => (darstellung.thema = w)} /></div>
  <div class="feld">Glas<Segment name="Glas" werte={wahlen.glas} wert={darstellung.glas} onwahl={(w) => (darstellung.glas = w)} /></div>
  <div class="feld">
    Dahinter<Segment name="Hintergrund" werte={wahlen.grund} wert={darstellung.grund} onwahl={(w) => (darstellung.grund = w)} />
    {#if darstellung.grund === "bild"}
      {#if hintergrund.bilder.length > 1}
        <div class="reihe">
          <Knopf text="Voriges Bild" symbol="chevron-left" nur klein onclick={() => hintergrund.blaettere(-1)} />
          <span class="zahl">{hintergrund.nummer + 1} von {hintergrund.bilder.length}</span>
          <Knopf text="Nächstes Bild" symbol="chevron-right" nur klein onclick={() => hintergrund.blaettere(1)} />
        </div>
      {:else if !hintergrund.bilder.length}
        <span class="leise">Noch kein Bild da. <a href="/settings/darstellung">Bild hinzufügen</a></span>
      {/if}
    {/if}
  </div>
  <div class="feld">Schrift<Segment name="Schriftgröße" werte={wahlen.schrift} wert={darstellung.schrift} onwahl={(w) => (darstellung.schrift = w)} /></div>
</div>

<style>
  .wahl {
    display: grid;
    gap: 0.75rem;
    grid-template-columns: minmax(0, 1fr);
  }
  .feld {
    justify-items: start;
  }
</style>
