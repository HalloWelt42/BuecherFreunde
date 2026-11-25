<script lang="ts">
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import type { Notiz } from "../../lib/typen";
  let { sitzung, n }: { sitzung: Lesesitzung; n: Notiz } = $props();
  let ort = $derived(String(n.page_reference ?? "").trim());
</script>

<div class="stellenkarte">
  <textarea class="eingabe" rows={Math.min(8, Math.max(2, n.content.split("\n").length + 1))} aria-label="Buchnotiz" value={n.content} oninput={(e) => sitzung.aendereNotiz(n.id, e.currentTarget.value)}></textarea>
  <div class="reihe">
    {#if ort}<Knopf text={/^\d+$/.test(ort) ? `Seite ${ort}` : ort} symbol="arrow-right" klein frei onclick={() => sitzung.griffe?.zurStelle(ort, n.cfi_reference ?? "", 0)} />{/if}
    <Knopf text="Kopieren" symbol="copy" nur klein frei onclick={() => void navigator.clipboard.writeText(n.content)} />
    <Knopf text="An die Schnellnotiz anhängen" symbol="note-sticky" nur klein frei onclick={() => sitzung.anSchnellnotiz(n.content)} />
    <Knopf text="Schnellnotiz damit ersetzen" symbol="right-left" nur klein frei onclick={() => void sitzung.ersetzeSchnellnotiz(n.content)} />
    <Knopf text="Notiz löschen" symbol="trash" nur klein frei onclick={() => void sitzung.loescheNotiz(n)} />
  </div>
</div>
