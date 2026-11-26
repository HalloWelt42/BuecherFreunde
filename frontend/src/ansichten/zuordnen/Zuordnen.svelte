<script lang="ts">
  // Zuordnen in zwei Spalten (BF-67), für Sammlung, Regal und die Freigaben eines Kindes (BF-78) gleich: links was drin
  // ist, rechts der Bestand. Ziehen in beide Richtungen, auch mehrere angehakte; dazu die Tasten. Am Telefon untereinander
  // mit Umschalter, ohne Ziehen.
  import { untrack } from "svelte";
  import { zahl } from "../../lib/format";
  import Suchfeld from "../../lib/schale/Suchfeld.svelte";
  import { schale } from "../../lib/stand/schale.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Segment from "../../lib/teile/Segment.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";
  import Zustand from "../../lib/teile/Zustand.svelte";
  import { BUCHHINWEIS } from "../bibliothek/schnellfilter";
  import { reihenkopf } from "../sammlung/angaben";
  import Spalte from "./Spalte.svelte";
  import { zielAus } from "./ziel";
  import { Zuordnung, type Spalte as Spaltenname } from "./zuordnung.svelte";

  let { params }: { params: Record<string, string> } = $props();

  /** Tippen im Suchfeld: erst nach einer kurzen Pause neu laden */
  const WARTE_MS = 250;
  // Die Ansicht entsteht je Adresse neu (App.svelte), Ziel und Zustand bleiben deshalb fest
  const ziel = untrack(() => zielAus(params.art, params.id));
  const zuordnung = ziel ? new Zuordnung(ziel) : null;

  let name = $derived(ziel?.name() ?? "");
  const ZIELNAME = { sammlung: "Sammlung", regal: "Regal", freigabe: "Familie" } as const;
  let sicht = $state<Spaltenname>("drin");
  let dazuZahl = $derived(zuordnung?.angehakt("uebrig").length ?? 0);
  let herausZahl = $derived(zuordnung?.angehakt("drin").length ?? 0);
  /** Nur eine Sammlung hat Bände: Name und Kopf ihrer Titel fallen links weg */
  let reihe = $derived(zuordnung?.ziel.ordne ? [name, reihenkopf(zuordnung.drin.liste.map((b) => b.title))] : undefined);

  $effect(() => {
    if (zuordnung) void zuordnung.drin.laden(zuordnung.ziel.drin);
  });
  // Der Bestand folgt seinen Filtern; "Gleicher Autor" braucht erst die linke Spalte
  $effect(() => {
    if (!zuordnung?.drin.geladen) return;
    const filter = zuordnung.uebrigFilter;
    const uhr = setTimeout(() => void zuordnung.uebrig.laden(filter), WARTE_MS);
    return () => clearTimeout(uhr);
  });
</script>

{#snippet dazu(z: Zuordnung)}
  <Knopf text={dazuZahl ? `${zahl(dazuZahl)} dazu` : "Dazu"} symbol={schale.telefon ? "plus" : "arrow-left"} haupt gesperrt={!dazuZahl || z.laeuft} onclick={() => void z.dazu(z.angehakt("uebrig"))} />
{/snippet}
{#snippet heraus(z: Zuordnung)}
  <Knopf text="Heraus" symbol={schale.telefon ? "minus" : ""} gesperrt={!herausZahl || z.laeuft} onclick={() => void z.heraus(z.angehakt("drin"))}>{#if !schale.telefon}<Symbol name="arrow-right" />{/if}</Knopf>
{/snippet}
{#snippet links(z: Zuordnung)}
  <Spalte zuordnung={z} spalte="drin" titel={z.ziel.drinText} zusatz={zahl(z.drin.gesamt)} {reihe} leer="Noch leer" />
{/snippet}
{#snippet rechts(z: Zuordnung)}
  <Spalte zuordnung={z} spalte="uebrig" titel="Bestand" zusatz={z.ziel.bestandText(z.ohneSammlung)} leer="Kein Buch passt">
    <div class="reihe">
      <label class="zuordnungssuche mulde"><Symbol name="magnifying-glass" /><input type="search" placeholder={BUCHHINWEIS} aria-label="Bestand durchsuchen" bind:value={z.wort} /></label>
      <Chip text="Gleicher Autor" gedrueckt={z.gleicherAutor} gesperrt={!z.autor} titel={z.autor ? `Nur Bücher von ${z.autor}` : undefined} onclick={() => (z.gleicherAutor = !z.gleicherAutor)} />
      <Chip text="Ohne Sammlung" gedrueckt={z.ohneSammlung} onclick={() => (z.ohneSammlung = !z.ohneSammlung)} />
    </div>
  </Spalte>
{/snippet}

<div class="werkzeug">
  <Suchfeld id="suchfeld-m" klasse="suchfeld-mobil" />
  {#if ziel}<Knopf text={name || ZIELNAME[ziel.art]} symbol="arrow-left" klein href={ziel.zurueck} />{/if}
  <h1>Zuordnen</h1>
</div>

<div class="inhalt zuordnen-flaeche">
  {#if !zuordnung}
    <Zustand art="fehler" text="Diese Sammlung, dieses Regal oder dieses Profil gibt es nicht."><Knopf text="Zur Bibliothek" symbol="book-bookmark" klein href="/" /></Zustand>
  {:else if schale.telefon}
    <div class="zuordnen telefon">
      <Segment name="Spalte" werte={[["drin", zuordnung.ziel.drinText], ["uebrig", "Bestand"]]} wert={sicht} onwahl={(w) => (sicht = w)} />
      <div class="reihe">{#if sicht === "uebrig"}{@render dazu(zuordnung)}{:else}{@render heraus(zuordnung)}{/if}</div>
      {#if sicht === "drin"}{@render links(zuordnung)}{:else}{@render rechts(zuordnung)}{/if}
    </div>
  {:else}
    <div class="zuordnen">
      {@render links(zuordnung)}
      <div class="zuordnungsmitte">{@render dazu(zuordnung)}{@render heraus(zuordnung)}</div>
      {@render rechts(zuordnung)}
    </div>
  {/if}
</div>
