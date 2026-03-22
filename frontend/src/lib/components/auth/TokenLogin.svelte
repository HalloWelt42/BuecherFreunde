<script>
  import { setToken } from "../../api/client.js";

  let { onSuccess = () => {} } = $props();

  let token = $state("");
  let fehler = $state("");
  let pruefen = $state(false);

  async function anmelden() {
    const t = token.trim();
    if (!t) {
      fehler = "Bitte Token eingeben";
      return;
    }

    pruefen = true;
    fehler = "";

    try {
      const res = await fetch("/api/config", {
        headers: { Authorization: `Bearer ${t}` },
      });

      if (res.ok) {
        setToken(t);
        onSuccess();
      } else {
        fehler = "Ungültiger Token";
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
    <p class="login-hint">API-Token eingeben, um fortzufahren.</p>
    <p class="login-sub">Der Token steht in der <code>.env</code>-Datei auf dem Server.</p>

    <div class="login-field">
      <input
        class="login-input"
        type="password"
        placeholder="API-Token"
        bind:value={token}
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

  .login-sub {
    font-size: 0.75rem;
    color: var(--color-text-muted);
    text-align: center;
  }

  .login-sub code {
    font-family: var(--font-mono);
    background: var(--color-bg-tertiary);
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
    font-size: 0.6875rem;
  }

  .login-field {
    width: 100%;
    margin-top: 0.5rem;
  }

  .login-input {
    width: 100%;
    padding: 0.625rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 8px;
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.875rem;
    font-family: var(--font-mono);
    outline: none;
    box-sizing: border-box;
  }

  .login-input:focus {
    border-color: var(--color-accent);
  }

  .login-input::placeholder {
    color: var(--color-text-muted);
    font-family: var(--font-sans);
  }

  .login-error {
    font-size: 0.8125rem;
    color: var(--color-error);
    font-weight: 500;
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
    margin-top: 0.25rem;
  }

  .login-btn:hover:not(:disabled) {
    background: var(--color-accent-hover);
  }

  .login-btn:disabled {
    opacity: 0.6;
    cursor: not-allowed;
  }
</style>
