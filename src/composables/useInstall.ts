import { computed, ref } from 'vue'

interface BeforeInstallPromptEvent extends Event {
  prompt(): Promise<void>
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }>
}

const deferred = ref<BeforeInstallPromptEvent | null>(null)
const installed = ref(false)
let wired = false

function wire(): void {
  if (wired) return
  wired = true
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault() // keep it so our own button can trigger the browser's install sheet
    deferred.value = e as BeforeInstallPromptEvent
  })
  window.addEventListener('appinstalled', () => { installed.value = true; deferred.value = null })
}

const isStandalone = (): boolean =>
  window.matchMedia('(display-mode: standalone)').matches ||
  (navigator as Navigator & { standalone?: boolean }).standalone === true

// iPadOS 13+ reports itself as a Mac, so also check for touch support.
const isIos = (): boolean =>
  /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

export function useInstall() {
  wire()
  return {
    standalone: computed(() => installed.value || isStandalone()),
    ios: isIos(),
    canPrompt: computed(() => deferred.value !== null),
    async install(): Promise<void> {
      const ev = deferred.value
      if (!ev) return
      await ev.prompt()
      await ev.userChoice
      deferred.value = null
    },
  }
}
