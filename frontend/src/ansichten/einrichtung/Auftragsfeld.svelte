<script lang="ts">
  // Ein Auftrag der Einrichtung mit Balken, Zahl und Pause; auf Wunsch jeder Teil mit eigenem Balken (Neuaufbau, Einspielen)
  import { steuereAuftrag, type Auftragsstand } from "../../lib/api/einrichtung";
  import { auftragszahl, teilzahl } from "../../lib/einrichtung/saetze";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Balken from "../../lib/teile/Balken.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";

  interface Eigenschaften {
    auftrag: Auftragsstand;
    /** "geprüft", "Büchern fertig" */
    wort: string;
    /** Teile mit ihrem Zeichen, in dieser Folge; ohne: keine Teile */
    teile?: Record<string, string>;
    /** Steht der Name schon darüber (ein Schritt mit genau diesem Auftrag), heißt er hier nicht noch einmal */
    titel?: string;
    /** Eine eigene Zeile unter dem Balken statt "x von y" (Kopieren: Originale, Größe, Prüfsummen) */
    zeile?: string;
    onneu: (a: Auftragsstand) => void;
  }
  let { auftrag, wort, teile = {}, titel = undefined, zeile = "", onneu }: Eigenschaften = $props();

  let laeuft = $state(false);
  let steuerbar = $derived(auftrag.art !== "nachfuehren");
  let liste = $derived(auftrag.teile.filter((t) => teile[t.schluessel]));

  async function steuere(aktion: "pause" | "fortsetzen") {
    laeuft = true;
    try {
      onneu(await steuereAuftrag(auftrag.art, aktion));
    } catch (e) {
      melde.schlecht(e, aktion === "pause" ? "Keine Pause" : "Nicht fortgesetzt");
    } finally {
      laeuft = false;
    }
  }
</script>

<div class="platte ew-auftrag">
  <div class="reihe">
    <b>{titel ?? auftrag.was}</b>
    {#if steuerbar}
      <span class="schiebt">
        {#if auftrag.stand === "laeuft" || auftrag.stand === "wartet"}
          <Knopf text="Pause" symbol="pause" klein frei {laeuft} onclick={() => void steuere("pause")} />
        {:else if auftrag.stand === "pause"}
          <Knopf text="Fortsetzen" symbol="play" klein frei {laeuft} onclick={() => void steuere("fortsetzen")} />
        {/if}
      </span>
    {/if}
  </div>
  <Balken anteil={auftrag.gesamt ? auftrag.fertig / auftrag.gesamt : auftrag.stand === "fertig" ? 1 : 0} name={auftrag.was} gut={auftrag.stand === "fertig"} />
  <span class="leise zahl">{zeile || (auftrag.stand === "fertig" && !auftrag.gesamt ? "fertig" : auftragszahl(auftrag, wort))}{#if auftrag.stand === "pause"}, Pause{/if}</span>
  {#if auftrag.grund}<p class="marke-text {auftrag.stand === 'fehler' ? 'schlecht' : 'warn'}">{auftrag.grund}</p>{/if}
  {#if liste.length}
    <div class="ew-teile">
      {#each liste as t (t.schluessel)}
        <div class="ew-teil">
          <Symbol name={teile[t.schluessel]} />
          <span class="name">{t.name}</span>
          <Balken anteil={t.gesamt ? t.fertig / t.gesamt : 0} name={t.name} gut={!!t.gesamt && t.fertig >= t.gesamt} />
          <span class="leise zahl">{teilzahl(t)}</span>
        </div>
      {/each}
    </div>
  {/if}
</div>
