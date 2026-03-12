<template>
  <div class="attendance-page">
    <header class="attendance-header">
      <button class="icon-btn" aria-label="Back" @click="goBack">
        <ArrowLeft :size="18" />
      </button>
    </header>

    <section class="attendance-empty">
      <h1 class="empty-title">Under Development</h1>
      <p class="empty-subtitle">Attendance flow will appear here.</p>
    </section>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'

const router = useRouter()

function goBack() {
  router.back()
}
</script>

<style scoped>
.attendance-page {
  min-height: 100vh;
  padding: 28px 24px 110px;
  background: var(--color-bg);
}

.attendance-header {
  display: flex;
  align-items: center;
  margin-bottom: 16px;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 50%;
  background: #ffffff;
  color: var(--color-text-always-dark);
  border: none;
  cursor: pointer;
  box-shadow: 0 6px 18px rgba(0,0,0,0.08);
  transition: transform 0.15s ease;
}

.icon-btn:active {
  transform: scale(0.95);
}

.attendance-empty {
  display: flex;
  flex-direction: column;
  gap: 8px;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding-top: 80px;
}

.empty-title {
  font-size: 20px;
  font-weight: 800;
  color: var(--color-text-always-dark);
  letter-spacing: -0.4px;
  margin: 0;
}

.empty-subtitle {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-text-muted);
  margin: 0;
}

@media (min-width: 768px) {
  .attendance-page {
    padding: 28px 36px 40px;
  }
}
</style>
