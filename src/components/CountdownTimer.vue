<script setup lang="ts">
import { computed } from 'vue'
import { useNow } from '../composables/useNow'
import { splitDuration } from '../utils/time'

const props = defineProps<{ target: number; mode: 'close' | 'open' }>()
const now = useNow()

const remaining = computed(() => props.target - now.value)
const parts = computed(() => splitDuration(remaining.value))
// Closing within 24h is the moment people miss, so it gets the urgent colour.
const urgent = computed(() => props.mode === 'close' && remaining.value < 24 * 3600 * 1000)
const units = computed(() => [
  { k: 'd', label: 'days', v: parts.value.d },
  { k: 'h', label: 'hrs', v: parts.value.h },
  { k: 'm', label: 'min', v: parts.value.m },
  { k: 's', label: 'sec', v: parts.value.s },
])
</script>

<template>
  <div>
    <p class="mb-1 text-xs font-medium uppercase tracking-wide" :class="urgent ? 'text-rose-300' : 'text-slate-400'">
      {{ mode === 'close' ? (urgent ? 'Closing soon' : 'Closes in') : 'Opens in' }}
    </p>
    <div class="grid grid-cols-4 gap-2" role="timer" :aria-label="`${parts.d} days ${parts.h} hours ${parts.m} minutes remaining`">
      <div
        v-for="u in units"
        :key="u.k"
        class="rounded-lg py-2 text-center"
        :class="urgent ? 'bg-rose-500/15 ring-1 ring-rose-400/40' : 'bg-slate-800 ring-1 ring-slate-700'"
      >
        <div class="text-xl font-bold tabular-nums leading-none" :class="urgent ? 'text-rose-100' : 'text-white'">
          {{ String(u.v).padStart(2, '0') }}
        </div>
        <div class="mt-1 text-[10px] uppercase tracking-wide text-slate-400">{{ u.label }}</div>
      </div>
    </div>
  </div>
</template>
