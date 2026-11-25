<script lang="ts">
  // Rahmen aller Leser: Leiste oben, Feld rechts, Leiste unten, Auswahlmenü. Das Format liefert Fläche, Fuß und Darstellung.
  import type { Snippet } from "svelte";
  import { beiEsc } from "../../lib/flucht";
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
  import Spieler from "./Spieler.svelte";
  import Vorlesen from "./Vorlesen.svelte";

  interface Eigenschaften {
    sitzung: Lesesitzung;
    papier?: string;
    /** Farben des Blatts, für alles, was darüber schwebt */
    grund: string;
    tinte: string;
    art: Leseart;
    onart: (art: Leseart) => void;
    bereit: boolean;
    onzurueck: () => void;
    onabwahl: () => void;
    darstellung: Snippet;
    fuss: Snippet;
    treffer?: Snippet;
    children: Snippet;
  }
  let { sitzung, papier = "normal", grund, tinte, art, onart, bereit, onzurueck, onabwahl, darstellung, fuss, treffer = undefined, children }: Eigenschaften = $props();

  let rahmen: HTMLElement | undefined = $state();
  let vorleseKnopf = $state<HTMLElement | null>(null);
  let vorleseZeichen = $state<HTMLElement | null>(null);
  let vorlesenOffen = $state(false);
  // Liest es gerade aus diesem Buch vor?
  let liestHier = $derived(vorlesen.aktiv && !!sitzung.quelle && vorlesen.quelle === sitzung.quelle);
  let zustand = $derived(!liestHier ? "volume-low" : vorlesen.wartet && !vorlesen.pausiert ? "circle-notch" : vorlesen.pausiert ? "pause" : "volume-high");

  $effect(() => {
    if (sitzung.feld) return beiEsc(() => (sitzung.feld = ""));
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
<div class="leser" onpointermove={(e) => sitzung.regt(e)} class:mit-treffer={!!treffer && !schale.vollbild} class:randlos={schale.vollbild} data-papier={papier} style:--randgrund={grund} style:--randtinte={tinte} style:--blattrand="{blattrand.wert}px" style:--blattrand-oben="{blattrand.oben(schale.vollbild)}px" bind:this={rahmen}>
  {@render children()}

  {#if schale.vollbild}
    <button type="button" class="schwebezeichen links" aria-label="Vollbild verlassen" title="Vollbild verlassen" onclick={() => void schale.vollbildUmschalten()}><Symbol name="compress" /></button>
    {#if bereit}<button type="button" class="schwebezeichen rechts" aria-label="Vorlesen" title="Vorlesen" aria-expanded={vorlesenOffen} bind:this={vorleseZeichen} onclick={() => (vorlesenOffen = !vorlesenOffen)}><Symbol name={zustand} dreht={zustand === "circle-notch"} /></button>{/if}
  {:else}
    <div class="leseleiste oben glas klar">
      <Knopf text="Zurück" symbol="arrow-left" nur frei klein onclick={onzurueck} />
      <b title={sitzung.buch.title}>{sitzung.buch.title}</b>
      <Knopf text="Inhaltsverzeichnis" symbol="list" nur frei klein gesperrt={!sitzung.kapitel.length} titel={sitzung.kapitel.length ? "Inhaltsverzeichnis" : "Dieses Buch hat kein Inhaltsverzeichnis"} gedrueckt={sitzung.feld === "inhalt"} onclick={() => sitzung.schalteFeld("inhalt")} />
      <Knopf text="Notizen und Markierungen" symbol="highlighter" nur frei klein gesperrt={!bereit} gedrueckt={sitzung.feld === "stellen"} onclick={() => sitzung.schalteFeld("stellen")} />
      <!-- Am Telefon steht das Vorlesen im Feld; liest es gerade, auch hier -->
      <span class="reihe" class:nur-breit={!liestHier}><Knopf text="Vorlesen" symbol={liestHier ? zustand : "volume-high"} nur frei klein gesperrt={!bereit} gedrueckt={liestHier} aufgeklappt={vorlesenOffen} bind:element={vorleseKnopf} onclick={() => (vorlesenOffen = !vorlesenOffen)} /></span>
      <span class="nur-breit reihe"><Knopf text="Vollbild" symbol="expand" nur frei klein onclick={() => void schale.vollbildUmschalten()} /></span>
      <Knopf text="Schrift, Papier, Ansicht" symbol="font" nur frei klein gesperrt={!bereit} gedrueckt={sitzung.feld === "darstellung"} onclick={() => sitzung.schalteFeld("darstellung")} />
    </div>
  {/if}

  {#if sitzung.feld && bereit}
    <aside class="seitenfeld rollen glas dicht" aria-label="Seitenfeld">
      {#if sitzung.feld === "inhalt"}
        <Verzeichnis {sitzung} />
      {:else if sitzung.feld === "stellen"}
        <Stellenfeld {sitzung} />
      {:else}
        <h2>Schrift und Papier</h2>
        <Leseartwahl {art} {onart} />
        {@render darstellung()}
        <Leserwerkzeuge {sitzung} />
      {/if}
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
