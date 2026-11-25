<script lang="ts">
  // Danke sagen: Ko-fi und drei Kryptowährungen
  import { melde } from "../../lib/stand/meldungen.svelte";
  import Chip from "../../lib/teile/Chip.svelte";
  import Karte from "../../lib/teile/Karte.svelte";
  import Knopf from "../../lib/teile/Knopf.svelte";

  interface Waehrung {
    kennung: string;
    name: string;
    kuerzel: string;
    adresse: string;
  }

  const waehrungen: Waehrung[] = [
    { kennung: "btc", name: "Bitcoin", kuerzel: "BTC", adresse: "bc1qnd599khdkv3v3npmj9ufxzf6h4fzanny2acwqr" },
    { kennung: "doge", name: "Dogecoin", kuerzel: "DOGE", adresse: "DL7tuiYCqm3xQjMDXChdxeQxqUGMACn1ZV" },
    { kennung: "eth", name: "Ethereum", kuerzel: "ETH", adresse: "0x8A28fc47bFFFA03C8f685fa0836E2dBe1CA14F27" },
  ];

  let gewaehlt = $state("btc");
  let w = $derived(waehrungen.find((x) => x.kennung === gewaehlt) ?? waehrungen[0]);

  async function kopiere() {
    try {
      await navigator.clipboard.writeText(w.adresse);
      melde.gut(`${w.kuerzel}-Adresse kopiert`);
    } catch {
      melde.warn("Kopieren ging nicht, Adresse bitte markieren");
    }
  }
</script>

<div class="werkzeug"><h1>Danke sagen</h1></div>
<div class="inhalt rollen">
  <div class="raster">
    <Karte titel="BücherFreunde unterstützen" symbol="heart">
      <p>BücherFreunde ist ein freies Projekt ohne Gewinnabsicht. Wenn es dir gefällt, freue ich mich über eine kleine Aufmerksamkeit.</p>
      <div class="reihe"><Knopf text="Auf Ko-fi unterstützen" symbol="mug-hot" haupt extern href="https://ko-fi.com/HalloWelt42" /></div>
      <p class="leise">Vielen Dank für deine Unterstützung!</p>
    </Karte>
    <Karte titel="Mit Kryptowährung" symbol="coins">
      <div class="reihe" role="group" aria-label="Währung">
        {#each waehrungen as x (x.kennung)}<Chip text={x.name} zahl={x.kuerzel} gedrueckt={gewaehlt === x.kennung} onclick={() => (gewaehlt = x.kennung)} />{/each}
      </div>
      <div class="krypto">
        <img src="/images/{w.kennung}-qr.svg" alt="QR-Code der Adresse für {w.name}" width="160" height="160" />
        <div class="krypto-text">
          <b>{w.name}</b>
          <code class="pfad">{w.adresse}</code>
          <div class="reihe"><Knopf text="Adresse kopieren" symbol="copy" klein onclick={() => void kopiere()} /></div>
        </div>
      </div>
    </Karte>
  </div>
</div>

<style>
  .krypto {
    display: flex;
    flex-wrap: wrap;
    gap: 0.875rem;
    align-items: center;
  }
  .krypto img {
    width: 10rem;
    height: 10rem;
    padding: 0.5rem;
    border-radius: var(--r2);
    background: #fff;
  }
  .krypto-text {
    flex: 1 1 12rem;
    min-width: 0;
    display: grid;
    gap: 0.5rem;
  }
</style>
