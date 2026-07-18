# Proofreading Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 7 proofreading features: word repetition detection, cliché detection, accept-all/dismiss-all, undo stack, document summary card, formal-tone enforcement, and LaTeX citation consistency checks.

**Architecture:** Static checks (repetition, clichés, citations) run purely in the frontend with no LLM, reactive to text changes, and are wired into the existing backdrop highlighter as additional range types. LLM-based issues continue to stream from the backend; the formal-tone enforcement is a one-line prompt change. All UI additions (summary, accept-all, undo) live in existing components.

**Tech Stack:** Svelte 5 (legacy syntax — `on:`, `$:`, `createEventDispatcher`), FastAPI (Python), CSS custom properties, no new npm packages needed.

---

## File Map

**Create:**
- `frontend/src/lib/static-checks.js` — `detectRepetition(text)`, `detectCliches(text)`
- `frontend/src/lib/latex-bib.js` — `checkCitations(text)`

**Modify:**
- `backend/analyzer.py:18-26` — add formal-tone instruction to SYSTEM_PROMPT_TEMPLATE
- `frontend/src/app.css:29-34` — add `--mark-rep-bg`, `--mark-cliche-bg` tokens
- `frontend/src/components/Editor.svelte:5,14` — add `staticRanges` prop; pass to `buildBackdropHtml`
- `frontend/src/lib/highlighter.js:11,110-137` — extend `build()` to accept `staticRanges`; render `frag-rep`/`frag-cliche`
- `frontend/src/components/Editor.svelte:92-131` — add `.frag-rep` and `.frag-cliche` CSS rules
- `frontend/src/App.svelte` — undo stack, compute static issues, pass to Suggestions + Editor, accept-all handler, Ctrl+Z listener
- `frontend/src/components/Suggestions.svelte` — accept-all/dismiss-all per card + global, static issues section, document summary card

---

## Task 1: Formal tone in system prompt

**Files:**
- Modify: `backend/analyzer.py:18-26`

- [ ] **Step 1: Update SYSTEM_PROMPT_TEMPLATE**

Replace lines 18-26 in `backend/analyzer.py`:

```python
SYSTEM_PROMPT_TEMPLATE = (
    "You are a professional writing assistant for formal documents. "
    "Analyse the following sentence for grammar, spelling, style, and punctuation errors. "
    "Use {variant} English conventions. "
    "Flag contractions (e.g. don't, it's, they're), colloquialisms, and informal intensifiers "
    "(very, really, quite, pretty much) as style issues. "
    "Return a JSON object only, no prose. Schema: "
    '{{"issues": [{{"type": "grammar|spelling|style|punctuation", '
    '"original_fragment": "...", "suggestion": "...", "explanation": "..."}}]}} '
    'If there are no issues, return {{"issues": []}}.'
)
```

- [ ] **Step 2: Verify the server restarts cleanly**

Run: `cd /Users/dragon/Documents/Github.nosync/semantix && python -c "from backend.analyzer import SYSTEM_PROMPT_TEMPLATE; print(SYSTEM_PROMPT_TEMPLATE[:80])"`

Expected output starts with: `You are a professional writing assistant for formal documents.`

---

## Task 2: CSS tokens for repetition and cliché marks

**Files:**
- Modify: `frontend/src/app.css:29-34`
- Modify: `frontend/src/components/Editor.svelte` (style block)

- [ ] **Step 1: Add tokens to app.css**

After the `--mark-ctx-bg` line in `:root`, add:

```css
  --mark-rep-bg:    rgba(245, 158, 11, 0.18);
  --mark-cliche-bg: rgba(139, 92, 246, 0.15);
```

- [ ] **Step 2: Add CSS rules in Editor.svelte**

After the `:global(.frag-ctx)` rule in `Editor.svelte`'s `<style>` block, add:

```css
  :global(.frag-rep) {
    background: var(--mark-rep-bg);
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
```

---

## Task 3: Static checks module

**Files:**
- Create: `frontend/src/lib/static-checks.js`

- [ ] **Step 1: Create `static-checks.js`**

```javascript
const STOPWORDS = new Set([
  'a','an','the','is','was','are','were','be','been','being',
  'have','has','had','do','does','did','will','would','could',
  'should','may','might','must','shall','can','to','of','in',
  'on','at','for','with','by','from','about','into','through',
  'during','before','after','under','above','but','and','or',
  'nor','yet','so','as','if','while','when','where','how',
  'what','who','which','that','this','these','those','it','its',
  'he','his','she','her','they','their','we','our','you','your',
  'i','me','my','him','us','not','no','also','then','than',
  'more','most','some','such','each','other','any','all','very',
  'just','even','only','both','own','same','few','much','well',
  'still','now','here','there','up','down','out','off','over',
  'again','been','however','therefore','thus','hence','whereas',
  'moreover','furthermore','nevertheless','although','because',
  'since','unless','until','whether','while','where','whereby',
])

const CLICHES = [
  { phrase: 'at the end of the day',    message: 'Cliché. Use a specific conclusion instead.' },
  { phrase: 'think outside the box',    message: 'Cliché. Use "think creatively" or "explore new approaches".' },
  { phrase: 'low-hanging fruit',         message: 'Cliché jargon. Use "easiest gains" or "simplest improvements".' },
  { phrase: 'move the needle',           message: 'Jargon cliché. Use "make a measurable impact".' },
  { phrase: 'paradigm shift',            message: 'Overused jargon. Use "fundamental change" if that is what you mean.' },
  { phrase: 'game changer',             message: 'Cliché. Describe the actual impact specifically.' },
  { phrase: 'circle back',              message: 'Informal jargon. Use "revisit" or "return to".' },
  { phrase: 'touch base',              message: 'Informal jargon. Use "follow up" or "consult".' },
  { phrase: 'going forward',            message: 'Vague filler. Use "in future" or omit.' },
  { phrase: 'it goes without saying',   message: 'Redundant. If it goes without saying, omit the sentence.' },
  { phrase: 'needless to say',          message: 'Redundant filler. Omit and state your point directly.' },
  { phrase: 'due to the fact that',     message: 'Verbose. Replace with "because".' },
  { phrase: 'in the event that',        message: 'Verbose. Replace with "if".' },
  { phrase: 'it should be noted that',  message: 'Filler phrase. Start with the actual point.' },
  { phrase: 'it is important to note',  message: 'Filler phrase. Start with the actual point.' },
  { phrase: 'on a daily basis',         message: 'Verbose. Replace with "daily".' },
  { phrase: 'at this juncture',         message: 'Formal filler. Replace with "now" or "at this point".' },
  { phrase: 'in the near future',       message: 'Vague. Specify a timeframe.' },
  { phrase: 'at this point in time',    message: 'Verbose filler. Replace with "now" or "currently".' },
  { phrase: 'a large number of',        message: 'Verbose. Replace with "many".' },
  { phrase: 'a majority of',            message: 'Verbose. Replace with "most".' },
  { phrase: 'with regard to',           message: 'Formal filler. Replace with "regarding" or "about".' },
  { phrase: 'deep dive',                message: 'Jargon. Use "thorough analysis" or "detailed examination".' },
  { phrase: 'best practice',            message: 'Overused jargon. Describe the specific practice.' },
  { phrase: 'pain point',               message: 'Jargon. Use "problem" or "challenge".' },
  { phrase: 'drill down',               message: 'Jargon. Use "examine in detail" or "investigate further".' },
  { phrase: 'actionable',               message: 'Jargon. Use "practical" or "applicable".' },
  { phrase: 'proactive approach',       message: 'Redundant jargon. Use "anticipating problems" or be specific.' },
  { phrase: 'robust solution',          message: 'Vague jargon. Describe what makes it robust.' },
  { phrase: 'synergy',                  message: 'Overused jargon. Describe the specific collaborative benefit.' },
]

export function detectRepetition(text) {
  if (!text || !text.trim()) return []

  const wordRegex = /\b([a-zA-Z]{5,})\b/g
  const wordCount = {}
  const wordPositions = {}
  let match

  while ((match = wordRegex.exec(text)) !== null) {
    const word = match[1].toLowerCase()
    if (STOPWORDS.has(word)) continue
    wordCount[word] = (wordCount[word] || 0) + 1
    if (!wordPositions[word]) wordPositions[word] = []
    wordPositions[word].push({ start: match.index, end: match.index + match[1].length })
  }

  const threshold = text.split(/\s+/).length < 150 ? 3 : 5

  const issues = []
  for (const [word, count] of Object.entries(wordCount)) {
    if (count < threshold) continue
    issues.push({
      id: `rep-${word}`,
      category: 'repetition',
      fragment: word,
      count,
      message: `"${word}" is used ${count} times. Consider varying your word choice.`,
      ranges: wordPositions[word],
    })
  }

  return issues.sort((a, b) => b.count - a.count)
}

export function detectCliches(text) {
  if (!text || !text.trim()) return []

  const lower = text.toLowerCase()
  const issues = []

  for (const { phrase, message } of CLICHES) {
    let searchFrom = 0
    let idx
    let occurrenceIndex = 0

    while ((idx = lower.indexOf(phrase, searchFrom)) !== -1) {
      issues.push({
        id: `cliche-${phrase.replace(/\s+/g, '-')}-${occurrenceIndex}`,
        category: 'cliche',
        fragment: text.slice(idx, idx + phrase.length),
        message,
        ranges: [{ start: idx, end: idx + phrase.length }],
      })
      searchFrom = idx + phrase.length
      occurrenceIndex++
    }
  }

  return issues
}
```

- [ ] **Step 2: Smoke-test in browser console**

After wiring into the app (Task 9), open DevTools and run:
```js
import('/src/lib/static-checks.js').then(m => {
  console.log(m.detectCliches('At the end of the day, we should touch base.'))
})
```
Expected: array with 2 issues (category: 'cliche').

---

## Task 4: LaTeX citation checker

**Files:**
- Create: `frontend/src/lib/latex-bib.js`

- [ ] **Step 1: Create `latex-bib.js`**

```javascript
const CITE_PATTERN = /\\(?:cite|citep|citet|citealt|citealp|citenum|citeauthor|citeyear)(?:\[[^\]]*\])?\{([^}]+)\}/g
const BIBITEM_PATTERN = /\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}/g

export function checkCitations(text) {
  const cited = new Set()
  const defined = new Set()
  const issues = []

  let m
  while ((m = CITE_PATTERN.exec(text)) !== null) {
    for (const key of m[1].split(',').map(k => k.trim())) {
      if (key) cited.add(key)
    }
  }

  while ((m = BIBITEM_PATTERN.exec(text)) !== null) {
    defined.add(m[1].trim())
  }

  if (cited.size === 0 && defined.size === 0) return []

  for (const key of cited) {
    if (!defined.has(key)) {
      issues.push({
        id: `cite-missing-${key}`,
        category: 'citation',
        fragment: key,
        message: `Citation key "${key}" is used but not defined in the bibliography.`,
        ranges: [],
      })
    }
  }

  for (const key of defined) {
    if (!cited.has(key)) {
      issues.push({
        id: `cite-unused-${key}`,
        category: 'citation',
        fragment: key,
        message: `Bibliography entry "${key}" is defined but never cited.`,
        ranges: [],
      })
    }
  }

  return issues
}
```

---

## Task 5: Extend BackdropHighlighter for static ranges

**Files:**
- Modify: `frontend/src/lib/highlighter.js`

- [ ] **Step 1: Update `build()` signature and `_collectRanges` to merge static ranges**

Replace the `build` method and update `buildBackdropHtml`:

```javascript
build(text, sentences, staticRanges = []) {
  if (!text) return ''
  const ranges = this._collectRanges(text, sentences)

  for (const { start, end, type } of staticRanges) {
    if (start < end) {
      ranges.push({ start, end, type, ctxStart: start, ctxEnd: end })
    }
  }

  if (!ranges.length) return escapeHtml(text)
  return this._renderHtml(text, this._filterOverlaps(ranges))
}
```

- [ ] **Step 2: Add rendering for `rep` and `cliche` types in `_renderHtml`**

In the `_renderHtml` method, extend the if/else chain that handles type:

```javascript
if (type === 'del') {
  html += `<span class="frag-del">${content}</span>`
} else if (type === 'spell') {
  html += `<span class="frag-spell">${content}</span>`
} else if (type === 'ins') {
  html += `<span class="frag-ins"></span>`
} else if (type === 'rep') {
  html += `<span class="frag-rep">${content}</span>`
} else if (type === 'cliche') {
  html += `<span class="frag-cliche">${content}</span>`
}
```

- [ ] **Step 3: Update `buildBackdropHtml` export to pass staticRanges**

```javascript
export function buildBackdropHtml(text, sentences, staticRanges = []) {
  return highlighter.build(text, sentences, staticRanges)
}
```

---

## Task 6: Wire static issues into Editor and App

**Files:**
- Modify: `frontend/src/components/Editor.svelte`
- Modify: `frontend/src/App.svelte`

- [ ] **Step 1: Add `staticRanges` prop to Editor.svelte**

In the `<script>` block, add after the existing props:

```javascript
export let staticRanges = []
```

Change the reactive backdropHtml line:

```javascript
$: backdropHtml = buildBackdropHtml(value, sentences, staticRanges)
```

- [ ] **Step 2: Compute static issues in App.svelte**

At the top of App.svelte's `<script>`, add the imports:

```javascript
import { detectRepetition, detectCliches } from './lib/static-checks.js'
import { checkCitations } from './lib/latex-bib.js'
```

Add reactive computation after the `mode` reactive statement:

```javascript
$: repetitionIssues = detectRepetition(text)
$: clicherIssues = detectCliches(text)
$: citationIssues = mode === 'latex' ? checkCitations(text) : []
$: staticIssues = [...repetitionIssues, ...clicherIssues, ...citationIssues]

$: staticRanges = staticIssues.flatMap(issue =>
  issue.ranges.map(r => ({ ...r, type: issue.category === 'repetition' ? 'rep' : 'cliche' }))
).filter(r => issue => r.start < r.end)
```

Wait — the `staticRanges` derivation needs to be correct. Let me write it properly:

```javascript
$: staticRanges = staticIssues.flatMap(issue => {
  const rangeType = issue.category === 'repetition' ? 'rep'
    : issue.category === 'cliche' ? 'cliche'
    : null
  if (!rangeType) return []
  return issue.ranges.map(r => ({ start: r.start, end: r.end, type: rangeType }))
})
```

- [ ] **Step 3: Pass staticRanges and staticIssues through App.svelte template**

In the `<Editor>` component in App.svelte's template:

```svelte
<Editor
  bind:this={editorRef}
  value={text}
  sentences={$analysis.sentences}
  activeIndex={$analysis.activeIndex}
  staticRanges={staticRanges}
  on:change={onTextChange}
/>
```

In the `<Suggestions>` component:

```svelte
<Suggestions
  totalSentences={sentenceCount}
  staticIssues={staticIssues}
  on:select={onSentenceSelect}
  on:accept={onAccept}
  on:acceptAll={onAcceptAll}
/>
```

---

## Task 7: Undo stack

**Files:**
- Modify: `frontend/src/App.svelte`

- [ ] **Step 1: Add undo history state**

In App.svelte's `<script>`, add:

```javascript
let undoStack = []
const MAX_UNDO = 50
```

- [ ] **Step 2: Push to undo stack before each accept**

In `onAccept`, push before modifying text:

```javascript
function onAccept(e) {
  const { original, fragment, suggestion } = e.detail
  undoStack = [...undoStack.slice(-MAX_UNDO + 1), text]
  const fixedSentence = original.replace(fragment, suggestion)
  const newText = text.replace(original, fixedSentence)
  if (newText !== text) {
    text = newText
  } else {
    text = text.replace(fragment, suggestion)
  }
  clearTimeout(debounceTimer)
  triggerAnalysis()
}
```

- [ ] **Step 3: Add acceptAll handler**

```javascript
function onAcceptAll(e) {
  const { sentences: sentencesToFix } = e.detail
  undoStack = [...undoStack.slice(-MAX_UNDO + 1), text]
  let current = text
  for (const { original, issues } of sentencesToFix) {
    const sorted = [...issues].sort((a, b) => {
      return original.lastIndexOf(b.original_fragment) - original.lastIndexOf(a.original_fragment)
    })
    let fixed = original
    for (const issue of sorted) {
      fixed = fixed.replace(issue.original_fragment, issue.suggestion)
    }
    current = current.replace(original, fixed)
  }
  text = current
  clearTimeout(debounceTimer)
  triggerAnalysis()
}
```

- [ ] **Step 4: Add keyboard undo handler via svelte:window**

In App.svelte's template, add above the `<div class="app">`:

```svelte
<svelte:window on:keydown={handleKeydown} />
```

In the script block:

```javascript
function handleKeydown(e) {
  if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
    if (undoStack.length === 0) return
    e.preventDefault()
    text = undoStack[undoStack.length - 1]
    undoStack = undoStack.slice(0, -1)
    clearTimeout(debounceTimer)
    triggerAnalysis()
  }
}
```

---

## Task 8: Accept-all / Dismiss-all + static issues in Suggestions

**Files:**
- Modify: `frontend/src/components/Suggestions.svelte`

- [ ] **Step 1: Add props and acceptAll dispatch**

In Suggestions.svelte's `<script>`, add:

```javascript
export let staticIssues = []

let dismissedStatic = new Set()

$: if ($analysis.sentences.length === 0) {
  dismissed = new Set()
  dismissedStatic = new Set()
}

function dismissStaticKey(issue) {
  return issue.id
}

function acceptAllForSentence(result) {
  const issues = getVisibleIssues(result, dismissed)
  dismissed = new Set([...dismissed, ...issues.map(i => dismissKey(result, i))])
  dispatch('acceptAll', {
    sentences: [{ original: result.original, issues }]
  })
}

function dismissAllForSentence(result) {
  const issues = getVisibleIssues(result, dismissed)
  dismissed = new Set([...dismissed, ...issues.map(i => dismissKey(result, i))])
}

function acceptAllGlobal() {
  const toAccept = visibleSentences
    .filter(r => !r.parse_error)
    .map(r => ({ original: r.original, issues: getVisibleIssues(r, dismissed) }))
    .filter(s => s.issues.length > 0)

  for (const s of toAccept) {
    for (const issue of s.issues) {
      dismissed = new Set([...dismissed, dismissKey({ sentence_index: $analysis.sentences.find(r => r.original === s.original)?.sentence_index }, issue)])
    }
  }
  dispatch('acceptAll', { sentences: toAccept })
}

function dismissAllGlobal() {
  const newDismissed = new Set(dismissed)
  for (const r of visibleSentences) {
    for (const i of getVisibleIssues(r, dismissed)) {
      newDismissed.add(dismissKey(r, i))
    }
  }
  dismissed = newDismissed
}

$: visibleStaticIssues = staticIssues.filter(i => !dismissedStatic.has(i.id))
```

- [ ] **Step 2: Add "Accept all" / "Dismiss all" buttons to each sentence card header**

Replace the existing `.card-header` div in the template:

```svelte
<div class="card-header">
  <span class="sentence-label">Sentence {result.sentence_index + 1}</span>
  <div class="card-header-right">
    {#if result.parse_error}
      <span class="badge warning">⚠ Could not analyse</span>
    {:else}
      <span class="badge issues">
        {getVisibleIssues(result, dismissed).length} issue{getVisibleIssues(result, dismissed).length !== 1 ? 's' : ''}
      </span>
      {#if getVisibleIssues(result, dismissed).length > 1}
        <button class="bulk-btn accept-bulk" title="Accept all in sentence"
          on:click|stopPropagation={() => acceptAllForSentence(result)}>✓ All</button>
        <button class="bulk-btn dismiss-bulk" title="Dismiss all in sentence"
          on:click|stopPropagation={() => dismissAllForSentence(result)}>✕ All</button>
      {/if}
    {/if}
  </div>
</div>
```

- [ ] **Step 3: Add static issues section below the LLM sentence cards**

After the `{/each}` for `visibleSentences` and before the `{#if $analysis.streaming}` block:

```svelte
{#if visibleStaticIssues.length > 0}
  <div class="static-section">
    <div class="static-section-header">Document checks</div>

    {#each visibleStaticIssues as issue (issue.id)}
      <div class="static-issue">
        <div class="static-issue-header">
          <span class="issue-type {issue.category}">{issue.category}</span>
          <button class="action-btn dismiss-btn" title="Dismiss"
            on:click={() => { dismissedStatic = new Set([...dismissedStatic, issue.id]) }}>✕</button>
        </div>
        <p class="static-fragment">"{issue.fragment}"
          {#if issue.count} — {issue.count} occurrences{/if}
        </p>
        <p class="explanation">{issue.message}</p>
      </div>
    {/each}
  </div>
{/if}
```

- [ ] **Step 4: Add CSS for new elements**

In the `<style>` block of Suggestions.svelte, add:

```css
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

  .static-issue-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .issue-type.repetition { color: #d97706; }
  .issue-type.cliche     { color: #7c3aed; }
  .issue-type.citation   { color: #0369a1; }

  .static-fragment {
    font-size: 0.85rem;
    color: #374151;
    font-style: italic;
    margin: 0;
  }
```

---

## Task 9: Document summary card

**Files:**
- Modify: `frontend/src/components/Suggestions.svelte`

- [ ] **Step 1: Compute summary counts**

In the `<script>` block, add:

```javascript
$: llmIssueCounts = (() => {
  const counts = { grammar: 0, spelling: 0, style: 0, punctuation: 0 }
  for (const s of $analysis.sentences) {
    for (const i of getVisibleIssues(s, dismissed)) {
      if (counts[i.type] !== undefined) counts[i.type]++
    }
  }
  return counts
})()

$: totalLlmIssues = Object.values(llmIssueCounts).reduce((a, b) => a + b, 0)
$: hasContent = $analysis.sentences.length > 0 || visibleStaticIssues.length > 0
$: showSummary = hasContent && !$analysis.streaming
```

- [ ] **Step 2: Add summary card at top of suggestions panel**

Add this at the very top of `.suggestions-panel`, before the error banner:

```svelte
{#if showSummary}
  <div class="summary-card">
    <div class="summary-row">
      {#if totalLlmIssues > 0}
        {#each Object.entries(llmIssueCounts).filter(([, n]) => n > 0) as [type, count]}
          <span class="summary-badge {type}">{count} {type}</span>
        {/each}
      {/if}
      {#if repetitionIssues > 0}
        <span class="summary-badge repetition">{repetitionCount} repetition{repetitionCount !== 1 ? 's' : ''}</span>
      {/if}
      {#if clicheCount > 0}
        <span class="summary-badge cliche">{clicheCount} cliché{clicheCount !== 1 ? 's' : ''}</span>
      {/if}
      {#if citationCount > 0}
        <span class="summary-badge citation">{citationCount} citation issue{citationCount !== 1 ? 's' : ''}</span>
      {/if}
    </div>
    {#if totalLlmIssues > 1 || visibleStaticIssues.length > 0}
      <div class="summary-actions">
        {#if totalLlmIssues > 1}
          <button class="summary-btn accept" on:click={acceptAllGlobal}>Accept all grammar fixes</button>
          <button class="summary-btn dismiss" on:click={dismissAllGlobal}>Dismiss all</button>
        {/if}
      </div>
    {/if}
  </div>
{/if}
```

The summary card needs the repetition/cliché/citation counts broken out from `visibleStaticIssues`. Add these reactive derivations in the script block:

```javascript
export let staticIssues = []  // (already added in Task 8)

$: repetitionCount  = visibleStaticIssues.filter(i => i.category === 'repetition').length
$: clicheCount      = visibleStaticIssues.filter(i => i.category === 'cliche').length
$: citationCount    = visibleStaticIssues.filter(i => i.category === 'citation').length
```

- [ ] **Step 3: Add summary card CSS**

```css
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
  }

  .summary-badge.grammar     { background: #fef9c3; color: #854d0e; }
  .summary-badge.spelling    { background: #fee2e2; color: #b91c1c; }
  .summary-badge.style       { background: #ede9fe; color: #6d28d9; }
  .summary-badge.punctuation { background: #e0f2fe; color: #0369a1; }
  .summary-badge.repetition  { background: #fef3c7; color: #92400e; }
  .summary-badge.cliche      { background: #f3e8ff; color: #6d28d9; }
  .summary-badge.citation    { background: #e0f2fe; color: #0369a1; }

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
```

---

## Task 10: Fix globalAcceptAll sentence key lookup

The `acceptAllGlobal` function in Task 8 has a flawed dismissKey lookup. Here is the corrected version:

**Files:**
- Modify: `frontend/src/components/Suggestions.svelte`

- [ ] **Step 1: Replace acceptAllGlobal with correct implementation**

```javascript
function acceptAllGlobal() {
  const toAccept = []
  const newDismissed = new Set(dismissed)

  for (const r of visibleSentences) {
    if (r.parse_error) continue
    const issues = getVisibleIssues(r, dismissed)
    if (issues.length === 0) continue
    toAccept.push({ original: r.original, issues })
    for (const i of issues) newDismissed.add(dismissKey(r, i))
  }

  dismissed = newDismissed
  if (toAccept.length > 0) dispatch('acceptAll', { sentences: toAccept })
}
```

---

## Self-Review Checklist

**Spec coverage:**

| Feature | Task |
|---------|------|
| Word repetition detection | Task 3, Task 5, Task 6 |
| Cliché/weak phrase detection | Task 3, Task 5, Task 6 |
| Accept all / Dismiss all | Task 7, Task 8 |
| Undo stack | Task 7 |
| Document-level summary | Task 9 |
| Formal tone (always formal) | Task 1 |
| LaTeX citation checks | Task 4, Task 6 |

**Gaps found and fixed:**
- `acceptAllGlobal` had a flawed dismissKey lookup → added Task 10 with corrected implementation
- `staticRanges` derivation in App.svelte had a scoping bug (used `issue` inside filter predicate where it wasn't in scope) → corrected in Task 6 Step 2 below

**Corrected `staticRanges` derivation (Task 6, Step 2):**

```javascript
$: staticRanges = staticIssues.flatMap(issue => {
  const rangeType = issue.category === 'repetition' ? 'rep'
    : issue.category === 'cliche' ? 'cliche'
    : null
  if (!rangeType) return []
  return issue.ranges.map(r => ({ start: r.start, end: r.end, type: rangeType }))
})
```

**Type consistency check:**
- `dispatch('acceptAll', { sentences: [...] })` — dispatched in Suggestions, handled as `on:acceptAll={onAcceptAll}` in App.svelte ✓
- `issue.ranges` — defined in static-checks.js and latex-bib.js, read in highlighter.js and Suggestions.svelte ✓
- `issue.category` — used consistently as `'repetition' | 'cliche' | 'citation'` ✓
- `issue.id` — used as dismissedStatic key ✓
- `issue.count` — only present on repetition issues; template guards with `{#if issue.count}` ✓
