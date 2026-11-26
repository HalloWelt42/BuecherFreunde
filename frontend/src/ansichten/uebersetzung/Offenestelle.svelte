<script lang="ts">
  // Eine offene Stelle im Prüfbericht (Entwurf Abschnitt 4): Englisch und Deutsch nebeneinander, die beanstandete Stelle
  // markiert, der Befund; neu übersetzen, von Hand bearbeiten (die festen Prüfungen entscheiden) oder so annehmen
  import { ApiError } from "../../lib/api/client";
  import { aendereBlock } from "../../lib/api/uebersetzung";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { befundname, befundzeichen } from "../../lib/uebersetzung/texte";
  import type { Befund, Blockaktion, Blockantwort, OffeneStelle } from "../../lib/uebersetzung/typen";
  import Markentext from "./Markentext.svelte";

  let { stelle, fassung, onerledigt }: { stelle: OffeneStelle; fassung: number; onerledigt: (antwort: Blockantwort) => void } = $props();

  let bearbeitet = $state(false);
  let text = $state("");
  let abgelehnt = $state<Befund[]>([]);
  let arbeitet = $state<"" | Blockaktion["aktion"]>("");
  let markiert = $derived(stelle.befunde.find((b) => b.stelle)?.stelle ?? "");

  function bearbeiten() {
    text = stelle.deutsch || stelle.original;
    abgelehnt = [];
    bearbeitet = true;
  }

  async function tue(aktion: Blockaktion, gut: string) {
    arbeitet = aktion.aktion;
    try {
      const antwort = await aendereBlock(fassung, stelle.kennung, aktion);
      melde.gut(gut);
      bearbeitet = false;
      onerledigt(antwort);
    } catch (e) {
      const befunde = e instanceof ApiError && e.status === 422 ? (e.data?.befunde as Befund[] | undefined) : undefined;
      if (befunde?.length) abgelehnt = befunde;
      else melde.schlecht(e, "Nicht geändert");
    } finally {
      arbeitet = "";
    }
  }
</script>

{#snippet befundliste(liste: Befund[])}
  {#each liste as b, n (n)}
    <div class="befundzeile"><Symbol name={befundzeichen(b)} /><span><b>{befundname(b)}:</b> {b.text}</span></div>
  {/each}
{/snippet}

<article class="offenestelle platte" aria-label={stelle.ort}>
  <div class="reihe"><b>{stelle.ort}</b>{#if stelle.seite_original}<span class="leise">Seite {stelle.seite_gedruckt || stelle.seite_original} im Original</span>{/if}</div>
  <div class="stellenpaar">
    <div lang="en"><small>Englisch</small><Markentext text={stelle.original} /></div>
    {#if bearbeitet}
      <label class="feld" lang="de">Deutsch<textarea class="eingabe" bind:value={text}></textarea></label>
    {:else}
      <div lang="de"><small>Deutsch</small>{#if stelle.deutsch}<Markentext text={stelle.deutsch} stelle={markiert} />{:else}<span class="leise">keine Übersetzung</span>{/if}</div>
    {/if}
  </div>
  {#if bearbeitet && abgelehnt.length}
    <span class="marke-text warn"><Symbol name="circle-exclamation" />Der Text besteht die festen Prüfungen nicht</span>
    {@render befundliste(abgelehnt)}
  {:else}
    {@render befundliste(stelle.befunde)}
  {/if}
  <div class="reihe gleichtasten">
    {#if bearbeitet}
      <Knopf text="Speichern" symbol="check" klein haupt laeuft={arbeitet === "setzen"} gesperrt={!!arbeitet || !text.trim()} onclick={() => void tue({ aktion: "setzen", text }, "Gespeichert")} />
      <Knopf text="Abbrechen" klein gesperrt={!!arbeitet} onclick={() => (bearbeitet = false)} />
    {:else}
      <Knopf text="Neu übersetzen" symbol="rotate" klein haupt laeuft={arbeitet === "neu"} gesperrt={!!arbeitet} onclick={() => void tue({ aktion: "neu" }, "Wird neu übersetzt")} />
      <Knopf text="Bearbeiten" symbol="pen" klein gesperrt={!!arbeitet} onclick={bearbeiten} />
      <Knopf text="So annehmen" symbol="check" klein laeuft={arbeitet === "annehmen"} gesperrt={!!arbeitet || !stelle.deutsch} titel={stelle.deutsch ? undefined : "Es gibt keine Übersetzung zum Annehmen"} onclick={() => void tue({ aktion: "annehmen" }, "Angenommen")} />
    {/if}
  </div>
</article>
