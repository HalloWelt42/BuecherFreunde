<script lang="ts">
  // Eine Datei Begleitmaterial (BF-81): Art, Name und Größe; Öffnen in der App oder Herunterladen, Umbenennen in der Zeile,
  // Entfernen nach der Folgenvorschau. Am Telefon stehen die Tasten als Zeichen in gleich breiten Feldern.
  import { materialDatei, type Material } from "../../lib/api/material";
  import { groesse } from "../../lib/format";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { namensteile, type Materialstand } from "./material.svelte";

  let { m, stand, darfUmbenennen, darfEntfernen }: { m: Material; stand: Materialstand; darfUmbenennen: boolean; darfEntfernen: boolean } = $props();

  let teile = $derived(namensteile(m.name));
  let benennt = $derived(stand.benennt === m.id);
  let entwurf = $state("");
  let mitTasten = $derived(darfUmbenennen || darfEntfernen);

  function beginne() {
    entwurf = teile.stamm;
    stand.benennt = m.id;
  }

  function fokus(feld: HTMLInputElement) {
    feld.focus();
    feld.select();
  }

  function taste(e: KeyboardEvent) {
    if (e.key === "Enter") {
      e.preventDefault();
      void stand.umbenennen(m, entwurf);
    } else if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      stand.benennt = "";
    }
  }
</script>

{#if benennt}
  <div class="materialzeile umbenennen">
    <span class="dateizeichen"><Symbol name={m.zeichen} /></span>
    <span class="namensfeld"><input class="eingabe" bind:value={entwurf} aria-label="Neuer Name" maxlength="200" onkeydown={taste} use:fokus />{#if teile.endung}<span class="leise">{teile.endung}</span>{/if}</span>
    <span class="zweinur">
      <Knopf text="Speichern" symbol="check" nur klein haupt gesperrt={!entwurf.trim()} laeuft={stand.arbeitet} onclick={() => void stand.umbenennen(m, entwurf)} />
      <Knopf text="Abbrechen" symbol="xmark" nur klein frei onclick={() => (stand.benennt = "")} />
    </span>
  </div>
{:else}
  <div class="materialzeile" class:ohne-tasten={!mitTasten}>
    <span class="dateizeichen"><Symbol name={m.zeichen} /></span>
    <span class="name"><b>{m.name}</b><small>{m.art_name}, {groesse(m.groesse)}</small></span>
    <span class="tun">
      {#if m.oeffnen}
        <Knopf text="Öffnen" symbol="eye" klein href="/book/{m.buch_id}/material/{encodeURIComponent(m.id)}" titel="{m.name} in der App öffnen" />
      {:else}
        <Knopf text="Herunterladen" symbol="download" klein href={materialDatei(m.buch_id, m.id, true)} download={m.name} titel="{m.name} herunterladen" />
      {/if}
    </span>
    {#if mitTasten}
      <Knopf text="{m.name} umbenennen" symbol="pen" nur klein frei gesperrt={!darfUmbenennen || stand.arbeitet || !!stand.benennt} onclick={beginne} />
      <Knopf text="{m.name} entfernen" symbol="trash" nur klein frei gesperrt={!darfEntfernen || stand.arbeitet} onclick={() => void stand.entfernen(m)} />
    {/if}
  </div>
{/if}
