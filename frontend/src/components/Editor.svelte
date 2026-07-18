<script>
  import { createEventDispatcher } from "svelte";
  import { buildBackdropHtml, buildRangeHtml } from "../lib/highlighter.js";

  export let value = "";
  export let sentences = [];
  export let activeIndex = null;
  export let staticRanges = [];
  export let activeRange = null;

  const dispatch = createEventDispatcher();

  let textareaEl;
  let backdropEl;
  let activeEl;

  $: backdropHtml = buildBackdropHtml(value, sentences, staticRanges);
  $: activeHtml = buildRangeHtml(value, activeRange);

  function handleInput(e) {
    value = e.target.value;
    dispatch("change", { text: value });
  }

  function syncScroll() {
    if (!textareaEl) return;
    if (backdropEl) backdropEl.scrollTop = textareaEl.scrollTop;
    if (activeEl) activeEl.scrollTop = textareaEl.scrollTop;
  }

  function scrollAllTo(scrollTop) {
    textareaEl.scrollTo({ top: scrollTop, behavior: "smooth" });
    backdropEl.scrollTop = scrollTop;
    if (activeEl) activeEl.scrollTop = scrollTop;
  }

  // The active-sentence wash is already laid out in the ghost layer, so its
  // span's offsetTop is the scroll target — no measurement DOM needed.
  export function scrollToActive() {
    if (!textareaEl || !activeEl) return false;
    const span = activeEl.querySelector(".frag-active");
    if (!span) return false;
    scrollAllTo(Math.max(0, span.offsetTop - textareaEl.clientHeight / 3));
    return true;
  }

  export function highlightRange(start, end) {
    if (!textareaEl || !backdropEl) return;

    const contentEl = backdropEl.firstElementChild;
    if (!contentEl) return;

    const full = textareaEl.value;
    const savedHtml = contentEl.innerHTML;
    const marker = document.createElement("span");
    contentEl.textContent = "";
    contentEl.append(
      document.createTextNode(full.substring(0, start)),
      marker,
      document.createTextNode(full.substring(start)),
    );
    const scrollTop = Math.max(
      0,
      marker.offsetTop - textareaEl.clientHeight / 3,
    );
    contentEl.innerHTML = savedHtml;

    scrollAllTo(scrollTop);
  }
</script>

<div class="editor-wrapper" class:has-active={activeIndex !== null}>
  <div class="backdrop active-layer" bind:this={activeEl} aria-hidden="true">
    <div class="backdrop-content">{@html activeHtml}</div>
  </div>
  <div class="backdrop" bind:this={backdropEl} aria-hidden="true">
    <div class="backdrop-content">{@html backdropHtml}</div>
  </div>
  <textarea
    bind:this={textareaEl}
    class="editor"
    placeholder="Paste or type your text here…"
    {value}
    on:input={handleInput}
    on:scroll={syncScroll}
    spellcheck="false"
    autocomplete="off"
    autocorrect="off"
  ></textarea>
</div>

<style>
  .editor-wrapper {
    height: 100%;
    display: flex;
    flex-direction: column;
    position: relative;
    overflow: hidden;
  }

  .backdrop {
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
    z-index: 2;
  }

  .backdrop-content {
    font-family: var(--font-mono);
    font-size: 0.95rem;
    line-height: 1.7;
    padding: 1.25rem;
    box-sizing: border-box;
    white-space: pre-wrap;
    word-wrap: break-word;
    overflow-wrap: break-word;
    color: transparent;
    min-height: 100%;
  }

  :global(.frag-del) {
    background: var(--mark-del-bg);
    text-decoration: line-through;
    text-decoration-color: var(--mark-del-line);
    border-radius: var(--radius-sm);
    -webkit-box-decoration-break: clone;
    box-decoration-break: clone;
  }

  :global(.frag-spell) {
    text-decoration: underline wavy;
    text-decoration-color: var(--mark-spell-line);
  }

  :global(.frag-ins) {
    position: relative;
  }

  :global(.frag-ins::before) {
    content: "^";
    position: absolute;
    bottom: -1.1em;
    left: -0.1em;
    color: var(--mark-ins-color);
    font-size: 0.75em;
    font-weight: 800;
    pointer-events: none;
  }

  :global(.frag-ctx) {
    background: var(--mark-ctx-bg);
    border-radius: var(--radius-sm);
    -webkit-box-decoration-break: clone;
    box-decoration-break: clone;
  }

  :global(.frag-cliche) {
    background: var(--mark-cliche-bg);
    border-radius: var(--radius-sm);
    -webkit-box-decoration-break: clone;
    box-decoration-break: clone;
  }

  :global(.frag-rep) {
    background: var(--mark-rep-bg);
    border-radius: var(--radius-sm);
    -webkit-box-decoration-break: clone;
    box-decoration-break: clone;
  }

  :global(.frag-cite) {
    text-decoration: underline wavy;
    text-decoration-color: var(--mark-cite-line);
  }

  :global(.frag-active) {
    background: var(--mark-active-bg);
    border-radius: var(--radius-sm);
    -webkit-box-decoration-break: clone;
    box-decoration-break: clone;
  }

  .editor {
    position: relative;
    z-index: 1;
    flex: 1;
    width: 100%;
    resize: none;
    border: none;
    outline: none;
    font-family: var(--font-mono);
    font-size: 0.95rem;
    line-height: 1.7;
    padding: 1.25rem;
    box-sizing: border-box;
    color: var(--color-text);
    background: transparent;
  }

  .editor::placeholder {
    color: #aaa;
  }

  .editor-wrapper {
    border-left: 3px solid transparent;
  }

  .editor-wrapper.has-active {
    border-left-color: var(--color-primary);
  }
</style>
