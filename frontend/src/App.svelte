<script>
  import { onMount, onDestroy, tick } from "svelte";
  import { analysis } from "./lib/stores.js";
  import Editor from "./components/Editor.svelte";
  import Suggestions from "./components/Suggestions.svelte";
  import Translator from "./components/Translator.svelte";
  import {
    detectCliches,
    detectRepetition,
    detectDoubledWords,
    detectLongSentences,
    detectStartRepetition,
    splitSentences,
    maskLatex,
  } from './lib/static-checks.js'
  import { checkCitations } from './lib/latex-bib.js'
  import { computeStats } from './lib/text-stats.js'

  let page = window.location.pathname.replace(/\/$/, '') || '/'

  function navigate(to) {
    history.pushState(null, '', to)
    page = to
  }

  function onPopState() {
    page = window.location.pathname.replace(/\/$/, '') || '/'
  }

  let text = "";
  let variant = "british";
  let modeChoice = "auto";
  let debounceTimer = null;
  let sentenceCount = 0;
  let editorRef;
  let fileInput;
  let undoStack = []
  let redoStack = []
  const MAX_UNDO = 50
  let dismissedStatic = new Set()
  try {
    dismissedStatic = new Set(
      JSON.parse(localStorage.getItem("semantix_dismissed_static") || "[]"),
    )
  } catch (_) {}
  let typingSnapshotTaken = false
  let draftReady = false
  let copied = false
  let copyTimer = null
  let llmStatus = "unknown";
  let llmModel = "";
  let healthTimer = null;
  let lastError = null;
  let models = [];
  let analyzerModel = "";
  let apiStyle = null;

  $: detectedMode =
    /\\(?:begin|end|section|usepackage|documentclass|textbf|emph)\s*\{/.test(
      text,
    )
      ? "latex"
      : "plain";
  $: mode = modeChoice === "auto" ? detectedMode : modeChoice;

  // Static checks run on a LaTeX-masked copy so commands, math, and keys are
  // not flagged as prose; masking preserves offsets into the raw text.
  $: checkText = mode === 'latex' ? maskLatex(text) : text

  $: clicheIssues = detectCliches(checkText)
  $: repetitionIssues = detectRepetition(checkText)
  $: doubledIssues = detectDoubledWords(checkText)
  $: longSentenceIssues = detectLongSentences(checkText)
  $: startRepIssues = detectStartRepetition(checkText)
  // Citation checking disabled for now — flip this flag to re-enable.
  const CITATIONS_ENABLED = false
  $: citationIssues = CITATIONS_ENABLED && mode === 'latex' ? checkCitations(text) : []
  $: staticIssues = [
    ...doubledIssues,
    ...repetitionIssues,
    ...clicheIssues,
    ...longSentenceIssues,
    ...startRepIssues,
    ...citationIssues,
  ].filter(issue => !dismissedStatic.has(issue.id))

  // Repeated words are listed in the table but not marked in the editor —
  // editor marks are for grammar-level issues only.
  const RANGE_TYPES = { cliche: 'cliche', doubled: 'rep' }
  $: staticRanges = staticIssues.flatMap(issue => {
    const type = RANGE_TYPES[issue.category]
    if (!type) return []
    return issue.ranges.map(r => ({ start: r.start, end: r.end, type }))
  })

  $: stats = computeStats(checkText)
  $: if (!text.trim() && dismissedStatic.size) {
    dismissedStatic = new Set()
    persistDismissedStatic()
  }

  $: activeSentence =
    $analysis.activeIndex == null
      ? null
      : $analysis.sentences.find((s) => s.sentence_index === $analysis.activeIndex);
  $: sentenceActiveRange = (() => {
    if (!activeSentence) return null;
    const start = text.indexOf(activeSentence.original);
    return start === -1 ? null : { start, end: start + activeSentence.original.length };
  })();
  // A jump briefly washes its target so the word is findable without
  // permanent editor marks.
  let jumpFlash = null;
  let jumpFlashTimer = null;
  $: activeRange = jumpFlash ?? sentenceActiveRange;

  async function checkHealth() {
    try {
      const resp = await fetch("/health");
      const data = await resp.json();
      const wasOffline = llmStatus !== "online";
      llmStatus = data.ollama ? "online" : "offline";
      llmModel = data.model || "";
      if (llmStatus === "online" && wasOffline && models.length === 0) loadModels();
    } catch (_) {
      llmStatus = "offline";
    }
  }

  async function loadModels() {
    try {
      const resp = await fetch("/models");
      const data = await resp.json();
      models = data.models || [];
      analyzerModel = data.analyzer_model || "";
      apiStyle = data.api_style;
    } catch (_) {}
  }

  // The configured model may not be in the server's list (e.g. not pulled yet).
  $: modelOptions =
    analyzerModel && !models.includes(analyzerModel)
      ? [analyzerModel, ...models]
      : models;

  async function onModelChange() {
    try {
      await fetch("/models/select", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ target: "analyzer", model: analyzerModel }),
      });
      llmModel = analyzerModel;
      if (text.trim()) {
        clearTimeout(debounceTimer);
        triggerAnalysis();
      }
    } catch (_) {}
  }

  $: {
    if ($analysis.error && $analysis.error !== lastError) {
      lastError = $analysis.error;
      checkHealth();
    } else if (!$analysis.error) {
      lastError = null;
    }
  }

  onMount(() => {
    try {
      const saved = JSON.parse(
        localStorage.getItem("semantix_settings") || "{}",
      );
      if (saved.variant) variant = saved.variant;
      if (saved.modeChoice) modeChoice = saved.modeChoice;
    } catch (_) {}
    try {
      const draft = localStorage.getItem("semantix_draft");
      if (draft && draft.trim()) {
        text = draft;
        triggerAnalysis();
      }
    } catch (_) {}
    draftReady = true;
    fetch("/warmup", { method: "POST" }).catch(() => {});
    checkHealth();
    loadModels();
    healthTimer = setInterval(checkHealth, 60000);
  });

  onDestroy(() => clearInterval(healthTimer));

  $: localStorage.setItem(
    "semantix_settings",
    JSON.stringify({ variant, modeChoice }),
  );

  $: if (draftReady) saveDraft(text);

  function saveDraft(t) {
    try {
      if (t.length < 500000) localStorage.setItem("semantix_draft", t);
    } catch (_) {}
  }

  async function copyText() {
    try {
      await navigator.clipboard.writeText(text);
      copied = true;
      clearTimeout(copyTimer);
      copyTimer = setTimeout(() => (copied = false), 1500);
    } catch (_) {}
  }

  function persistDismissedStatic() {
    try {
      localStorage.setItem(
        "semantix_dismissed_static",
        JSON.stringify([...dismissedStatic]),
      );
    } catch (_) {}
  }

  function onDismissStatic(e) {
    dismissedStatic = new Set([...dismissedStatic, e.detail.id]);
    persistDismissedStatic();
  }

  function onJumpRange(e) {
    const { start, end } = e.detail;
    editorRef?.highlightRange(start, end);
    jumpFlash = { start, end };
    clearTimeout(jumpFlashTimer);
    jumpFlashTimer = setTimeout(() => (jumpFlash = null), 1600);
  }

  function onTextChange(e) {
    // One undo step per typing burst, so Ctrl+Z after an accept doesn't
    // silently revert past everything typed since.
    if (!typingSnapshotTaken) {
      undoStack = [...undoStack.slice(-MAX_UNDO + 1), text];
      redoStack = [];
      typingSnapshotTaken = true;
    }
    text = e.detail.text;
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      typingSnapshotTaken = false;
      triggerAnalysis();
    }, 800);
  }

  function setVariant(v) {
    variant = v;
    clearTimeout(debounceTimer);
    if (text.trim()) triggerAnalysis();
  }

  function setModeChoice(m) {
    if (modeChoice === m) return;
    modeChoice = m;
    clearTimeout(debounceTimer);
    if (text.trim()) triggerAnalysis();
  }

  function openFile() {
    fileInput?.click();
  }

  function onFileChosen(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    file.text().then((content) => {
      text = content;
      clearTimeout(debounceTimer);
      triggerAnalysis();
    });
    e.target.value = "";
  }

  function downloadText() {
    const blob = new Blob([text], { type: "text/plain" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = mode === "latex" ? "semantix.tex" : "semantix.txt";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  function triggerAnalysis() {
    sentenceCount = splitSentences(checkText).length || 1;
    analysis.analyse(text, variant, mode);
  }

  async function onSentenceSelect(e) {
    const { original } = e.detail;
    if (!original || !editorRef) return;

    // select() set activeIndex just before dispatching; wait for the ghost
    // layer to render the .frag-active wash, then scroll to it.
    await tick();
    if (editorRef.scrollToActive()) return;

    // No wash means the sentence text isn't in the raw text verbatim (LaTeX
    // mode, or the text was edited) — scroll to the longest matching phrase.
    const words = original.trim().split(/\s+/);
    for (let n = Math.min(7, words.length); n >= 3; n--) {
      for (let i = 0; i <= words.length - n; i++) {
        const phrase = words.slice(i, i + n).join(" ");
        const first = text.indexOf(phrase);
        if (first === -1) continue;
        const unique = text.indexOf(phrase, first + 1) === -1;
        if (unique || n === 3) {
          editorRef.highlightRange(first, first + phrase.length);
          return;
        }
      }
    }
  }

  function onAccept(e) {
    const { index, original, fragment, suggestion } = e.detail
    undoStack = [...undoStack.slice(-MAX_UNDO + 1), text]
    redoStack = []
    const fixedSentence = original.replace(fragment, suggestion)
    const newText = text.replace(original, fixedSentence)
    if (newText !== text) {
      text = newText
    } else {
      text = text.replace(fragment, suggestion)
    }
    clearTimeout(debounceTimer)
    // Re-check only the edited sentence; other cards stay untouched.
    analysis.recheckSentence(index, fixedSentence)
  }

  function onAcceptAll(e) {
    const { sentences: sentencesToFix } = e.detail
    undoStack = [...undoStack.slice(-MAX_UNDO + 1), text]
    redoStack = []
    let current = text
    const rechecks = []
    for (const { index, original, issues } of sentencesToFix) {
      const sorted = [...issues].sort((a, b) => {
        return original.lastIndexOf(b.original_fragment) - original.lastIndexOf(a.original_fragment)
      })
      let fixed = original
      // Applies fixes right-to-left so earlier offsets stay valid; assumes non-overlapping fragments.
      for (const issue of sorted) {
        fixed = fixed.replace(issue.original_fragment, issue.suggestion)
      }
      current = current.replace(original, fixed)
      rechecks.push([index, fixed])
    }
    text = current
    clearTimeout(debounceTimer)
    for (const [index, fixed] of rechecks) analysis.recheckSentence(index, fixed)
  }

  function handleKeydown(e) {
    if (!(e.ctrlKey || e.metaKey)) return
    const key = e.key.toLowerCase()
    if (key === 'z' && !e.shiftKey) {
      if (undoStack.length === 0) return
      e.preventDefault()
      redoStack = [...redoStack, text]
      text = undoStack[undoStack.length - 1]
      undoStack = undoStack.slice(0, -1)
      clearTimeout(debounceTimer)
      triggerAnalysis()
    } else if ((key === 'z' && e.shiftKey) || key === 'y') {
      if (redoStack.length === 0) return
      e.preventDefault()
      undoStack = [...undoStack.slice(-MAX_UNDO + 1), text]
      text = redoStack[redoStack.length - 1]
      redoStack = redoStack.slice(0, -1)
      clearTimeout(debounceTimer)
      triggerAnalysis()
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} on:popstate={onPopState} />

<div class="app">
  <header class="header">
    <span class="logo">Semantix</span>
    <nav class="nav">
      <a
        href="/"
        class:active={page === '/'}
        on:click|preventDefault={() => navigate('/')}
      >Proofread</a>
      <a
        href="/translate"
        class:active={page === '/translate'}
        on:click|preventDefault={() => navigate('/translate')}
      >Translate</a>
    </nav>
    <div class="toolbar">
      <span
        class="status-dot {llmStatus}"
        title={llmStatus === "online"
          ? `LLM online${llmModel ? " · " + llmModel : ""}`
          : llmStatus === "offline"
            ? "LLM offline — check Ollama"
            : "Checking LLM…"}
      ></span>
      {#if page !== '/translate'}
        {#if mode === "latex"}
          <span class="mode-badge">LaTeX</span>
        {/if}
        {#if modelOptions.length > 0}
          <select
            class="model-select"
            bind:value={analyzerModel}
            on:change={onModelChange}
            title="Analysis model{apiStyle ? ` (${apiStyle === 'openai' ? 'OpenAI v1' : 'Ollama native'} API)` : ''}"
          >
            {#each modelOptions as m (m)}
              <option value={m}>{m}</option>
            {/each}
          </select>
        {/if}
        <button type="button" class="tool-btn" on:click={openFile} title="Open a .txt, .md, or .tex file">Open</button>
        <button type="button"
          class="tool-btn"
          on:click={copyText}
          disabled={!text.trim()}
          title="Copy text to clipboard">{copied ? "Copied ✓" : "Copy"}</button
        >
        <button type="button"
          class="tool-btn"
          on:click={downloadText}
          disabled={!text.trim()}
          title="Download text as a file">Save</button
        >
        <div class="toggle-group">
          <button type="button"
            class="toggle-btn"
            class:active={modeChoice === "auto"}
            title="Detect LaTeX automatically"
            on:click={() => setModeChoice("auto")}>Auto</button
          >
          <button type="button"
            class="toggle-btn"
            class:active={modeChoice === "plain"}
            on:click={() => setModeChoice("plain")}>Plain</button
          >
          <button type="button"
            class="toggle-btn"
            class:active={modeChoice === "latex"}
            on:click={() => setModeChoice("latex")}>LaTeX</button
          >
        </div>
        <div class="toggle-group">
          <button type="button"
            class="toggle-btn"
            class:active={variant === "british"}
            on:click={() => setVariant("british")}>British</button
          >
          <button type="button"
            class="toggle-btn"
            class:active={variant === "american"}
            on:click={() => setVariant("american")}>American</button
          >
        </div>
        <input
          type="file"
          accept=".txt,.md,.markdown,.tex,.text"
          bind:this={fileInput}
          on:change={onFileChosen}
          style="display: none"
        />
      {:else}
        <div class="toolbar-spacer"></div>
      {/if}
    </div>
  </header>

  <!-- Kept mounted so a finished translation survives tab switches. -->
  <div class="page-wrap" class:page-hide={page !== '/translate'}>
    <Translator />
  </div>
    <main class="main" class:page-hide={page === '/translate'}>
      <section class="panel left-panel">
        <div class="editor-slot">
          <Editor
            bind:this={editorRef}
            value={text}
            sentences={$analysis.sentences}
            activeIndex={$analysis.activeIndex}
            staticRanges={staticRanges}
            activeRange={activeRange}
            on:change={onTextChange}
          />
        </div>
        <div class="stats-bar">
          <span>{stats.words} word{stats.words === 1 ? "" : "s"}</span>
          <span>{text.length} chars</span>
          <span>{stats.sentences} sentence{stats.sentences === 1 ? "" : "s"}</span>
          {#if stats.words > 0}
            <span>~{stats.minutes} min read</span>
          {/if}
          {#if stats.flesch !== null}
            <span title="Flesch reading ease (0–100, higher is easier to read)">
              readability {stats.flesch} · {stats.fleschLabel}
            </span>
          {/if}
        </div>
      </section>

      <div class="divider"></div>

      <section class="panel right-panel">
        <Suggestions
          totalSentences={sentenceCount}
          staticIssues={staticIssues}
          on:select={onSentenceSelect}
          on:accept={onAccept}
          on:acceptAll={onAcceptAll}
          on:dismissStatic={onDismissStatic}
          on:jump={onJumpRange}
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

  .nav {
    display: flex;
    gap: 0.25rem;
  }

  .nav a {
    padding: 0.3rem 0.75rem;
    border-radius: var(--radius-md);
    font-size: 0.85rem;
    font-weight: 500;
    color: var(--color-text-muted);
    text-decoration: none;
    transition: background 0.12s, color 0.12s;
  }

  .nav a:hover {
    background: var(--bg-panel);
    color: var(--color-text);
  }

  .nav a.active {
    background: var(--color-primary);
    color: #fff;
    font-weight: 600;
  }

  .toolbar-spacer {
    width: 1px;
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

  .page-wrap {
    display: flex;
    flex-direction: column;
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .page-hide {
    display: none !important;
  }

  .panel {
    flex: 1;
    overflow: hidden;
    display: flex;
    flex-direction: column;
  }

  .editor-slot {
    flex: 1;
    min-height: 0;
    position: relative;
    overflow: hidden;
  }

  .stats-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem 1rem;
    padding: 0.4rem 1.25rem;
    border-top: 1px solid var(--color-border);
    font-size: 0.72rem;
    color: var(--color-text-muted);
    background: var(--bg-surface);
    flex-shrink: 0;
  }

  .tool-btn {
    padding: 0.3rem 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--bg-surface);
    cursor: pointer;
    font-size: 0.82rem;
    color: var(--color-text-muted);
    transition:
      background 0.12s,
      color 0.12s;
  }

  .tool-btn:hover:not(:disabled) {
    background: var(--bg-panel);
    color: var(--color-text);
  }

  .tool-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .model-select {
    padding: 0.3rem 0.5rem;
    border: 1px solid var(--color-border);
    border-radius: 6px;
    background: var(--bg-surface);
    cursor: pointer;
    font-size: 0.8rem;
    color: var(--color-text-muted);
    max-width: 170px;
    text-overflow: ellipsis;
  }

  .model-select:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: 1px;
  }

  .status-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #cbd5e1;
    flex-shrink: 0;
  }

  .status-dot.online {
    background: var(--color-success);
  }

  .status-dot.offline {
    background: var(--color-error);
  }

  .divider {
    width: 1px;
    background: var(--color-border);
    flex-shrink: 0;
  }
</style>
