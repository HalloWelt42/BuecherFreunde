<script lang="ts">
  // Hinter allem: Regalwand oder eigenes Bild, darüber das Licht des gewählten Buchs
  import { darstellung } from "../stand/darstellung.svelte";
  import { hintergrund } from "../stand/hintergrund.svelte";
  import { wahl } from "../stand/wahl.svelte";
  import { regalfarben } from "./regalfarben";
  import { zeichneBild, zeichneRegalwand } from "./regalwand";

  let flaeche: HTMLCanvasElement | undefined = $state();
  let farben = $state(regalfarben.jetzt);
  let bildadresse = $derived(darstellung.grund === "bild" ? hintergrund.adresse : "");

  $effect(() => regalfarben.beiNeuen((neu) => (farben = neu)));

  $effect(() => {
    if (darstellung.grund === "bild" && !hintergrund.bilder.length) void hintergrund.laden();
  });

  $effect(() => {
    const f = flaeche;
    if (!f) return;
    if (!bildadresse) {
      zeichneRegalwand(f, farben);
      return;
    }
    const bild = new Image();
    let gilt = true;
    bild.onload = () => gilt && zeichneBild(f, bild);
    bild.onerror = () => gilt && zeichneRegalwand(f, farben);
    bild.src = bildadresse;
    return () => (gilt = false);
  });
</script>

<div class="kulisse" style:--k1={wahl.licht[0]} style:--k2={wahl.licht[1]} style:--k3={wahl.licht[2]}>
  <canvas bind:this={flaeche} aria-hidden="true"></canvas>
</div>
