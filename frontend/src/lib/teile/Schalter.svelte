<script lang="ts">
  // Schalter für an und aus (BF-78). Die Beschriftung steht daneben; `name` sagt Vorleseprogrammen, was er schaltet.
  // Die Tippfläche reicht über den sichtbaren Schalter hinaus, damit er auch am Telefon gut zu treffen ist.
  let { an, name, gesperrt = false, onwahl }: { an: boolean; name: string; gesperrt?: boolean; onwahl: (an: boolean) => void } = $props();
</script>

<button type="button" class="schalter" class:an role="switch" aria-checked={an} aria-label={name} title={name} disabled={gesperrt} onclick={() => onwahl(!an)}></button>

<style>
  .schalter {
    position: relative;
    flex: none;
    width: 2.75rem;
    height: 1.5rem;
    border-radius: 99px;
    background: var(--vertieft-2);
    box-shadow: inset 0 0 0 1px var(--linie);
    cursor: pointer;
  }
  .schalter::before {
    content: "";
    position: absolute;
    inset: -0.625rem -0.25rem;
  }
  .schalter::after {
    content: "";
    position: absolute;
    top: 3px;
    left: 3px;
    width: calc(1.5rem - 6px);
    height: calc(1.5rem - 6px);
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 1px 2px rgb(0 0 0 / 0.3);
    transition: left 0.15s ease;
  }
  .schalter.an {
    background: var(--messing-flaeche);
  }
  .schalter.an::after {
    left: calc(100% - 1.5rem + 3px);
  }
  .schalter:disabled {
    opacity: 0.45;
    cursor: default;
  }
  @media (prefers-reduced-motion: reduce) {
    .schalter::after {
      transition: none;
    }
  }
</style>
