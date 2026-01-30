import type { ReactNode } from 'react'

interface TooltipProps {
  content: string
  children: ReactNode
  side?: 'top' | 'bottom' | 'left' | 'right'
}

export function Tooltip({ content, children, side = 'top' }: TooltipProps) {
  return (
    <span className="tooltip-wrapper" data-tooltip={content} data-tooltip-side={side}>
      {children}
    </span>
  )
}
