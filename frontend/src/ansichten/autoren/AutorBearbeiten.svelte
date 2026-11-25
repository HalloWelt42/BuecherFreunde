<script lang="ts">
  // Angaben des Autors an Ort und Stelle ändern; bei einem Fehler bleiben die Eingaben stehen
  import { aktualisiereAutor, type Autoreneinzeln } from "../../lib/api/authors";
  import { beiEsc } from "../../lib/flucht";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import { aenderungen, formularVon, pruefe, type Autorformular } from "./angaben";

  let { autor, onfertig, onabbruch }: { autor: Autoreneinzeln; onfertig: (neu: Autoreneinzeln) => void; onabbruch: () => void } = $props();

  // Das Formular gehört zum Autor, mit dem das Bearbeiten begann
  // svelte-ignore state_referenced_locally
  let f = $state<Autorformular>(formularVon(autor));
  let speichert = $state(false);
  let gescheitert = $state("");
  let versucht = $state(false);

  let fehler = $derived(pruefe(f));
  let zeige = $derived(versucht ? fehler : {});

  $effect(() => beiEsc(onabbruch));

  async function speichere(e: SubmitEvent) {
    e.preventDefault();
    versucht = true;
    if (Object.keys(fehler).length) return;
    const daten = aenderungen(autor, f);
    if (!Object.keys(daten).length) {
      onabbruch();
      return;
    }
    speichert = true;
    gescheitert = "";
    try {
      onfertig(await aktualisiereAutor(autor.id, daten));
      melde.gut("Gespeichert");
    } catch (grund) {
      gescheitert = grund instanceof Error ? grund.message : String(grund);
    } finally {
      speichert = false;
    }
  }

  const felder: [keyof Autorformular, string, string, string][] = [
    ["name", "Name", "", "text"], ["nationality", "Nationalität", "Deutschland", "text"], ["birth_year", "Geburtsjahr", "JJJJ", "numeric"], ["death_year", "Todesjahr", "JJJJ", "numeric"], ["website", "Website", "https://", "url"],
  ];
</script>

<Karte titel="Autor bearbeiten" symbol="pen" breit>
  <form class="formular" onsubmit={speichere}>
    <div class="zweifeld">
      {#each felder as [k, text, platz, art] (k)}
        <label class="feld" class:ganz={k === "website"}>
          {text}
          <input class="eingabe" type="text" inputmode={art as "text" | "numeric" | "url"} placeholder={platz} maxlength={art === "numeric" ? 5 : undefined} aria-invalid={!!zeige[k]} autocomplete="off" bind:value={f[k]} />
          {#if zeige[k]}<span class="marke-text schlecht"><Symbol name="circle-exclamation" />{zeige[k]}</span>{/if}
        </label>
      {/each}
      <label class="feld ganz">Biografie, Markdown möglich<textarea class="eingabe" rows="14" bind:value={f.biography}></textarea></label>
    </div>
    {#if gescheitert}<p class="marke-text schlecht" role="alert"><Symbol name="triangle-exclamation" />Nicht gespeichert: {gescheitert}</p>{/if}
    <div class="reihe">
      <Knopf text="Speichern" symbol="check" haupt klein art="submit" laeuft={speichert} />
      <Knopf text="Abbrechen" klein onclick={onabbruch} gesperrt={speichert} />
    </div>
  </form>
</Karte>

<style>
  .formular {
    display: grid;
    gap: 0.75rem;
    grid-template-columns: minmax(0, 1fr);
  }
  .feld {
    align-content: start;
  }
  textarea {
    min-height: 14rem;
  }
</style>
