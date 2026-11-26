<!-- Die Lesezeit als Kinderuhr (Entwurf Runde 3): Zeigeruhr mit großen Zahlen, ohne Sekundenzeiger, die restliche Lesezeit als
     farbiges Stück vom Minutenzeiger bis zum Punkt am Rand; daneben dezent der Rest und die Gesamtzeit des Tages. Alles ändert sich
     nur einmal je Minute, am Minutenwechsel der Uhr des Geräts; bei reduzierter Bewegung springen die Zeiger ohne Übergang.
     klein: in der Kopfzeile beim Lesen, nur mit den zwölf Stundenstrichen. mitText: ab Stufe Erstes Lesen. -->
<script lang="ts">
  import { untrack } from "svelte";
  import { dauerText } from "./datum";
  import type { Lesezeituhr } from "./lesezeit.svelte";
  import { minutentakt } from "./minutentakt.svelte";
  import { minutenBis, MINUTENZEIGER, ort, RAND, restMinuten, STUNDENZEIGER, striche, stueckMinuten, stueckPfad, uhrtext, zahlen, zeigerwinkel } from "./uhr";

  let { uhr, klein = false, mitText = true, ruheAb = null }: { uhr: Lesezeituhr; klein?: boolean; mitText?: boolean; ruheAb?: string | null } = $props();

  $effect(() => minutentakt.beobachte());

  // Nur der Minutentakt zählt; was die Lesezeit dazwischen tut, zeigt erst der nächste Wechsel
  let bild = $derived.by(() => {
    const jetzt = minutentakt.jetzt;
    return untrack(() => {
      const stand = uhr.stand;
      if (stand.rest_s === null) return null;
      const rest = restMinuten(uhr.rest ?? 0);
      const stunde = jetzt.getHours();
      const minute = jetzt.getMinutes();
      const dauer = stueckMinuten(rest, minutenBis(ruheAb ?? stand.ruhe_ab, jetzt));
      return {
        stunde, minute, rest, dauer,
        gesamt: Math.round((stand.heute_s + stand.rest_s) / 60),
        winkel: zeigerwinkel(stunde, minute),
        pfad: stueckPfad(minute, dauer),
        punkt: ort(minute + dauer, RAND),
      };
    });
  });

  const STRICHE_GROSS = striche(true);
  const STRICHE_KLEIN = striche(false);
  const ZAHLEN_ORTE = zahlen();
</script>

{#if bild}
  <span class="k-uhr" class:k-uhr-klein={klein}>
    <svg viewBox="0 0 100 100" role="img" aria-label={uhrtext(bild.stunde, bild.minute, bild.rest)}>
      <circle cx="50" cy="50" r="47.5" class="u-blatt" />
      {#if bild.dauer >= 60}
        <circle cx="50" cy="50" r={RAND} class="u-stueck" />
      {:else if bild.pfad}
        <path d={bild.pfad} class="u-stueck" />
      {/if}
      {#each klein ? STRICHE_KLEIN : STRICHE_GROSS as s (s.bis.join())}
        <line x1={s.von[0]} y1={s.von[1]} x2={s.bis[0]} y2={s.bis[1]} class:u-stunde={s.stunde} class="u-strich" />
      {/each}
      {#if !klein}
        {#each ZAHLEN_ORTE as z (z.zahl)}
          <text x={z.bei[0]} y={z.bei[1]} dy=".36em" text-anchor="middle" class="u-zahl">{z.zahl}</text>
        {/each}
      {/if}
      {#if bild.dauer > 0}<circle cx={bild.punkt[0]} cy={bild.punkt[1]} r="3.4" class="u-punkt" />{/if}
      <line x1="50" y1="50" x2="50" y2={50 - STUNDENZEIGER} class="u-zeiger u-std" style:transform="rotate({bild.winkel.stunde}deg)" />
      <line x1="50" y1="50" x2="50" y2={50 - MINUTENZEIGER} class="u-zeiger u-min" style:transform="rotate({bild.winkel.minute}deg)" />
      <circle cx="50" cy="50" r="3.6" class="u-achse" />
    </svg>
    {#if mitText}
      <span class="u-text" class:bald={uhr.hinweis}><b>noch {dauerText(bild.rest)}</b><small>heute {dauerText(bild.gesamt)}</small></span>
    {/if}
  </span>
{/if}
