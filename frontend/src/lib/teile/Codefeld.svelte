<script lang="ts">
  // Einen Code eintippen (Koppeln, Umzug): ein unsichtbares Feld über den Kästchen, das Kästchen der nächsten Stelle leuchtet
  import Codekaestchen from "./Codekaestchen.svelte";

  let { code, laenge, name, normal, onwahl }: { code: string; laenge: number; name: string; normal: (text: string) => string; onwahl: (code: string) => void } = $props();

  let fokus = $state(false);

  function tippt(e: Event & { currentTarget: HTMLInputElement }) {
    const neu = normal(e.currentTarget.value);
    e.currentTarget.value = neu;
    onwahl(neu);
  }
</script>

<label class="codefeld">
  <Codekaestchen {code} {laenge} aktiv={fokus ? Math.min(code.length, laenge - 1) : -1} />
  <input aria-label={name} value={code} autocomplete="one-time-code" autocapitalize="characters" spellcheck="false" oninput={tippt} onfocus={() => (fokus = true)} onblur={() => (fokus = false)} />
</label>

<style>
  .codefeld {
    position: relative;
    display: block;
  }
  input {
    position: absolute;
    inset: 0;
    width: 100%;
    border: 0;
    background: none;
    color: transparent;
    caret-color: transparent;
    outline: 0;
    font-size: 1rem;
  }
</style>
