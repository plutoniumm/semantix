const STOPWORDS = new Set([
  'about', 'above', 'after', 'again', 'against', 'although', 'because',
  'been', 'being', 'before', 'below', 'between', 'both', 'could',
  'during', 'each', 'every', 'furthermore', 'hence', 'however', 'might',
  'moreover', 'must', 'nevertheless', 'other', 'ought', 'shall', 'should',
  'since', 'some', 'such', 'that', 'their', 'there', 'therefore', 'these',
  'they', 'this', 'those', 'through', 'thus', 'under', 'unless', 'until',
  'whereas', 'whereby', 'whether', 'which', 'while', 'where',
  'would', 'will', 'with', 'your', 'from', 'into', 'onto', 'upon',
])

const CLICHES = [
  { phrase: 'at the end of the day',    message: 'Cliché. Use a specific conclusion instead.' },
  { phrase: 'think outside the box',    message: 'Cliché. Use "think creatively" or "explore new approaches".' },
  { phrase: 'low-hanging fruit',        message: 'Cliché jargon. Use "easiest gains" or "simplest improvements".' },
  { phrase: 'move the needle',          message: 'Jargon cliché. Use "make a measurable impact".' },
  { phrase: 'paradigm shift',           message: 'Overused jargon. Use "fundamental change" if that is what you mean.' },
  { phrase: 'game changer',             message: 'Cliché. Describe the actual impact specifically.' },
  { phrase: 'circle back',              message: 'Informal jargon. Use "revisit" or "return to".' },
  { phrase: 'touch base',               message: 'Informal jargon. Use "follow up" or "consult".' },
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

const LONG_SENTENCE_WORDS = 35

// Blanks out LaTeX constructs with equal-length whitespace so that character
// offsets in the masked text still address the original text.
export function maskLatex(text) {
  const blank = (m) => m.replace(/[^\n]/g, ' ')
  const KEEP_ARG_CMDS = /\\(?:textit|textbf|emph|texttt|textrm|textsc|text|mbox|section\*?|subsection\*?|subsubsection\*?|paragraph|title|caption)\{/g
  const NON_PROSE_ENVS = /\\begin\{(equation|align|gather|multline|eqnarray|displaymath|algorithm|algorithmic|lstlisting|verbatim|tabular|array|matrix|pmatrix|bmatrix|vmatrix)(\*?)\}[\s\S]*?\\end\{\1\2\}/g

  return text
    .replace(/(?<!\\)%[^\n]*/g, blank)
    .replace(/\$\$[\s\S]*?\$\$/g, blank)
    .replace(/\\\[[\s\S]*?\\\]/g, blank)
    .replace(/\$[^$\n]*\$/g, blank)
    .replace(NON_PROSE_ENVS, blank)
    .replace(KEEP_ARG_CMDS, blank)
    .replace(/\\[a-zA-Z@]+\*?(?:\[[^\]]*\])?(?:\{[^{}]*\})*/g, blank)
    .replace(/[{}~]/g, ' ')
}

// Sentence segmentation with character offsets. Newlines are treated as
// ordinary whitespace so soft-wrapped prose stays in one sentence.
export function splitSentences(text) {
  const sentences = []
  const re = /[^.!?]+(?:[.!?]+["')\]]*|$)/g
  let m
  while ((m = re.exec(text)) !== null) {
    const raw = m[0]
    const lead = raw.length - raw.trimStart().length
    const trimmed = raw.trim()
    if (trimmed) {
      sentences.push({
        text: trimmed,
        start: m.index + lead,
        end: m.index + lead + trimmed.length,
      })
    }
  }
  return sentences
}

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

export function detectDoubledWords(text) {
  if (!text || !text.trim()) return []

  const issues = []
  const re = /\b([A-Za-z]+)(\s+)(\1)\b/gi
  let m

  while ((m = re.exec(text)) !== null) {
    // Skip masked-LaTeX gaps and paragraph breaks — those are not true doubles.
    if (m[2].length > 3 || m[2].includes('\n\n')) continue
    issues.push({
      id: `doubled-${m[1].toLowerCase()}-${m.index}`,
      category: 'doubled',
      fragment: m[0],
      message: `"${m[1]}" appears twice in a row. Remove the duplicate if unintentional.`,
      ranges: [{ start: m.index, end: m.index + m[0].length }],
    })
    // Resume right after the first word so triples are also caught.
    re.lastIndex = m.index + m[1].length
  }

  return issues
}

export function detectLongSentences(text) {
  if (!text || !text.trim()) return []

  const issues = []
  for (const s of splitSentences(text)) {
    const words = s.text.split(/\s+/).filter(Boolean).length
    if (words <= LONG_SENTENCE_WORDS) continue
    const preview = s.text.length > 80 ? s.text.slice(0, 80) + '…' : s.text
    issues.push({
      id: `long-${s.start}`,
      category: 'long-sentence',
      fragment: preview,
      message: `This sentence is ${words} words long. Consider splitting it into shorter sentences.`,
      ranges: [{ start: s.start, end: s.end }],
    })
  }

  return issues
}

export function detectStartRepetition(text) {
  if (!text || !text.trim()) return []

  const sentences = splitSentences(text)
  const issues = []
  let run = []

  const flush = () => {
    if (run.length >= 3) {
      const word = run[0].word
      issues.push({
        id: `startrep-${word}-${run[0].s.start}`,
        category: 'start-repetition',
        fragment: run.map(r => r.s.text.split(/\s+/)[0]).join(' … '),
        message: `${run.length} consecutive sentences begin with "${word}". Vary your sentence openings.`,
        ranges: [{ start: run[0].s.start, end: run[run.length - 1].s.end }],
      })
    }
    run = []
  }

  for (const s of sentences) {
    const m = s.text.match(/[A-Za-z']+/)
    const word = m ? m[0].toLowerCase() : null
    if (word && run.length && run[0].word === word) {
      run.push({ word, s })
    } else {
      flush()
      if (word) run.push({ word, s })
    }
  }
  flush()

  return issues
}
