<script setup lang="ts">
import type { TabKey } from '../types'

defineProps<{
  modelValue: TabKey
  counts: Record<TabKey, number>
}>()
defineEmits<{ 'update:modelValue': [TabKey] }>()

const tabs: { key: TabKey; label: string }[] = [
  { key: 'eligible', label: 'All Eligible' },
  { key: 'foreign', label: 'Foreign 10%' },
  { key: 'general', label: 'General Public' },
  { key: 'upcoming', label: 'Upcoming' },
]
</script>

<template>
  <div class="no-scrollbar overflow-x-auto border-b border-ink px-4 py-3" role="tablist" aria-label="Filter issues">
    <div class="flex w-max gap-2">
      <button
        v-for="t in tabs"
        :key="t.key"
        role="tab"
        type="button"
        :aria-selected="modelValue === t.key"
        class="flex items-center gap-2 whitespace-nowrap border border-ink px-3 py-1.5 text-xs font-bold"
        :class="modelValue === t.key ? 'bg-brand text-ink' : 'bg-paper text-ink active:bg-paper-deep'"
        @click="$emit('update:modelValue', t.key)"
      >
        {{ t.label }}
        <span class="tabular-nums" :class="modelValue === t.key ? 'text-ink' : 'text-ink-soft'">{{ counts[t.key] }}</span>
      </button>
    </div>
  </div>
</template>
