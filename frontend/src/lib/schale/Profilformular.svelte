<script lang="ts">
  // Ein Profil anlegen oder ändern (BF-78): Name, Rolle, Geburtsjahr, Symbol und Farbe, dazu die PIN. Das Fenster steht
  // einmal in der Schale; der Kopf öffnet es für das eigene Profil, der Elternbereich für jedes, das man ändern darf.
  // Löschen zeigt vorher, was mit dem Profil verloren geht.
  import { untrack } from "svelte";
  import { aendereProfil, legeProfilAn, loescheProfil, profilfolgen, type Profil, type Profilangaben, type Profilfolgen, type Rolle } from "../api/familie";
  import { ROLLEN, stufeVorschlag } from "../familie";
  import { anzahl } from "../format";
  import { navigate, route } from "../router.svelte";
  import { familie } from "../stand/familie.svelte";
  import { ich } from "../stand/ich.svelte";
  import { melde } from "../stand/meldungen.svelte";
  import { profilformular, type Formularziel } from "../stand/profilformular.svelte";
  import { frage } from "../stand/rueckfrage.svelte";
  import Farbwahl from "../teile/Farbwahl.svelte";
  import Fenster from "../teile/Fenster.svelte";
  import Knopf from "../teile/Knopf.svelte";
  import Profilbild from "../teile/Profilbild.svelte";
  import Segment from "../teile/Segment.svelte";
  import Symbolwahl from "../teile/Symbolwahl.svelte";
  import Pinsetzen from "./Pinsetzen.svelte";

  let { ziel }: { ziel: Formularziel } = $props();

  /** Nach dem Anlegen bleibt das Fenster offen und zeigt das neue Profil, damit gleich die PIN folgen kann */
  let profil = $state<Profil | null>(untrack(() => ("profil" in ziel ? ziel.profil : null)));
  const ERSTE_FARBE = "#3b82f6";
  let angaben = $state(untrack(() => ({
    name: profil?.name ?? "",
    rolle: profil?.rolle ?? ("neu" in ziel ? ziel.neu : "erwachsen") as Rolle,
    geburtsjahr: profil?.geburtsjahr ? String(profil.geburtsjahr) : "",
    zeichen: profil?.zeichen ?? "",
    farbe: profil?.farbe || ERSTE_FARBE,
  })));
  let laeuft = $state(false);
  let fehler = $state("");

  let selbst = $derived(!!profil && ich.istSelbst(profil));
  let mitRolle = $derived(!profil || ich.darfRolle(profil));
  let jahr = $derived(/^\d{4}$/.test(angaben.geburtsjahr) ? Number(angaben.geburtsjahr) : null);
  let vorschlag = $derived(stufeVorschlag(jahr, familie.stufen.stufen));
  let titel = $derived(!profil ? "Neues Profil" : selbst ? "Mein Profil" : `Profil ${profil.name}`);
  let vorschau = $derived({ zeichen: angaben.zeichen, farbe: angaben.farbe });

  $effect(() => void familie.ladeStufen().catch(() => undefined));

  const schliesse = () => profilformular.schliesse();

  /** Was sich geändert hat; neu angelegt wird alles */
  function geaendert(): Profilangaben {
    const alle: Profilangaben = { name: angaben.name.trim(), zeichen: angaben.zeichen, farbe: angaben.farbe };
    if (mitRolle) alle.rolle = angaben.rolle;
    if (angaben.rolle === "kind") alle.geburtsjahr = jahr;
    // Ein Kind braucht eine Stufe: der Vorschlag aus dem Geburtsjahr, sonst die erste
    if (angaben.rolle === "kind" && !profil?.stufe) alle.stufe = vorschlag?.schluessel ?? familie.stufen.stufen[0]?.schluessel ?? null;
    if (!profil) return alle;
    const p = profil;
    return Object.fromEntries(Object.entries(alle).filter(([k, w]) => p[k as keyof Profil] !== w)) as Profilangaben;
  }

  async function speichere(e: SubmitEvent) {
    e.preventDefault();
    laeuft = true;
    fehler = "";
    try {
      if (!profil) {
        const neu = await legeProfilAn(geaendert());
        await familie.laden();
        profilformular.angelegt(neu);
        profil = neu;
        melde.gut(`Profil ${neu.name} angelegt`);
        return;
      }
      const aenderung = geaendert();
      if (Object.keys(aenderung).length) {
        const neu = await aendereProfil(profil.id, aenderung);
        ich.profilGeaendert(neu);
        await familie.laden();
        melde.gut("Gespeichert");
      }
      schliesse();
    } catch (err) {
      fehler = err instanceof Error ? err.message : String(err);
    } finally {
      laeuft = false;
    }
  }

  function pinGeaendert(neu: Profil) {
    profil = { ...profil, ...neu };
    ich.profilGeaendert(neu);
    void familie.laden();
  }

  /** Was mit dem Profil verloren geht, in Sätzen; null zählt nicht */
  function folgenText(f: Profilfolgen): string[] {
    const teile = [
      f.notizen && anzahl(f.notizen, "Notiz", "Notizen"),
      f.markierungen && anzahl(f.markierungen, "Markierung", "Markierungen"),
      f.etiketten && anzahl(f.etiketten, "Etikett", "Etiketten"),
      f.lesestaende && anzahl(f.lesestaende, "Lesestand", "Lesestände"),
      f.freigaben && anzahl(f.freigaben, "Freigabe", "Freigaben"),
    ].filter(Boolean) as string[];
    return [
      teile.length ? `Es gehen verloren: ${teile.join(", ")}.` : "Notizen, Markierungen, Etiketten, Lesestände und Freigaben hat das Profil keine.",
      ...(f.private_buecher ? [`${anzahl(f.private_buecher, "Buch verliert", "Bücher verlieren")} "Nur für mich" und ${f.private_buecher === 1 ? "ist" : "sind"} danach für alle sichtbar; die Bücher selbst bleiben.`] : []),
      "Name, Bild und PIN des Profils gehen verloren.",
    ];
  }

  async function loesche() {
    if (!profil) return;
    const p = profil;
    let folgen: Profilfolgen;
    try {
      folgen = await profilfolgen(p.id);
    } catch (e) {
      melde.schlecht(e, "Folgen nicht geladen, nichts gelöscht");
      return;
    }
    const ja = await frage({ titel: `Profil ${p.name} löschen?`, folgen: folgenText(folgen), ja: "Profil löschen" });
    if (!ja) return;
    try {
      await loescheProfil(p.id);
      await familie.laden();
      // Stand das gelöschte Profil in der Adresse des Elternbereichs, zeigt er wieder sein erstes
      if (route.path.split("/").includes(p.id)) navigate("/settings/familie", true);
      melde.gut(`Profil ${p.name} gelöscht`);
      schliesse();
    } catch (e) {
      melde.schlecht(e, "Nicht gelöscht");
    }
  }
</script>

<Fenster {titel} breite="36rem" onschliessen={schliesse}>
  <form id="profilformular" class="formular" onsubmit={speichere}>
    <div class="profilvorschau"><Profilbild profil={vorschau} groesse="3.5rem" /><b>{angaben.name.trim() || "Ohne Namen"}</b></div>
    <label class="feld">Name<input class="eingabe" data-fokus bind:value={angaben.name} required maxlength="40" /></label>
    {#if fehler}<p class="marke-text schlecht" role="alert">{fehler}</p>{/if}
    {#if mitRolle}
      <div class="feld">Rolle<span class="rollenwahl"><Segment name="Rolle" werte={ROLLEN} wert={angaben.rolle} onwahl={(w) => (angaben.rolle = w)} /></span></div>
    {/if}
    {#if angaben.rolle === "kind"}
      <label class="feld">Geburtsjahr<input class="eingabe jahr" inputmode="numeric" maxlength="4" placeholder="etwa 2018" bind:value={angaben.geburtsjahr} /></label>
      {#if vorschlag}<p class="leise">Vorschlag für die Stufe: {vorschlag.name}{profil ? "" : ". Das Profil beginnt damit."}</p>{/if}
    {/if}
    <div class="feld">Symbol<Symbolwahl wert={angaben.zeichen} farbe={angaben.farbe} onwahl={(s) => (angaben.zeichen = s)} /></div>
    <div class="feld">Farbe<Farbwahl wert={angaben.farbe} onwahl={(f) => (angaben.farbe = f)} /></div>
  </form>
  {#if profil && ich.darfPin(profil)}
    <section class="pinteil">
      <h3>{profil.rolle === "kind" ? "Bild-PIN" : "PIN"}</h3>
      {#key profil.id}<Pinsetzen {profil} ongeaendert={pinGeaendert} />{/key}
    </section>
  {/if}
  {#snippet fuss()}
    {#if profil && ich.darfLoeschen(profil)}<Knopf text="Profil löschen" symbol="trash" klasse="gefahr" onclick={() => void loesche()} />{/if}
    <span class="schiebt reihe">
      <Knopf text="Abbrechen" onclick={schliesse} />
      <button class="knopf haupt" type="submit" form="profilformular" disabled={laeuft || !angaben.name.trim()}>{profil ? "Speichern" : "Anlegen"}</button>
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
  .jahr {
    max-width: 8rem;
  }
  .pinteil {
    display: grid;
    gap: 0.5rem;
    padding-top: 0.75rem;
    border-top: 1px solid var(--linie);
  }
  h3 {
    font-size: 1rem;
    font-weight: 600;
  }
</style>
