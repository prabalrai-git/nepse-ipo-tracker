<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useNtfyTopic } from '../composables/useNtfyTopic'
import { useInstall } from '../composables/useInstall'
import { copyText } from '../utils/time'

const props = defineProps<{ modelValue: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const { topic, configured, topicUrl, save, clear, sendTest } = useNtfyTopic()
const { standalone, ios, canPrompt, install } = useInstall()

const dialog = ref<HTMLDialogElement | null>(null)
const draft = ref('')
const draftError = ref<string | null>(null)
const reveal = ref(false)
const copied = ref<'' | 'name' | 'url'>('')
const test = ref<{ state: 'idle' | 'sending' | 'ok' | 'error'; msg: string }>({ state: 'idle', msg: '' })

watch(() => props.modelValue, (open) => {
  const d = dialog.value
  if (!d) return
  if (open && !d.open) d.showModal()
  if (!open && d.open) d.close()
})

// "••••" version of the topic so shoulder-surfing / screenshots don't leak it.
const masked = computed(() => (topic.value ? `${topic.value.slice(0, 8)}${'•'.repeat(12)}` : ''))

function onSave(): void {
  draftError.value = save(draft.value)
  if (!draftError.value) { draft.value = ''; reveal.value = false }
}
function onRemove(): void {
  clear(); test.value = { state: 'idle', msg: '' }
}
async function copy(what: 'name' | 'url'): Promise<void> {
  const ok = await copyText(what === 'name' ? topic.value : topicUrl.value)
  copied.value = ok ? what : ''
  window.setTimeout(() => { copied.value = '' }, 2000)
}
async function onTest(): Promise<void> {
  test.value = { state: 'sending', msg: 'Sending…' }
  try {
    await sendTest()
    test.value = { state: 'ok', msg: 'Sent. Your phone should buzz within a few seconds. If not, re-check step 3.' }
  } catch (e) {
    test.value = { state: 'error', msg: e instanceof Error ? e.message : 'Could not send. Check your connection.' }
  }
}
function onBackdrop(e: MouseEvent): void {
  if (e.target === dialog.value) emit('update:modelValue', false)
}
</script>

<template>
  <dialog
    ref="dialog"
    class="m-auto max-h-[90vh] w-[calc(100%-2rem)] max-w-md overflow-y-auto rounded-2xl bg-slate-900 p-0 text-slate-100 ring-1 ring-slate-600 backdrop:bg-black/70"
    aria-labelledby="setup-title"
    @close="emit('update:modelValue', false)"
    @click="onBackdrop"
  >
    <div class="p-5">
      <div class="flex items-start justify-between gap-3">
        <div>
          <h2 id="setup-title" class="text-lg font-bold text-white">Phone alerts setup</h2>
          <p class="mt-0.5 text-sm text-slate-400">About 30 seconds, one time.</p>
        </div>
        <button type="button" class="rounded-full bg-slate-800 px-3 py-1.5 text-sm ring-1 ring-slate-600" aria-label="Close" @click="emit('update:modelValue', false)">✕</button>
      </div>

      <ol class="mt-5 space-y-6 text-sm">
        <li>
          <p class="font-semibold text-white">1. Install the free ntfy app</p>
          <div class="mt-2 flex flex-wrap gap-2">
            <a class="rounded-lg bg-slate-800 px-3 py-2 ring-1 ring-slate-600" href="https://apps.apple.com/app/ntfy/id1625396347" target="_blank" rel="noopener noreferrer">iPhone: App Store ↗</a>
            <a class="rounded-lg bg-slate-800 px-3 py-2 ring-1 ring-slate-600" href="https://play.google.com/store/apps/details?id=io.heckel.ntfy" target="_blank" rel="noopener noreferrer">Android: Google Play ↗</a>
          </div>
        </li>

        <li>
          <p class="font-semibold text-white">2. Enter your private topic</p>
          <p class="mt-1 text-slate-400">
            The same value as your GitHub secret <code class="rounded bg-slate-800 px-1">NTFY_TOPIC</code>.
            It's saved only on this device and is never sent anywhere except ntfy.sh.
          </p>

          <template v-if="!configured">
            <form class="mt-3 flex gap-2" @submit.prevent="onSave">
              <input
                v-model="draft"
                type="text"
                autocomplete="off"
                autocapitalize="off"
                spellcheck="false"
                placeholder="nepse-ipo-…"
                aria-label="ntfy topic"
                class="min-w-0 flex-1 rounded-lg bg-slate-800 px-3 py-2.5 text-base text-white ring-1 ring-slate-600 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-sky-400"
              />
              <button type="submit" class="rounded-lg bg-sky-400 px-4 py-2.5 font-semibold text-sky-950 active:bg-sky-300">Save</button>
            </form>
            <p v-if="draftError" class="mt-2 text-rose-300" role="alert">{{ draftError }}</p>
          </template>

          <template v-else>
            <div class="mt-3 flex items-center justify-between gap-2 rounded-lg bg-slate-800 px-3 py-2.5 ring-1 ring-slate-600">
              <code class="min-w-0 break-all text-base">{{ reveal ? topic : masked }}</code>
              <button type="button" class="shrink-0 text-sky-300 underline underline-offset-2" @click="reveal = !reveal">{{ reveal ? 'Hide' : 'Show' }}</button>
            </div>
            <div class="mt-2 flex flex-wrap gap-2">
              <button type="button" class="rounded-lg bg-slate-800 px-3 py-2 font-medium ring-1 ring-slate-600 active:bg-slate-700" @click="copy('url')">
                {{ copied === 'url' ? 'Copied ✓' : 'Copy topic URL' }}
              </button>
              <button type="button" class="rounded-lg bg-slate-800 px-3 py-2 font-medium ring-1 ring-slate-600 active:bg-slate-700" @click="copy('name')">
                {{ copied === 'name' ? 'Copied ✓' : 'Copy topic name' }}
              </button>
              <button type="button" class="rounded-lg px-3 py-2 text-slate-400 underline underline-offset-2" @click="onRemove">Remove</button>
            </div>
            <p class="mt-2 text-xs text-amber-200/90">Treat this like a password: anyone who has it can read or fake your alerts.</p>
          </template>
        </li>

        <li :class="configured ? '' : 'opacity-50'">
          <p class="font-semibold text-white">3. Subscribe in the ntfy app</p>
          <ol class="mt-1 list-decimal space-y-0.5 pl-5 text-slate-300">
            <li>Open ntfy and tap <strong>+</strong> (Subscribe to topic).</li>
            <li>Paste the <strong>topic name</strong> (use the copy button above).</li>
            <li>Leave the server as <strong>ntfy.sh</strong>, tap <strong>Subscribe</strong>, and allow notifications.</li>
          </ol>
        </li>

        <li :class="configured ? '' : 'opacity-50'">
          <p class="font-semibold text-white">4. Check it works</p>
          <button
            type="button"
            class="mt-2 rounded-lg bg-emerald-500 px-4 py-2.5 font-semibold text-emerald-950 active:bg-emerald-400 disabled:opacity-50"
            :disabled="!configured || test.state === 'sending'"
            @click="onTest"
          >Send test notification</button>
          <p v-if="test.msg" class="mt-2" :class="test.state === 'error' ? 'text-rose-300' : test.state === 'ok' ? 'text-emerald-300' : 'text-slate-400'" role="status">{{ test.msg }}</p>
        </li>

        <li>
          <p class="font-semibold text-white">5. Add this app to your home screen</p>
          <p v-if="standalone" class="mt-1 text-emerald-300">Already installed ✓</p>
          <template v-else-if="canPrompt">
            <button type="button" class="mt-2 rounded-lg bg-slate-800 px-4 py-2.5 font-semibold ring-1 ring-slate-600 active:bg-slate-700" @click="install">Install app</button>
          </template>
          <p v-else-if="ios" class="mt-1 text-slate-300">
            In <strong>Safari</strong>, tap the <strong>Share</strong> button, then <strong>Add to Home Screen</strong>.
          </p>
          <p v-else class="mt-1 text-slate-300">
            In your browser menu (⋮), choose <strong>Install app</strong> or <strong>Add to Home screen</strong>.
          </p>
        </li>
      </ol>
    </div>
  </dialog>
</template>
