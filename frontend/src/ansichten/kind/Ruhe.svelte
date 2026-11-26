<!-- Der Ruheschirm: die Lesezeit ist um oder es ist Ruhezeit. Die Bücher ruhen, und es steht da, wann es weitergeht. Hinaus nur
     über das Schloss für die Eltern. Klein: Nachtschirm, die Katze schläft groß mit (streicheln geht). Groß (BF-88): ruhiger, kein
     Nachtschirm, nur ein Hinweis in der gewohnten Fläche; ist die Katze an, schläft sie klein im Kopf. -->
<script lang="ts">
  import { untrack } from "svelte";
  import { ansage } from "../../lib/kind/ansage.svelte";
  import { HINWEIS, RUHEZEIT, TASTE } from "../../lib/kind/ansagen";
  import Katze from "../../lib/kind/Katze.svelte";
  import { weiterAb } from "../../lib/kind/lesezeit.svelte";
  import type { Ich, Lesezeitstand } from "../../lib/kind/typen";

  let { ich, lesezeit, onschloss }: { ich: Ich; lesezeit: Lesezeitstand; onschloss: () => void } = $props();

  let gross = $derived(ich.gestaltung === "gross");
  let wann = $derived(weiterAb(lesezeit.ruhe_bis, new Date()));
  let wer = $derived(ich.katze.an ? `${ich.katze.name || "Die Katze"} schläft schon.` : "");
  // Einmal, wenn die Ruhe beginnt
  $effect(() => untrack(() => void ansage.hinweis([lesezeit.ruht ? RUHEZEIT : HINWEIS.lesezeitUm])));

  function schloss() {
    onschloss();
    void ansage.taste([TASTE.schloss]);
    void ansage.hinweis([HINWEIS.fragEltern]);
  }
</script>

{#if gross}
  <header class="kopf glas milch">
    <span class="g-wer"><span class="k-bild" style:background={ich.profil.farbe} aria-hidden="true"><i class="fa-solid fa-{ich.profil.zeichen}"></i></span><span>{ich.profil.name}</span></span>
    <div class="g-rechts">
      {#if ich.katze.an}<Katze name={ich.katze.name} zustand="ruht" schnurren={ich.katze.schnurren} groesse="2.25rem" />{/if}
      <button class="knopf nur" type="button" aria-label="Für Eltern" title="Für Eltern" onclick={schloss}><i class="fa-solid fa-lock" aria-hidden="true"></i></button>
    </div>
  </header>

  <div class="buehne glas klar">
    <div class="g-ruhe" role="status">
      <div class="platte g-ruhekarte">
        <i class="fa-solid fa-moon" aria-hidden="true"></i>
        <b>{lesezeit.ruht ? "Ruhezeit" : "Lesezeit um"}</b>
        <span class="leise">{wann} geht es weiter.</span>
      </div>
    </div>
  </div>
{:else}
  <header class="k-kopf">
    <div class="k-rechts">
      <button class="k-schloss" type="button" aria-label="Für Eltern" onclick={schloss}><i class="fa-solid fa-lock" aria-hidden="true"></i></button>
    </div>
  </header>

  <div class="k-ruhe" role="status">
    <i class="fa-solid fa-moon mond" aria-hidden="true"></i>
    <b>Jetzt ruhen die Bücher.</b>
    <p>{wer} {wann} geht es weiter.</p>
    {#if ich.katze.an}
      <Katze name={ich.katze.name} zustand="ruht" schnurren={ich.katze.schnurren} nacht groesse="clamp(8rem, 17vw, 12rem)" />
    {/if}
  </div>

  <div class="k-fuss"></div>
{/if}
