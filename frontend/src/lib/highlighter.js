import { isValidIssue, classifyDiff } from './issue-utils.js'

function escapeHtml ( str ) {
  return str
    .replace( /&/g, '&amp;' )
    .replace( /</g, '&lt;' )
    .replace( />/g, '&gt;' )
}

class BackdropHighlighter {
  build ( text, sentences ) {
    if ( !text ) return ''
    const ranges = this._collectRanges( text, sentences )
    if ( !ranges.length ) return escapeHtml( text )
    return this._renderHtml( text, this._filterOverlaps( ranges ) )
  }

  _collectRanges ( text, sentences ) {
    const ranges = []
    for ( const sentence of sentences ) {
      if ( !sentence.issues?.length ) continue
      const sentStart = text.indexOf( sentence.original )
      const sentEnd = sentStart !== -1 ? sentStart + sentence.original.length : -1

      for ( const issue of sentence.issues ) {
        if ( !isValidIssue( issue ) ) continue
        if ( issue.original_fragment.includes( '\\' ) ) continue

        const issueRanges = this._issueRanges( text, sentStart, sentEnd, issue )
        ranges.push( ...issueRanges )
      }
    }
    return ranges
  }

  _issueRanges ( text, sentStart, sentEnd, issue ) {
    const frag = issue.original_fragment

    let fragStart
    if ( sentStart !== -1 ) {
      fragStart = text.indexOf( frag, sentStart )
      if ( fragStart === -1 || fragStart >= sentEnd ) return []
    } else {
      fragStart = text.indexOf( frag )
      if ( fragStart === -1 ) return []
    }

    const ranges = []
    let origPos = fragStart

    for ( const { text: segText, type } of classifyDiff( frag, issue.suggestion ) ) {
      if ( type === 'unchanged' ) {
        origPos += segText.length
        continue
      }

      const start = origPos
      const end = type === 'add' ? origPos : origPos + segText.length
      const { ctxStart, ctxEnd } = this._contextBounds( text, start, end )
      ranges.push( { start, end, type: type === 'add' ? 'ins' : type, ctxStart, ctxEnd } )

      if ( type !== 'add' ) origPos += segText.length
    }

    return ranges
  }

  _contextBounds ( text, start, end ) {
    let ctxStart = start
    let i = start - 1
    while ( i >= 0 && text[ i ] === ' ' ) i--
    if ( i >= 0 && text[ i ] !== '\n' ) {
      while ( i > 0 && text[ i - 1 ] !== ' ' && text[ i - 1 ] !== '\n' ) i--
      ctxStart = i
    }

    let ctxEnd = end
    i = end
    while ( i < text.length && text[ i ] === ' ' ) i++
    if ( i < text.length && text[ i ] !== '\n' ) {
      while ( i < text.length && text[ i ] !== ' ' && text[ i ] !== '\n' ) i++
      ctxEnd = i
    }

    return { ctxStart, ctxEnd }
  }

  _filterOverlaps ( ranges ) {
    ranges.sort( ( a, b ) => a.start - b.start || a.end - b.end )
    const filtered = []
    let lastEnd = -1
    for ( const r of ranges ) {
      if ( r.start >= lastEnd ) {
        filtered.push( { ...r } )
        lastEnd = r.end > r.start ? r.end : r.start
      }
    }
    for ( let i = 0;i < filtered.length - 1;i++ ) {
      const cur = filtered[ i ]
      const nxt = filtered[ i + 1 ]
      if ( cur.ctxEnd > nxt.ctxStart ) {
        const mid = Math.floor( ( cur.end + nxt.start ) / 2 )
        cur.ctxEnd = Math.max( cur.end, mid )
        nxt.ctxStart = Math.min( nxt.start, mid )
      }
    }
    return filtered
  }

  _renderHtml ( text, ranges ) {
    let html = ''
    let pos = 0
    for ( const { start, end, type, ctxStart, ctxEnd } of ranges ) {
      const hasCtx = ctxStart < start || ctxEnd > end
      const outerStart = hasCtx ? ctxStart : start
      const outerEnd = hasCtx ? ctxEnd : end

      html += escapeHtml( text.slice( pos, outerStart ) )
      if ( hasCtx ) html += '<span class="frag-ctx">'
      html += escapeHtml( text.slice( outerStart, start ) )

      const content = escapeHtml( text.slice( start, end ) )
      if ( type === 'del' ) {
        html += `<span class="frag-del">${ content }</span>`
      } else if ( type === 'spell' ) {
        html += `<span class="frag-spell">${ content }</span>`
      } else if ( type === 'ins' ) {
        html += `<span class="frag-ins"></span>`
      }

      html += escapeHtml( text.slice( end, outerEnd ) )
      if ( hasCtx ) html += '</span>'
      pos = outerEnd
    }
    html += escapeHtml( text.slice( pos ) )
    return html
  }
}

export const highlighter = new BackdropHighlighter()

export function buildBackdropHtml ( text, sentences ) {
  return highlighter.build( text, sentences )
}
