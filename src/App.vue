<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Ipo, TabKey } from './types'
import FilterTabs from './components/FilterTabs.vue'
import IpoCard from './components/IpoCard.vue'
import PwaStatus from './components/PwaStatus.vue'
import SetupModal from './components/SetupModal.vue'
import { useIpos } from './composables/useIpos'
import { useNow } from './composables/useNow'
import { ageHours, closeAt, fmtMoment, fmtTime, JST, liveStatus, MERO_SHARE_URL, NPT, openAt } from './utils/time'

const STALE_AFTER_HOURS = 30 // scraper runs twice a day; beyond this something is wrong

const { feed, ipos, loading, error, fromCache, reload } = useIpos()
const setupOpen = ref(false)
const now = useNow()

function stored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key)
    return allowed.includes(v as T) ? (v as T) : fallback
  } catch {
    return fallback
  }
}
function store(key: string, value: string): void {
  try { localStorage.setItem(key, value) } catch { /* private mode: preference just won't persist */ }
}

const tab = ref<TabKey>(stored<TabKey>('ipo-tab', ['eligible', 'foreign', 'general', 'upcoming'], 'eligible'))
const showOther = ref(stored('ipo-show-other', ['0', '1'], '0') === '1')
watch(tab, (v) => store('ipo-tab', v))
watch(showOther, (v) => store('ipo-show-other', v ? '1' : '0'))

const pool = computed<Ipo[]>(() => ipos.value.filter((i) => showOther.value || i.eligible))

function matches(i: Ipo, key: TabKey): boolean {
  if (key === 'foreign') return i.quota_type === 'FOREIGN_EMPLOYMENT'
  if (key === 'general') return i.quota_type === 'GENERAL_PUBLIC'
  if (key === 'upcoming') return liveStatus(i, now.value) === 'Upcoming'
  return true
}

function order(a: Ipo, b: Ipo): number {
  const rank = { Open: 0, Upcoming: 1, Closed: 2 } as const
  const sa = liveStatus(a, now.value)
  const sb = liveStatus(b, now.value)
  if (sa !== sb) return rank[sa] - rank[sb]
  if (sa === 'Open') return closeAt(a) - closeAt(b) // soonest deadline first
  if (sa === 'Upcoming') return openAt(a) - openAt(b)
  return closeAt(b) - closeAt(a)
}

const visible = computed(() => pool.value.filter((i) => matches(i, tab.value)).sort(order))

// Badges count issues you can still act on (open or upcoming); closed ones just trail dimmed.
const counts = computed<Record<TabKey, number>>(() => {
  const active = pool.value.filter((i) => liveStatus(i, now.value) !== 'Closed')
  const n = (k: TabKey) => active.filter((i) => matches(i, k)).length
  return { eligible: n('eligible'), foreign: n('foreign'), general: n('general'), upcoming: n('upcoming') }
})

const updatedAt = computed(() => (feed.value?.last_updated_utc ? Date.parse(feed.value.last_updated_utc) : null))
const dataAge = computed(() => ageHours(feed.value?.last_updated_utc ?? null, now.value))
const isStale = computed(() => dataAge.value != null && dataAge.value > STALE_AFTER_HOURS)
const unverified = computed(() => feed.value?.crosscheck?.missing_from_primary ?? [])
const hasActiveInView = computed(() => visible.value.some((i) => liveStatus(i, now.value) !== 'Closed'))
</script>

<template>
  <div class="mx-auto min-h-screen max-w-xl border-x border-ink bg-paper pb-20 md:my-0">
    <header class="sticky top-0 z-10 bg-paper pt-[env(safe-area-inset-top)]">
      <div class="grid h-14 grid-cols-[3.5rem_1fr_3.5rem] border-b border-ink">
        <button
          type="button"
          class="relative flex items-center justify-center border-r border-ink active:bg-paper-deep"
          aria-label="Alert settings"
          @click="setupOpen = true"
        >
          <svg viewBox="0 0 24 24" class="h-6 w-6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9" /><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" /></svg>
        </button>
        <h1 class="flex flex-col items-center justify-center leading-none">
          <span class="text-[10px] font-bold uppercase tracking-[0.35em] text-brand-deep">Nepse</span>
          <span class="mt-1 font-display text-xl font-bold uppercase tracking-[0.12em]">IPO Alert</span>
        </h1>
        <button
          type="button"
          class="flex items-center justify-center border-l border-ink active:bg-paper-deep disabled:opacity-50"
          :disabled="loading"
          aria-label="Refresh data"
          @click="reload"
        >
          <svg viewBox="0 0 24 24" class="h-6 w-6" :class="loading ? 'animate-spin' : ''" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M21 12a9 9 0 1 1-3-6.7" /><path d="M21 4v5h-5" /></svg>
        </button>
      </div>
      <FilterTabs v-model="tab" :counts="counts" :all-label="showOther ? 'All Issues' : 'All Eligible'" />
    </header>

    <section class="border-b border-ink bg-sun px-5 py-6 text-center">
      <h2 class="font-display text-2xl font-bold leading-tight">Never miss an IPO.</h2>
      <p class="mx-auto mt-2 max-w-xs text-xs">Foreign 10% and General Public issues, pushed to your phone the moment they are announced or open.</p>
      <button
        type="button"
        class="mt-4 w-full border border-ink bg-paper px-4 py-3 text-sm font-bold active:bg-paper-deep"
        @click="setupOpen = true"
      >Alert settings</button>
      <p v-if="updatedAt" class="mt-3 text-xs underline underline-offset-2">
        Updated {{ fmtTime(updatedAt, JST) }} JST · {{ fmtTime(updatedAt, NPT) }} NPT
      </p>
    </section>

    <main class="space-y-4 px-4 pt-5">
      <div v-if="error" class="border border-ink bg-sun p-3 text-xs" role="alert">
        <template v-if="fromCache">
          Can't reach the server ({{ error }}). Showing your last saved copy, so it may be out of date.
        </template>
        <template v-else>Couldn't load IPO data: {{ error }}.</template>
      </div>

      <div v-if="isStale" class="border border-ink bg-brand p-3 text-xs font-bold" role="alert">
        Data is {{ Math.floor(dataAge ?? 0) }} hours old, so the scraper may be failing and alerts may be delayed.
        Check
        <a :href="MERO_SHARE_URL" target="_blank" rel="noopener noreferrer" class="underline">MeroShare</a>
        directly.
      </div>

      <div v-if="unverified.length" class="border border-ink bg-sun p-3 text-xs" role="alert">
        <p class="font-bold">{{ unverified.length }} announcement(s) not yet confirmed in the main feed</p>
        <ul class="mt-1 list-disc space-y-1 pl-5">
          <li v-for="m in unverified" :key="m.text">
            {{ m.text }}
            <a v-if="m.url" :href="m.url" target="_blank" rel="noopener noreferrer" class="underline">source ↗</a>
          </li>
        </ul>
      </div>

      <p v-if="!feed && loading" class="py-16 text-center text-ink-soft">Loading IPOs…</p>

      <template v-else-if="feed">
        <IpoCard v-for="ipo in visible" :key="ipo.id" :ipo="ipo" />

        <div v-if="!hasActiveInView" class="border border-ink p-6 text-center">
          <p class="font-display text-lg font-bold">Nothing open or upcoming here</p>
          <p class="mt-1 text-xs text-ink-soft">
            You'll get a phone alert the moment a matching IPO is announced.
          </p>
        </div>
      </template>

      <label class="flex items-start gap-3 border border-ink p-3 text-xs">
        <input v-model="showOther" type="checkbox" class="mt-0.5 h-5 w-5 shrink-0 accent-[#f26b21]" />
        <span>
          <span class="font-bold">Also show other issues</span>
          <span class="block text-ink-soft">Mutual funds, local-resident IPOs, right shares, debentures. No alerts are sent for these.</span>
        </span>
      </label>

      <p class="pt-2 text-center text-[11px] text-ink-soft">
        Data from ShareSansar, cross-checked with MeroLagani. Always confirm on MeroShare before applying.
      </p>
    </main>
  </div>
  <SetupModal v-model="setupOpen" />
  <PwaStatus />
</template>
