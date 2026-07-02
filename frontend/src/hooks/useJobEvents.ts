import { useEffect, useRef } from 'react'

/** Opens a WebSocket to the queue's live event stream and calls `onEvent` for each job state
 * change. Purely a latency optimization on top of polling (see usePolling.ts) -- if the socket
 * never connects or drops, the caller's existing polling still keeps the UI correct, just
 * slower. Reconnects with backoff so a transient drop doesn't permanently go quiet. */
export function useJobEvents(queueId: string | undefined, onEvent: () => void) {
  const onEventRef = useRef(onEvent)
  onEventRef.current = onEvent

  useEffect(() => {
    if (!queueId) return
    const token = localStorage.getItem('token')
    if (!token) return

    let socket: WebSocket | null = null
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null
    let cancelled = false

    const connect = () => {
      if (cancelled) return
      const wsBase = (import.meta.env.VITE_API_URL as string).replace(/^http/, 'ws')
      socket = new WebSocket(`${wsBase}/api/v1/ws/queues/${queueId}?token=${encodeURIComponent(token)}`)
      socket.onmessage = () => onEventRef.current()
      socket.onclose = () => {
        if (!cancelled) reconnectTimer = setTimeout(connect, 3000)
      }
      socket.onerror = () => socket?.close()
    }

    connect()
    return () => {
      cancelled = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
      socket?.close()
    }
  }, [queueId])
}
