import { ref, computed, onMounted, onBeforeUnmount } from 'vue'
import type { IpoFeed } from '../types'

const CACHE_KEY = 'ipo-feed-cache-v1'
const REFRESH_AFTER_MS = 10 * 60 * 1000

function readCache(): IpoFeed | null {
  try {
    const raw = localStorage.getItem(CACHE_KEY)
    return raw ? validate(JSON.parse(raw)) : null
  } catch {
    return null
  }
}

function writeCache(feed: IpoFeed): void {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify(feed)) } catch { /* storage full or blocked */ }
}

function validate(value: unknown): IpoFeed {
  const feed = value as IpoFeed
  if (!feed || !Array.isArray(feed.ipos)) throw new Error('Unexpected data format')
  return feed
}

export function useIpos() {
  const feed = ref<IpoFeed | null>(readCache())
  const loading = ref(false)
  const error = ref<string | null>(null)
  const fromCache = ref(feed.value !== null)
  const lastFetchAt = ref(0)

  async function load(): Promise<void> {
    loading.value = true
    try {
      // no-store: never show a stale browser-cached file; the service worker handles offline.
      const res = await fetch(`${import.meta.env.BASE_URL}data/ipos.json`, { cache: 'no-store' })
      if (!res.ok) throw new Error(`Server returned ${res.status}`)
      feed.value = validate(await res.json())
      writeCache(feed.value)
      fromCache.value = false
      error.value = null
      lastFetchAt.value = Date.now()
    } catch (e) {
      // Keep whatever we already have (cached copy) and say so; never blank the screen.
      error.value = e instanceof Error ? e.message : 'Could not load data'
      fromCache.value = feed.value !== null
    } finally {
      loading.value = false
    }
  }

  function onVisible(): void {
    if (document.visibilityState === 'visible' && Date.now() - lastFetchAt.value > REFRESH_AFTER_MS) void load()
  }

  onMounted(() => {
    void load()
    document.addEventListener('visibilitychange', onVisible)
  })
  onBeforeUnmount(() => document.removeEventListener('visibilitychange', onVisible))

  const ipos = computed(() => feed.value?.ipos ?? [])
  return { feed, ipos, loading, error, fromCache, reload: load }
}
