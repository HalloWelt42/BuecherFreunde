<script>
  import Router from "svelte-spa-router";
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

  const routes = {
    "/": Library,
    "/book/:id": BookDetail,
    "/book/:id/read": Reader,
    "/search": SearchResults,
    "/collection/:id": CollectionView,
    "/import": Import,
    "/settings": Settings,
  };
</script>

<div class="app-layout" class:sidebar-collapsed={!ui.sidebarOpen}>
  <div class="grid-header">
    <Header />
  </div>

  <div class="grid-sidebar">
    <Sidebar />
  </div>

  <main class="grid-main">
    <Router {routes} />
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
      "sidebar main"
      "footer footer";
    grid-template-columns: var(--sidebar-width) 1fr;
    grid-template-rows: var(--header-height) 1fr auto;
    min-height: 100vh;
  }

  .app-layout.sidebar-collapsed {
    grid-template-columns: 0 1fr;
  }

  .grid-header {
    grid-area: header;
  }

  .grid-sidebar {
    grid-area: sidebar;
    overflow: hidden;
  }

  .grid-main {
    grid-area: main;
    padding: 1.5rem;
    overflow-y: auto;
  }

  .grid-footer {
    grid-area: footer;
  }
</style>
