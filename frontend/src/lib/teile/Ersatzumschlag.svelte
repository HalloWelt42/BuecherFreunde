<script lang="ts">
  // Gezeichneter Umschlag für Bücher ohne Bild; die Farben hängen fest am Buch
  import { VORGABE } from "../palette";
  let { buch }: { buch: { id: number; title: string; author?: string } } = $props();

  const HOEHE = 290;
  let farben = $derived(VORGABE[buch.id % VORGABE.length]);

  function umbrechen(text: string, laenge: number): string[] {
    const zeilen: string[] = [];
    for (const wort of text.split(/\s+/)) {
      const letzte = zeilen[zeilen.length - 1];
      if (letzte !== undefined && `${letzte} ${wort}`.length <= laenge) zeilen[zeilen.length - 1] = `${letzte} ${wort}`;
      else zeilen.push(wort);
    }
    return zeilen;
  }

  let zeilen = $derived.by(() => {
    const alle = umbrechen(buch.title || "Ohne Titel", 14);
    return alle.length > 6 ? [...alle.slice(0, 5), `${alle[5]} ...`] : alle;
  });
  let grad = $derived(Math.min(27, 164 / (Math.max(...zeilen.map((z) => z.length)) * 0.6)));
</script>

<svg viewBox="0 0 200 {HOEHE}" aria-hidden="true">
  <rect width="200" height={HOEHE} fill={farben[0]} />
  <rect x="18" y="30" width="46" height="7" fill={farben[1]} />
  {#each zeilen as zeile, n (n)}<text x="18" y={72 + n * grad * 1.13} class="t" font-size={grad} fill={farben[2]}>{zeile}</text>{/each}
  <text x="18" y={HOEHE - 20} class="a" fill={farben[2]}>{(buch.author ?? "").slice(0, 28)}</text>
</svg>

<style>
  .t {
    font-family: var(--buchschrift);
    font-weight: 700;
  }
  .a {
    font: 600 12px var(--schrift);
  }
</style>
