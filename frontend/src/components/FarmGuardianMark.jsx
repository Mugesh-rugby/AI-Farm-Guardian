import { Leaf } from 'lucide-react'

export default function FarmGuardianMark({ className = 'h-10 w-10', iconClassName = 'h-5 w-5' }) {
  return (
    <span className={`inline-flex shrink-0 items-center justify-center rounded-xl bg-emerald-700 text-white ${className}`}>
      <Leaf aria-hidden="true" className={iconClassName} />
    </span>
  )
}
