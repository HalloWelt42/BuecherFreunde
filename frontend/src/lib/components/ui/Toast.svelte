<script>
  import { ui } from "../../stores/ui.svelte.js";

  const icons = {
    success: "fa-circle-check",
    error: "fa-circle-xmark",
    info: "fa-circle-info",
    warning: "fa-triangle-exclamation",
  };
</script>

{#if ui.toasts.length > 0}
  <div class="toast-container">
    {#each ui.toasts as toast (toast.id)}
      <div
        class="toast toast-{toast.typ}"
        role="alert"
        onclick={() => ui.removeToast(toast.id)}
      >
        <i class="fa-solid {icons[toast.typ] || icons.info}"></i>
        <span class="toast-text">{toast.text}</span>
        <button class="toast-close" onclick={() => ui.removeToast(toast.id)}>
          <i class="fa-solid fa-xmark"></i>
        </button>
      </div>
    {/each}
  </div>
{/if}

<style>
  .toast-container {
    position: fixed;
    top: 1rem;
    right: 1rem;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    max-width: 360px;
    pointer-events: none;
  }

  .toast {
    display: flex;
    align-items: center;
    gap: 0.625rem;
    padding: 0.625rem 0.875rem;
    border-radius: 6px;
    font-size: 0.8125rem;
    line-height: 1.4;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
    pointer-events: auto;
    cursor: pointer;
    animation: toast-in 0.25s ease-out;
    border: 1px solid;
  }

  .toast i:first-child {
    font-size: 1rem;
    flex-shrink: 0;
  }

  .toast-text {
    flex: 1;
  }

  .toast-close {
    background: none;
    border: none;
    color: inherit;
    opacity: 0.5;
    cursor: pointer;
    padding: 0;
    font-size: 0.75rem;
    flex-shrink: 0;
  }

  .toast-close:hover {
    opacity: 1;
  }

  /* Typen */
  .toast-success {
    background: #0d3320;
    color: #4ade80;
    border-color: #166534;
  }

  .toast-error {
    background: #3b1219;
    color: #f87171;
    border-color: #7f1d1d;
  }

  .toast-info {
    background: #0c2d48;
    color: #60a5fa;
    border-color: #1e3a5f;
  }

  .toast-warning {
    background: #3d2e0a;
    color: #fbbf24;
    border-color: #78350f;
  }

  /* Light Mode */
  :global(:root:not(.dark)) .toast-success {
    background: #f0fdf4;
    color: #166534;
    border-color: #bbf7d0;
  }

  :global(:root:not(.dark)) .toast-error {
    background: #fef2f2;
    color: #991b1b;
    border-color: #fecaca;
  }

  :global(:root:not(.dark)) .toast-info {
    background: #eff6ff;
    color: #1e40af;
    border-color: #bfdbfe;
  }

  :global(:root:not(.dark)) .toast-warning {
    background: #fffbeb;
    color: #92400e;
    border-color: #fde68a;
  }

  @keyframes toast-in {
    from {
      opacity: 0;
      transform: translateX(1rem);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }
</style>
