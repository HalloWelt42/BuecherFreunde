<script lang="ts">
  // Schritt Familie und Kinder: allein oder Familie, die Profile mit Rolle und PIN, dazu die Stimme der Familie. Unter Wartung
  // sind neue Profile und die Stimme nur vorgemerkt.
  import { untrack } from "svelte";
  import { setzeEinrichtungsstimme, type Schritt } from "../../lib/api/einrichtung";
  import type { Profil } from "../../lib/api/familie";
  import { rollenText } from "../../lib/familie";
  import { einrichtung } from "../../lib/stand/einrichtung.svelte";
  import { familie } from "../../lib/stand/familie.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Profilbild from "../../lib/teile/Profilbild.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Stimmwahl from "../einstellungen/familie/Stimmwahl.svelte";
  import Profilfenster from "./Profilfenster.svelte";
  import Schrittrahmen from "./Schrittrahmen.svelte";

  let { schritt }: { schritt: Schritt } = $props();

  const WER: ["allein" | "familie", string, string][] = [["allein", "Nur ich", "user"], ["familie", "Familie", "people-roof"]];
  let wer = $state<"allein" | "familie">(untrack(() => (familie.profile.length > 1 ? "familie" : "allein")));
  let fenster = $state(false);
  /** Unter Wartung: Namen der vorgemerkten Profile und die vorgemerkte Stimme */
  let vorgemerkt = $state<string[]>([]);
  let stimme = $state<string | null>(null);

  $effect(() => {
    void familie.laden().catch(() => undefined);
    void familie.ladeStufen().catch(() => undefined);
  });

  const pin = (p: Profil) => (p.rolle === "kind" ? (p.hat_bild_pin ? "Bild-PIN gesetzt" : "ohne Bild-PIN") : p.hat_pin ? "PIN gesetzt" : "ohne PIN");

  async function waehleStimme(neu: string) {
    try {
      const v = await setzeEinrichtungsstimme(neu);
      if (v.angewandt) await familie.laden();
      else stimme = neu;
    } catch (e) {
      melde.schlecht(e, "Stimme nicht gespeichert");
    }
  }
</script>

<Schrittrahmen ueberspringen={!schritt.pflicht}>
  <div class="feld">Wer liest?<span class="ew-voll"><Segment name="Wer liest" werte={WER} wert={wer} onwahl={(w) => (wer = w)} /></span></div>
  {#if wer === "familie"}
    <nav class="profilliste platte" aria-label="Profile der Familie">
      <div class="kopfzeile">Familie</div>
      {#each familie.profile as p (p.id)}
        <div class="profilzeile"><Profilbild profil={p} groesse="2.25rem" /><span>{p.name}<small>{rollenText(p, familie.stufen.stufen)}, {pin(p)}</small></span></div>
      {/each}
      {#each vorgemerkt as n, k (k)}
        <div class="profilzeile"><Profilbild profil={null} groesse="2.25rem" /><span>{n}<small>vorgemerkt, gilt erst nach dem Übernehmen</small></span></div>
      {/each}
      <Knopf text="Profil" symbol="plus" klein titel="Neues Profil" gesperrt={einrichtung.arbeitet} onclick={() => (fenster = true)} />
      <div class="elternzeile familienstimme">
        <span>Stimme der Familie<small>{stimme === null ? "spricht 'Wer liest?' und die Namen, Vorgabe für alle Kinder" : "vorgemerkt, gilt erst nach dem Übernehmen"}</small></span>
        <Stimmwahl stimme={stimme ?? familie.stimme} name="Stimme der Familie" nurSymbol onwahl={waehleStimme} />
      </div>
    </nav>
    <p class="leise">Freigaben und Lesezeit je Kind stehen danach im Elternbereich.</p>
  {:else}
    <p class="leise ew-hinweiszeile"><Symbol name="user" /><span>Nur du liest hier. Weitere Profile lassen sich jederzeit unter Einstellungen, Familie anlegen.</span></p>
  {/if}
</Schrittrahmen>

{#if fenster}<Profilfenster onschliessen={() => (fenster = false)} onvorgemerkt={(n) => (vorgemerkt = [...vorgemerkt, n])} />{/if}

<style>
  .familienstimme {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    margin-top: 0.625rem;
    padding: 0.5rem 0.5rem 0;
    border-top: 1px solid var(--linie);
  }
  .familienstimme > span:first-child {
    flex: 1 1 6rem;
  }
  .familienstimme > :global(.stimmtasten) {
    margin-left: auto;
  }
</style>
