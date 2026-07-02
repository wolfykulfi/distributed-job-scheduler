import type { HTMLAttributes } from 'react'

/** Rectangular bordered container — the Swiss replacement for a rounded "card". */
export default function Panel({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div {...props} className={`rounded-none border-2 border-black bg-white p-6 ${className}`} />
}
