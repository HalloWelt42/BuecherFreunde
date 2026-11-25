<script lang="ts">
  // Rahmen aller Leser: Leiste oben, Feld rechts, Leiste unten, Auswahlmenü. Das Format liefert Fläche, Fuß und Darstellung.
  import type { Snippet } from "svelte";
  import { beiEsc } from "../../lib/flucht";
  import type { Leseart } from "../../lib/leser/fluss/fluss";
  import type { Lesesitzung } from "../../lib/leser/sitzung.svelte";
  import { geraet } from "../../lib/stand/geraet.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Menue from "../../lib/teile/Menue.svelte";
  import Auswahlmenue from "./Auswahlmenue.svelte";
  import Leseartwahl from "./Leseartwahl.svelte";
  import Leserwerkzeuge from "./Leserwerkzeuge.svelte";
  import Stellenfeld from "./Stellenfeld.svelte";
  import Verzeichnis from "./Verzeichnis.svelte";
  import { vorlesen } from "../../lib/stand/vorlesen.svelte";
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
  let vorlesenOffen = $state(false);
  // Mit dem Finger gehört der Bildschirm im Vollbild ganz dem Text
  let ohneLeisten = $derived(schale.vollbild && (schale.telefon || geraet.telefon));

  $effect(() => {
    if (sitzung.feld) return beiEsc(() => (sitzung.feld = ""));
  });
  $effect(() => {
    if (schale.vollbild) return beiEsc(() => void schale.vollbildUmschalten());
  });
</script>

<div class="leser" class:mit-treffer={!!treffer && !ohneLeisten} class:ohne-leisten={ohneLeisten} data-papier={papier} style:--leserand-grund={grund} style:--leserand-tinte={tinte} bind:this={rahmen}>
  {@render children()}

  {#if ohneLeisten}
    <div class="leseleiste leisten-her glas klar"><Knopf text="Leisten zeigen" symbol="compress" nur frei klein onclick={() => void schale.vollbildUmschalten()} /></div>
  {:else}
    <div class="leseleiste oben glas klar">
      <Knopf text="Zurück" symbol="arrow-left" nur frei klein onclick={onzurueck} />
      <b title={sitzung.buch.title}>{sitzung.buch.title}</b>
      <Knopf text="Inhaltsverzeichnis" symbol="list" nur frei klein gesperrt={!sitzung.kapitel.length} titel={sitzung.kapitel.length ? "Inhaltsverzeichnis" : "Dieses Buch hat kein Inhaltsverzeichnis"} gedrueckt={sitzung.feld === "inhalt"} onclick={() => sitzung.schalteFeld("inhalt")} />
      <Knopf text="Notizen und Markierungen" symbol="highlighter" nur frei klein gesperrt={!bereit} gedrueckt={sitzung.feld === "stellen"} onclick={() => sitzung.schalteFeld("stellen")} />
      <span class="nur-breit reihe">
        <Knopf text="Vorlesen" symbol="volume-high" nur frei klein gesperrt={!bereit} gedrueckt={vorlesen.aktiv} aufgeklappt={vorlesenOffen} bind:element={vorleseKnopf} onclick={() => (vorlesenOffen = !vorlesenOffen)} />
        <Knopf text={schale.vollbild ? "Vollbild verlassen" : "Vollbild"} symbol={schale.vollbild ? "compress" : "expand"} nur frei klein gedrueckt={schale.vollbild} onclick={() => void schale.vollbildUmschalten()} />
      </span>
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

  {#if treffer && !ohneLeisten}<div class="leseleiste treffer unten glas klar">{@render treffer()}</div>{/if}
  {#if bereit && !ohneLeisten}<div class="leseleiste unten glas klar">{@render fuss()}</div>{/if}
  {#if sitzung.auswahl && rahmen}<Auswahlmenue {sitzung} {rahmen} {onabwahl} />{/if}
</div>

{#if vorlesenOffen}
  <Menue anker={vorleseKnopf} name="Vorlesen" breite="21rem" onschliessen={() => (vorlesenOffen = false)}><Vorlesen {sitzung} onfertig={() => (vorlesenOffen = false)} /></Menue>
{/if}

<style>
  .nur-breit {
    gap: 0.25rem;
  }
</style>
