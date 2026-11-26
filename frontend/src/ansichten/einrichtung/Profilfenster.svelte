<script lang="ts">
  // Ein neues Profil im Schritt Familie: Name, Rolle, für Kinder Geburtsjahr und Stufe, Symbol und Farbe. Auf einer neuen
  // Installation gilt es sofort, dann folgt gleich die PIN oder Bild-PIN; unter Wartung ist es nur vorgemerkt.
  import { legeEinrichtungsprofilAn } from "../../lib/api/einrichtung";
  import type { Profil, Profilangaben, Rolle, Stufe } from "../../lib/api/familie";
  import { ROLLEN, stufeVorschlag } from "../../lib/familie";
  import { familie } from "../../lib/stand/familie.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Farbwahl from "../../lib/teile/Farbwahl.svelte";
  import Fenster from "../../lib/teile/Fenster.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Profilbild from "../../lib/teile/Profilbild.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Symbolwahl from "../../lib/teile/Symbolwahl.svelte";
  import Pinsetzen from "../../lib/schale/Pinsetzen.svelte";

  let { onschliessen, onvorgemerkt }: { onschliessen: () => void; onvorgemerkt: (name: string) => void } = $props();

  let name = $state("");
  let rolle = $state<Rolle>("kind");
  let geburtsjahr = $state("");
  let stufe = $state<Stufe | "">("");
  let zeichen = $state("");
  let farbe = $state("#3b82f6");
  let laeuft = $state(false);
  let fehler = $state("");
  /** Nach dem Anlegen bleibt das Fenster offen, damit gleich die PIN folgen kann */
  let angelegt = $state<Profil | null>(null);

  $effect(() => void familie.ladeStufen().catch(() => undefined));

  let jahr = $derived(/^\d{4}$/.test(geburtsjahr) ? Number(geburtsjahr) : null);
  let vorschlag = $derived(stufeVorschlag(jahr, familie.stufen.stufen));
  let stufen = $derived(familie.stufen.stufen.map((s) => [s.schluessel, s.name] as [Stufe, string]));
  let gilt = $derived<Stufe | "">(stufe || vorschlag?.schluessel || familie.stufen.stufen[0]?.schluessel || "");

  async function lege(e: SubmitEvent) {
    e.preventDefault();
    laeuft = true;
    fehler = "";
    const angaben: Profilangaben = { name: name.trim(), rolle, zeichen, farbe, ...(rolle === "kind" ? { geburtsjahr: jahr, stufe: gilt || null } : {}) };
    try {
      const vorher = new Set(familie.profile.map((p) => p.id));
      const v = await legeEinrichtungsprofilAn(angaben);
      if (!v.angewandt) {
        onvorgemerkt(angaben.name ?? "");
        onschliessen();
        return;
      }
      await familie.laden();
      angelegt = familie.profile.find((p) => !vorher.has(p.id)) ?? null;
      melde.gut(`Profil ${angaben.name} angelegt`);
      if (!angelegt) onschliessen();
    } catch (err) {
      fehler = err instanceof Error ? err.message : String(err);
    } finally {
      laeuft = false;
    }
  }

  function pinGeaendert(p: Profil) {
    angelegt = p;
    void familie.laden();
  }
</script>

<Fenster titel={angelegt ? `Profil ${angelegt.name}` : "Neues Profil"} breite="36rem" {onschliessen}>
  {#if angelegt}
    <div class="profilvorschau"><Profilbild profil={angelegt} groesse="3.5rem" /><b>{angelegt.name}</b></div>
    <section class="pinteil">
      <h3>{angelegt.rolle === "kind" ? "Bild-PIN" : "PIN"}</h3>
      {#key angelegt.id}<Pinsetzen profil={angelegt} ongeaendert={pinGeaendert} />{/key}
    </section>
  {:else}
    <form id="einrichtungsprofil" class="formular" onsubmit={lege}>
      <div class="profilvorschau"><Profilbild profil={{ zeichen, farbe }} groesse="3.5rem" /><b>{name.trim() || "Ohne Namen"}</b></div>
      <label class="feld">Name<input class="eingabe" data-fokus bind:value={name} required maxlength="40" /></label>
      <div class="feld">Rolle<span class="rollenwahl"><Segment name="Rolle" werte={ROLLEN} wert={rolle} onwahl={(w) => (rolle = w)} /></span></div>
      {#if rolle === "kind"}
        <label class="feld">Geburtsjahr<input class="eingabe jahr" inputmode="numeric" maxlength="4" placeholder="etwa 2018" bind:value={geburtsjahr} /></label>
        {#if vorschlag}<p class="leise">Vorschlag für die Stufe: {vorschlag.name}.</p>{/if}
        {#if stufen.length}<div class="feld">Stufe<span class="stufenwahl"><Segment name="Stufe" werte={stufen} wert={gilt} onwahl={(w) => (stufe = w)} /></span></div>{/if}
      {/if}
      <div class="feld">Symbol<Symbolwahl wert={zeichen} {farbe} onwahl={(s) => (zeichen = s)} /></div>
      <div class="feld">Farbe<Farbwahl wert={farbe} onwahl={(f) => (farbe = f)} /></div>
      {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
    </form>
  {/if}
  {#snippet fuss()}
    <span class="schiebt reihe">
      {#if angelegt}
        <Knopf text="Fertig" symbol="check" haupt onclick={onschliessen} />
      {:else}
        <Knopf text="Abbrechen" onclick={onschliessen} />
        <button class="knopf haupt" type="submit" form="einrichtungsprofil" disabled={laeuft || !name.trim()}>Anlegen</button>
      {/if}
    </span>
  {/snippet}
</Fenster>

<style>
  .profilvorschau {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 1.125rem;
    overflow-wrap: anywhere;
    min-width: 0;
  }
  .rollenwahl :global(.segment) {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .stufenwahl :global(.segment) {
    flex-wrap: wrap;
  }
  .jahr {
    max-width: 8rem;
  }
  .pinteil {
    display: grid;
    gap: 0.5rem;
  }
  h3 {
    font-size: 1rem;
    font-weight: 600;
  }
</style>
