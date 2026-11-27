<script setup lang="ts">
import type { TabKey } from '../types'

defineProps<{
  modelValue: TabKey
  counts: Record<TabKey, number>
}>()
defineEmits<{ 'update:modelValue': [TabKey] }>()

const tabs: { key: TabKey; label: string }[] = [
  { key: 'eligible', label: 'All Eligible' },
  { key: 'foreign', label: '🇯🇵 Foreign Quota (10%)' },
  { key: 'general', label: '🇳🇵 General Public' },
  { key: 'upcoming', label: 'Upcoming' },
]
</script>

<template>
  <div class="-mx-4 overflow-x-auto px-4 pb-1" role="tablist" aria-label="Filter issues">
    <div class="flex w-max gap-2">
      <button
        v-for="t in tabs"
        :key="t.key"
        role="tab"
        type="button"
        :aria-selected="modelValue === t.key"
        class="flex items-center gap-2 whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium ring-1 transition-colors"
        :class="modelValue === t.key
          ? 'bg-white text-slate-900 ring-white'
          : 'bg-slate-800 text-slate-300 ring-slate-700 active:bg-slate-700'"
        @click="$emit('update:modelValue', t.key)"
      >
        {{ t.label }}
        <span
          class="rounded-full px-2 py-0.5 text-xs font-semibold tabular-nums"
          :class="modelValue === t.key ? 'bg-slate-900 text-white' : 'bg-slate-700 text-slate-200'"
        >{{ counts[t.key] }}</span>
      </button>
    </div>
  </div>
</template>
