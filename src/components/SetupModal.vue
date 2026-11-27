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
    class="m-auto max-h-[90vh] w-[calc(100%-2rem)] max-w-md overflow-y-auto border border-ink bg-paper p-0 text-ink backdrop:bg-ink/60"
    aria-labelledby="setup-title"
    @close="emit('update:modelValue', false)"
    @click="onBackdrop"
  >
    <div class="p-5">
      <div class="flex items-start justify-between gap-3">
        <div>
          <h2 id="setup-title" class="font-display text-xl font-bold">Phone alerts setup</h2>
          <p class="mt-0.5 text-xs text-ink-soft">About 30 seconds, one time.</p>
        </div>
        <button type="button" class="border border-ink px-3 py-1.5 text-sm active:bg-paper-deep" aria-label="Close" @click="emit('update:modelValue', false)">✕</button>
      </div>

      <ol class="mt-5 space-y-6 text-sm">
        <li>
          <p class="font-bold">1. Install the free ntfy app</p>
          <div class="mt-2 flex flex-wrap gap-2">
            <a class="border border-ink px-3 py-2 active:bg-paper-deep" href="https://apps.apple.com/app/ntfy/id1625396347" target="_blank" rel="noopener noreferrer">iPhone: App Store ↗</a>
            <a class="border border-ink px-3 py-2 active:bg-paper-deep" href="https://play.google.com/store/apps/details?id=io.heckel.ntfy" target="_blank" rel="noopener noreferrer">Android: Google Play ↗</a>
          </div>
        </li>

        <li>
          <p class="font-bold">2. Enter your private topic</p>
          <p class="mt-1 text-ink-soft">
            The same value as your GitHub secret <code class="bg-paper-deep px-1">NTFY_TOPIC</code>.
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
                class="min-w-0 flex-1 border border-ink bg-paper px-3 py-2.5 text-base placeholder:text-ink-soft/60"
              />
              <button type="submit" class="border border-ink bg-brand px-4 py-2.5 font-bold active:bg-brand-deep">Save</button>
            </form>
            <p v-if="draftError" class="mt-2 text-brand-deep font-bold" role="alert">{{ draftError }}</p>
          </template>

          <template v-else>
            <div class="mt-3 flex items-center justify-between gap-2 border border-ink px-3 py-2.5">
              <code class="min-w-0 break-all text-base">{{ reveal ? topic : masked }}</code>
              <button type="button" class="shrink-0 underline underline-offset-2" @click="reveal = !reveal">{{ reveal ? 'Hide' : 'Show' }}</button>
            </div>
            <div class="mt-2 flex flex-wrap gap-2">
              <button type="button" class="border border-ink px-3 py-2 font-bold active:bg-paper-deep" @click="copy('url')">
                {{ copied === 'url' ? 'Copied ✓' : 'Copy topic URL' }}
              </button>
              <button type="button" class="border border-ink px-3 py-2 font-bold active:bg-paper-deep" @click="copy('name')">
                {{ copied === 'name' ? 'Copied ✓' : 'Copy topic name' }}
              </button>
              <button type="button" class="px-3 py-2 text-ink-soft underline underline-offset-2" @click="onRemove">Remove</button>
            </div>
            <p class="mt-2 text-xs text-ink-soft">Treat this like a password: anyone who has it can read or fake your alerts.</p>
          </template>
        </li>

        <li :class="configured ? '' : 'opacity-50'">
          <p class="font-bold">3. Subscribe in the ntfy app</p>
          <ol class="mt-1 list-decimal space-y-0.5 pl-5 text-ink">
            <li>Open ntfy and tap <strong>+</strong> (Subscribe to topic).</li>
            <li>Paste the <strong>topic name</strong> (use the copy button above).</li>
            <li>Leave the server as <strong>ntfy.sh</strong>, tap <strong>Subscribe</strong>, and allow notifications.</li>
          </ol>
        </li>

        <li :class="configured ? '' : 'opacity-50'">
          <p class="font-bold">4. Check it works</p>
          <button
            type="button"
            class="mt-2 border border-ink bg-brand px-4 py-2.5 font-bold active:bg-brand-deep disabled:opacity-50"
            :disabled="!configured || test.state === 'sending'"
            @click="onTest"
          >Send test notification</button>
          <p v-if="test.msg" class="mt-2" :class="test.state === 'error' ? 'text-brand-deep font-bold' : test.state === 'ok' ? 'text-ink font-bold' : 'text-ink-soft'" role="status">{{ test.msg }}</p>
        </li>

        <li>
          <p class="font-bold">5. Add this app to your home screen</p>
          <p v-if="standalone" class="mt-1 text-ink font-bold">Already installed ✓</p>
          <template v-else-if="canPrompt">
            <button type="button" class="mt-2 border border-ink px-4 py-2.5 font-bold active:bg-paper-deep" @click="install">Install app</button>
          </template>
          <p v-else-if="ios" class="mt-1 text-ink">
            In <strong>Safari</strong>, tap the <strong>Share</strong> button, then <strong>Add to Home Screen</strong>.
          </p>
          <p v-else class="mt-1 text-ink">
            In your browser menu (⋮), choose <strong>Install app</strong> or <strong>Add to Home screen</strong>.
          </p>
        </li>
      </ol>
    </div>
  </dialog>
</template>
