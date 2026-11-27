<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRegisterSW } from 'virtual:pwa-register/vue'

const online = ref(navigator.onLine)
const updateOnline = () => { online.value = navigator.onLine }

const readyToast = ref(false)
const { needRefresh, offlineReady, updateServiceWorker } = useRegisterSW({
  onRegisteredSW(_url, registration) {
    // A phone app can stay open for days: look for a new version every hour.
    if (registration) window.setInterval(() => { void registration.update() }, 60 * 60 * 1000)
  },
})

onMounted(() => {
  window.addEventListener('online', updateOnline)
  window.addEventListener('offline', updateOnline)
})
onBeforeUnmount(() => {
  window.removeEventListener('online', updateOnline)
  window.removeEventListener('offline', updateOnline)
})

watch(offlineReady, (v) => {
  if (!v) return
  readyToast.value = true
  window.setTimeout(() => { readyToast.value = false; offlineReady.value = false }, 4000)
})
</script>

<template>
  <div class="pointer-events-none fixed inset-x-0 bottom-0 z-30 flex flex-col items-center gap-2 px-4 pb-[max(1rem,env(safe-area-inset-bottom))]">
    <div v-if="needRefresh" class="pointer-events-auto flex w-full max-w-xl items-center justify-between gap-3 border border-ink bg-sun px-4 py-3 text-sm font-bold" role="status">
      <span>A new version is available.</span>
      <button type="button" class="border border-ink bg-ink px-3 py-1.5 font-bold text-paper" @click="updateServiceWorker(true)">Reload</button>
    </div>
    <div v-else-if="readyToast" class="pointer-events-auto border border-ink bg-brand px-4 py-2 text-sm font-bold" role="status">
      Ready to work offline
    </div>
    <div v-if="!online" class="pointer-events-auto border border-ink bg-ink px-4 py-2 text-sm font-bold text-paper" role="status">
      You're offline. Showing saved data.
    </div>
  </div>
</template>
