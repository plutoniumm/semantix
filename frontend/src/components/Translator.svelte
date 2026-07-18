<script>
  import { onMount } from 'svelte'
  import { LANGUAGES } from '../lib/languages.js'

  let sourceLang = 'eng_Latn'
  let targetLang = 'fra_Latn'
  let inputText  = ''
  let outputText = ''
  let loading    = false
  let error      = null
  let models = []
  let translateModel = ''

  onMount(async () => {
    try {
      const resp = await fetch('/models')
      const data = await resp.json()
      models = data.models || []
      translateModel = data.translate_model || ''
    } catch (_) {}
  })

  $: modelOptions =
    translateModel && !models.includes(translateModel)
      ? [translateModel, ...models]
      : models

  async function onModelChange() {
    try {
      await fetch('/models/select', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target: 'translator', model: translateModel }),
      })
    } catch (_) {}
  }

  async function translate() {
    if (!inputText.trim()) return
    loading = true
    error   = null
    outputText = ''
    try {
      const resp = await fetch('/translation', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: inputText, source_lang: sourceLang, target_lang: targetLang }),
      })
      if (!resp.ok) {
        const data = await resp.json().catch(() => ({}))
        throw new Error(data.detail || `Server error ${resp.status}`)
      }
      const data = await resp.json()
      outputText = data.translation
    } catch (err) {
      error = err.message
    } finally {
      loading = false
    }
  }

  function swapLanguages() {
    ;[sourceLang, targetLang] = [targetLang, sourceLang]
    ;[inputText, outputText]  = [outputText, inputText]
  }

  let copied = false
  let copyTimer = null

  async function copyOutput() {
    try {
      await navigator.clipboard.writeText(outputText)
      copied = true
      clearTimeout(copyTimer)
      copyTimer = setTimeout(() => (copied = false), 1500)
    } catch (_) {}
  }

  function onInputKeydown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault()
      translate()
    }
  }
</script>

<div class="translator">
  <div class="lang-bar">
    <select bind:value={sourceLang} class="lang-select">
      {#each LANGUAGES as lang (lang.code)}
        <option value={lang.code}>{lang.name}</option>
      {/each}
    </select>

    <button type="button" class="swap-btn" on:click={swapLanguages} title="Swap languages">&#8644;</button>

    <select bind:value={targetLang} class="lang-select">
      {#each LANGUAGES as lang (lang.code)}
        <option value={lang.code}>{lang.name}</option>
      {/each}
    </select>

    <button type="button"
      class="translate-btn"
      on:click={translate}
      disabled={loading || !inputText.trim()}
    >
      {#if loading}<span class="spinner"></span>{/if}
      Translate
    </button>

    {#if modelOptions.length > 0}
      <select
        class="lang-select model-select"
        bind:value={translateModel}
        on:change={onModelChange}
        title="Translation model"
      >
        {#each modelOptions as m (m)}
          <option value={m}>{m}</option>
        {/each}
      </select>
    {/if}
  </div>

  {#if error}
    <div class="error-banner">{error}</div>
  {/if}

  <div class="panels">
    <div class="pane">
      <textarea
        class="text-panel"
        placeholder="Enter text to translate…"
        bind:value={inputText}
        spellcheck="false"
        on:keydown={onInputKeydown}
      ></textarea>
      <div class="pane-footer">
        <span>{inputText.length} chars</span>
        <span class="hint">Ctrl+Enter to translate</span>
      </div>
    </div>

    <div class="panel-divider"></div>

    <div class="pane">
      <textarea
        class="text-panel output"
        readonly
        placeholder="Translation will appear here…"
        value={outputText}
        spellcheck="false"
      ></textarea>
      <div class="pane-footer">
        <span>{outputText.length} chars</span>
        {#if outputText}
          <button type="button" class="copy-out" on:click={copyOutput}>{copied ? 'Copied ✓' : 'Copy'}</button>
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .translator {
    display: flex;
    flex-direction: column;
    flex: 1;
    overflow: hidden;
  }

  .lang-bar {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.6rem 1.5rem;
    border-bottom: 1px solid var(--color-border);
    background: var(--bg-surface);
    flex-shrink: 0;
  }

  .lang-select {
    flex: 1;
    padding: 0.35rem 0.6rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    font-size: 0.85rem;
    color: var(--color-text);
    background: var(--bg-app);
    cursor: pointer;
    max-width: 220px;
  }

  .lang-select:focus {
    outline: 2px solid var(--color-primary);
    outline-offset: 1px;
  }

  .model-select {
    flex: 0 1 auto;
    max-width: 180px;
    margin-left: auto;
    font-size: 0.8rem;
    color: var(--color-text-muted);
    text-overflow: ellipsis;
  }

  .swap-btn {
    padding: 0.35rem 0.6rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--bg-app);
    color: var(--color-text-muted);
    font-size: 1.1rem;
    cursor: pointer;
    line-height: 1;
    transition: background 0.12s, color 0.12s;
  }

  .swap-btn:hover {
    background: var(--bg-panel);
    color: var(--color-primary);
  }

  .translate-btn {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.35rem 1rem;
    border: none;
    border-radius: var(--radius-md);
    background: var(--color-primary);
    color: #fff;
    font-size: 0.85rem;
    font-weight: 600;
    cursor: pointer;
    transition: opacity 0.12s;
    white-space: nowrap;
  }

  .translate-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .spinner {
    display: inline-block;
    width: 0.8em;
    height: 0.8em;
    border: 2px solid rgba(255, 255, 255, 0.4);
    border-top-color: #fff;
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .error-banner {
    padding: 0.5rem 1.5rem;
    background: rgba(239, 68, 68, 0.08);
    color: var(--color-error);
    font-size: 0.85rem;
    border-bottom: 1px solid rgba(239, 68, 68, 0.2);
    flex-shrink: 0;
  }

  .panels {
    display: flex;
    flex: 1;
    overflow: hidden;
  }

  .pane {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .pane-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.3rem 1.25rem;
    border-top: 1px solid var(--color-border);
    font-size: 0.72rem;
    color: var(--color-text-muted);
    background: var(--bg-surface);
    flex-shrink: 0;
    min-height: 1.9rem;
  }

  .hint {
    opacity: 0.7;
  }

  .copy-out {
    padding: 0.15rem 0.6rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    background: var(--bg-app);
    color: var(--color-text-muted);
    font-size: 0.72rem;
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }

  .copy-out:hover {
    background: var(--bg-panel);
    color: var(--color-text);
  }

  .text-panel {
    flex: 1;
    resize: none;
    border: none;
    outline: none;
    font-family: var(--font-mono);
    font-size: 0.95rem;
    line-height: 1.7;
    padding: 1.25rem;
    box-sizing: border-box;
    color: var(--color-text);
    background: var(--bg-app);
  }

  .text-panel.output {
    background: var(--bg-surface);
    color: var(--color-text);
  }

  .text-panel::placeholder {
    color: #aaa;
  }

  .panel-divider {
    width: 1px;
    background: var(--color-border);
    flex-shrink: 0;
  }
</style>
