<script>
  import { onMount } from "svelte";
  import { analysis } from "./lib/stores.js";
  import Editor from "./components/Editor.svelte";
  import Suggestions from "./components/Suggestions.svelte";

  let text = "";
  let variant = "british";
  let debounceTimer = null;
  let sentenceCount = 0;
  let editorRef;

  $: mode =
    /\\(?:begin|end|section|usepackage|documentclass|textbf|emph)\s*\{/.test(
      text,
    )
      ? "latex"
      : "plain";

  onMount(() => {
    try {
      const saved = JSON.parse(
        localStorage.getItem("semantix_settings") || "{}",
      );
      if (saved.variant) variant = saved.variant;
    } catch (_) {}
    fetch("/warmup", { method: "POST" }).catch(() => {});
  });

  $: localStorage.setItem("semantix_settings", JSON.stringify({ variant }));

  function onTextChange(e) {
    text = e.detail.text;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(triggerAnalysis, 800);
  }

  function setVariant(v) {
    variant = v;
    clearTimeout(debounceTimer);
    if (text.trim()) triggerAnalysis();
  }

  function triggerAnalysis() {
    sentenceCount = (text.match(/[.!?]+/g) || []).length || 1;
    analysis.analyse(text, variant, mode);
  }

  function onSentenceSelect(e) {
    const { original } = e.detail;
    if (!original || !editorRef) return;

    const start = text.indexOf(original);
    if (start !== -1) {
      editorRef.highlightRange(start, start + original.length);
      return;
    }

    const words = original.trim().split(/\s+/);
    for (let n = Math.min(7, words.length); n >= 3; n--) {
      for (let i = 0; i <= words.length - n; i++) {
        const phrase = words.slice(i, i + n).join(" ");
        const first = text.indexOf(phrase);
        if (first === -1) continue;
        const unique = text.indexOf(phrase, first + 1) === -1;
        if (unique || n === 3) {
          if (editorRef.findAndScrollTo(phrase)) return;
        }
      }
    }
  }

  function onAccept(e) {
    const { original, fragment, suggestion } = e.detail;
    const fixedSentence = original.replace(fragment, suggestion);
    const newText = text.replace(original, fixedSentence);
    if (newText !== text) {
      text = newText;
    } else {
      text = text.replace(fragment, suggestion);
    }
    clearTimeout(debounceTimer);
    triggerAnalysis();
  }
</script>

<div class="app">
  <header class="header">
    <span class="logo">Semantix</span>
    <div class="toolbar">
      {#if mode === "latex"}
        <span class="mode-badge">LaTeX</span>
      {/if}
      <div class="toggle-group">
        <button
          class="toggle-btn"
          class:active={variant === "british"}
          on:click={() => setVariant("british")}>British</button
        >
        <button
          class="toggle-btn"
          class:active={variant === "american"}
          on:click={() => setVariant("american")}>American</button
        >
      </div>
    </div>
  </header>

  <main class="main">
    <section class="panel left-panel">
      <Editor
        bind:this={editorRef}
        value={text}
        sentences={$analysis.sentences}
        activeIndex={$analysis.activeIndex}
        on:change={onTextChange}
      />
    </section>

    <div class="divider"></div>

    <section class="panel right-panel">
      <Suggestions
        totalSentences={sentenceCount}
        on:select={onSentenceSelect}
        on:accept={onAccept}
      />
    </section>
  </main>
</div>

<style>
  .app {
    display: flex;
    flex-direction: column;
    height: 100vh;
    overflow: hidden;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 1.5rem;
    border-bottom: 1px solid var(--color-border);
    background: var(--bg-app);
    flex-shrink: 0;
  }

  .logo {
    font-size: 1.1rem;
    font-weight: 700;
    color: var(--color-primary);
    letter-spacing: -0.02em;
  }

  .toolbar {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .mode-badge {
    font-size: 0.72rem;
    font-weight: 700;
    color: #7c3aed;
    background: #ede9fe;
    border-radius: 4px;
    padding: 2px 7px;
    letter-spacing: 0.04em;
  }

  .toggle-group {
    display: flex;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    overflow: hidden;
  }

  .toggle-btn {
    padding: 0.3rem 0.75rem;
    border: none;
    background: var(--bg-surface);
    cursor: pointer;
    font-size: 0.82rem;
    color: var(--color-text-muted);
    transition:
      background 0.12s,
      color 0.12s;
  }

  .toggle-btn.active {
    background: var(--color-primary);
    color: #fff;
    font-weight: 600;
  }

  .main {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .panel {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .divider {
    width: 1px;
    background: var(--color-border);
    flex-shrink: 0;
  }
</style>
