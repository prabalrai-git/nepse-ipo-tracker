import { ref, readonly } from 'vue'

// One shared 1-second clock for every countdown on the page.
const now = ref(Date.now())
let timer: number | undefined

export function useNow() {
  if (timer === undefined) {
    timer = window.setInterval(() => { now.value = Date.now() }, 1000)
    // Browsers freeze timers in background tabs; resync the moment the page is visible again.
    document.addEventListener('visibilitychange', () => { now.value = Date.now() })
  }
  return readonly(now)
}
