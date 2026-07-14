import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: string | Date): string {
  return new Date(date).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric'
  })
}

export function formatSalary(min?: number, max?: number): string {
  if (!min && !max) return 'Not specified'
  if (min && max) return `$${(min / 1000).toFixed(0)}k - $${(max / 1000).toFixed(0)}k`
  if (min) return `$${(min / 1000).toFixed(0)}k+`
  return `Up to $${(max! / 1000).toFixed(0)}k`
}
