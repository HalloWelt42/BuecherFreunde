<script>
  import { setToken } from "../../api/client.js";

  let { onSuccess = () => {} } = $props();

  let benutzername = $state("");
  let passwort = $state("");
  let fehler = $state("");
  let pruefen = $state(false);

  async function anmelden() {
    const name = benutzername.trim();
    if (!name || !passwort) {
      fehler = "Bitte Benutzername und Passwort eingeben";
      return;
    }

    pruefen = true;
    fehler = "";

    try {
      const res = await fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ benutzername: name, passwort }),
      });

      if (res.ok) {
        const daten = await res.json();
        setToken(daten.token);
        onSuccess();
      } else if (res.status === 401) {
        fehler = "Benutzername oder Passwort ist falsch";
      } else {
        fehler = "Anmeldung fehlgeschlagen";
      }
    } catch {
      fehler = "Server nicht erreichbar";
    } finally {
      pruefen = false;
    }
  }

  function onKeydown(e) {
    if (e.key === "Enter") anmelden();
  }
</script>

<div class="login-overlay">
  <div class="login-card">
    <div class="login-icon">
      <i class="fa-solid fa-book-open-reader"></i>
    </div>
    <h1 class="login-title">BücherFreunde</h1>
    <p class="login-hint">Bitte anmelden, um fortzufahren.</p>

    <div class="login-field">
      <input
        class="login-input"
        type="text"
        autocomplete="username"
        placeholder="Benutzername"
        bind:value={benutzername}
        onkeydown={onKeydown}
        disabled={pruefen}
      />
    </div>

    <div class="login-field">
      <input
        class="login-input"
        type="password"
        autocomplete="current-password"
        placeholder="Passwort"
        bind:value={passwort}
        onkeydown={onKeydown}
        disabled={pruefen}
      />
    </div>

    {#if fehler}
      <p class="login-error">{fehler}</p>
    {/if}

    <button class="login-btn" onclick={anmelden} disabled={pruefen}>
      {#if pruefen}
        <i class="fa-solid fa-spinner fa-spin"></i> Prüfe...
      {:else}
        <i class="fa-solid fa-right-to-bracket"></i> Anmelden
      {/if}
    </button>
  </div>
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
</style>
