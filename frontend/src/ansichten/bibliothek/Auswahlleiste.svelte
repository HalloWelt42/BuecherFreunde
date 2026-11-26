<script lang="ts">
  // Stapelaktionen für die gewählten Bücher
  import { bulkAction, type Sammelaktion } from "../../lib/api/books";
  import { beiEsc, schreibtGerade } from "../../lib/flucht";
  import { anzahl } from "../../lib/format";
  import { auswahl } from "../../lib/stand/auswahl.svelte";
  import { bestand } from "../../lib/stand/bestand.svelte";
  import { buecher } from "../../lib/stand/buecher.svelte";
  import { ich } from "../../lib/stand/ich.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import { wahl } from "../../lib/stand/wahl.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Menue from "../../lib/teile/Menue.svelte";
  import Regalwahl from "../../lib/teile/Regalwahl.svelte";

  const TITEL_HOECHSTENS = 5;
  let laeuft = $state(false);
  let regalOffen = $state(false);
  let regalKnopf = $state<HTMLElement | null>(null);

  let titel = $derived(buecher.liste.filter((b) => auswahl.hat(b.id)).map((b) => b.title));
  let titelkurz = $derived(titel.slice(0, TITEL_HOECHSTENS).join(", ") + (auswahl.zahl > TITEL_HOECHSTENS ? ` und ${auswahl.zahl - TITEL_HOECHSTENS} weitere` : ""));
  let leer = $derived(auswahl.zahl === 0);

  $effect(() => {
    if (!leer) return beiEsc(() => auswahl.leere());
  });

  async function tun(aktion: Sammelaktion, wert: unknown, text: string) {
    laeuft = true;
    try {
      await bulkAction(auswahl.ids, aktion, wert);
      melde.gut(text);
      bestand.geaendert();
    } catch (e) {
      melde.schlecht(e, "Nicht geändert");
    } finally {
      laeuft = false;
    }
  }

  async function entferne() {
    const n = auswahl.zahl;
    const ja = await frage({
      titel: `${anzahl(n, "Buch", "Bücher")} entfernen?`,
      text: titelkurz,
      folgen: ["Der Eintrag verschwindet aus der Bibliothek, mit Lesestand, Bewertung, Notizen und Markierungen.", "Regale und Sammlungen verlieren das Buch.", "Die Datei selbst bleibt liegen."],
      ja: n === 1 ? "Buch entfernen" : `${n} Bücher entfernen`,
    });
    if (!ja) return;
    if (wahl.buch && auswahl.hat(wahl.buch.id)) wahl.buch = null;
    await tun("loeschen", null, n === 1 ? "Buch entfernt" : `${n} Bücher entfernt`);
    auswahl.leere();
  }

  function taste(e: KeyboardEvent) {
    if (leer || schreibtGerade(e) || document.querySelector("dialog[open]")) return;
    if (e.key === "Delete" || e.key === "Backspace") {
      e.preventDefault();
      void entferne();
    }
  }
</script>

<svelte:window onkeydown={taste} />

<span class="reihe leiste-auswahl">
  <b class="zahl" title={titelkurz}>{auswahl.zahl} gewählt</b>
  <Knopf text="Alle" symbol="check-double" klein titel="Alle geladenen Bücher wählen" onclick={() => auswahl.ersetze(buecher.liste.map((b) => b.id))} />
  <Knopf text="Favorit" symbol="heart" klein gesperrt={leer || laeuft} onclick={() => void tun("favorit", true, "Als Favorit gemerkt")} />
  <Knopf text="Lesesofa" symbol="couch" klein gesperrt={leer || laeuft} onclick={() => void tun("zu_lesen", true, "Aufs Lesesofa gelegt")} />
  <Knopf text="Regal zuweisen" symbol="folder-plus" klein gesperrt={leer || laeuft} aufgeklappt={regalOffen} bind:element={regalKnopf} onclick={() => (regalOffen = !regalOffen)} />
  {#if ich.darf("loeschen")}<Knopf text="Entfernen" symbol="trash" klein gesperrt={leer || laeuft} onclick={() => void entferne()} />{/if}
  <Knopf text="Auswahl aufheben" symbol="xmark" klein frei gesperrt={leer} onclick={() => auswahl.leere()} />
</span>
{#if !leer}<span class="leise auswahltitel">{titelkurz}</span>{/if}

{#if regalOffen}
  <Menue anker={regalKnopf} name="Regal zuweisen" onschliessen={() => (regalOffen = false)}>
    <Regalwahl onwahl={(r) => { regalOffen = false; void tun("kategorie_zuweisen", r.id, `Regal ${r.name} zugewiesen`); }} />
  </Menue>
{/if}

<style>
  .leiste-auswahl {
    width: 100%;
  }
  .auswahltitel {
    width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
