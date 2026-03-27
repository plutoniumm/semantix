import { writable } from 'svelte/store'

function createAnalysisStore () {
  const { subscribe, set, update } = writable( {
    sentences: [],
    streaming: false,
    error: null,
    activeIndex: null,
  } )

  let eventSource = null

  function reset () {
    if ( eventSource ) {
      eventSource.close()
      eventSource = null
    }
    set( { sentences: [], streaming: false, error: null, activeIndex: null } )
  }

  async function analyse ( text, variant, mode = 'plain' ) {
    reset()

    if ( !text || !text.trim() ) return

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
      update( s => ( { ...s, sentences: [ ...s.sentences, result ] } ) )
    } )

    eventSource.addEventListener( 'done', () => {
      eventSource.close()
      eventSource = null
      update( s => ( { ...s, streaming: false } ) )
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

  function dismissError () {
    update( s => ( { ...s, error: null } ) )
  }

  return { subscribe, analyse, reset, setActiveIndex, dismissError }
}

export const analysis = createAnalysisStore()
