<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Ipo, TabKey } from './types'
import FilterTabs from './components/FilterTabs.vue'
import IpoCard from './components/IpoCard.vue'
import PwaStatus from './components/PwaStatus.vue'
import SetupModal from './components/SetupModal.vue'
import { useNtfyTopic } from './composables/useNtfyTopic'
import { useIpos } from './composables/useIpos'
import { useNow } from './composables/useNow'
import { ageHours, closeAt, fmtMoment, fmtTime, JST, liveStatus, MERO_SHARE_URL, NPT, openAt } from './utils/time'

const STALE_AFTER_HOURS = 30 // scraper runs twice a day; beyond this something is wrong

const { feed, ipos, loading, error, fromCache, reload } = useIpos()
const { configured } = useNtfyTopic()
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
  <div class="mx-auto min-h-screen max-w-xl pb-16">
    <header class="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 px-4 pb-3 pt-[max(0.75rem,env(safe-area-inset-top))] backdrop-blur">
      <div class="flex items-center justify-between gap-3">
        <div>
          <h1 class="text-lg font-bold text-white">NEPSE IPO Alert</h1>
          <p class="text-xs text-slate-400">
            <template v-if="updatedAt">
              Updated {{ fmtTime(updatedAt, JST) }} JST · {{ fmtTime(updatedAt, NPT) }} NPT
            </template>
            <template v-else>Waiting for first data…</template>
          </p>
        </div>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="relative rounded-full bg-slate-800 px-3 py-2 text-sm font-medium text-slate-200 ring-1 ring-slate-700 active:bg-slate-700"
            aria-label="Phone alert setup"
            @click="setupOpen = true"
          >
            🔔
            <span v-if="!configured" class="absolute -right-0.5 -top-0.5 h-3 w-3 rounded-full bg-amber-400 ring-2 ring-slate-950" aria-hidden="true"></span>
          </button>
          <button
            type="button"
            class="rounded-full bg-slate-800 px-3 py-2 text-sm font-medium text-slate-200 ring-1 ring-slate-700 active:bg-slate-700 disabled:opacity-50"
            :disabled="loading"
            aria-label="Refresh data"
            @click="reload"
          >
            <span :class="loading ? 'inline-block animate-spin' : ''">↻</span>
            {{ loading ? 'Loading' : 'Refresh' }}
          </button>
        </div>
      </div>
      <div class="mt-1">
        <FilterTabs v-model="tab" :counts="counts" />
      </div>
    </header>

    <main class="space-y-3 px-4 pt-4">
      <div v-if="error" class="rounded-xl bg-amber-500/15 p-3 text-sm text-amber-200 ring-1 ring-amber-400/40" role="alert">
        <template v-if="fromCache">
          Can't reach the server ({{ error }}). Showing your last saved copy, so it may be out of date.
        </template>
        <template v-else>Couldn't load IPO data: {{ error }}.</template>
      </div>

      <button
        v-if="!configured"
        type="button"
        class="flex w-full items-center justify-between gap-3 rounded-xl bg-amber-400/15 p-3 text-left text-sm text-amber-100 ring-1 ring-amber-400/40 active:bg-amber-400/25"
        @click="setupOpen = true"
      >
        <span><strong>Set up phone alerts</strong><span class="block text-xs text-amber-200/80">Get notified the moment an eligible IPO is announced or opens.</span></span>
        <span aria-hidden="true">→</span>
      </button>

      <div v-if="isStale" class="rounded-xl bg-rose-500/15 p-3 text-sm text-rose-200 ring-1 ring-rose-400/40" role="alert">
        Data is {{ Math.floor(dataAge ?? 0) }} hours old, so the scraper may be failing and alerts may be delayed.
        Check
        <a :href="MERO_SHARE_URL" target="_blank" rel="noopener noreferrer" class="underline">MeroShare</a>
        directly.
      </div>

      <div v-if="unverified.length" class="rounded-xl bg-orange-500/15 p-3 text-sm text-orange-200 ring-1 ring-orange-400/40" role="alert">
        <p class="font-semibold">{{ unverified.length }} announcement(s) not yet confirmed in the main feed</p>
        <ul class="mt-1 list-disc space-y-1 pl-5">
          <li v-for="m in unverified" :key="m.text">
            {{ m.text }}
            <a v-if="m.url" :href="m.url" target="_blank" rel="noopener noreferrer" class="underline">source ↗</a>
          </li>
        </ul>
      </div>

      <p v-if="!feed && loading" class="py-16 text-center text-slate-400">Loading IPOs…</p>

      <template v-else-if="feed">
        <IpoCard v-for="ipo in visible" :key="ipo.id" :ipo="ipo" />

        <div v-if="!hasActiveInView" class="rounded-2xl bg-slate-900 p-6 text-center ring-1 ring-slate-700">
          <p class="text-base font-semibold text-white">Nothing open or upcoming here</p>
          <p class="mt-1 text-sm text-slate-400">
            You'll get a phone alert the moment a matching IPO is announced.
          </p>
        </div>
      </template>

      <label class="flex items-center gap-3 rounded-xl bg-slate-900 p-3 text-sm text-slate-300 ring-1 ring-slate-800">
        <input v-model="showOther" type="checkbox" class="h-5 w-5 accent-sky-400" />
        <span>
          Also show other issues
          <span class="block text-xs text-slate-500">Mutual funds, local-resident IPOs, right shares, debentures. No alerts are sent for these.</span>
        </span>
      </label>

      <p class="pt-2 text-center text-xs text-slate-500">
        Data from ShareSansar, cross-checked with MeroLagani. Always confirm on MeroShare before applying.
      </p>
    </main>
  </div>
  <SetupModal v-model="setupOpen" />
  <PwaStatus />
</template>
