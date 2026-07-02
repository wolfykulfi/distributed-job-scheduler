/** Only "in trouble" states get the accent red — everything else stays black/white/gray,
 * keeping red a functional signal rather than decoration. */
const ACCENT_STATES = new Set(['failed', 'dead_letter'])
const MUTED_STATES = new Set(['cancelled', 'offline'])

export default function StatusBadge({ status }: { status: string }) {
  let classes = 'border-black bg-white text-black'
  if (ACCENT_STATES.has(status)) classes = 'border-swiss-accent bg-swiss-accent text-white'
  else if (MUTED_STATES.has(status)) classes = 'border-black/30 bg-swiss-muted text-black/50'
  else if (status === 'completed' || status === 'succeeded' || status === 'online') classes = 'border-black bg-black text-white'

  return (
    <span className={`inline-block rounded-none border-2 px-2 py-0.5 text-[10px] font-bold tracking-widest uppercase ${classes}`}>
      {status.replace('_', ' ')}
    </span>
  )
}
