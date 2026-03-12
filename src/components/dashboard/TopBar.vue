<template>
  <header class="flex items-center justify-between px-0 pt-5 pb-2 md:px-0 md:pt-6">
    <!-- Profile Card (Expands on Hover or Tap) -->
    <button 
      @click="isProfileExpanded = !isProfileExpanded"
      class="profile-pill flex items-center rounded-full pl-3 pr-4 py-2 transition-all duration-300 cursor-pointer"
      :class="{ 'is-expanded': isProfileExpanded }"
      style="background: var(--color-profile-bg);"
    >
      <div class="flex items-center gap-3">
        <!-- Avatar -->
        <div class="relative flex-shrink-0">
          <img
            v-if="avatarUrl"
            :src="avatarUrl"
            :alt="displayName"
            class="w-10 h-10 rounded-full object-cover"
          />
          <div
            v-else
            class="avatar-fallback w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white transition-colors duration-300"
            style="background: linear-gradient(135deg, #0A0A0A 0%, #333 100%);"
          >
            {{ initials }}
          </div>
          <!-- Online dot -->
          <span
            class="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full border-2 border-white transition-colors duration-300"
            style="background: var(--color-primary);"
          />
        </div>

        <!-- Name & greeting -->
        <div class="leading-none text-left">
          <p class="text-[10px] font-medium transition-colors duration-300" style="color: var(--color-text-muted);">Welcome Back</p>
          <p class="text-[13px] font-bold transition-colors duration-300" style="color: var(--color-text-always-dark);">{{ displayName }}</p>
        </div>
      </div>
      
      <!-- Hidden Sign Out section (Reveals on Hover or active state) -->
      <div 
        @click.stop="handleLogout"
        class="signout-pill flex items-center overflow-hidden max-w-0 opacity-0 transition-all duration-300 ease-in-out whitespace-nowrap hover:opacity-75 cursor-pointer"
      >
        <LogOut :size="18" color="#FF0B0B" :stroke-width="2.5" class="mr-2" />
        <span class="text-[14px] font-medium" style="color: #FF0B0B; letter-spacing: -0.02em;">Sign Out</span>
      </div>
    </button>

    <!-- Right side actions -->
    <div class="flex items-center gap-2">
      <!-- Notifications & Theme Toggle Pill -->
      <div 
        class="flex items-center gap-1 transition-colors duration-300"
        style="border-radius: 28px; padding: 6px 10px; background: var(--color-nav-pill-bg);"
      >
        <!-- Bell notification -->
        <button
          @click="$emit('toggle-notifications')"
          class="relative flex items-center justify-center w-9 h-9 rounded-full transition-all duration-150 hover:bg-black/5 active:scale-95"
          aria-label="Notifications"
        >
          <Bell :size="18" color="var(--color-text-always-dark)" :stroke-width="2" />
          <!-- unread badge -->
          <span
            v-if="unreadCount > 0"
            class="absolute top-1.5 right-1.5 w-2 h-2 rounded-full"
            style="background: var(--color-primary);"
          />
        </button>

        <!-- Spacer/Divider -->
        <div class="w-[1px] h-5 bg-gray-200 mx-0.5"></div>

        <!-- Dark Mode Toggle -->
        <button
          @click="toggleDarkMode"
          class="relative flex items-center justify-center w-9 h-9 rounded-full transition-all duration-150 hover:bg-gray-100 active:scale-95"
          aria-label="Toggle Dark Mode"
        >
          <Moon 
            :size="18" 
            :color="isDarkMode ? 'var(--color-primary)' : 'var(--color-text-primary)'" 
            :stroke-width="2" 
          />
        </button>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { Bell, Moon, LogOut } from 'lucide-vue-next'
import { isDarkMode, toggleDarkMode } from '@/config/theme.js'

const props = defineProps({
  user: {
    type: Object,
    default: null,
  },
  unreadCount: {
    type: Number,
    default: 0,
  },
})

defineEmits(['toggle-notifications'])

const isProfileExpanded = ref(false)
const router = useRouter()

function handleLogout() {
  // Clear the actual token used by the router's beforeEach guard
  localStorage.removeItem('aura_token')
  localStorage.removeItem('aura_user_roles')
  
  // Navigate back to the Login view
  router.push({ name: 'Login' })
}

const displayName = computed(() => {
  if (!props.user) return 'User'
  const names = [props.user.first_name, props.user.middle_name, props.user.last_name]
    .filter(Boolean)
  if (names.length) return names.join(' ')
  return props.user.email?.split('@')[0] || 'User'
})

const initials = computed(() => {
  const name = displayName.value
  const parts = name.split(' ').filter(Boolean)
  if (parts.length >= 2) return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase()
  return name.slice(0, 2).toUpperCase()
})

const avatarUrl = computed(() => {
  return (
    props.user?.student_profile?.photo_url ||
    props.user?.student_profile?.avatar_url ||
    props.user?.avatar_url ||
    null
  )
})
</script>

<style scoped>
.profile-pill:hover .signout-pill,
.profile-pill.is-expanded .signout-pill {
  max-width: 150px;
  opacity: 1;
  margin-left: 24px;
  margin-right: 4px;
}
</style>
