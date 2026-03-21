<script>
  import { route, matchRoute, handleLinkClick } from "./lib/router.svelte.js";
  import { ui } from "./lib/stores/ui.svelte.js";
  import Header from "./lib/components/layout/Header.svelte";
  import Sidebar from "./lib/components/layout/Sidebar.svelte";
  import Footer from "./lib/components/layout/Footer.svelte";

  import Library from "./pages/Library.svelte";
  import BookDetail from "./pages/BookDetail.svelte";
  import Reader from "./pages/Reader.svelte";
  import SearchResults from "./pages/SearchResults.svelte";
  import CollectionView from "./pages/CollectionView.svelte";
  import Import from "./pages/Import.svelte";
  import Settings from "./pages/Settings.svelte";

  const routeDefs = [
    { pattern: "/book/:id/read", component: Reader },
    { pattern: "/book/:id", component: BookDetail },
    { pattern: "/search", component: SearchResults },
    { pattern: "/collection/:id", component: CollectionView },
    { pattern: "/import", component: Import },
    { pattern: "/settings/*", component: Settings },
    { pattern: "/settings", component: Settings },
    { pattern: "/", component: Library },
  ];

  // route ist reaktives Objekt ($state in .svelte.js)
  let resolved = $derived.by(() => {
    const path = route.path;
    for (const def of routeDefs) {
      const match = matchRoute(def.pattern, path);
      if (match !== null) {
        const hasParams = Object.keys(match).length > 0;
        return { component: def.component, params: hasParams ? match : null };
      }
    }
    return null;
  });
</script>

<svelte:document onclick={handleLinkClick} />

<div class="app-layout" class:sidebar-collapsed={!ui.sidebarOpen}>
  <div class="grid-header">
    <Header />
  </div>

  <div class="grid-sidebar">
    <Sidebar currentPath={route.path} />
  </div>

  <main class="grid-main">
    {#if resolved}
      {#key route.path}
        {#if resolved.params}
          <resolved.component params={resolved.params} />
        {:else}
          <resolved.component />
        {/if}
      {/key}
    {/if}
  </main>

  <div class="grid-footer">
    <Footer />
  </div>
</div>

<style>
  .app-layout {
    display: grid;
    grid-template-areas:
      "header header"
      "sidebar main";
    grid-template-columns: var(--sidebar-width) 1fr;
    grid-template-rows: var(--header-height) 1fr;
    height: 100vh;
    overflow: hidden;
  }

  .app-layout.sidebar-collapsed {
    grid-template-columns: 0 1fr;
  }

  .app-layout.sidebar-collapsed .grid-sidebar {
    width: 0;
    padding: 0;
    border: none;
  }

  .grid-header {
    grid-area: header;
    z-index: 20;
  }

  .grid-sidebar {
    grid-area: sidebar;
    overflow-y: auto;
    overflow-x: hidden;
    transition: width 0.2s ease, padding 0.2s ease;
    width: var(--sidebar-width);
  }

  .grid-main {
    grid-area: main;
    padding: 1.5rem;
    overflow-y: auto;
    overflow-x: hidden;
  }

  .grid-footer {
    grid-area: footer;
    z-index: 50;
  }
</style>
