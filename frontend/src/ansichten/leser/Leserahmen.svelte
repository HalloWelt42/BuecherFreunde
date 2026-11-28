<script lang="ts">
  // Rahmen aller Leser: Leiste oben, Feld rechts, Leiste unten, Auswahlmenü. Das Format liefert Fläche, Fuß und Darstellung.
  import type { Snippet } from "svelte";
  import { beiEsc, offenesFeld } from "../../lib/flucht";
  import type { Leseart } from "../../lib/leser/fluss/fluss";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { blattrand } from "../../lib/leser/blattrand.svelte";
  import { zeigeBlattgrund } from "../../lib/stand/blattgrund";
  import { schale } from "../../lib/stand/schale.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Menue from "../../lib/teile/Menue.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Auswahlmenue from "./Auswahlmenue.svelte";
  import Leseartwahl from "./Leseartwahl.svelte";
  import Leserwerkzeuge from "./Leserwerkzeuge.svelte";
  import Stellenfeld from "./Stellenfeld.svelte";
  import Verzeichnis from "./Verzeichnis.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
  import { randmarken } from "../../lib/leser/randschalter.svelte";
  import Randmarken from "./Randmarken.svelte";
  import Codetastenebene from "./Codetastenebene.svelte";
  import Spieler from "./Spieler.svelte";
  import Blattfeinheiten from "./Blattfeinheiten.svelte";
  import Breitenregler from "./Breitenregler.svelte";
  import { blattbreite, teileAuf } from "../../lib/leser/leseraum.svelte";
  import { liesAbHier } from "../../lib/leser/vorlesestart";
  import { kontext, type Angebot } from "../../lib/stand/kontextmenue.svelte";
  import Fokusfeld from "./Fokusfeld.svelte";
  import Hilfensteuerung from "./Hilfensteuerung.svelte";
  import Tastenfeld from "./Tastenfeld.svelte";
  import { hilfenCss, lesehilfen } from "../../lib/leser/lesehilfen.svelte";
  import Vorlesen from "./Vorlesen.svelte";

  interface Eigenschaften {
    sitzung: Lesesitzung;
    papier?: string;
    /** Farben des Blatts, für alles, was darüber schwebt */
    grund: string;
    tinte: string;
    art: Leseart;
    onart: (art: Leseart) => void;
    /** Wirken Abstände im Satz (nicht beim PDF als Bild)? */
    satz?: boolean;
    bereit: boolean;
    onzurueck: () => void;
    onabwahl: () => void;
    darstellung: Snippet;
    /** Knöpfe des Formats in der Leiste oben, vor Schrift, Papier, Ansicht; nur am Rechner (BF-126) */
    leiste?: Snippet;
    fuss: Snippet;
    treffer?: Snippet;
    children: Snippet;
  }
  let { sitzung, papier = "normal", grund, tinte, art, onart, satz = true, bereit, onzurueck, onabwahl, darstellung, leiste = undefined, fuss, treffer = undefined, children }: Eigenschaften = $props();

  /** Seitenrand der Bühne (--rand-seite) */
  const RAND_SEITE = 16;

  let rahmen: HTMLElement | undefined = $state();
  let feldflaeche: HTMLElement | undefined = $state();
  let leisteOben: HTMLElement | undefined = $state();
  // Aufteilung des Leseraums (lib/leser/leseraum.svelte.ts): rechts Marken und Feld, links das Blatt
  let raumbreite = $state(0);
  let feldbreite = $state(0);
  let raum = $derived(teileAuf({ breite: raumbreite, feld: feldbreite, rand: RAND_SEITE, telefon: schale.telefon, vollbild: schale.vollbild, marken: randmarken.an, feldOffen: !!sitzung.feld && bereit }));
  let vorleseKnopf = $state<HTMLElement | null>(null);
  let vorleseZeichen = $state<HTMLElement | null>(null);
  let vorlesenOffen = $state(false);
  // Liest es gerade aus diesem Buch vor?
  let liestHier = $derived(vorlesen.aktiv && !!sitzung.quelle && vorlesen.quelle === sitzung.quelle);
  // Gescrollt blättert kein Tippen: die Marken am Rand fangen es hier
  function tippeRand(e: MouseEvent) {
    if (!sitzung.randtreffer?.(e.clientX, e.clientY)) return;
    e.preventDefault();
    e.stopPropagation();
  }

  // Kontextmenü im Buch (BF-42): mit Auswahl das Auswahlmenü, ohne Vorlesen ab hier und Etikett hier. Langes Drücken am
  // Telefon gehört der Auswahl des Browsers.
  function imBuch(e: MouseEvent, finger: boolean): Angebot {
    if (finger || !bereit) return null;
    if (sitzung.auswahl || (e.view ?? window).getSelection()?.toString().trim()) return "eigen";
    return [
      { text: "Vorlesen ab hier", symbol: "play", gesperrt: !sitzung.quelle, tun: () => liesAbHier(sitzung) },
      ...(sitzung.mitEtiketten ? [{ text: "Etikett hier", symbol: "tag", tun: () => sitzung.etikettHier() }] : []),
    ];
  }

  let hilfen = $derived(Object.entries(hilfenCss(lesehilfen.wirksam)).map(([k, v]) => `${k}: ${v}`).join("; "));
  // Das Feld Fokus zeigt beim Öffnen gleich, was es tut; danach schaltet nur noch, wer schaltet (BF-40)
  function fokusfeld() {
    sitzung.schalteFeld("fokus");
    if (sitzung.feld === "fokus" && !lesehilfen.fokus.an) lesehilfen.setzeFokus({ an: true });
  }

  let zustand = $derived(!liestHier ? "volume-low" : vorlesen.wartet && !vorlesen.pausiert ? "circle-notch" : vorlesen.pausiert ? "pause" : "volume-high");

  // Esc und ein Druck daneben schließen das Feld (lib/flucht.ts); die Leiste oben schaltet es selbst, und beim Feld Fokus
  // gehören die Griffe des Fokus dazu
  $effect(() => {
    if (!sitzung.feld) return;
    return offenesFeld(() => [feldflaeche, leisteOben, sitzung.feld === "fokus" ? rahmen?.querySelector(".fokus") : null], () => (sitzung.feld = ""));
  });
  $effect(() => {
    if (schale.vollbild) return beiEsc(() => void schale.vollbildUmschalten());
  });
  // Im Vollbild gehört der ganze Bildschirm dem Blatt
  $effect(() => {
    if (schale.vollbild) sitzung.feld = "";
  });
  $effect(() => {
    if (schale.vollbild) return zeigeBlattgrund(grund);
  });
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="leser" onpointermove={(e) => sitzung.regt(e)} onclickcapture={tippeRand} class:mit-treffer={!!treffer && !schale.vollbild} class:randlos={schale.vollbild} class:ruhig={sitzung.ruhig} class:ohne-leisten={sitzung.leistenAus} class:feld-daneben={raum.feldDaneben} style={hilfen} data-papier={papier} style:--randgrund={grund} style:--randtinte={tinte} style:--blattrand="{blattrand.wert}px" style:--blattrand-oben="{blattrand.oben(schale.vollbild)}px" style:--raum-rechts="{raum.rechts}px" style:--lesebreite="{blattbreite.wert}px" bind:this={rahmen} bind:clientWidth={raumbreite} use:kontext={imBuch}>
  {@render children()}
  {#if bereit && rahmen && sitzung.code}<Codetastenebene {sitzung} {rahmen} />{/if}
  {#if bereit && rahmen && randmarken.an && sitzung.mitStellen}<Randmarken {sitzung} {rahmen} {raum} feld={raum.feldDaneben ? feldflaeche : undefined} />{/if}
  {#if bereit && rahmen}<Hilfensteuerung {sitzung} {rahmen} offen={vorlesenOffen} />{/if}

  {#if schale.vollbild}
    <button type="button" class="schwebezeichen links" aria-label="Vollbild verlassen" title="Vollbild verlassen" onclick={() => void schale.vollbildUmschalten()}><Symbol name="compress" /></button>
    {#if bereit}<button type="button" class="schwebezeichen rechts" aria-label="Vorlesen" title="Vorlesen" aria-expanded={vorlesenOffen} bind:this={vorleseZeichen} onclick={() => (vorlesenOffen = !vorlesenOffen)}><Symbol name={zustand} dreht={zustand === "circle-notch"} /></button>{/if}
  {:else}
    <div class="leseleiste oben glas klar" bind:this={leisteOben}>
      <Knopf text="Zurück" symbol="arrow-left" nur frei klein onclick={onzurueck} />
      <b title={sitzung.fassung.titel ?? sitzung.buch.title}>{sitzung.fassung.titel ?? sitzung.buch.title}</b>
      <Knopf text="Inhaltsverzeichnis" symbol="list" nur frei klein gesperrt={!sitzung.kapitel.length} titel={sitzung.kapitel.length ? "Inhaltsverzeichnis" : "Dieses Buch hat kein Inhaltsverzeichnis"} gedrueckt={sitzung.feld === "inhalt"} onclick={() => sitzung.schalteFeld("inhalt")} />
      <!-- Notizen und Markierungen hängen am Original; in einer Übersetzung gibt es sie noch nicht (BF-71) -->
      {#if sitzung.mitStellen}<Knopf text="Notizen und Markierungen" symbol="highlighter" nur frei klein gesperrt={!bereit} gedrueckt={sitzung.feld === "stellen"} onclick={() => sitzung.schalteFeld("stellen")} />{/if}
      <!-- Am Telefon steht das Vorlesen im Feld; liest es gerade, auch hier -->
      <span class="reihe" class:nur-breit={!liestHier}><Knopf text="Vorlesen" symbol={liestHier ? zustand : "volume-high"} nur frei klein gesperrt={!bereit} gedrueckt={liestHier} aufgeklappt={vorlesenOffen} bind:element={vorleseKnopf} onclick={() => (vorlesenOffen = !vorlesenOffen)} /></span>
      <span class="nur-breit reihe">
        <Knopf text="Fokus und Hilfen" symbol="crosshairs" nur frei klein gesperrt={!bereit} gedrueckt={sitzung.feld === "fokus" || lesehilfen.fokus.an} onclick={fokusfeld} />
        <Knopf text="Vollbild" symbol="expand" nur frei klein onclick={() => void schale.vollbildUmschalten()} />
        <Knopf text="Tastenkürzel" symbol="keyboard" nur frei klein gedrueckt={sitzung.feld === "tasten"} onclick={() => sitzung.schalteFeld("tasten")} />
      </span>
      {#if leiste}<span class="nur-breit reihe">{@render leiste()}</span>{/if}
      <Knopf text="Schrift, Papier, Ansicht" symbol="font" nur frei klein gesperrt={!bereit} gedrueckt={sitzung.feld === "darstellung"} onclick={() => sitzung.schalteFeld("darstellung")} />
    </div>
  {/if}

  {#if sitzung.feld && bereit}
    <aside class="seitenfeld glas dicht" aria-label="Seitenfeld" bind:this={feldflaeche} bind:offsetWidth={feldbreite}>
      <!-- Glas rollt nie selbst: die Scheibe steht, gerollt wird innen -->
      <div class="rollen">
      {#if sitzung.feld === "inhalt"}
        <Verzeichnis {sitzung} />
      {:else if sitzung.feld === "stellen"}
        <Stellenfeld {sitzung} />
      {:else if sitzung.feld === "fokus"}
        <Fokusfeld {sitzung} />
      {:else if sitzung.feld === "tasten"}
        <Tastenfeld />
      {:else}
        <h2>Schrift und Papier</h2>
        <Leseartwahl {art} {onart} />
        {@render darstellung()}
        {#if !schale.telefon}<Breitenregler />{/if}
        {#if !schale.telefon}<Blattfeinheiten {sitzung} text={satz} />{/if}
        <Leserwerkzeuge {sitzung} />
      {/if}
      </div>
    </aside>
  {/if}

  {#if treffer && !schale.vollbild}<div class="leseleiste treffer unten glas klar">{@render treffer()}</div>{/if}
  {#if bereit && !schale.vollbild}<div class="leseleiste unten glas klar">{@render fuss()}</div>{/if}
  {#if liestHier && schale.vollbild && sitzung.spieler}
    <div class="spielerleiste glas klar" role="region" aria-label="Vorlesen" onpointerenter={() => sitzung.zeigeSpieler(true)} onpointerleave={() => sitzung.zeigeSpieler()}>
      <span class="klein spielername">{vorlesen.name}</span>
      <Spieler art={sitzung.quelle?.einheitsart} />
    </div>
  {/if}
  {#if liestHier && vorlesen.weg}
    <button type="button" class="zurstelle glas klar knopf klein" class:hoeher={schale.vollbild && sitzung.spieler} onclick={() => vorlesen.zurStelle()}><Symbol name="location-crosshairs" />Zur Stelle</button>
  {/if}
  {#if sitzung.auswahl && rahmen}<Auswahlmenue {sitzung} {rahmen} {onabwahl} />{/if}
</div>

{#if vorlesenOffen}
  <Menue anker={schale.vollbild ? vorleseZeichen : vorleseKnopf} name="Vorlesen" breite="21rem" onschliessen={() => (vorlesenOffen = false)}><Vorlesen {sitzung} /></Menue>
{/if}

<style>
  .nur-breit {
    gap: 0.25rem;
  }
</style>
