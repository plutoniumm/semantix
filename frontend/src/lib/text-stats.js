import { splitSentences } from './static-checks.js'

function syllables(word) {
  const w = word.toLowerCase().replace(/[^a-z]/g, '')
  if (!w) return 0
  if (w.length <= 3) return 1
  const stripped = w.replace(/e$/, '')
  const groups = stripped.match(/[aeiouy]+/g)
  return Math.max(1, groups ? groups.length : 1)
}

function fleschLabel(score) {
  if (score >= 70) return 'easy'
  if (score >= 60) return 'standard'
  if (score >= 50) return 'moderate'
  if (score >= 30) return 'difficult'
  return 'very difficult'
}

export function computeStats(text) {
  const empty = { words: 0, sentences: 0, minutes: 0, flesch: null, fleschLabel: '' }
  if (!text || !text.trim()) return empty

  const words = text.trim().split(/\s+/).filter(w => /[A-Za-z0-9]/.test(w))
  if (!words.length) return empty

  const sentenceCount = Math.max(1, splitSentences(text).length)
  const syllableCount = words.reduce((sum, w) => sum + syllables(w), 0)

  const raw = 206.835
    - 1.015 * (words.length / sentenceCount)
    - 84.6 * (syllableCount / words.length)
  const flesch = Math.round(Math.min(100, Math.max(0, raw)))

  return {
    words: words.length,
    sentences: sentenceCount,
    minutes: Math.max(1, Math.round(words.length / 200)),
    flesch,
    fleschLabel: fleschLabel(flesch),
  }
}
