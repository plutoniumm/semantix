import { writable } from 'svelte/store'

function createAnalysisStore () {
  const { subscribe, set, update } = writable( {
    sentences: [],
    streaming: false,
    error: null,
    activeIndex: null,
  } )

  let eventSource = null
  let lastVariant = 'british'

  function reset () {
    if ( eventSource ) {
      eventSource.close()
      eventSource = null
    }
    set( { sentences: [], streaming: false, error: null, activeIndex: null } )
  }

  async function analyse ( text, variant, mode = 'plain' ) {
    if ( eventSource ) {
      eventSource.close()
      eventSource = null
    }
    lastVariant = variant

    if ( !text || !text.trim() ) {
      set( { sentences: [], streaming: false, error: null, activeIndex: null } )
      return
    }

    // Keep previous results on screen (marked stale) while the new run
    // streams in; each fresh result replaces its sentence as it arrives.
    update( s => ( {
      ...s,
      error: null,
      sentences: s.sentences.map( r => ( { ...r, stale: true } ) ),
    } ) )

    let session_id
    try {
      const resp = await fetch( '/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify( { text, variant, mode } ),
      } )
      if ( !resp.ok ) throw new Error( `POST /analyze failed: ${ resp.status }` )
      const data = await resp.json()
      session_id = data.session_id
      if ( !session_id ) throw new Error( 'POST /analyze: missing session_id in response' )
    } catch ( err ) {
      update( s => ( { ...s, error: err.message } ) )
      return
    }

    update( s => ( { ...s, streaming: true } ) )
    eventSource = new EventSource( `/analyze/stream/${ session_id }` )

    eventSource.addEventListener( 'sentence', ( e ) => {
      const result = JSON.parse( e.data )
      // Sentences are analysed concurrently and may arrive out of order.
      update( s => ( {
        ...s,
        sentences: [
          ...s.sentences.filter( r => r.sentence_index !== result.sentence_index ),
          result,
        ].sort( ( a, b ) => a.sentence_index - b.sentence_index ),
      } ) )
    } )

    eventSource.addEventListener( 'done', () => {
      eventSource.close()
      eventSource = null
      // Prune stale results the new run no longer produced.
      update( s => ( {
        ...s,
        streaming: false,
        sentences: s.sentences.filter( r => !r.stale ),
      } ) )
    } )

    eventSource.addEventListener( 'error', ( e ) => {
      let message = 'Analysis failed'
      try { message = JSON.parse( e.data ).message } catch ( _ ) { }
      eventSource.close()
      eventSource = null
      update( s => ( { ...s, streaming: false, error: message } ) )
    } )

    eventSource.onerror = () => {
      if ( !eventSource ) return
      eventSource.close()
      eventSource = null
      update( s => ( { ...s, streaming: false, error: 'Connection to server lost' } ) )
    }
  }

  function setActiveIndex ( index ) {
    update( s => ( { ...s, activeIndex: index } ) )
  }

  // Abort the current run but keep everything already received.
  function stop () {
    if ( eventSource ) {
      eventSource.close()
      eventSource = null
    }
    update( s => ( { ...s, streaming: false } ) )
  }

  // Re-analyse a single (edited) sentence in place, leaving other cards alone.
  async function recheckSentence ( index, sentence ) {
    update( s => ( {
      ...s,
      sentences: s.sentences.map( r =>
        r.sentence_index === index ? { ...r, original: sentence, retrying: true } : r ),
    } ) )

    try {
      const resp = await fetch( '/analyze/sentence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify( { sentence, variant: lastVariant, sentence_index: index } ),
      } )
      if ( !resp.ok ) throw new Error( `Recheck failed: ${ resp.status }` )
      const result = await resp.json()
      update( s => ( {
        ...s,
        sentences: s.sentences.map( r => r.sentence_index === index ? result : r ),
      } ) )
    } catch ( err ) {
      update( s => ( {
        ...s,
        sentences: s.sentences.map( r =>
          r.sentence_index === index ? { ...r, retrying: false } : r ),
        error: err.message,
      } ) )
    }
  }

  function dismissError () {
    update( s => ( { ...s, error: null } ) )
  }

  async function retrySentence ( index ) {
    let original = null
    update( s => {
      const target = s.sentences.find( r => r.sentence_index === index )
      if ( !target ) return s
      original = target.original
      return {
        ...s,
        sentences: s.sentences.map( r =>
          r.sentence_index === index ? { ...r, retrying: true } : r ),
      }
    } )
    if ( original === null ) return

    try {
      const resp = await fetch( '/analyze/sentence', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify( { sentence: original, variant: lastVariant, sentence_index: index } ),
      } )
      if ( !resp.ok ) throw new Error( `Retry failed: ${ resp.status }` )
      const result = await resp.json()
      update( s => ( {
        ...s,
        sentences: s.sentences.map( r => r.sentence_index === index ? result : r ),
      } ) )
    } catch ( err ) {
      update( s => ( {
        ...s,
        sentences: s.sentences.map( r =>
          r.sentence_index === index ? { ...r, retrying: false } : r ),
        error: err.message,
      } ) )
    }
  }

  return { subscribe, analyse, reset, stop, setActiveIndex, dismissError, retrySentence, recheckSentence }
}

export const analysis = createAnalysisStore()
