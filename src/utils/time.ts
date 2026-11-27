import type { Ipo, Status } from '../types'

export const MERO_SHARE_URL = 'https://cdsc.com.np'
export const NPT = 'Asia/Kathmandu'
export const JST = 'Asia/Tokyo'

// Nepal is UTC+05:45 all year (no daylight saving), so a fixed offset is exact.
const NPT_OFFSET = '+05:45'

/** Issues are dated by Nepal calendar day. Opening = start of that day. */
export const openAt = (i: Ipo): number => Date.parse(`${i.open_date}T00:00:00${NPT_OFFSET}`)
/**
 * Closing = end of the closing day. MeroShare's exact closing hour is not published in the
 * data, so the UI treats the last second of the day as the limit and labels it "approx.".
 */
export const closeAt = (i: Ipo): number => Date.parse(`${i.close_date}T23:59:59${NPT_OFFSET}`)

/** Status recomputed against the current clock, so a card flips without a new scrape. */
export function liveStatus(i: Ipo, now: number): Status {
  if (now < openAt(i)) return 'Upcoming'
  if (now <= closeAt(i)) return 'Open'
  return 'Closed'
}

export function splitDuration(ms: number): { d: number; h: number; m: number; s: number } {
  const total = Math.max(0, Math.floor(ms / 1000))
  return {
    d: Math.floor(total / 86400),
    h: Math.floor((total % 86400) / 3600),
    m: Math.floor((total % 3600) / 60),
    s: total % 60,
  }
}

/** "Tue 1 Dec, 23:59" in the given zone. */
export function fmtMoment(ms: number, timeZone: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone, weekday: 'short', day: 'numeric', month: 'short',
    hour: '2-digit', minute: '2-digit', hour12: false,
  }).format(new Date(ms)).replace(',', '')
}

/** "10:59" in the given zone. */
export function fmtTime(ms: number, timeZone: string): string {
  return new Intl.DateTimeFormat('en-GB', { timeZone, hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(ms))
}

/** "Tue 1 Dec" for a plain Nepal calendar date. */
export function fmtDay(iso: string): string {
  return new Intl.DateTimeFormat('en-GB', {
    timeZone: 'UTC', weekday: 'short', day: 'numeric', month: 'short',
  }).format(new Date(`${iso}T00:00:00Z`)).replace(',', '')
}

export function fmtNumber(n: number | null): string {
  return n == null ? '—' : n.toLocaleString('en-US')
}

export function fmtRs(n: number | null): string {
  return n == null ? '—' : `Rs ${n.toLocaleString('en-US', { maximumFractionDigits: 2 })}`
}

export const quotaLabel = (q: Ipo['quota_type']): string =>
  q === 'FOREIGN_EMPLOYMENT' ? 'Foreign Employment (10%)' : q === 'GENERAL_PUBLIC' ? 'General Public' : 'Other'

export function ageHours(iso: string | null, now: number): number | null {
  if (!iso) return null
  const t = Date.parse(iso)
  return Number.isNaN(t) ? null : (now - t) / 3_600_000
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // Clipboard API is blocked in some contexts (insecure origin, old WebView): fall back.
    try {
      const ta = document.createElement('textarea')
      ta.value = text
      ta.setAttribute('readonly', '')
      ta.style.cssText = 'position:fixed;top:0;left:0;opacity:0'
      document.body.appendChild(ta)
      ta.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(ta)
      return ok
    } catch {
      return false
    }
  }
}
