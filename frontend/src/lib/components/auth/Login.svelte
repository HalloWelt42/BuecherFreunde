<script>
  // Anmeldung mit dem Konto der Kellerwolke: Passwort oder Code vom Rechner (Kellerwolke, Einstellungen, Geräte),
  // wie in den anderen eigenen Apps. Gekoppelte Geräte bleiben angemeldet, bis man sie trennt.
  import { setToken } from "../../api/client.js";

  let { onSuccess = () => {} } = $props();

  const CODE_LAENGE = 8;
  const LINK_MARKE = "koppeln=";

  function codeNormal(text) {
    return text.replace(/[^0-9a-z]/gi, "").toUpperCase().slice(0, CODE_LAENGE);
  }

  function codeAusLink() {
    const marke = location.hash.slice(1);
    if (!marke.startsWith(LINK_MARKE)) return "";
    history.replaceState(null, "", location.pathname + location.search);
    return codeNormal(marke.slice(LINK_MARKE.length));
  }

  function geraeteArt() {
    const eigen = matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
    return eigen ? "webapp" : "browser";
  }

  function namensvorschlag() {
    const ua = navigator.userAgent;
    if (/iPad|Tablet/i.test(ua) || (/Macintosh/.test(ua) && navigator.maxTouchPoints > 1)) return "Tablet";
    if (/iPhone|Mobile/i.test(ua)) return "Telefon";
    if (/Android/i.test(ua)) return "Tablet";
    return "Rechner";
  }

  const ausLink = codeAusLink();
  let modus = $state(ausLink ? "code" : "passwort");
  let kennung = $state("");
  let passwort = $state("");
  let code = $state(ausLink);
  let geraet = $state(namensvorschlag());
  let fokus = $state(false);
  let fehler = $state("");
  let laeuft = $state(false);
  let angaben = $state({ name: "BücherFreunde", kellerwolke: "", besitzer: null, eingerichtet: true });

  $effect(() => {
    fetch("/api/anmeldung/app").then((r) => (r.ok ? r.json() : null)).then((a) => { if (a) angaben = a; }).catch(() => {});
  });

  async function senden(pfad, koerper) {
    fehler = "";
    laeuft = true;
    try {
      const res = await fetch(pfad, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(koerper) });
      const daten = await res.json().catch(() => ({}));
      if (!res.ok) {
        fehler = daten.detail || (res.status === 401 ? "Anmeldung fehlgeschlagen" : `Fehler ${res.status}`);
        return;
      }
      setToken(daten.token);
      onSuccess();
    } catch {
      fehler = "Server nicht erreichbar";
    } finally {
      laeuft = false;
    }
  }

  function mitPasswort(e) {
    e.preventDefault();
    senden("/api/anmeldung", { kennung: kennung.trim(), passwort });
  }

  function mitCode(e) {
    e.preventDefault();
    senden("/api/anmeldung/koppeln", { code, name: geraet.trim(), art: geraeteArt() });
  }
</script>

<div class="login-overlay">
  {#if modus === "passwort"}
    <form class="login-card" onsubmit={mitPasswort}>
      <div class="login-icon"><i class="fa-solid fa-book-open-reader"></i></div>
      <h1 class="login-title">{angaben.name}</h1>
      <p class="login-hint">
        <i class="fa-solid fa-cloud"></i> Anmelden mit deinem Konto der Kellerwolke{#if angaben.kellerwolke}{" "}unter <b>{angaben.kellerwolke}</b>{/if}.
        {#if angaben.besitzer}Diese App gehört dem Konto <b>{angaben.besitzer}</b>.{/if}
      </p>
      {#if !angaben.eingerichtet}
        <p class="login-error">Die App ist noch nicht mit der Kellerwolke verbunden (App-Zugang fehlt).</p>
      {/if}
      <div class="login-field">
        <input class="login-input" type="text" autocomplete="username" placeholder="Name oder Kürzel" bind:value={kennung} disabled={laeuft} />
      </div>
      <div class="login-field">
        <input class="login-input" type="password" autocomplete="current-password" placeholder="Passwort" bind:value={passwort} disabled={laeuft} />
      </div>
      {#if fehler}<p class="login-error">{fehler}</p>{/if}
      <button class="login-btn" type="submit" disabled={laeuft || !kennung.trim() || !passwort}>
        {#if laeuft}<i class="fa-solid fa-spinner fa-spin"></i> Anmelden ...{:else}<i class="fa-solid fa-right-to-bracket"></i> Anmelden{/if}
      </button>
      <div class="login-oder">oder</div>
      <button class="login-btn zweit" type="button" onclick={() => ((modus = "code"), (fehler = ""))}>
        <i class="fa-solid fa-link"></i> Mit Code koppeln
      </button>
      <p class="login-hint klein">Den Code zeigt die Kellerwolke unter Einstellungen, Geräte.</p>
    </form>
  {:else}
    <form class="login-card" onsubmit={mitCode}>
      <div class="kopf-zeile">
        <button class="rund" type="button" title="Zurück zur Anmeldung" onclick={() => ((modus = "passwort"), (fehler = ""))}>
          <i class="fa-solid fa-chevron-left"></i>
        </button>
        <h1 class="login-title">Gerät koppeln</h1>
      </div>
      <p class="login-hint">
        Tipp den Code aus der Kellerwolke{#if angaben.kellerwolke}{" "}unter <b>{angaben.kellerwolke}</b>{/if} ein (dort Einstellungen,
        Geräte). Danach bleibt dieses Gerät angemeldet, bis du es trennst; ein Passwort wird hier nicht gespeichert.
      </p>
      {#if fehler}<p class="login-error">{fehler}</p>{/if}
      <label class="code-feld">
        <span class="kaestchen" aria-hidden="true">
          {#each Array.from({ length: CODE_LAENGE }) as _, i (i)}
            {#if i === CODE_LAENGE / 2}<span class="luecke"></span>{/if}
            <span class="k" class:aktiv={fokus && i === Math.min(code.length, CODE_LAENGE - 1)}>{code[i] ?? ""}</span>
          {/each}
        </span>
        <input aria-label="Kopplungscode" value={code} autocomplete="one-time-code" autocapitalize="characters" spellcheck="false"
               oninput={(e) => { code = codeNormal(e.currentTarget.value); e.currentTarget.value = code; }}
               onfocus={() => (fokus = true)} onblur={() => (fokus = false)} />
      </label>
      <div class="login-field">
        <input class="login-input" placeholder="Name des Geräts" bind:value={geraet} maxlength="60" />
      </div>
      <button class="login-btn" type="submit" disabled={laeuft || code.length !== CODE_LAENGE || !geraet.trim()}>
        <i class="fa-solid fa-link"></i> {laeuft ? "Koppeln ..." : "Koppeln"}
      </button>
    </form>
  {/if}
</div>

<style>
  .login-overlay {
    position: fixed;
    inset: 0;
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--color-bg-primary);
  }

  .login-card {
    width: 100%;
    max-width: 360px;
    padding: 2.5rem 2rem;
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 12px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.75rem;
  }

  .login-icon {
    font-size: 2.5rem;
    color: var(--color-accent);
    margin-bottom: 0.25rem;
  }

  .login-title {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .login-hint {
    font-size: 0.875rem;
    color: var(--color-text-secondary);
    text-align: center;
  }

  .login-field {
    width: 100%;
    margin-top: 0.25rem;
  }

  .login-input {
    width: 100%;
    padding: 0.625rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.875rem;
    outline: none;
    box-sizing: border-box;
  }

  .login-input:focus {
    border-color: var(--color-accent);
  }

  .login-input::placeholder {
    color: var(--color-text-muted);
  }

  .login-error {
    font-size: 0.8125rem;
    color: var(--color-error);
    font-weight: 500;
    text-align: center;
  }

  .login-btn {
    width: 100%;
    padding: 0.625rem;
    border: none;
    border-radius: 8px;
    background: var(--color-accent);
    color: #fff;
    font-size: 0.875rem;
    font-weight: 600;
    font-family: inherit;
    cursor: pointer;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.5rem;
    margin-top: 0.5rem;
  }

  .login-btn:hover:not(:disabled) {
    background: var(--color-accent-hover);
  }

  .login-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }

  .login-hint.klein {
    font-size: 0.8rem;
  }

  .login-oder {
    font-size: 0.8rem;
    color: var(--color-text-muted);
  }

  .login-btn.zweit {
    background: transparent;
    color: var(--color-text-primary);
    border: 1px solid var(--color-border);
    margin-top: 0;
  }

  .login-btn.zweit:hover:not(:disabled) {
    background: var(--color-bg-primary);
  }

  .kopf-zeile {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    width: 100%;
  }

  .rund {
    width: 2rem;
    height: 2rem;
    border-radius: 50%;
    border: 1px solid var(--color-border);
    background: transparent;
    color: var(--color-text-primary);
    cursor: pointer;
  }

  .code-feld {
    position: relative;
    width: 100%;
    display: flex;
    justify-content: center;
    cursor: text;
  }

  .kaestchen {
    display: flex;
    gap: 0.35rem;
  }

  .k {
    width: 2rem;
    height: 2.6rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.2rem;
    font-weight: 600;
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
  }

  .k.aktiv {
    border-color: var(--color-accent);
  }

  .luecke {
    width: 0.5rem;
  }

  .code-feld input {
    position: absolute;
    inset: 0;
    opacity: 0;
    font-size: 16px;
  }
</style>
