import { ref } from 'vue'

export const isNavigationPending = ref(true)

export function setNavigationPending(value) {
  isNavigationPending.value = Boolean(value)
}
