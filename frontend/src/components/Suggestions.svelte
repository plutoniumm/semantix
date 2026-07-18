<script>
  import { isValidIssue, classifyDiff } from "../lib/issue-utils.js";
  import { analysis } from "../lib/stores.js";
  import { createEventDispatcher } from "svelte";

  export let totalSentences = 0;
  export let staticIssues = [];

  const dispatch = createEventDispatcher();

  let dismissed = new Set();
  let hiddenTypes = new Set();
  let ignored = new Set();
  try {
    ignored = new Set(JSON.parse(localStorage.getItem("semantix_ignored") || "[]"));
  } catch (_) {}

  function persistIgnored() {
    try {
      localStorage.setItem("semantix_ignored", JSON.stringify([...ignored]));
    } catch (_) {}
  }

  function ignoreKey(issue) {
    return `${issue.type}:${issue.original_fragment}:${issue.suggestion}`;
  }

  function ignoreIssue(issue) {
    ignored = new Set([...ignored, ignoreKey(issue)]);
    persistIgnored();
  }

  function resetIgnored() {
    ignored = new Set();
    persistIgnored();
  }

  function toggleType(type) {
    const next = new Set(hiddenTypes);
    next.has(type) ? next.delete(type) : next.add(type);
    hiddenTypes = next;
  }

  const CAT_NAMES = {
    cliche: "cliché",
    repetition: "repetition",
    doubled: "doubled word",
    "long-sentence": "long sentence",
    "start-repetition": "openings",
    citation: "citation",
  };

  const STATIC_BADGES = [
    ["doubled", "doubled word", "doubled words"],
    ["repetition", "repeated word", "repeated words"],
    ["cliche", "cliché", "clichés"],
    ["long-sentence", "long sentence", "long sentences"],
    ["start-repetition", "repetitive opening", "repetitive openings"],
    ["citation", "citation issue", "citation issues"],
  ];

  // Keyed by content, not sentence index, so dismissals survive re-analysis
  // and index shifts after edits.
  function dismissKey(sentence, issue) {
    return `${issue.original_fragment}:${issue.suggestion}`;
  }

  // Clicking a repeated word cycles the editor through its occurrences.
  let repCycle = {};
  function jumpToRepetition(issue) {
    const idx = ((repCycle[issue.id] ?? -1) + 1) % issue.ranges.length;
    repCycle[issue.id] = idx;
    dispatch("jump", { ...issue.ranges[idx] });
  }

  function getVisibleIssues(sentence, dis, ign) {
    return sentence.issues.filter(
      (i) =>
        isValidIssue(i) &&
        !dis.has(dismissKey(sentence, i)) &&
        !ign.has(ignoreKey(i)),
    );
  }

  function getShownIssues(sentence, dis, ign, hidden) {
    return getVisibleIssues(sentence, dis, ign).filter((i) => !hidden.has(i.type));
  }

  // Clicking a card pins its highlight; hover previews without unpinning.
  // Esc (or selecting another card) releases the pin.
  let pinnedIndex = null;

  function select(result) {
    pinnedIndex = result.sentence_index;
    analysis.setActiveIndex(result.sentence_index);
    dispatch("select", {
      index: result.sentence_index,
      original: result.original,
    });
  }

  function onWindowKeydown(e) {
    if (e.key === "Escape" && pinnedIndex !== null) {
      pinnedIndex = null;
      analysis.setActiveIndex(null);
    }
  }

  function cardKeydown(e, result) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      select(result);
    }
  }

  function jumpToStatic(issue) {
    if (issue.ranges && issue.ranges.length > 0)
      dispatch("jump", { ...issue.ranges[0] });
  }

  function staticKeydown(e, issue) {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      jumpToStatic(issue);
    }
  }

  function accept(result, issue) {
    dismissed = new Set([...dismissed, dismissKey(result, issue)]);
    dispatch("accept", {
      index: result.sentence_index,
      original: result.original,
      fragment: issue.original_fragment,
      suggestion: issue.suggestion,
    });
  }

  function dismiss(result, issue) {
    dismissed = new Set([...dismissed, dismissKey(result, issue)]);
  }

  function acceptAllForSentence(result) {
    const issues = getShownIssues(result, dismissed, ignored, hiddenTypes);
    dismissed = new Set([...dismissed, ...issues.map((i) => dismissKey(result, i))]);
    dispatch("acceptAll", {
      sentences: [{ index: result.sentence_index, original: result.original, issues }],
    });
  }

  function dismissAllForSentence(result) {
    const issues = getShownIssues(result, dismissed, ignored, hiddenTypes);
    dismissed = new Set([...dismissed, ...issues.map((i) => dismissKey(result, i))]);
  }

  function acceptAllGlobal() {
    const toAccept = [];
    const newDismissed = new Set(dismissed);

    for (const r of visibleSentences) {
      if (r.parse_error) continue;
      const issues = getShownIssues(r, dismissed, ignored, hiddenTypes);
      if (issues.length === 0) continue;
      toAccept.push({ index: r.sentence_index, original: r.original, issues });
      for (const i of issues) newDismissed.add(dismissKey(r, i));
    }

    dismissed = newDismissed;
    if (toAccept.length > 0) dispatch("acceptAll", { sentences: toAccept });
  }

  function dismissAllGlobal() {
    const newDismissed = new Set(dismissed);
    for (const r of visibleSentences) {
      for (const i of getShownIssues(r, dismissed, ignored, hiddenTypes)) {
        newDismissed.add(dismissKey(r, i));
      }
    }
    dismissed = newDismissed;
  }

  $: visibleSentences = $analysis.sentences.filter(
    (r) => r.parse_error || getShownIssues(r, dismissed, ignored, hiddenTypes).length > 0,
  );

  $: llmIssueCounts = (() => {
    const counts = { grammar: 0, spelling: 0, style: 0, punctuation: 0 };
    for (const s of $analysis.sentences) {
      if (s.parse_error) continue;
      for (const i of getVisibleIssues(s, dismissed, ignored)) {
        if (counts[i.type] !== undefined) counts[i.type]++;
      }
    }
    return counts;
  })();

  $: totalLlmIssues = Object.values(llmIssueCounts).reduce((a, b) => a + b, 0);
  $: staticCounts = STATIC_BADGES.map(([cat, one, many]) => ({
    cat,
    one,
    many,
    n: staticIssues.filter((i) => i.category === cat).length,
  })).filter((b) => b.n > 0);
  $: hasContent = $analysis.sentences.length > 0 || staticIssues.length > 0;
  $: showSummary = hasContent;
  $: freshCount = $analysis.sentences.filter((r) => !r.stale).length;
  $: repetitionRows = staticIssues
    .filter((i) => i.category === "repetition")
    .sort((a, b) => b.count - a.count);
  $: otherStatic = staticIssues.filter((i) => i.category !== "repetition");
</script>

<svelte:window on:keydown={onWindowKeydown} />

<div class="suggestions-panel">
  {#if $analysis.error}
    <div class="error-banner">
      <span>{$analysis.error}</span>
      <button type="button" on:click={analysis.dismissError}>✕</button>
    </div>
  {/if}

  {#if $analysis.streaming}
    <div class="analyzing-card">
      <div class="spinner"></div>
      <span>Analysing{totalSentences > 0
          ? ` (${Math.min(freshCount + 1, totalSentences)} of ${totalSentences})`
          : "…"}</span>
      <button type="button"
        class="bulk-btn stop-btn"
        title="Stop analysis and keep the results so far"
        on:click={analysis.stop}>■ Stop</button>
    </div>
  {/if}

  {#if showSummary}
    <div class="summary-card">
      <div class="summary-row">
        {#each Object.entries(llmIssueCounts).filter(([, n]) => n > 0) as [type, count] (type)}
          <button type="button"
            class="summary-badge {type}"
            class:muted={hiddenTypes.has(type)}
            title={hiddenTypes.has(type) ? `Show ${type} issues` : `Hide ${type} issues`}
            on:click={() => toggleType(type)}>{count} {type}</button>
        {/each}
        {#each staticCounts as b (b.cat)}
          <span class="summary-badge {b.cat}">{b.n} {b.n === 1 ? b.one : b.many}</span>
        {/each}
      </div>
      {#if totalLlmIssues > 1 || ignored.size > 0}
        <div class="summary-actions">
          {#if totalLlmIssues > 1}
            <button type="button" class="summary-btn accept" on:click={acceptAllGlobal}>Accept all grammar fixes</button>
            <button type="button" class="summary-btn dismiss" on:click={dismissAllGlobal}>Dismiss all</button>
          {/if}
          {#if ignored.size > 0}
            <button type="button"
              class="summary-btn dismiss"
              title="Clear the persistent ignore list"
              on:click={resetIgnored}>{ignored.size} ignored · reset</button>
          {/if}
        </div>
      {/if}
    </div>
  {/if}

  {#if $analysis.sentences.length === 0 && !$analysis.streaming && !$analysis.error}
    <p class="empty-state">Paste text on the left to begin analysis.</p>
  {:else if !$analysis.streaming && $analysis.sentences.length > 0 && visibleSentences.length === 0 && staticIssues.length === 0}
    <p class="empty-state">No issues found.</p>
  {/if}

  {#each visibleSentences as result (result.sentence_index)}
    {@const visibleForCard = getShownIssues(result, dismissed, ignored, hiddenTypes)}
    <!-- svelte-ignore a11y-click-events-have-key-events -->
    <!-- svelte-ignore a11y-no-static-element-interactions -->
    <div
      class="sentence-card"
      class:active={$analysis.activeIndex === result.sentence_index}
      class:stale={result.stale}
      role="button"
      tabindex="0"
      on:click={() => select(result)}
      on:keydown={(e) => cardKeydown(e, result)}
      on:mouseenter={() => analysis.setActiveIndex(result.sentence_index)}
      on:mouseleave={() => analysis.setActiveIndex(pinnedIndex)}
    >
      <div class="card-header">
        <span class="sentence-label">Sentence {result.sentence_index + 1}</span>
        <div class="card-header-right">
          {#if result.parse_error}
            <span class="badge warning">⚠ Could not analyse</span>
            <button type="button"
              class="bulk-btn retry-btn"
              disabled={result.retrying}
              title="Re-run analysis for this sentence"
              on:click|stopPropagation={() => analysis.retrySentence(result.sentence_index)}
              >{result.retrying ? "Retrying…" : "↻ Retry"}</button>
          {:else}
            <span class="badge issues">
              {visibleForCard.length} issue{visibleForCard.length !== 1 ? "s" : ""}
            </span>
            {#if visibleForCard.length > 1}
              <button type="button"
                class="bulk-btn accept-bulk"
                title="Accept all in sentence"
                on:click|stopPropagation={() => acceptAllForSentence(result)}>✓ All</button>
              <button type="button"
                class="bulk-btn dismiss-bulk"
                title="Dismiss all in sentence"
                on:click|stopPropagation={() => dismissAllForSentence(result)}>✕ All</button>
            {/if}
          {/if}
        </div>
      </div>

      <p class="original-text">{result.original}</p>

      {#each visibleForCard as issue (ignoreKey(issue))}
        <div class="issue">
          <div class="issue-header">
            <span class="issue-type">{issue.type}</span>
            <div class="issue-actions">
              <button type="button"
                class="action-btn accept-btn"
                title="Accept change"
                on:click|stopPropagation={() => accept(result, issue)}>✓</button>
              <button type="button"
                class="action-btn dismiss-btn"
                title="Dismiss"
                on:click|stopPropagation={() => dismiss(result, issue)}>✕</button>
              <button type="button"
                class="action-btn ignore-btn"
                title="Ignore this suggestion everywhere (persists across sessions)"
                on:click|stopPropagation={() => ignoreIssue(issue)}>⊘</button>
            </div>
          </div>
          <div class="issue-diff">
            {#each classifyDiff(issue.original_fragment, issue.suggestion) as part, i (i)}
              {#if part.type === "del"}
                <span class="diff-del">{part.text}</span>
              {:else if part.type === "spell"}
                <span class="diff-del">{part.text}</span><span class="diff-add">{part.addedText}</span>
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

  {#if staticIssues.length > 0}
    <div class="static-section">
      <div class="static-section-header">Document checks</div>

      {#if repetitionRows.length > 0}
        <table class="rep-table">
          <thead>
            <tr><th>Repeated word</th><th class="rep-count">Count</th><th></th></tr>
          </thead>
          <tbody>
            {#each repetitionRows as issue (issue.id)}
              <tr>
                <td>
                  <button type="button"
                    class="rep-word"
                    title="Jump to next occurrence"
                    on:click={() => jumpToRepetition(issue)}>{issue.fragment}</button>
                </td>
                <td class="rep-count">{issue.count}×</td>
                <td class="rep-actions">
                  <button type="button"
                    class="action-btn dismiss-btn"
                    title="Dismiss"
                    on:click={() => dispatch("dismissStatic", { id: issue.id })}>✕</button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}

      {#each otherStatic as issue (issue.id)}
        <!-- svelte-ignore a11y-no-static-element-interactions -->
        <div
          class="static-issue"
          class:jumpable={issue.ranges && issue.ranges.length > 0}
          role="button"
          tabindex="0"
          title={issue.ranges && issue.ranges.length > 0 ? "Jump to text" : undefined}
          on:click={() => jumpToStatic(issue)}
          on:keydown={(e) => staticKeydown(e, issue)}
        >
          <div class="static-issue-header">
            <span class="issue-type {issue.category}">{CAT_NAMES[issue.category] ?? issue.category}</span>
            <button type="button"
              class="action-btn dismiss-btn"
              title="Dismiss"
              on:click|stopPropagation={() => dispatch("dismissStatic", { id: issue.id })}>✕</button>
          </div>
          <p class="static-fragment">"{issue.fragment}"{#if issue.count} — {issue.count} occurrences{/if}</p>
          <p class="explanation">{issue.message}</p>
        </div>
      {/each}
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

  .sentence-card.stale {
    opacity: 0.55;
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

  .ignore-btn {
    background: var(--bg-surface);
    color: #94a3b8;
    border: 1px solid #cbd5e1;
  }

  .ignore-btn:hover {
    background: #fef2f2;
    color: #b91c1c;
    border-color: #fca5a5;
  }

  .retry-btn {
    background: #eff6ff;
    color: var(--color-primary);
    border: 1px solid #bfdbfe;
  }

  .retry-btn:hover:not(:disabled) {
    background: #dbeafe;
  }

  .retry-btn:disabled {
    opacity: 0.6;
    cursor: wait;
  }

  .stop-btn {
    margin-left: auto;
    background: #fef2f2;
    color: #b91c1c;
    border: 1px solid #fca5a5;
  }

  .stop-btn:hover {
    background: #fee2e2;
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

  .card-header-right {
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }

  .bulk-btn {
    font-size: 0.68rem;
    font-weight: 700;
    padding: 0.15rem 0.45rem;
    border-radius: var(--radius-sm);
    cursor: pointer;
    line-height: 1;
    transition: background 0.12s;
  }

  .accept-bulk {
    background: #f0fdf4;
    color: var(--color-success);
    border: 1px solid #86efac;
  }

  .accept-bulk:hover { background: #dcfce7; }

  .dismiss-bulk {
    background: var(--bg-surface);
    color: #94a3b8;
    border: 1px solid #cbd5e1;
  }

  .dismiss-bulk:hover { background: #f1f5f9; }

  .static-section {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .static-section-header {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    padding: 0.25rem 0;
  }

  .static-issue {
    background: #fff;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 0.75rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .static-issue.jumpable {
    cursor: pointer;
  }

  .static-issue.jumpable:hover {
    border-color: var(--color-primary);
  }

  .static-issue-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .issue-type.repetition       { color: #d97706; }
  .issue-type.doubled          { color: #d97706; }
  .issue-type.cliche           { color: #7c3aed; }
  .issue-type.citation         { color: #0369a1; }
  .issue-type.long-sentence    { color: #475569; }
  .issue-type.start-repetition { color: #0d9488; }

  .static-fragment {
    font-size: 0.85rem;
    color: #374151;
    font-style: italic;
    margin: 0;
  }

  .rep-table {
    width: 100%;
    border-collapse: collapse;
    background: #fff;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    overflow: hidden;
    font-size: 0.85rem;
  }

  .rep-table th {
    font-size: 0.7rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    color: var(--color-text-muted);
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--color-border);
  }

  .rep-table td {
    padding: 0.35rem 0.75rem;
    border-bottom: 1px solid var(--bg-surface);
  }

  .rep-table tbody tr:last-child td {
    border-bottom: none;
  }

  .rep-word {
    background: none;
    border: none;
    padding: 0;
    font-family: inherit;
    font-size: 0.85rem;
    font-style: italic;
    color: #92400e;
    cursor: pointer;
    text-decoration: underline dotted;
    text-underline-offset: 3px;
  }

  .rep-count {
    text-align: right;
    color: var(--color-text-muted);
    width: 3.5rem;
  }

  .rep-actions {
    width: 2rem;
    text-align: right;
  }

  .summary-card {
    background: #fff;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-lg);
    padding: 0.75rem 1rem;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .summary-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
  }

  .summary-badge {
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.2rem 0.55rem;
    border-radius: 999px;
    border: none;
    font-family: inherit;
  }

  button.summary-badge {
    cursor: pointer;
  }

  .summary-badge.muted {
    opacity: 0.45;
    text-decoration: line-through;
  }

  .summary-badge.grammar     { background: #fef9c3; color: #854d0e; }
  .summary-badge.spelling    { background: #fee2e2; color: #b91c1c; }
  .summary-badge.style       { background: #ede9fe; color: #6d28d9; }
  .summary-badge.punctuation { background: #e0f2fe; color: #0369a1; }
  .summary-badge.repetition  { background: #fef3c7; color: #92400e; }
  .summary-badge.doubled     { background: #fef3c7; color: #92400e; }
  .summary-badge.cliche      { background: #f3e8ff; color: #6d28d9; }
  .summary-badge.citation    { background: #e0f2fe; color: #0369a1; }
  .summary-badge.long-sentence    { background: #f1f5f9; color: #475569; }
  .summary-badge.start-repetition { background: #ccfbf1; color: #0f766e; }

  .summary-actions {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  .summary-btn {
    font-size: 0.78rem;
    font-weight: 600;
    padding: 0.3rem 0.75rem;
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: background 0.12s;
  }

  .summary-btn.accept {
    background: #f0fdf4;
    color: var(--color-success);
    border: 1px solid #86efac;
  }

  .summary-btn.accept:hover { background: #dcfce7; }

  .summary-btn.dismiss {
    background: var(--bg-surface);
    color: #94a3b8;
    border: 1px solid #cbd5e1;
  }

  .summary-btn.dismiss:hover { background: #f1f5f9; }
</style>
