import type { ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'danger'

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: 'bg-black text-white hover:bg-swiss-accent',
  secondary: 'bg-white text-black border-2 border-black hover:bg-black hover:text-white',
  danger: 'bg-white text-swiss-accent border-2 border-swiss-accent hover:bg-swiss-accent hover:text-white',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

export default function Button({ variant = 'primary', className = '', ...props }: ButtonProps) {
  return (
    <button
      {...props}
      className={`swiss-focusable inline-flex items-center justify-center rounded-none px-4 py-2.5 text-xs font-bold tracking-widest uppercase transition-colors duration-150 ease-linear disabled:cursor-not-allowed disabled:opacity-40 ${VARIANT_CLASSES[variant]} ${className}`}
    />
  )
}
