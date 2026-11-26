<script lang="ts">
  // Der Kinderleser: ein Buch Seite für Seite, ohne Rollen und ohne Menüs. Oben das Buch, die Lesezeit, die schlafende Katze und
  // das Haus zurück zum Regal; in der Mitte die Seite (Bild und Text nebeneinander oder untereinander); unten gleich große Tasten,
  // nur die, die die Stufe erlaubt. Text in der Kinderdarstellung (Schrift, Größe, kurze Zeilen, Abstände aus ich.darstellung),
  // farbige Silben und Lesezeile, wenn die Eltern sie erlauben; das Kind schaltet sie selbst an und aus. Vorgelesen wird mit dem
  // Vorlesen der App, das gelesene Wort leuchtet mit. Ist die Lesezeit um, endet erst die Seite, dann kommt die Ruhe.
  import { untrack } from "svelte";
  import { holeBuch, coverUrl } from "../../lib/api/books";
  import { toggleFavorit } from "../../lib/api/user-data";
  import type { Kinderquelle } from "../../lib/kind/inhalt";
  import { Kinderlesestand } from "../../lib/kind/leser.svelte";
  import type { Lesezeituhr } from "../../lib/kind/lesezeit.svelte";
  import { Kindermarkierungen, type Kindermarkierung } from "../../lib/kind/markierungen.svelte";
  import Katze from "../../lib/kind/Katze.svelte";
  import Kinderuhr from "../../lib/kind/Kinderuhr.svelte";
  import { oeffneKinderquelle, formatVon } from "../../lib/kind/quellen";
  import type { Seitenmass } from "../../lib/kind/seiten";
  import { ladeSilbentrenner, silbentrennerBereit } from "../../lib/kind/silben";
  import { kindangabenAus, kinderlesewerte } from "../../lib/kind/stelle";
  import type { Ich, Kinderstelle, Wort } from "../../lib/kind/typen";
  import { lesewerte } from "../../lib/lesestand";
  import { buchort, Positionsspeicher } from "../../lib/leser/position";
  import { wischen } from "../../lib/leser/wischen";
  import { liesJson, merkeJson } from "../../lib/speicher";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import type { BuchEinzeln } from "../../lib/typen";
  import Buchkachel from "./Buchkachel.svelte";
  import Lesetext from "./Lesetext.svelte";
  import Notizen from "./Notizen.svelte";

  let { ich, buch: id, uhr, onzurueck }: { ich: Ich; buch: number; uhr: Lesezeituhr; onzurueck: () => void } = $props();

  /** Ist die Ruhe fällig und blättert das Kind nicht weiter, kommt sie nach dieser Frist trotzdem */
  const NACHFRIST_MS = 120_000;
  /** Der Hinweis kurz vor dem Ende steht so lange groß da */
  const HINWEIS_MS = 8000;

  const d = $derived(ich.darstellung);
  const f = $derived(ich.faehigkeiten);

  let buch = $state.raw<BuchEinzeln | null>(null);
  let stand = $state.raw<Kinderlesestand | null>(null);
  let fehler = $state("");
  let fertig = $state(false);
  let lieblingsbuch = $state(false);
  let flaeche = $state<HTMLElement>();
  let breite = $state(0);
  let hoehe = $state(0);
  let schriftstand = $state(0);
  let mass = $state.raw<(Seitenmass & { quer: boolean; bildhoehe: number }) | null>(null);
  let silbenBereit = $state(silbentrennerBereit());
  let stift = $state(false);
  let notizen = $state(false);
  let entfernen = $state.raw<Kindermarkierung | null>(null);
  let markierungen = $state.raw<Kindermarkierungen | null>(null);
  let grosserHinweis = $state(false);

  // Was das Kind selbst an- und ausschaltet, je Profil auf diesem Gerät gemerkt; erlaubt ist es nur, wenn die Eltern es erlauben
  // svelte-ignore state_referenced_locally
  const SCHLUESSEL = `kind.hilfen.${ich.profil.id}`;
  let eigene = $state(liesJson<{ silben?: boolean; zeile?: boolean }>(SCHLUESSEL, {}));
  let silbenAn = $derived(d.silben && eigene.silben !== false);
  let zeileAn = $derived(d.lesezeile && eigene.zeile !== false);
  function schalte(was: "silben" | "zeile") {
    eigene = { ...eigene, [was]: !(was === "silben" ? silbenAn : zeileAn) };
    merkeJson(SCHLUESSEL, eigene);
  }

  // Vorlesen: läuft es aus diesem Buch?
  let vorlesequelle: ReturnType<Kinderlesestand["vorlesequelle"]> | null = null;
  let liestVor = $derived(vorlesen.aktiv && !!vorlesequelle && vorlesen.quelle === vorlesequelle);
  let kannVorlesen = $derived(f.has("vorlesen") && vorlesen.stimmen.length > 0);
  let tempoVorher = vorlesen.tempo;

  let speicher: Positionsspeicher | null = null;
  /** Hört auf, beim Verlassen der Seite zu speichern, und speichert, was offen ist */
  let speicherAus: (() => void) | null = null;

  async function merkeStelle(stelle: Kinderstelle) {
    const s = stand;
    if (!s || !speicher) return;
    const grund = await s.quelle.lesewerte(stelle).catch(() => ({}));
    speicher.merke(kinderlesewerte(fertig ? { ...grund, percent: 100 } : grund, stelle, s.lesezeichen, fertig));
  }

  async function oeffne() {
    fehler = "";
    try {
      const b = await holeBuch(id);
      buch = b;
      lieblingsbuch = b.is_favorite;
      const angaben = kindangabenAus(b.reading_position);
      const werte = lesewerte(b.reading_position);
      const q: Kinderquelle | null = await oeffneKinderquelle(b, angaben?.lesezeichen ? angaben.lesezeichen.einheit + 1 : angaben ? angaben.einheit + 1 : (werte.page ?? 1));
      if (!q) {
        fehler = "Dieses Buch lässt sich hier nicht lesen.";
        return;
      }
      speicher = new Positionsspeicher(buchort(b.id), q.art);
      speicherAus = speicher.starte();
      const s = new Kinderlesestand(q, {
        ruheFaellig: () => uhr.faellig,
        ruhe: zurRuhe,
        gerueckt: (stelle) => void merkeStelle(stelle),
        wortgenau: () => vorlesen.stimme.startsWith("geraet:"),
      });
      vorlesequelle = s.vorlesequelle();
      // Ein Lesezeichen gibt an, wo das Buch aufgeht; sonst die Stelle, an der zuletzt gelesen wurde. Ein fertiges Buch beginnt neu.
      const start = angaben?.fertig ? { einheit: 0, zeichen: 0 } : (angaben?.lesezeichen ?? (angaben ? { einheit: angaben.einheit, zeichen: angaben.zeichen } : await q.stelleAus(werte)) ?? { einheit: 0, zeichen: 0 });
      stand = s;
      await s.beginne(start, angaben?.fertig ? null : (angaben?.lesezeichen ?? null));
      if (f.has("markierungen")) {
        const m = new Kindermarkierungen(b.id, q);
        markierungen = m;
        void m.lade().catch(() => undefined);
      }
    } catch (e) {
      fehler = e instanceof Error ? e.message : String(e);
    }
  }

  // Öffnen und Aufräumen hängen an nichts anderem als am Einhängen des Lesers
  $effect(() => {
    untrack(() => {
      void oeffne();
      uhr.liest = true;
      vorlesen.pruefe();
    });
    return () => {
      uhr.liest = false;
      uhr.vorliest = false;
      if (vorlesequelle && vorlesen.quelle === vorlesequelle) vorlesen.halt();
      vorlesen.tempo = tempoVorher;
      speicherAus?.();
      stand?.quelle.schliesse();
    };
  });

  $effect(() => {
    uhr.vorliest = liestVor && !vorlesen.pausiert;
  });

  // Silben: die Trennmuster erst laden, wenn sie zu sehen sind
  $effect(() => {
    if (silbenAn && !silbenBereit) void ladeSilbentrenner().then(() => (silbenBereit = true)).catch(() => melde.warn("Die Silben ließen sich nicht laden"));
  });

  // Die Schrift muss geladen sein, bevor gemessen wird; neue Schriften lösen neues Messen aus
  $effect(() => {
    const groesse = d.groesse;
    const fam = d.schrift;
    const gewicht = d.fett ? 700 : 400;
    void Promise.all([document.fonts.load(`${gewicht} ${groesse}px ${fam}`), document.fonts.load(`700 ${groesse * 1.25}px ${fam}`)]).then(() => schriftstand++).catch(() => schriftstand++);
    const neu = () => schriftstand++;
    document.fonts.addEventListener?.("loadingdone", neu);
    return () => document.fonts.removeEventListener?.("loadingdone", neu);
  });

  /** Das Maß der Fläche für den Umbruch: Breiten aus der Schrift (Leinwand), Höhen aus Zeilenabstand und Absätzen */
  function messe(b: number, h: number): (Seitenmass & { quer: boolean; bildhoehe: number }) | null {
    if (b < 50 || h < 50) return null;
    const rem = parseFloat(getComputedStyle(document.documentElement).fontSize) || 16;
    const groesse = d.groesse * (rem / 16);
    const leinwand = document.createElement("canvas").getContext("2d");
    if (!leinwand) return null;
    const buchstabe = d.abstand_buchstabe * groesse;
    const wortabstand = d.abstand_wort * groesse;
    // Überschriften: 1,25-fach, ohne Zeichenabstand; der Wortabstand wächst mit (em)
    const messer = (font: string, zusatz: number, wort: number) => {
      const breite = (t: string) => {
        leinwand.font = font;
        return leinwand.measureText(t).width + zusatz * [...t].length;
      };
      return { breite, leer: breite(" ") + wort };
    };
    const text = messer(`${d.fett ? 700 : 400} ${groesse}px ${d.schrift}`, buchstabe, wortabstand);
    const titel = messer(`700 ${groesse * 1.25}px ${d.schrift}`, 0, wortabstand * 1.25);
    const probe = "Die kleine Katze schläft gern im warmen Korb.";
    const zeichenbreite = text.breite(probe) / probe.length;
    // Rand der Seite, Abstand von Bild und Text, und ein wenig Luft für Rundungen und die helle Lesezeile
    const rand = 1.5 * rem * 2;
    const luft = Math.ceil(0.5 * groesse);
    const innen = b - rand;
    const hoch = h - luft * 2;
    const hoechstens = Math.max(8 * zeichenbreite, d.zeichen_je_zeile * zeichenbreite);
    const quer = innen > hoch * 1.15;
    const abstand = 1.5 * rem;
    const bildhoehe = Math.round(hoch * 0.42);
    const sicher = (x: number) => Math.floor(x * 0.97);
    return {
      text: { breite: sicher(Math.min(innen, hoechstens)), hoehe: hoch },
      textMitBild: quer ? { breite: sicher(Math.min((innen - abstand) / 2, hoechstens)), hoehe: hoch } : { breite: sicher(Math.min(innen, hoechstens)), hoehe: hoch - bildhoehe - abstand },
      zeile: Math.round(groesse * d.zeilenabstand),
      titelzeile: Math.round(groesse * 1.25 * d.zeilenabstand),
      absatz: Math.round(groesse * d.abstand_absatz),
      woerter: d.woerter_je_zeile,
      leer: text.leer,
      mass: text.breite,
      titelmass: titel.breite,
      quer,
      bildhoehe,
    };
  }

  $effect(() => {
    void schriftstand;
    const s = stand;
    const m = messe(breite, hoehe);
    if (!m) return;
    untrack(() => {
      mass = m;
      void s?.setzeMass(m);
    });
  });

  // Blättern, Wischen und Tasten
  async function blaettere(richtung: 1 | -1) {
    const s = stand;
    if (!s) return;
    stift = false;
    if (richtung > 0) await s.weiter();
    else await s.zurueck();
    // Wer selbst blättert, hört ab der neuen Seite
    if (liestVor && vorlesequelle) {
      if (vorlesen.pausiert || s.amEnde) vorlesen.halt();
      else liesVor();
    }
  }

  $effect(() => {
    if (!flaeche) return;
    return wischen(flaeche, { links: () => void blaettere(1), rechts: () => void blaettere(-1) });
  });

  function taste(e: KeyboardEvent) {
    if (notizen || entfernen || (e.target as Element).closest?.("input, textarea")) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") void blaettere(1);
    else if (e.key === "ArrowLeft" || e.key === "PageUp") void blaettere(-1);
    else if (zeileAn && e.key === "ArrowDown") stand?.setzeZeile(stand.zeile + 1);
    else if (zeileAn && e.key === "ArrowUp") stand?.setzeZeile(stand.zeile - 1);
    else return;
    e.preventDefault();
  }

  function liesVor() {
    const s = stand;
    if (!s || !buch || !vorlesequelle) return;
    vorlesen.tempo = d.tempo;
    vorlesen.liesBuch(vorlesequelle, { von: s.vorleseanfang(zeileAn), bis: null }, buch.title, { titel: buch.title, autor: buch.author, bild: coverUrl(buch.id, buch.cover_stand) }, buch.id);
  }

  function vorleseTaste() {
    if (!liestVor) return liesVor();
    if (vorlesen.pausiert) vorlesen.weiter();
    else vorlesen.pausiere();
  }

  // Ein Buch der Stufe Vorlesen liest sich beim Öffnen von selbst vor
  let vonSelbst = false;
  $effect(() => {
    if (vonSelbst || !stand?.jetzt || !kannVorlesen || !d.vorlesen_von_selbst) return;
    vonSelbst = true;
    untrack(liesVor);
  });

  function zurRuhe() {
    if (vorlesequelle && vorlesen.quelle === vorlesequelle) vorlesen.halt();
    speicher?.sofort();
    onzurueck();
  }

  // Bleibt die Seite stehen, obwohl die Ruhe fällig ist, kommt sie nach der Frist
  $effect(() => {
    if (!uhr.faellig) return;
    const frist = setTimeout(zurRuhe, NACHFRIST_MS);
    return () => clearTimeout(frist);
  });

  // Der sanfte Hinweis: einmal groß, dann bleibt die Zeit oben warm
  let hinweisGezeigt = false;
  $effect(() => {
    if (!uhr.hinweis || hinweisGezeigt) return;
    hinweisGezeigt = true;
    grosserHinweis = true;
    setTimeout(() => (grosserHinweis = false), HINWEIS_MS);
  });

  // Zu Ende gelesen: gemerkt als fertig, das Lesezeichen ist weg
  $effect(() => {
    const s = stand;
    if (!s?.amEnde || untrack(() => fertig)) return;
    untrack(() => {
      fertig = true;
      s.lesezeichen = null;
      void merkeStelle(s.stelle);
    });
  });

  async function lieblingUmschalten() {
    try {
      lieblingsbuch = (await toggleFavorit(id)).ist_favorit;
    } catch (e) {
      melde.schlecht(e);
    }
  }

  function getippt(zeile: number, wort: Wort | null) {
    const s = stand;
    if (!s) return;
    if (stift && wort && markierungen) {
      const da = markierungen.bei(s.einheit, wort);
      if (da && !markierungen.anfang) entfernen = da;
      else void s.quelle.einheit(s.einheit).then((e) => markierungen!.tippe(e, wort)).catch((e) => melde.schlecht(e));
      return;
    }
    if (zeileAn) s.tippeZeile(zeile);
  }

  async function entferneMarkierung(m: Kindermarkierung) {
    entfernen = null;
    await markierungen?.entferne(m).catch((e) => melde.schlecht(e));
  }

  let seite = $derived(stand?.jetzt ?? null);
  let mitBild = $derived(!!seite?.bild && !!mass);
  let textbreite = $derived(mass ? (mitBild ? mass.textMitBild.breite : mass.text.breite) : 0);
  let seitenname = $derived(stand && formatVon(buch ?? { file_format: "" }) === "pdf" ? stand.quelle.name(stand.einheit) : "");
  let markiertBei = $derived.by(() => {
    const m = markierungen;
    const e = stand?.einheit ?? -1;
    return (w: Wort) => !!m?.bei(e, w);
  });
  let anfangBei = $derived(markierungen?.anfang && markierungen.anfang.einheit === stand?.einheit ? markierungen.anfang.wort.von : -1);
</script>

<svelte:window onkeydown={taste} />

<header class="k-kopf">
  <span class="k-buchname"><i class="fa-solid fa-book-open" aria-hidden="true"></i><span>{buch?.title ?? ""}{seitenname ? `, ${seitenname}` : ""}</span></span>
  <div class="k-rechts">
    <Kinderuhr {uhr} klein mitText={ich.profil.stufe !== "vorlesen"} />
    {#if ich.katze.an}<Katze name={ich.katze.name} zustand="schlaeft" groesse="clamp(3rem, 6.5vw, 4.25rem)" />{/if}
    <button class="k-taste rund" type="button" aria-label="Zum Regal" onclick={onzurueck}><i class="fa-solid fa-house" aria-hidden="true"></i></button>
  </div>
</header>

<div class="k-lesemitte" bind:this={flaeche} bind:clientWidth={breite} bind:clientHeight={hoehe}>
  {#if grosserHinweis}
    <div class="k-hinweis" role="status"><i class="fa-regular fa-clock" aria-hidden="true"></i>Gleich ist die Lesezeit um</div>
  {/if}
  {#if fehler}
    <div class="k-leer">
      <i class="fa-solid fa-book-skull" aria-hidden="true"></i><span>{fehler}</span>
      <button class="k-taste quer" type="button" onclick={() => void oeffne()}><i class="fa-solid fa-rotate-right" aria-hidden="true"></i>Noch einmal</button>
    </div>
  {:else if stand?.fehler}
    <div class="k-leer">
      <i class="fa-solid fa-plug-circle-xmark" aria-hidden="true"></i><span>{stand.fehler}</span>
      <button class="k-taste quer" type="button" onclick={() => void stand?.zeige(stand.stelle)}><i class="fa-solid fa-rotate-right" aria-hidden="true"></i>Noch einmal</button>
    </div>
  {:else if stand?.amEnde && buch}
    <div class="k-schluss">
      <i class="fa-solid fa-circle-check k-schlusszeichen" aria-hidden="true"></i>
      <b>Fertig!</b>
      <Buchkachel {buch} onwahl={onzurueck} />
    </div>
  {:else if seite && mass}
    <div class="k-blatt" class:mit-bild={mitBild && seite.zeilen.length > 0} class:nur-bild={mitBild && !seite.zeilen.length} class:quer={mass.quer} class:hochkant={!mass.quer} style:--bildhoehe="{mass.bildhoehe}px"
      style:--k-leseschrift={d.schrift} style:--k-groesse="{(d.groesse / 16) * 1}rem" style:--k-gewicht={d.fett ? 700 : 400}
      style:--k-zeilenhoehe="{mass.zeile}px" style:--k-titelhoehe="{mass.titelzeile}px" style:--k-absatz="{mass.absatz}px"
      style:--k-buchstabe="{d.abstand_buchstabe}em" style:--k-wort="{d.abstand_wort}em">
      {#if seite.bild}
        <div class="k-seitenbild"><img src={seite.bild.adresse} alt={seite.bild.text} draggable="false" /></div>
      {/if}
      {#if seite.zeilen.length}
        <Lesetext zeilen={seite.zeilen} breite={textbreite} silben={silbenAn && silbenBereit} zeile={zeileAn ? (stand?.zeile ?? 0) : -1} wort={d.mitlesen && liestVor ? (stand?.wort ?? -1) : -1} anfang={anfangBei} markiert={markiertBei} ontippe={getippt} />
      {/if}
    </div>
  {:else if !fehler}
    <div class="k-leer"><i class="fa-solid fa-book-open fa-beat-fade" aria-hidden="true"></i></div>
  {/if}
</div>

<footer class="k-fuss">
  <div class="k-tasten">
    <button class="k-taste" type="button" disabled={!stand || (stand.istErste && !stand.amEnde)} onclick={() => void blaettere(-1)}><i class="fa-solid fa-arrow-left" aria-hidden="true"></i>Zurück</button>
    {#if f.has("lesezeichen") && stand && !stand.amEnde}
      <button class="k-taste" class:an={stand.aufLesezeichen} type="button" aria-pressed={stand.aufLesezeichen} onclick={() => stand?.lesezeichenUmschalten()}><i class="fa-{stand.aufLesezeichen ? 'solid' : 'regular'} fa-bookmark" aria-hidden="true"></i>Merken</button>
    {/if}
    {#if kannVorlesen && !stand?.amEnde}
      <button class="k-taste" class:haupt={d.vorlesen_von_selbst} class:an={liestVor && !d.vorlesen_von_selbst} type="button" disabled={!stand?.jetzt} onclick={vorleseTaste}>
        {#if liestVor && !vorlesen.pausiert}<i class="fa-solid fa-pause" aria-hidden="true"></i>Pause{:else if liestVor}<i class="fa-solid fa-play" aria-hidden="true"></i>Weiter hören{:else}<i class="fa-solid fa-volume-high" aria-hidden="true"></i>Vorlesen{/if}
      </button>
    {/if}
    {#if d.silben && !stand?.amEnde}
      <button class="k-taste" class:an={silbenAn} type="button" aria-pressed={silbenAn} onclick={() => schalte("silben")}><i class="fa-solid fa-palette" aria-hidden="true"></i>Silben</button>
    {/if}
    {#if d.lesezeile && !stand?.amEnde}
      <button class="k-taste" class:an={zeileAn} type="button" aria-pressed={zeileAn} onclick={() => schalte("zeile")}><i class="fa-solid fa-grip-lines" aria-hidden="true"></i>Zeile</button>
    {/if}
    {#if f.has("markierungen") && markierungen && !stand?.amEnde}
      <button class="k-taste" class:an={stift} type="button" aria-pressed={stift} onclick={() => ((stift = !stift), markierungen && (markierungen.anfang = null))}><i class="fa-solid fa-highlighter" aria-hidden="true"></i>Stift</button>
    {/if}
    {#if f.has("notizen") && stand && !stand.amEnde}
      <button class="k-taste" type="button" onclick={() => (notizen = true)}><i class="fa-solid fa-note-sticky" aria-hidden="true"></i>Notiz</button>
    {/if}
    {#if f.has("favoriten")}
      <button class="k-taste" class:an={lieblingsbuch} type="button" aria-pressed={lieblingsbuch} onclick={() => void lieblingUmschalten()}><i class="fa-{lieblingsbuch ? 'solid' : 'regular'} fa-heart" aria-hidden="true"></i>Mag ich</button>
    {/if}
    {#if stand?.amEnde}
      <button class="k-taste haupt" type="button" onclick={onzurueck}><i class="fa-solid fa-house" aria-hidden="true"></i>Zum Regal</button>
    {:else}
      <button class="k-taste" type="button" disabled={!stand?.jetzt} onclick={() => void blaettere(1)}><i class="fa-solid fa-arrow-right" aria-hidden="true"></i>Weiter</button>
    {/if}
  </div>
</footer>

{#if notizen && stand && buch}
  <Notizen buch={buch.id} ort={stand.quelle.ort(stand.stelle)} onschliessen={() => (notizen = false)} />
{/if}
{#if entfernen}
  <div class="k-dialog" role="dialog" aria-modal="true" aria-label="Markierung entfernen">
    <div>
      <div class="k-dialogkopf"><i class="fa-solid fa-highlighter" aria-hidden="true"></i><span>Markierung wegnehmen?</span></div>
      <blockquote class="k-notiz">{entfernen.text}</blockquote>
      <div class="k-wahl">
        <button class="k-taste quer" type="button" onclick={() => (entfernen = null)}><i class="fa-solid fa-arrow-left" aria-hidden="true"></i>Behalten</button>
        <button class="k-taste quer" type="button" onclick={() => void entferneMarkierung(entfernen!)}><i class="fa-solid fa-eraser" aria-hidden="true"></i>Wegnehmen</button>
      </div>
    </div>
  </div>
{/if}
