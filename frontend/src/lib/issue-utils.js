import { diffWords } from 'diff'

export function isValidIssue ( issue ) {
  return !!(
    issue.type &&
    issue.original_fragment &&
    issue.suggestion &&
    issue.original_fragment !== issue.suggestion
  )
}

export function classifyDiff ( original, suggestion ) {
  const parts = diffWords( original, suggestion )
  const result = []

  for ( let i = 0;i < parts.length;i++ ) {
    const part = parts[ i ]

    if ( !part.added && !part.removed ) {
      result.push( { text: part.value, type: 'unchanged' } )
      continue
    }

    if ( part.removed ) {
      const nextIsAdded = i + 1 < parts.length && parts[ i + 1 ].added
      if ( nextIsAdded ) {
        result.push( { text: part.value, addedText: parts[ i + 1 ].value, type: 'spell' } )
        i++
      } else {
        result.push( { text: part.value, type: 'del' } )
      }
      continue
    }

    if ( part.added ) {
      result.push( { text: part.value, type: 'add' } )
    }
  }

  return result
}
