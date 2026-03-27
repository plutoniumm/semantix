<script>
  import { createEventDispatcher } from "svelte";
  import { buildBackdropHtml } from "../lib/highlighter.js";

  export let value = "";
  export let sentences = [];
  export let activeIndex = null;

  const dispatch = createEventDispatcher();

  let textareaEl;
  let backdropEl;

  $: backdropHtml = buildBackdropHtml(value, sentences);

  function handleInput(e) {
    value = e.target.value;
    dispatch("change", { text: value });
  }

  function syncScroll() {
    if (backdropEl && textareaEl) {
      backdropEl.scrollTop = textareaEl.scrollTop;
    }
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

    textareaEl.scrollTop = scrollTop;
    backdropEl.scrollTop = scrollTop;
  }

  export function findAndScrollTo(phrase) {
    if (!textareaEl || !backdropEl || !window.find) return false;

    const found = window.find(phrase, false, false, true);
    if (!found) return false;

    const sel = window.getSelection();
    const rect =
      sel?.rangeCount > 0 ? sel.getRangeAt(0).getBoundingClientRect() : null;
    sel?.removeAllRanges();
    if (!rect) return false;

    const textareaRect = textareaEl.getBoundingClientRect();
    const currentOffset = rect.top - textareaRect.top;
    const scrollTop = Math.max(
      0,
      textareaEl.scrollTop + currentOffset - textareaEl.clientHeight / 3,
    );
    textareaEl.scrollTop = scrollTop;
    backdropEl.scrollTop = scrollTop;
    return true;
  }
</script>

<div class="editor-wrapper" class:has-active={activeIndex !== null}>
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
