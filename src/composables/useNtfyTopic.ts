import { computed, ref } from 'vue'
const KEY = 'ntfy-topic-v1'
const SERVER = 'https://ntfy.sh'
const VALID = /^[A-Za-z0-9_-]{1,64}$/

function read(): string {
  try { return localStorage.getItem(KEY) ?? '' } catch { return '' }
}

// Module-level so the header dot and the modal always agree.
const topic = ref<string>(read())

/**
 * The ntfy topic works like a password (anyone who knows it can read or forge your alerts),
 * and this site is public, so it is NEVER part of the build. The user enters it once and it
 * lives only in this browser's localStorage.
 */
export function useNtfyTopic() {
  /** Accepts a bare topic or a pasted https://ntfy.sh/<topic> URL. Returns an error message or null. */
  function save(input: string): string | null {
    const cleaned = input.trim().replace(/^https?:\/\/ntfy\.sh\//i, '').replace(/\/+$/, '')
    if (!VALID.test(cleaned)) {
      return 'Use 1-64 letters, digits, "-" or "_". Paste just the topic name, exactly as in your GitHub secret.'
    }
    try { localStorage.setItem(KEY, cleaned) } catch { return 'This browser blocked saving. Disable private mode and try again.' }
    topic.value = cleaned
    return null
  }

  function clear(): void {
    try { localStorage.removeItem(KEY) } catch { /* nothing to remove */ }
    topic.value = ''
  }

  async function sendTest(): Promise<void> {
    if (!topic.value) throw new Error('Save your topic first.')
    // Same JSON publish form the scraper uses. ntfy.sh allows cross-origin publishing.
    const dashboard = `${window.location.origin}${import.meta.env.BASE_URL}`
    const res = await fetch(SERVER, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        topic: topic.value,
        title: 'NEPSE · TEST',
        message: 'If you can read this, alerts are working.',
        priority: 4,
        click: dashboard,
        icon: `${dashboard}pwa-192x192.png`,
        actions: [{ action: 'view', label: 'View details', url: dashboard }],
      }),
    })
    if (!res.ok) throw new Error(res.status === 429 ? 'ntfy is rate limiting you. Wait a minute and retry.' : `ntfy replied ${res.status}`)
  }

  return {
    topic,
    configured: computed(() => topic.value !== ''),
    topicUrl: computed(() => (topic.value ? `${SERVER}/${topic.value}` : '')),
    save,
    clear,
    sendTest,
  }
}
