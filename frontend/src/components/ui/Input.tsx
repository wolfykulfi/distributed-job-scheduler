import type { InputHTMLAttributes, SelectHTMLAttributes } from 'react'

type InputProps = InputHTMLAttributes<HTMLInputElement>

export function Input({ className = '', ...props }: InputProps) {
  return (
    <input
      {...props}
      className={`swiss-focusable w-full rounded-none border-2 border-black bg-white px-3 py-2 text-sm text-black placeholder:text-black/40 focus:border-swiss-accent focus:outline-none ${className}`}
    />
  )
}

type SelectProps = SelectHTMLAttributes<HTMLSelectElement>

export function Select({ className = '', children, ...props }: SelectProps) {
  return (
    <select
      {...props}
      className={`swiss-focusable w-full rounded-none border-2 border-black bg-white px-3 py-2 text-sm text-black focus:border-swiss-accent focus:outline-none ${className}`}
    >
      {children}
    </select>
  )
}
