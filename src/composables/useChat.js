/**
 * useChat — AI Chat Composable
 *
 * Owns all chat state and message logic.
 * Backend integration: replace the simulateAiResponse() function
 * with a real API call (e.g. POST /api/chat/message) when ready.
 *
 * Shared as a singleton (module-level refs) so SideNav mini-chat
 * and the floating AuraChatWindow stay perfectly in sync.
 */

import { ref, nextTick } from 'vue'

// ─── Shared singleton state ───────────────────────────────────────────────────
const messages   = ref([
  { id: 1, sender: 'ai', text: 'Hi! I am Aura AI. How can I help you today?' }
])
const inputText  = ref('')
const isTyping   = ref(false)
const isMiniOpen = ref(false)
const isFullOpen = ref(false)

// Holds a ref to the messages scroll container (set by the active chat view)
const scrollEl   = ref(null)

// ─── Helpers ──────────────────────────────────────────────────────────────────
function scrollToBottom() {
  nextTick(() => {
    if (scrollEl.value) {
      scrollEl.value.scrollTop = scrollEl.value.scrollHeight
    }
  })
}

// ─── Backend stub — replace this function with your real API call ─────────────
async function simulateAiResponse(userMessage) {
  /**
   * TODO: Replace with:
   * const { data } = await api.post('/chat/message', { message: userMessage })
   * return data.reply
   */
  await new Promise(resolve => setTimeout(resolve, 1400))
  return "I'm ready and waiting for my backend brain! Once we connect the API, I'll answer your questions about grades, schedule, and more."
}

// ─── Public actions ───────────────────────────────────────────────────────────
async function sendMessage() {
  const text = inputText.value.trim()
  if (!text || isTyping.value) return

  messages.value.push({ id: Date.now(), sender: 'user', text })
  inputText.value = ''
  isTyping.value  = true
  scrollToBottom()

  try {
    const reply = await simulateAiResponse(text)
    messages.value.push({ id: Date.now() + 1, sender: 'ai', text: reply })
  } catch {
    messages.value.push({
      id: Date.now() + 1,
      sender: 'ai',
      text: 'Something went wrong. Please try again.'
    })
  } finally {
    isTyping.value = false
    scrollToBottom()
  }
}

function openMini()  { isMiniOpen.value = true  }
function closeMini() { isMiniOpen.value = false }

function openFull()  {
  isFullOpen.value = true
  // Mini stays open in background; full window takes focus
}

function closeFull() { isFullOpen.value = false }

function openPill()  {
  // Called when user clicks the collapsed lime pill
  isMiniOpen.value = true
}

function expandToFull() {
  // Called from mini chat's Maximize button
  isMiniOpen.value = false   // hide the mini pill — full window takes over
  isFullOpen.value = true
}

function minimizeToMini() {
  // Called from full chat's Minimize button
  isFullOpen.value = false
  isMiniOpen.value = true
}

function closeAll() {
  isFullOpen.value = false
  isMiniOpen.value = false
}

// ─── Composable export ────────────────────────────────────────────────────────
export function useChat() {
  return {
    messages,
    inputText,
    isTyping,
    isMiniOpen,
    isFullOpen,
    scrollEl,
    sendMessage,
    openMini,
    closeMini,
    openFull,
    closeFull,
    openPill,
    expandToFull,
    minimizeToMini,
    closeAll,
  }
}
