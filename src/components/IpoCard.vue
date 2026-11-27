<script setup lang="ts">
import { computed } from 'vue'
import type { Ipo } from '../types'
import CountdownTimer from './CountdownTimer.vue'
import { useNow } from '../composables/useNow'
import { NPT, JST, openAt, closeAt, liveStatus, fmtMoment, fmtDay, fmtNumber, fmtRs, quotaLabel } from '../utils/time'

const props = defineProps<{ ipo: Ipo }>()
const now = useNow()

const status = computed(() => liveStatus(props.ipo, now.value))
const issueSize = computed(() =>
  props.ipo.units != null && props.ipo.price != null ? props.ipo.units * props.ipo.price : null,
)
const target = computed(() => (status.value === 'Upcoming' ? openAt(props.ipo) : closeAt(props.ipo)))

const statusClass = computed(() =>
  status.value === 'Open'
    ? 'bg-brand text-ink'
    : status.value === 'Upcoming'
      ? 'bg-sun text-ink'
      : 'bg-paper text-ink-soft',
)
const rows = computed(() => [
  ['Price / unit', fmtRs(props.ipo.price)],
  ['Total units', fmtNumber(props.ipo.units)],
  ['Issue size', fmtRs(issueSize.value)],
  ['Sector', props.ipo.sector ?? '—'],
  ['Manager', props.ipo.issue_manager ?? '—'],
])
</script>

<template>
  <article class="border border-ink bg-paper" :class="status === 'Closed' ? 'opacity-60' : ''">
    <header class="flex items-start justify-between gap-3 border-b border-ink p-4">
      <div class="min-w-0">
        <h2 class="font-display text-2xl font-bold leading-tight">{{ ipo.symbol }}</h2>
        <p class="mt-0.5 text-xs leading-snug text-ink-soft">{{ ipo.company_name }}</p>
      </div>
      <div class="flex shrink-0 flex-col items-end gap-1.5">
        <span class="border border-ink px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider" :class="statusClass">{{ status }}</span>
        <span class="border border-ink px-2 py-0.5 text-[11px] font-bold" :class="ipo.quota_type === 'FOREIGN_EMPLOYMENT' ? 'bg-ink text-paper' : 'bg-paper'">{{ quotaLabel(ipo.quota_type) }}</span>
      </div>
    </header>

    <div v-if="status !== 'Closed'" class="border-b border-ink p-4">
      <CountdownTimer :target="target" :mode="status === 'Upcoming' ? 'open' : 'close'" />
    </div>

    <dl class="px-4 pt-1 text-xs">
      <div v-for="r in rows" :key="r[0]" class="flex items-baseline justify-between gap-4 py-1.5">
        <dt class="shrink-0 text-ink-soft">{{ r[0] }}</dt>
        <dd class="text-right font-bold tabular-nums">{{ r[1] }}</dd>
      </div>
    </dl>

    <div class="mx-4 mb-4 mt-2 border-t border-ink pt-3 text-xs">
      <div class="flex items-baseline justify-between gap-4 py-1">
        <span class="text-ink-soft">Opens</span><span class="font-bold">{{ fmtDay(ipo.open_date) }}</span>
      </div>
      <div class="flex items-baseline justify-between gap-4 py-1">
        <span class="text-ink-soft">Closes</span><span class="font-bold">{{ fmtDay(ipo.close_date) }}</span>
      </div>
      <p class="mb-1 mt-3 text-[11px] font-bold uppercase tracking-widest text-ink-soft">{{ status === 'Closed' ? 'Closed' : 'Closes (approx.)' }}</p>
      <div class="flex items-baseline justify-between gap-4 py-1"><span>🇳🇵 Nepal time</span><span class="font-bold tabular-nums">{{ fmtMoment(closeAt(ipo), NPT) }}</span></div>
      <div class="flex items-baseline justify-between gap-4 py-1"><span>🇯🇵 Japan time</span><span class="font-bold tabular-nums">{{ fmtMoment(closeAt(ipo), JST) }}</span></div>
    </div>
  </article>
</template>
