<script>
  let { onFiles = () => {} } = $props();

  let dragging = $state(false);
  let fileInput;

  function handleDrop(event) {
    event.preventDefault();
    dragging = false;
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) {
      onFiles(files);
    }
  }

  function handleDragOver(event) {
    event.preventDefault();
    dragging = true;
  }

  function handleDragLeave() {
    dragging = false;
  }

  function handleClick() {
    fileInput?.click();
  }

  function handleFileSelect(event) {
    const files = Array.from(event.target.files);
    if (files.length > 0) {
      onFiles(files);
    }
    event.target.value = "";
  }
</script>

<div
  class="upload-zone"
  class:dragging
  role="button"
  tabindex="0"
  ondrop={handleDrop}
  ondragover={handleDragOver}
  ondragleave={handleDragLeave}
  onclick={handleClick}
  onkeydown={(e) => e.key === "Enter" && handleClick()}
>
  <input
    bind:this={fileInput}
    type="file"
    accept=".pdf,.epub,.mobi,.txt,.md"
    multiple
    class="file-input"
    onchange={handleFileSelect}
  />
  <p class="upload-icon"><i class="fa-solid fa-cloud-arrow-up"></i></p>
  <p class="upload-text">
    {dragging ? "Hier ablegen..." : "Bücher hierher ziehen oder klicken"}
  </p>
  <p class="upload-hint">PDF, EPUB, MOBI, TXT, MD</p>
</div>

<style>
  .upload-zone {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 3rem 2rem;
    border: 2px dashed var(--color-border);
    border-radius: 12px;
    text-align: center;
    cursor: pointer;
    transition: all 0.15s;
  }

  .upload-zone:hover,
  .upload-zone.dragging {
    border-color: var(--color-accent);
    background-color: var(--color-accent-light);
  }

  .file-input {
    display: none;
  }

  .upload-icon {
    font-size: 2.5rem;
    margin-bottom: 0.75rem;
  }

  .upload-text {
    color: var(--color-text-secondary);
    font-size: 0.9375rem;
  }

  .upload-hint {
    color: var(--color-text-muted);
    font-size: 0.8125rem;
    margin-top: 0.375rem;
  }
</style>
