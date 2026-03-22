<script>
  import { erstelleLabel } from "../../api/labels.js";

  let {
    bookId,
    positionLabel = "",
    positionPercent = 0,
    cfiReference = "",
    onCreated = () => {},
  } = $props();

  let open = $state(false);
  let name = $state("");
  let note = $state("");
  let selectedColor = $state("#4FC3F7");
  let saving = $state(false);
  let feedback = $state("");

  // Material Design Farben
  const farben = [
    { color: "#EF5350", name: "Rot" },
    { color: "#EC407A", name: "Pink" },
    { color: "#AB47BC", name: "Lila" },
    { color: "#7E57C2", name: "Violett" },
    { color: "#5C6BC0", name: "Indigo" },
    { color: "#42A5F5", name: "Blau" },
    { color: "#4FC3F7", name: "Hellblau" },
    { color: "#26C6DA", name: "Cyan" },
    { color: "#26A69A", name: "Teal" },
    { color: "#66BB6A", name: "Grün" },
    { color: "#9CCC65", name: "Hellgrün" },
    { color: "#FFEE58", name: "Gelb" },
    { color: "#FFA726", name: "Orange" },
    { color: "#FF7043", name: "Tiefes Orange" },
    { color: "#8D6E63", name: "Braun" },
    { color: "#BDBDBD", name: "Grau" },
  ];

  function toggle() {
    open = !open;
    if (open) {
      name = "";
      note = "";
      selectedColor = "#4FC3F7";
      feedback = "";
    }
  }

  async function save() {
    saving = true;
    try {
      await erstelleLabel(bookId, {
        color: selectedColor,
        name: name.slice(0, 50),
        note,
        page_reference: positionLabel,
        position_percent: positionPercent,
        cfi_reference: cfiReference,
      });
      feedback = "Label gesetzt";
      onCreated();
      setTimeout(() => { open = false; feedback = ""; }, 800);
    } catch {
      feedback = "Fehler";
    }
    saving = false;
  }
</script>

<div class="label-picker-wrap">
  <button class="tool-btn" class:active={open} onclick={toggle} title="Farbiges Label auf diese Stelle setzen">
    <i class="fa-solid fa-tag"></i>
  </button>

  {#if open}
    <div class="label-picker">
      {#if feedback}
        <div class="label-feedback">{feedback}</div>
      {:else}
        <div class="label-colors">
          {#each farben as f}
            <button
              class="color-dot"
              class:active={selectedColor === f.color}
              style="background-color: {f.color}"
              onclick={() => { selectedColor = f.color; }}
              title={f.name}
            ></button>
          {/each}
        </div>
        <input
          type="text"
          class="label-name-input"
          placeholder="Name (max. 50 Zeichen)"
          maxlength="50"
          bind:value={name}
        />
        <textarea
          class="label-note-input"
          placeholder="Notiz (optional)"
          rows="2"
          bind:value={note}
        ></textarea>
        <div class="label-footer">
          <span class="label-pos">{positionLabel}</span>
          <button class="label-save-btn" onclick={save} disabled={saving} title="Label speichern">
            <i class="fa-solid {saving ? 'fa-spinner fa-spin' : 'fa-check'}"></i> Setzen
          </button>
        </div>
      {/if}
    </div>
  {/if}
</div>

<style>
  .label-picker-wrap {
    position: relative;
  }

  .tool-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border: none;
    border-radius: 4px;
    background: none;
    color: var(--color-text-secondary);
    cursor: pointer;
    font-size: 0.75rem;
    transition: background-color 0.1s;
  }

  .tool-btn:hover {
    background-color: var(--color-bg-tertiary);
    color: var(--color-text-primary);
  }

  .tool-btn.active {
    background-color: var(--color-accent-light);
    color: var(--color-accent);
  }

  .label-picker {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 4px;
    width: 240px;
    padding: 10px;
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0,0,0,0.25);
    z-index: 50;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .label-colors {
    display: grid;
    grid-template-columns: repeat(8, 1fr);
    gap: 4px;
  }

  .color-dot {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
    transition: transform 0.1s;
  }

  .color-dot:hover {
    transform: scale(1.2);
  }

  .color-dot.active {
    border-color: var(--color-text-primary);
    transform: scale(1.15);
  }

  .label-name-input, .label-note-input {
    width: 100%;
    padding: 6px 8px;
    border: 1px solid var(--color-border);
    border-radius: 4px;
    background: var(--color-bg-primary);
    color: var(--color-text-primary);
    font-size: 0.75rem;
    font-family: inherit;
    resize: none;
  }

  .label-name-input:focus, .label-note-input:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  .label-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .label-pos {
    font-size: 0.625rem;
    color: var(--color-text-muted);
    font-family: inherit;
  }

  .label-save-btn {
    display: flex;
    align-items: center;
    gap: 4px;
    padding: 4px 12px;
    border: none;
    border-radius: 4px;
    background: var(--color-accent);
    color: white;
    cursor: pointer;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .label-save-btn:hover:not(:disabled) {
    opacity: 0.9;
  }

  .label-save-btn:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .label-feedback {
    padding: 8px;
    text-align: center;
    font-size: 0.75rem;
    font-weight: 600;
    color: var(--color-accent);
  }
</style>
