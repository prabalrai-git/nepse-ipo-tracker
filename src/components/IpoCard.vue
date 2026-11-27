<script setup lang="ts">
import { computed, ref } from 'vue'
import type { Ipo } from '../types'
import CountdownTimer from './CountdownTimer.vue'
import { useNow } from '../composables/useNow'
import {
  MERO_SHARE_URL, NPT, JST, openAt, closeAt, liveStatus, fmtMoment, fmtDay,
  fmtNumber, fmtRs, quotaLabel, detailsText, copyText,
} from '../utils/time'

const props = defineProps<{ ipo: Ipo }>()
const now = useNow()

const status = computed(() => liveStatus(props.ipo, now.value))
const isForeign = computed(() => props.ipo.quota_type === 'FOREIGN_EMPLOYMENT')
const issueSize = computed(() =>
  props.ipo.units != null && props.ipo.price != null ? props.ipo.units * props.ipo.price : null,
)
const target = computed(() => (status.value === 'Upcoming' ? openAt(props.ipo) : closeAt(props.ipo)))

const badgeClass = computed(() =>
  isForeign.value
    ? 'bg-amber-400 text-amber-950'
    : props.ipo.quota_type === 'GENERAL_PUBLIC'
      ? 'bg-sky-400/20 text-sky-200 ring-1 ring-sky-400/40'
      : 'bg-slate-700 text-slate-200',
)
const statusClass = computed(() =>
  status.value === 'Open'
    ? 'bg-emerald-500/20 text-emerald-300 ring-1 ring-emerald-400/40'
    : status.value === 'Upcoming'
      ? 'bg-indigo-500/20 text-indigo-200 ring-1 ring-indigo-400/40'
      : 'bg-slate-700 text-slate-400',
)

const copied = ref<'idle' | 'ok' | 'fail'>('idle')
let resetTimer: number | undefined
async function copyDetails(): Promise<void> {
  copied.value = (await copyText(detailsText(props.ipo, now.value))) ? 'ok' : 'fail'
  window.clearTimeout(resetTimer)
  resetTimer = window.setTimeout(() => { copied.value = 'idle' }, 2000)
}
</script>

<template>
  <article
    class="rounded-2xl bg-slate-900 p-4 ring-1"
    :class="[
      isForeign ? 'ring-amber-400/50' : 'ring-slate-700',
      status === 'Closed' ? 'opacity-60' : '',
    ]"
  >
    <header class="flex items-start justify-between gap-3">
      <div class="min-w-0">
        <h2 class="text-2xl font-bold tracking-tight text-white">{{ ipo.symbol }}</h2>
        <p class="text-sm leading-snug text-slate-300">{{ ipo.company_name }}</p>
      </div>
      <div class="flex shrink-0 flex-col items-end gap-1.5">
        <span class="rounded-full px-2.5 py-1 text-xs font-semibold" :class="statusClass">{{ status }}</span>
        <span class="rounded-full px-2.5 py-1 text-xs font-semibold" :class="badgeClass">{{ quotaLabel(ipo.quota_type) }}</span>
      </div>
    </header>

    <div v-if="status !== 'Closed'" class="mt-4">
      <CountdownTimer :target="target" :mode="status === 'Upcoming' ? 'open' : 'close'" />
    </div>

    <dl class="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 text-sm">
      <div>
        <dt class="text-xs text-slate-400">Price per unit</dt>
        <dd class="font-semibold text-white">{{ fmtRs(ipo.price) }}</dd>
      </div>
      <div>
        <dt class="text-xs text-slate-400">Total units</dt>
        <dd class="font-semibold text-white tabular-nums">{{ fmtNumber(ipo.units) }}</dd>
      </div>
      <div>
        <dt class="text-xs text-slate-400">Issue size</dt>
        <dd class="font-semibold text-white tabular-nums">{{ fmtRs(issueSize) }}</dd>
      </div>
      <div>
        <dt class="text-xs text-slate-400">Sector</dt>
        <dd class="font-semibold text-white">{{ ipo.sector ?? '—' }}</dd>
      </div>
      <div class="col-span-2">
        <dt class="text-xs text-slate-400">Issue manager</dt>
        <dd class="font-semibold text-white">{{ ipo.issue_manager ?? '—' }}</dd>
      </div>
    </dl>

    <div class="mt-4 space-y-2 rounded-xl bg-slate-800/70 p-3 text-xs text-slate-300">
      <p>
        <span class="text-slate-400">Opens</span> {{ fmtDay(ipo.open_date) }}
        <span class="mx-1 text-slate-600">|</span>
        <span class="text-slate-400">Closes</span> {{ fmtDay(ipo.close_date) }}
        <span class="text-slate-500">(Nepal dates)</span>
      </p>
      <div>
        <p class="mb-1 font-semibold text-slate-200">{{ status === 'Closed' ? 'Closed' : 'Closes (approx.)' }}</p>
        <p class="flex items-center justify-between"><span>🇳🇵 Nepal time</span><span class="font-medium tabular-nums text-white">{{ fmtMoment(closeAt(ipo), NPT) }}</span></p>
        <p class="flex items-center justify-between"><span>🇯🇵 Japan time</span><span class="font-medium tabular-nums text-white">{{ fmtMoment(closeAt(ipo), JST) }}</span></p>
      </div>
    </div>

    <div class="mt-4 flex flex-col gap-2 sm:flex-row">
      <a
        v-if="status === 'Open'"
        :href="MERO_SHARE_URL"
        target="_blank"
        rel="noopener noreferrer"
        class="flex-1 rounded-xl bg-emerald-500 px-4 py-3 text-center text-base font-bold text-emerald-950 active:bg-emerald-400"
      >Apply on MeroShare ↗</a>
      <button
        type="button"
        class="flex-1 rounded-xl bg-slate-800 px-4 py-3 text-center text-base font-semibold text-white ring-1 ring-slate-600 active:bg-slate-700"
        @click="copyDetails"
      >
        <span v-if="copied === 'ok'">Copied ✓</span>
        <span v-else-if="copied === 'fail'">Copy failed</span>
        <span v-else>Copy Details</span>
      </button>
    </div>

    <a
      v-if="ipo.announcement_url"
      :href="ipo.announcement_url"
      target="_blank"
      rel="noopener noreferrer"
      class="mt-3 inline-block text-sm text-sky-300 underline underline-offset-2"
    >Read offer letter ↗</a>
  </article>
</template>
