<script>
  let { params } = $props();
</script>

<div class="book-detail-page">
  <div class="page-header">
    <a href="#/" class="back-link">&larr; Zurück</a>
    <h1>Buchdetails</h1>
  </div>
  <p class="placeholder">Buch #{params.id} wird geladen...</p>
</div>

<style>
  .book-detail-page {
    max-width: 900px;
  }

  .page-header {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--color-text-primary);
  }

  .back-link {
    color: var(--color-accent);
    text-decoration: none;
    font-size: 0.875rem;
  }

  .placeholder {
    color: var(--color-text-muted);
  }
</style>
