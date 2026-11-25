<script lang="ts">
  // Eigene Bilder hinter dem Glas: hochladen, wählen, blättern, entfernen
  import { groesse } from "../../lib/format";
  import { darstellung } from "../../lib/stand/darstellung.svelte";
  import { hintergrund, type Hintergrundbild } from "../../lib/stand/hintergrund.svelte";
  import { melde } from "../../lib/stand/meldungen.svelte";
  import { frage } from "../../lib/stand/rueckfrage.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";
  import Symbol from "../../lib/teile/Symbol.svelte";

  const ARTEN = ["image/jpeg", "image/png", "image/webp"];
  const HOECHSTENS = 10 * 1024 * 1024;

  let laedt = $state(false);
  let zieht = $state(false);
  let wahlfeld: HTMLInputElement | undefined = $state();

  $effect(() => void hintergrund.laden());

  function hindernis(datei: File): string {
    if (!ARTEN.includes(datei.type)) return `${datei.name}: nur JPG, PNG und WebP`;
    return datei.size > HOECHSTENS ? `${datei.name}: ${groesse(datei.size)}, höchstens 10 MB` : "";
  }

  async function nimm(dateien: Iterable<File>) {
    laedt = true;
    let da = 0;
    for (const datei of dateien) {
      const grund = hindernis(datei);
      if (grund) {
        melde.warn(grund);
        continue;
      }
      try {
        await hintergrund.hochladen(datei);
        da += 1;
      } catch (e) {
        melde.schlecht(e, datei.name);
      }
    }
    laedt = false;
    if (!da) return;
    hintergrund.waehle(hintergrund.bilder.length - 1);
    darstellung.grund = "bild";
    melde.gut(da === 1 ? "Bild hinzugefügt" : `${da} Bilder hinzugefügt`);
  }

  function gewaehlt(e: Event & { currentTarget: HTMLInputElement }) {
    const feld = e.currentTarget;
    void nimm([...(feld.files ?? [])]);
    feld.value = "";
  }

  function abgelegt(e: DragEvent) {
    e.preventDefault();
    zieht = false;
    void nimm([...(e.dataTransfer?.files ?? [])]);
  }

  function waehle(nummer: number) {
    hintergrund.waehle(nummer);
    darstellung.grund = "bild";
  }

  async function entferne(bild: Hintergrundbild) {
    const ja = await frage({ titel: "Hintergrundbild entfernen?", text: bild.dateiname, folgen: ["Das Bild wird am Server gelöscht, auch für andere Geräte."], ja: "Bild entfernen" });
    if (!ja) return;
    try {
      await hintergrund.entferne(bild.dateiname);
      if (!hintergrund.bilder.length && darstellung.grund === "bild") darstellung.grund = "";
      melde.gut("Bild entfernt");
    } catch (e) {
      melde.schlecht(e, "Nicht entfernt");
    }
  }
</script>

<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="ablagefeld" class:zieht ondragover={(e) => { e.preventDefault(); zieht = true; }} ondragleave={() => (zieht = false)} ondrop={abgelegt}>
  <span class="klein">Bilder hierher ziehen. JPG, PNG oder WebP, je höchstens 10 MB.</span>
  <Knopf text="Bild hinzufügen" symbol="plus" klein laeuft={laedt} onclick={() => wahlfeld?.click()} />
  <input type="file" accept={ARTEN.join(",")} multiple hidden aria-label="Bilder wählen" bind:this={wahlfeld} onchange={gewaehlt} />
</div>

{#if hintergrund.bilder.length}
  <div class="bilder">
    {#each hintergrund.bilder as bild, n (bild.dateiname)}
      <div class="bildkarte" class:gewaehlt={darstellung.grund === "bild" && hintergrund.nummer === n}>
        <button type="button" class="vorschaubild" aria-pressed={darstellung.grund === "bild" && hintergrund.nummer === n} aria-label="Bild {n + 1} wählen" title="Dieses Bild zeigen" onclick={() => waehle(n)}>
          <img src={hintergrund.adresseVon(bild.dateiname)} alt="" loading="lazy" />
          {#if darstellung.grund === "bild" && hintergrund.nummer === n}<span class="zeigt"><Symbol name="check" /></span>{/if}
        </button>
        <span class="reihe unten"><span class="leise zahl">{n + 1} von {hintergrund.bilder.length}</span><span class="schiebt"><Knopf text="Bild entfernen" symbol="trash" nur klein frei onclick={() => void entferne(bild)} /></span></span>
      </div>
    {/each}
  </div>
{:else}
  <p class="leise">Noch kein eigenes Bild. Ein Bild wird einmal weichgezeichnet und liegt dann ruhig hinter dem Glas.</p>
{/if}
