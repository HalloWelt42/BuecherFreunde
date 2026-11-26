<script lang="ts">
  // Kategorie bearbeiten (BF-69): links Name, Bereich, Zeichen, Farbe; rechts Beschreibung für die KI und Regeln mit Treffern.
  // Die Farbe ist die des Bereichs, bis eine eigene gewählt wird.
  import { untrack } from "svelte";
  import { kategorietreffer } from "../../../lib/api/katalog";
  import { farbeVon, regelnAus } from "../../../lib/katalog";
  import Auswahl from "../../../lib/teile/Auswahl.svelte";
  import Farbwahl from "../../../lib/teile/Farbwahl.svelte";
  import Fenster from "../../../lib/teile/Fenster.svelte";
  import Haekchen from "../../../lib/teile/Haekchen.svelte";
  import Knopf from "../../../lib/teile/Knopf.svelte";
  import Symbol from "../../../lib/teile/Symbol.svelte";
  import Symbolwahl from "../../../lib/teile/Symbolwahl.svelte";
  import type { Katalogbereich, Kategorietreffer } from "../../../lib/typen";
  import Regeln from "./Regeln.svelte";
  import { pflege, type Kategoriefelder, type Kategoriestelle } from "./pflege.svelte";

  let { stelle, bereich, onschliessen }: { stelle: Kategoriestelle | null; bereich: Katalogbereich; onschliessen: () => void } = $props();

  const gespeichert = untrack(() => regelnAus(stelle?.kategorie.regeln));
  let felder = $state<Kategoriefelder>(
    untrack(() => {
      const k = stelle?.kategorie;
      return { name: k?.name ?? "", zeichen: k?.zeichen ?? "", farbe: k ? farbeVon(k, bereich) : bereich.farbe, ki_beschreibung: k?.ki_beschreibung ?? "", regeln: gespeichert, verborgen: !!k?.verborgen };
    }),
  );
  let ziel = $state(untrack(() => bereich.schluessel));
  let treffer = $state<Kategorietreffer | null>(null);
  let laeuft = $state(false);

  let zielbereich = $derived(pflege.bereiche.find((b) => b.schluessel === ziel) ?? bereich);
  let bereichswahl = $derived<[string, string][]>(pflege.bereiche.map((b) => [b.schluessel, b.name]));

  // Treffer zählt der Server nur im gültigen Katalog
  $effect(() => {
    const id = stelle?.kategorie.id;
    if (id === undefined || pflege.entwurf) return;
    void kategorietreffer(id).then((t) => (treffer = t), () => (treffer = null));
  });

  function waehleBereich(schluessel: string) {
    // Folgt die Farbe dem alten Bereich, folgt sie auch dem neuen
    const neu = pflege.bereiche.find((b) => b.schluessel === schluessel);
    if (neu && felder.farbe.toLowerCase() === zielbereich.farbe.toLowerCase()) felder.farbe = neu.farbe;
    ziel = schluessel;
  }

  async function speichere(e: SubmitEvent) {
    e.preventDefault();
    laeuft = true;
    const ok = await pflege.speichereKategorie(stelle, zielbereich, { ...felder, name: felder.name.trim(), ki_beschreibung: felder.ki_beschreibung.trim() });
    laeuft = false;
    if (ok) onschliessen();
  }

  async function entferne() {
    if (stelle && (await pflege.entferneKategorie(stelle))) onschliessen();
  }
</script>

<Fenster titel={stelle ? "Kategorie bearbeiten" : "Neue Kategorie"} breite="62rem" {onschliessen}>
  <form id="kategorieformular" class="kategorieformular" onsubmit={speichere}>
    <div class="links">
      <label class="feld">Name<input class="eingabe" data-fokus bind:value={felder.name} required maxlength="100" /></label>
      <div class="feld">Bereich<Auswahl name="Bereich" werte={bereichswahl} wert={ziel} onwahl={waehleBereich} /></div>
      <div class="feld">Zeichen<Symbolwahl wert={felder.zeichen ? `fa-${felder.zeichen}` : ""} farbe={felder.farbe} onwahl={(s) => (felder.zeichen = s.replace(/^fa-/, ""))} /></div>
      <div class="feld">Farbe<Farbwahl wert={felder.farbe} onwahl={(f) => (felder.farbe = f)} /></div>
    </div>
    <div class="rechts">
      <label class="feld">Beschreibung für die KI<textarea class="eingabe" rows="3" maxlength="2000" bind:value={felder.ki_beschreibung}></textarea></label>
      <div class="feld">
        <span>Regeln <span class="leise">(ein Treffer reicht, die KI sieht sich den Rest an)</span></span>
        <Regeln regeln={felder.regeln} {gespeichert} {treffer} onaendern={(r) => (felder.regeln = r)} />
      </div>
      <Haekchen text="Verborgen, nicht in der Leiste" an={felder.verborgen} onwahl={(an) => (felder.verborgen = an)} />
    </div>
  </form>
  {#snippet fuss()}
    {#if stelle}<Knopf text="Entfernen" symbol="trash" frei onclick={() => void entferne()} />{/if}
    <span class="schiebt reihe">
      <Knopf text="Abbrechen" onclick={onschliessen} />
      <button class="knopf haupt" type="submit" form="kategorieformular" disabled={laeuft || !felder.name.trim()}><Symbol name={laeuft ? "circle-notch" : "check"} dreht={laeuft} /><span>{stelle ? "Speichern" : "Anlegen"}</span></button>
    </span>
  {/snippet}
</Fenster>
