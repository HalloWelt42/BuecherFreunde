<!-- Der Ruheschirm: die Lesezeit ist um oder es ist Ruhezeit. Die Bücher ruhen, die Katze schläft mit (streicheln geht), und es
     steht da, wann es weitergeht. Hinaus nur über das Schloss für die Eltern. -->
<script lang="ts">
  import { untrack } from "svelte";
  import { ansage } from "../../lib/kind/ansage.svelte";
  import Katze from "../../lib/kind/Katze.svelte";
  import { weiterAb } from "../../lib/kind/lesezeit.svelte";
  import type { Ich, Lesezeitstand } from "../../lib/kind/typen";

  let { ich, lesezeit, onschloss }: { ich: Ich; lesezeit: Lesezeitstand; onschloss: () => void } = $props();

  let wann = $derived(weiterAb(lesezeit.ruhe_bis, new Date()));
  let wer = $derived(ich.katze.an ? `${ich.katze.name || "Die Katze"} schläft schon.` : "");
  let satz = $derived(`Jetzt ruhen die Bücher. ${wer} ${wann} geht es weiter.`.replace(/\s+/g, " "));

  // Einmal, wenn die Ruhe beginnt
  $effect(() => untrack(() => void ansage.hinweis(satz)));

  function schloss() {
    onschloss();
    void ansage.hinweis("Frag Mama oder Papa.");
  }
</script>

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
