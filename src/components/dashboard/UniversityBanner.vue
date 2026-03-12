<template>
  <!--
    University Banner Card
    The school logo is clipped by the card's overflow-hidden + border-radius,
    creating the "half-masked into the corner" effect from the designer reference.
    Backend-ready: schoolName + schoolLogo come from /school-settings/me response.
  -->
  <div
    class="relative rounded-3xl overflow-hidden w-full"
    style="background: var(--color-primary); min-height: 200px;"
  >
    <!-- Text content -->
    <div class="relative z-10 p-5 flex flex-col justify-between" style="min-height: 200px;">
      <div>
        <p class="text-[13px] font-semibold opacity-80" style="color: var(--color-banner-text);">Welcome to</p>
        <h2
          class="text-[28px] font-extrabold leading-tight mt-0.5"
          style="color: var(--color-banner-text); max-width: 55%;"
        >
          {{ schoolName }}
        </h2>
      </div>

      <!-- Announcement Button -->
      <button
        @click="$emit('announcement-click')"
        class="mt-4 flex items-center gap-3 rounded-full pl-3 pr-5 py-2.5 self-start transition-all duration-150 hover:scale-105 active:scale-95 group"
        style="background: var(--color-text-always-dark);"
      >
        <span class="flex items-center justify-center w-7 h-7 rounded-full bg-white/10 group-hover:bg-white/20 transition-colors">
          <ArrowRight :size="14" color="var(--color-surface)" :stroke-width="2.5" />
        </span>
        <span class="text-[12px] font-semibold" style="color: var(--color-surface);">Latest Announcement</span>
      </button>
    </div>

    <!--
      University Logo — absolutely positioned inside the card.
      right: -20px pushes ~15% of the logo beyond the card's right edge.
      The card's overflow:hidden + border-radius clips it naturally,
      creating the rounded mask effect seen in the designer reference.
      Adjust right offset (--logo-offset) to control how much is clipped.
    -->
    <div
      v-if="!logoFailed"
      class="logo-wrap"
    >
      <img
        :src="schoolLogo"
        :alt="schoolName + ' logo'"
        class="logo-img object-contain drop-shadow-xl opacity-95"
        @error="onLogoError"
      />
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ArrowRight } from 'lucide-vue-next'

defineProps({
  schoolName: {
    type: String,
    default: 'University Name',
  },
  schoolLogo: {
    type: String,
    default: '/logos/university_logo.svg',
  },
})

defineEmits(['announcement-click'])

const logoFailed = ref(false)

function onLogoError(e) {
  logoFailed.value = true
  e.target.style.display = 'none'
}
</script>

<style scoped>
/*
  Logo wrapper — absolute, vertically centred, pushed right so
  the card's overflow:hidden + rounded-3xl clips the right portion.
  Change right value to control how much of the logo is clipped:
    0px   = fully inside, touching the right edge
   -20px  = ~15% clipped  (current — matches designer)
   -40px  = ~30% clipped
*/
.logo-wrap {
  position: absolute;
  right: -20px;
  top: 68%;
  transform: translateY(-50%);
  pointer-events: none;
  z-index: 1;
}

.logo-img {
  width: 140px;
  height: 140px;
}

@media (min-width: 768px) {
  .logo-wrap {
    right: -24px;
  }
  .logo-img {
    width: 165px;
    height: 165px;
  }
}
</style>
