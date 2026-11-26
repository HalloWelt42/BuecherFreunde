<script lang="ts">
  // Karte "Fehlende Bände" im Reiter Hinzufügen (BF-75): die Suchadresse ist eine Vorlage mit Platzhaltern; ein Tipp auf einen
  // Platzhalter fügt ihn an der Schreibmarke ein, darunter steht die fertige Adresse für einen fehlenden Band (Probe des
  // Servers, merkt nichts). Gespeichert wird beim Verlassen des Felds; leer heißt: im Feld zum Band nur Kopieren.
  import { ladeSuchadresse, probiereSuchadresse, speichereSuchadresse, type Suchadresseinstellungen, type Suchprobe } from "../../lib/api/luecken";
  import { einfuegen } from "../../lib/luecken";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";

  const PROBE_NACH_MS = 400;

  let einstellungen = $state<Suchadresseinstellungen | null>(null);
  let vorlage = $state("");
  let probe = $state<Suchprobe | null>(null);
  let grund = $state("");
  let speichert = $state(false);
  let feld: HTMLInputElement | undefined = $state();

  $effect(() => {
    ladeSuchadresse()
      .then((e) => {
        einstellungen = e;
        vorlage = e.suchadresse;
      })
      .catch((e) => melde.schlecht(e, "Suchadresse nicht geladen"));
  });

  // Die Probe folgt der Eingabe nach kurzer Ruhe; ein Fehler der Vorlage steht unter dem Feld
  $effect(() => {
    const text = vorlage;
    if (!einstellungen) return;
    const uhr = setTimeout(() => {
      probiereSuchadresse(text)
        .then((p) => ((probe = p), (grund = "")))
        .catch((e) => ((probe = null), (grund = e instanceof Error ? e.message : String(e))));
    }, PROBE_NACH_MS);
    return () => clearTimeout(uhr);
  });

  async function speichere() {
    if (!einstellungen || vorlage.trim() === einstellungen.suchadresse) return;
    speichert = true;
    try {
      einstellungen = await speichereSuchadresse(vorlage.trim());
      vorlage = einstellungen.suchadresse;
      melde.gut(vorlage ? "Suchadresse gespeichert" : "Ohne Suchadresse: im Feld zum Band nur Kopieren");
    } catch (e) {
      melde.schlecht(e, "Nicht gespeichert");
    } finally {
      speichert = false;
    }
  }

  function fuegeEin(name: string) {
    const f = feld;
    const { text, marke } = einfuegen(vorlage, name, f?.selectionStart ?? vorlage.length, f?.selectionEnd ?? vorlage.length);
    vorlage = text;
    requestAnimationFrame(() => {
      f?.focus();
      f?.setSelectionRange(marke, marke);
    });
  }
</script>

<Karte titel="Fehlende Bände" symbol="puzzle-piece">
  <label class="feld">Suchadresse<input class="eingabe suchvorlage" type="url" spellcheck="false" placeholder="https://..." bind:value={vorlage} bind:this={feld} disabled={!einstellungen || speichert} onchange={() => void speichere()} /></label>
  {#if grund}<p class="marke-text warn"><Symbol name="triangle-exclamation" />{grund}</p>{/if}
  {#if einstellungen}
    <div class="feld">
      <span>Platzhalter</span>
      <div class="platzhalterwahl">
        {#each einstellungen.platzhalter as p (p.name)}<button type="button" class="chip" title="{p.bedeutung}; an der Schreibmarke einfügen" onpointerdown={(e) => e.preventDefault()} onclick={() => fuegeEin(p.name)}>{`{${p.name}}`}</button>{/each}
      </div>
    </div>
  {/if}
  {#if probe?.adresse && probe.luecke}
    <div class="mulde suchprobe">
      <span class="leise">Band {probe.luecke.nummer} der {probe.sammlung}</span>
      <code class="pfad">{probe.adresse}</code>
      <Knopf text="Ausprobieren" symbol="arrow-up-right-from-square" klein href={probe.adresse} extern />
    </div>
  {:else if vorlage.trim() && !grund && probe}
    <p class="leise">Noch kein fehlender Band, an dem sich die Adresse zeigen ließe.</p>
  {/if}
  <p class="leise">Leer: im Feld nur Kopieren.</p>
</Karte>
