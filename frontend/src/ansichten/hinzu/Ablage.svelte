<script lang="ts">
  // Ablegefläche und Dateiwahl
  import { lies, merke } from "../../lib/speicher";
  import { annahme } from "../../lib/stand/annahme.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Haekchen from "../../lib/teile/Haekchen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { brauchbar, gezogeneDateien } from "./dateien";

  const SCHLUESSEL = "annahme.anreichern";
  let feld: HTMLInputElement | undefined = $state();
  let ueber = $state(false);
  let ergaenzen = $state(lies(SCHLUESSEL) === "1");

  function setzeErgaenzen(an: boolean) {
    ergaenzen = an;
    merke(SCHLUESSEL, an ? "1" : "");
  }

  function nimm(dateien: File[]) {
    if (dateien.length) annahme.nimmAn(dateien, ergaenzen);
    else melde.info("Keine Datei dabei");
  }

  export function waehle() {
    feld?.click();
  }

  function gewaehlt() {
    nimm(brauchbar(feld?.files ?? []));
    if (feld) feld.value = "";
  }

  async function abgelegt(e: DragEvent) {
    ueber = false;
    if (e.dataTransfer) nimm(await gezogeneDateien(e.dataTransfer));
  }

  const mitDateien = (e: DragEvent) => !!e.dataTransfer?.types.includes("Files");
</script>

<!-- Ablegen geht überall im Fenster, solange diese Ansicht offen ist -->
<svelte:window
  ondragover={(e) => { if (mitDateien(e)) { e.preventDefault(); ueber = true; } }}
  ondragleave={(e) => { if (!e.relatedTarget) ueber = false; }}
  ondrop={(e) => { if (mitDateien(e)) { e.preventDefault(); void abgelegt(e); } }}
/>

<section class="ablage" class:ueber>
  <Symbol name="cloud-arrow-up" />
  <div>
    <b>Bücher hierher ziehen</b>
    <p class="leise">PDF, EPUB, MOBI, TXT und MD, auch ganze Ordner. Vor dem Hochladen wird geprüft, ob es das Buch schon gibt.</p>
    <Haekchen text="Danach Angaben aus Verzeichnissen ergänzen" an={ergaenzen} onwahl={setzeErgaenzen} />
  </div>
  <Knopf text="Dateien wählen" symbol="plus" haupt onclick={waehle} />
  <input type="file" multiple accept=".pdf,.epub,.mobi,.txt,.md" hidden bind:this={feld} onchange={gewaehlt} />
</section>

<style>
  .ueber {
    background: var(--messing-hauch);
    outline-color: var(--messing);
  }
</style>
