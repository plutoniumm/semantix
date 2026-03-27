<script>
  import { isValidIssue, classifyDiff } from "../lib/issue-utils.js";
  import { analysis } from "../lib/stores.js";
  import { createEventDispatcher } from "svelte";

  export let totalSentences = 0;

  const dispatch = createEventDispatcher();

  let dismissed = new Set();

  $: if ($analysis.sentences.length === 0) dismissed = new Set();

  function dismissKey(sentence, issue) {
    return `${sentence.sentence_index}:${issue.original_fragment}`;
  }

  function getVisibleIssues(sentence, dis) {
    return sentence.issues.filter(
      (i) => isValidIssue(i) && !dis.has(dismissKey(sentence, i)),
    );
  }

  function select(result) {
    analysis.setActiveIndex(result.sentence_index);
    dispatch("select", {
      index: result.sentence_index,
      original: result.original,
    });
  }

  function accept(result, issue) {
    dismissed = new Set([...dismissed, dismissKey(result, issue)]);
    dispatch("accept", {
      original: result.original,
      fragment: issue.original_fragment,
      suggestion: issue.suggestion,
    });
  }

  function dismiss(result, issue) {
    dismissed = new Set([...dismissed, dismissKey(result, issue)]);
  }

  $: visibleSentences = $analysis.sentences.filter(
    (r) => r.parse_error || getVisibleIssues(r, dismissed).length > 0,
  );
</script>

<div class="suggestions-panel">
  {#if $analysis.error}
    <div class="error-banner">
      <span>{$analysis.error}</span>
      <button on:click={analysis.dismissError}>✕</button>
    </div>
  {/if}

  {#if $analysis.sentences.length === 0 && !$analysis.streaming && !$analysis.error}
    <p class="empty-state">Paste text on the left to begin analysis.</p>
  {:else if !$analysis.streaming && $analysis.sentences.length > 0 && visibleSentences.length === 0}
    <p class="empty-state">No issues found.</p>
  {/if}

  {#each visibleSentences as result}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div
      class="sentence-card"
      class:active={$analysis.activeIndex === result.sentence_index}
      on:click={() => select(result)}
      on:mouseenter={() => analysis.setActiveIndex(result.sentence_index)}
      on:mouseleave={() => analysis.setActiveIndex(null)}
    >
      <div class="card-header">
        <span class="sentence-label">Sentence {result.sentence_index + 1}</span>
        {#if result.parse_error}
          <span class="badge warning">⚠ Could not analyse</span>
        {:else}
          <span class="badge issues">
            {getVisibleIssues(result, dismissed).length} issue{getVisibleIssues(
              result,
              dismissed,
            ).length > 1
              ? "s"
              : ""}
          </span>
        {/if}
      </div>

      <p class="original-text">{result.original}</p>

      {#each getVisibleIssues(result, dismissed) as issue}
        <div class="issue">
          <div class="issue-header">
            <span class="issue-type">{issue.type}</span>
            <div class="issue-actions">
              <button
                class="action-btn accept-btn"
                title="Accept change"
                on:click|stopPropagation={() => accept(result, issue)}>✓</button
              >
              <button
                class="action-btn dismiss-btn"
                title="Dismiss"
                on:click|stopPropagation={() => dismiss(result, issue)}
                >✕</button
              >
            </div>
          </div>
          <div class="issue-diff">
            {#each classifyDiff(issue.original_fragment, issue.suggestion) as part}
              {#if part.type === "del"}
                <span class="diff-del">{part.text}</span>
              {:else if part.type === "spell"}
                <span class="diff-del">{part.text}</span><span class="diff-add"
                  >{part.addedText}</span
                >
              {:else if part.type === "add"}
                <span class="diff-add">{part.text}</span>
              {:else}
                <span class="diff-unch">{part.text}</span>
              {/if}
            {/each}
          </div>
          <p class="explanation">{issue.explanation}</p>
        </div>
      {/each}
    </div>
  {/each}

  {#if $analysis.streaming}
    <div class="analyzing-card">
      <div class="spinner"></div>
      <span
        >Analysing{totalSentences > 0
          ? ` (${$analysis.sentences.length + 1} of ${totalSentences})`
          : "…"}</span
      >
    </div>
  {/if}
</div>

<style>
  .suggestions-panel {
    height: 100%;
    overflow-y: auto;
    padding: 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    background: var(--bg-panel);
  }

  .empty-state {
    color: #999;
    font-size: 0.9rem;
    text-align: center;
    margin-top: 2rem;
  }

  .error-banner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #fee2e2;
    border: 1px solid #fca5a5;
    border-radius: var(--radius-lg);
    padding: 0.75rem 1rem;
    color: #b91c1c;
    font-size: 0.9rem;
  }

  .error-banner button {
    background: none;
    border: none;
    cursor: pointer;
    color: #b91c1c;
    font-size: 0.9rem;
  }

  .sentence-card {
    background: #fff;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 0.875rem 1rem;
    cursor: pointer;
    transition:
      border-color 0.15s,
      box-shadow 0.15s;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .sentence-card:hover,
  .sentence-card.active {
    border-color: var(--color-primary);
    box-shadow: 0 0 0 2px rgba(37, 99, 235, 0.15);
  }

  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .sentence-label {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--color-text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .badge {
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.2rem 0.6rem;
    border-radius: 999px;
  }

  .badge.issues {
    background: #fef9c3;
    color: #854d0e;
  }

  .badge.warning {
    background: #ffedd5;
    color: #c2410c;
  }

  .original-text {
    font-size: 0.85rem;
    color: #374151;
    margin: 0;
    font-style: italic;
    line-height: 1.5;
  }

  .issue {
    background: var(--bg-surface);
    border-left: 3px solid var(--color-primary);
    padding: 0.5rem 0.75rem;
    border-radius: 0 var(--radius-md) var(--radius-md) 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .issue-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .issue-type {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--color-primary);
    letter-spacing: 0.08em;
  }

  .issue-actions {
    display: flex;
    gap: 0.25rem;
  }

  .action-btn {
    width: 22px;
    height: 22px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 0.75rem;
    font-weight: 700;
    padding: 0;
    line-height: 1;
    transition: background 0.12s;
  }

  .accept-btn {
    background: #f0fdf4;
    color: var(--color-success);
    border: 1px solid #86efac;
  }

  .accept-btn:hover {
    background: #dcfce7;
  }

  .dismiss-btn {
    background: var(--bg-surface);
    color: #94a3b8;
    border: 1px solid #cbd5e1;
  }

  .dismiss-btn:hover {
    background: #f1f5f9;
    color: var(--color-text-muted);
  }

  .issue-diff {
    font-size: 0.875rem;
    line-height: 1.6;
    font-family: inherit;
  }

  .diff-del {
    background: #fee2e2;
    color: #b91c1c;
    text-decoration: line-through;
    border-radius: var(--radius-sm);
    padding: 0 3px;
  }

  .diff-add {
    background: #dcfce7;
    color: #15803d;
    font-weight: 600;
    border-radius: var(--radius-sm);
    padding: 0 3px;
  }

  .diff-unch {
    color: #374151;
  }

  .explanation {
    font-size: 0.8rem;
    color: var(--color-text-muted);
    margin: 0;
    line-height: 1.4;
  }

  .analyzing-card {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    color: var(--color-text-muted);
    font-size: 0.85rem;
  }

  .spinner {
    width: 14px;
    height: 14px;
    border: 2px solid #cbd5e1;
    border-top-color: var(--color-primary);
    border-radius: 50%;
    animation: spin 0.7s linear infinite;
    flex-shrink: 0;
  }

  @keyframes spin {
    to {
      transform: rotate(360deg);
    }
  }
</style>
