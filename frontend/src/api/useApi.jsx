import { useEffect, useState } from 'react'

/**
 * Run an async API call when its dependencies change.
 *
 * Every function in api/orbitguard.js falls back to mock data when the backend
 * is unavailable, so `data` is normally populated; `error` only appears if the
 * fallback itself fails.
 *
 * @param {() => Promise<any>} fetcher
 * @param {any[]} deps
 * @returns {{ data: any, loading: boolean, error: Error|null }}
 */
export function useApi(fetcher, deps = []) {
  const [state, setState] = useState({ data: null, loading: true, error: null })

  useEffect(() => {
    let cancelled = false
    setState((s) => ({ ...s, loading: true, error: null }))
    fetcher()
      .then((data) => !cancelled && setState({ data, loading: false, error: null }))
      .catch((error) => !cancelled && setState({ data: null, loading: false, error }))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return state
}

/** Placeholder shown while a page's data loads. */
export function Loading({ label = 'Loading…' }) {
  return <div className="p-5 text-xs text-ink-faint">{label}</div>
}
