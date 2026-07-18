const CITE_PATTERN = /\\(cite|citep|citet|citealt|citealp|citenum|citeauthor|citeyear|nocite)(?:\[[^\]]*\])?\{([^}]+)\}/g
const BIBITEM_PATTERN = /\\bibitem(?:\[[^\]]*\])?\{([^}]+)\}/g

// Yields { key, start, end } for every comma-separated key inside a braced
// argument, with offsets into the full text.
function* keysWithOffsets(match, inner) {
  const innerStart = match.index + match[0].length - 1 - inner.length
  const seg = /[^,]+/g
  let m
  while ((m = seg.exec(inner)) !== null) {
    const lead = m[0].length - m[0].trimStart().length
    const key = m[0].trim()
    if (!key) continue
    const start = innerStart + m.index + lead
    yield { key, start, end: start + key.length }
  }
}

export function checkCitations(text) {
  const cited = new Map()   // key -> [{start, end}]
  const defined = new Map() // key -> [{start, end}]
  let nociteAll = false
  const issues = []

  let m
  CITE_PATTERN.lastIndex = 0
  while ((m = CITE_PATTERN.exec(text)) !== null) {
    for (const { key, start, end } of keysWithOffsets(m, m[2])) {
      if (m[1] === 'nocite' && key === '*') {
        nociteAll = true
        continue
      }
      if (!cited.has(key)) cited.set(key, [])
      cited.get(key).push({ start, end })
    }
  }

  BIBITEM_PATTERN.lastIndex = 0
  while ((m = BIBITEM_PATTERN.exec(text)) !== null) {
    for (const { key, start, end } of keysWithOffsets(m, m[1])) {
      if (!defined.has(key)) defined.set(key, [])
      defined.get(key).push({ start, end })
    }
  }

  if (cited.size === 0 && defined.size === 0) return []

  for (const [key, ranges] of cited) {
    if (!defined.has(key)) {
      issues.push({
        id: `cite-missing-${key}`,
        category: 'citation',
        fragment: key,
        message: `Citation key "${key}" is used but not defined in the bibliography.`,
        ranges,
      })
    }
  }

  if (!nociteAll) {
    for (const [key, ranges] of defined) {
      if (!cited.has(key)) {
        issues.push({
          id: `cite-unused-${key}`,
          category: 'citation',
          fragment: key,
          message: `Bibliography entry "${key}" is defined but never cited.`,
          ranges,
        })
      }
    }
  }

  for (const [key, ranges] of defined) {
    if (ranges.length > 1) {
      issues.push({
        id: `cite-dup-${key}`,
        category: 'citation',
        fragment: key,
        message: `Bibliography entry "${key}" is defined ${ranges.length} times.`,
        ranges,
      })
    }
  }

  return issues
}
