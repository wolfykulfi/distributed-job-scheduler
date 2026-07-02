/** Numbered section marker, e.g. "01. QUEUES" — the recurring Swiss-style structural cue. */
export default function SectionLabel({ index, children }: { index: number; children: string }) {
  return (
    <p className="mb-2 text-xs font-bold tracking-widest text-swiss-accent uppercase">
      {String(index).padStart(2, '0')}. {children}
    </p>
  )
}
