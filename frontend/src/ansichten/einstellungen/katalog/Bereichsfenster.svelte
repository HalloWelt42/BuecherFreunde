<script lang="ts">
  // Einen Bereich anlegen oder ändern (BF-69): Name, Beschreibung, für welche Arten er gilt, Zeichen, Farbe, verborgen;
  // Entfernen nach den Folgen
  import { untrack } from "svelte";
  import { GRAUTON } from "../../../lib/katalog";
  import { arten } from "../../../lib/stand/arten.svelte";
  import Farbwahl from "../../../lib/teile/Farbwahl.svelte";
  import Fenster from "../../../lib/teile/Fenster.svelte";
  import Haekchen from "../../../lib/teile/Haekchen.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Symbolwahl from "../../../lib/teile/Symbolwahl.svelte";
  import type { Katalogbereich } from "../../../lib/typen";
  import { pflege } from "./pflege.svelte";

  let { bereich, onschliessen }: { bereich: Katalogbereich | null; onschliessen: () => void } = $props();

  // Das Fenster arbeitet auf einer Abschrift; gespeichert wird erst mit dem Knopf
  let angaben = $state(
    untrack(() => ({ name: bereich?.name ?? "", beschreibung: bereich?.beschreibung ?? "", arten: [...(bereich?.arten ?? [""])], zeichen: bereich?.zeichen ?? "", farbe: bereich?.farbe || GRAUTON, verborgen: !!bereich?.verborgen })),
  );
  let laeuft = $state(false);
  /** Buch und die Arten des Servers, dazu gewählte, die er (noch) nicht nennt */
  let artwahl = $derived([...arten.typWerte(""), ...angaben.arten.filter((a) => a && !arten.typen.some((t) => t.id === a)).map((a): [string, string] => [a, a])]);

  $effect(() => void arten.laden());

  function schalteArt(art: string, an: boolean) {
    angaben.arten = an ? [...new Set([...angaben.arten, art])] : angaben.arten.filter((a) => a !== art);
  }

  async function speichere(e: SubmitEvent) {
    e.preventDefault();
    laeuft = true;
    const ok = await pflege.speichereBereich(bereich, { ...angaben, name: angaben.name.trim(), beschreibung: angaben.beschreibung.trim() });
    laeuft = false;
    if (ok) onschliessen();
  }

  async function entferne() {
    if (bereich && (await pflege.entferneBereich(bereich))) onschliessen();
  }
</script>

<Fenster titel={bereich ? "Bereich bearbeiten" : "Neuer Bereich"} {onschliessen}>
  <form id="bereichsformular" class="formular" onsubmit={speichere}>
    <label class="feld">Name<input class="eingabe" data-fokus bind:value={angaben.name} required maxlength="100" /></label>
    <label class="feld">Beschreibung<input class="eingabe" bind:value={angaben.beschreibung} maxlength="1000" /></label>
    <div class="feld">Gilt für<div class="artenwahl" role="group" aria-label="Gilt für">{#each artwahl as [art, name] (art)}<Haekchen text={name} an={angaben.arten.includes(art)} onwahl={(an) => schalteArt(art, an)} />{/each}</div></div>
    <Haekchen text="Verborgen, nicht in der Leiste" an={angaben.verborgen} onwahl={(an) => (angaben.verborgen = an)} />
    <div class="feld">Zeichen<Symbolwahl wert={angaben.zeichen ? `fa-${angaben.zeichen}` : ""} farbe={angaben.farbe} onwahl={(s) => (angaben.zeichen = s.replace(/^fa-/, ""))} /></div>
    <div class="feld">Farbe<Farbwahl wert={angaben.farbe} onwahl={(f) => (angaben.farbe = f)} /></div>
  </form>
  {#snippet fuss()}
    {#if bereich}<Knopf text="Entfernen" symbol="trash" frei onclick={() => void entferne()} />{/if}
    <span class="schiebt reihe">
      <Knopf text="Abbrechen" onclick={onschliessen} />
      <button class="knopf haupt" type="submit" form="bereichsformular" disabled={laeuft || !angaben.name.trim() || !angaben.arten.length}><Symbol name={laeuft ? "circle-notch" : "check"} dreht={laeuft} /><span>{bereich ? "Speichern" : "Anlegen"}</span></button>
    </span>
  {/snippet}
</Fenster>
