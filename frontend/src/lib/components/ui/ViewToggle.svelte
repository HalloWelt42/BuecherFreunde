<script>
  import { ui } from "../../stores/ui.svelte.js";
</script>

<div class="view-toggle">
  <button
    class="toggle-btn"
    class:active={ui.viewMode === "grid"}
    onclick={() => (ui.viewMode = "grid")}
    title="Grid-Ansicht"
  >
    &#9638;&#9638;
  </button>
  <button
    class="toggle-btn"
    class:active={ui.viewMode === "list"}
    onclick={() => (ui.viewMode = "list")}
    title="Listenansicht"
  >
    &#9776;
  </button>
</div>

<style>
  .view-toggle {
    display: flex;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    overflow: hidden;
  }

  .toggle-btn {
    background: none;
    border: none;
    padding: 0.375rem 0.625rem;
    cursor: pointer;
    color: var(--color-text-muted);
    font-size: 0.875rem;
    transition: all 0.15s;
  }

  .toggle-btn:not(:last-child) {
    border-right: 1px solid var(--color-border);
  }

  .toggle-btn.active {
    background-color: var(--color-accent);
    color: #fff;
  }

  .toggle-btn:hover:not(.active) {
    background-color: var(--color-bg-tertiary);
  }
</style>
