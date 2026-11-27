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
    <p class="mb-1.5 text-[11px] font-bold uppercase tracking-widest" :class="urgent ? 'text-brand-deep' : 'text-ink-soft'">
      {{ mode === 'close' ? (urgent ? 'Closing soon' : 'Closes in') : 'Opens in' }}
    </p>
    <div class="grid grid-cols-4 border border-ink" role="timer" :aria-label="`${parts.d} days ${parts.h} hours ${parts.m} minutes remaining`">
      <div
        v-for="(u, i) in units"
        :key="u.k"
        class="py-2 text-center"
        :class="[urgent ? 'bg-brand' : 'bg-paper', i > 0 ? 'border-l border-ink' : '']"
      >
        <div class="text-xl font-bold tabular-nums leading-none">{{ String(u.v).padStart(2, '0') }}</div>
        <div class="mt-1 text-[10px] uppercase tracking-widest" :class="urgent ? 'text-ink' : 'text-ink-soft'">{{ u.label }}</div>
      </div>
    </div>
  </div>
</template>
