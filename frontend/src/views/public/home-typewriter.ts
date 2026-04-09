export function coerceTypewriterText(value: unknown): string {
  return typeof value === 'string' ? value : ''
}
