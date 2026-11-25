<script lang="ts">
  // "Seite 41 von 1.104, gedruckt 23"; die Seite lässt sich eintippen
  import { zahl } from "../../lib/format";
  let { seite, gesamt, gedruckt = "", onseite }: { seite: number; gesamt: number; gedruckt?: string; onseite: (nr: number) => void } = $props();

  function setze(e: Event) {
    const feld = e.currentTarget as HTMLInputElement;
    const nr = Number.parseInt(feld.value, 10);
    if (nr >= 1 && nr <= gesamt) onseite(nr);
    else feld.value = String(seite);
  }
</script>

<span class="stand zahl klein">
  <span class="nicht-schmal">Seite</span>
  <input class="seitenzahl" inputmode="numeric" aria-label="Seite" value={seite} onfocus={(e) => e.currentTarget.select()} onchange={setze} onkeydown={(e) => e.key === "Enter" && e.currentTarget.blur()} />
  <span class="von"><span>von {zahl(gesamt)}{#if gedruckt}<span class="nicht-schmal">,</span>{/if}</span>{#if gedruckt}<span class="nebenbei">gedruckt {gedruckt}</span>{/if}</span>
</span>

<style>
  .von {
    display: flex;
    gap: 0.25rem;
    min-width: 0;
  }
  /* Am Telefon steht die gedruckte Zahl darunter, so bleibt Platz für den Schalter */
  @container app (max-width: 720px) {
    .von {
      flex-direction: column;
      gap: 0;
      line-height: 1.2;
    }
    .nebenbei {
      font-size: 0.75rem;
    }
  }
  @container app (max-width: 430px) {
    .nicht-schmal {
      display: none;
    }
  }
</style>
