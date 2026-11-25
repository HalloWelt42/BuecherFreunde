<script lang="ts">
  // Unten im Darstellungsfeld: was für jedes Format gilt und am Telefon nicht in die Leiste passt
  import { dateiUrl } from "../../lib/api/books";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Vorlesen from "./Vorlesen.svelte";
  let { sitzung }: { sitzung: Lesesitzung } = $props();

  async function vollbild() {
    sitzung.feld = "";
    await schale.vollbildUmschalten();
  }
</script>

<div class="feld werkzeuge">
  Werkzeuge
  <div class="reihe">
    <Knopf text={schale.vollbild ? "Vollbild verlassen" : "Vollbild"} symbol={schale.vollbild ? "compress" : "expand"} klein onclick={vollbild} />
    <Knopf text="Herunterladen" symbol="download" klein href={dateiUrl(sitzung.buch.id)} download={sitzung.buch.file_name || sitzung.buch.title} />
    <Knopf text="Im Browser öffnen" symbol="up-right-from-square" klein extern href={dateiUrl(sitzung.buch.id)} />
  </div>
  {#if schale.telefon}<Vorlesen {sitzung} />{/if}
</div>

<style>
  .werkzeuge {
    border-top: 1px solid var(--linie);
    padding-top: 0.75rem;
  }
</style>
