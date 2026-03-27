import { createApp } from 'vue'
import { Capacitor } from '@capacitor/core'
import router from '@/router/index.js'
import App from './App.vue'
import './assets/css/main.css'

import { loadTheme, applyTheme } from '@/config/theme.js'
import { clearDashboardSession, initializeDashboardSession } from '@/composables/useDashboardSession.js'
import { installAppErrorHandling, scheduleNonCriticalStartupTask } from '@/services/appBootstrap.js'
import { startDocumentBrandingSync } from '@/services/documentBranding.js'
import { getStoredAuthMeta, hasPrivilegedPendingFace } from '@/services/localAuth.js'
import { registerAuraServiceWorker, startMobileFullscreenSync } from '@/services/mobileFullscreen.js'
import { startPwaInstallSync } from '@/services/pwaInstall.js'
import { SESSION_EXPIRED_EVENT } from '@/services/sessionExpiry.js'

function resolveBootstrapThemeSettings() {
  const authMeta = getStoredAuthMeta()
  if (!authMeta) return null

  const hasBrandingSeed = (
    authMeta.schoolId != null
    || authMeta.schoolName
    || authMeta.logoUrl
    || authMeta.primaryColor
    || authMeta.secondaryColor
    || authMeta.accentColor
  )

  if (!hasBrandingSeed) return null

  return {
    school_id: authMeta.schoolId ?? null,
    school_name: authMeta.schoolName ?? null,
    school_code: authMeta.schoolCode ?? null,
    logo_url: authMeta.logoUrl ?? null,
    primary_color: authMeta.primaryColor ?? null,
    secondary_color: authMeta.secondaryColor ?? null,
    accent_color: authMeta.accentColor ?? null,
  }
}

applyTheme(loadTheme(resolveBootstrapThemeSettings()))

const app = createApp(App)
app.use(router)
installAppErrorHandling(app, router)
app.mount('#app')

scheduleNonCriticalStartupTask(() => startDocumentBrandingSync(router))
scheduleNonCriticalStartupTask(() => startPwaInstallSync())
scheduleNonCriticalStartupTask(() => registerAuraServiceWorker())
scheduleNonCriticalStartupTask(() => startMobileFullscreenSync())

// Session expiry listener
if (typeof window !== 'undefined') {
  window.addEventListener(SESSION_EXPIRED_EVENT, () => {
    clearDashboardSession()

    if (router.currentRoute.value?.name !== 'Login') {
      router.replace({ name: 'Login' }).catch(() => null)
    }
  })
}

// Pre-initialize session if token exists
if (localStorage.getItem('aura_token') && !hasPrivilegedPendingFace()) {
  scheduleNonCriticalStartupTask(() => initializeDashboardSession().catch(() => null), {
    timeoutMs: 500,
  })
}

// --- Capacitor Native Initialization ---
if (Capacitor.isNativePlatform()) {
  // Status bar styling
  import('@capacitor/status-bar').then(({ StatusBar, Style }) => {
    StatusBar.setStyle({ style: Style.Light }).catch(() => null)
    StatusBar.setBackgroundColor({ color: '#EBEBEB' }).catch(() => null)
  }).catch(() => null)

  // Splash screen (auto-hides via config, but ensure it hides)
  import('@capacitor/splash-screen').then(({ SplashScreen }) => {
    setTimeout(() => {
      SplashScreen.hide().catch(() => null)
    }, 2000)
  }).catch(() => null)

  // Android back button handler
  import('@capacitor/app').then(({ App: CapApp }) => {
    CapApp.addListener('backButton', ({ canGoBack }) => {
      if (canGoBack) {
        router.back()
      } else {
        // On root screens, minimize app instead of exiting
        CapApp.minimizeApp().catch(() => null)
      }
    })

    // Re-sync session when app returns to foreground
    CapApp.addListener('appStateChange', ({ isActive }) => {
      if (isActive && localStorage.getItem('aura_token')) {
        initializeDashboardSession().catch(() => null)
      }
    })
  }).catch(() => null)

  // Keyboard behavior — scroll focused input into view
  import('@capacitor/keyboard').then(({ Keyboard }) => {
    Keyboard.setAccessoryBarVisible({ isVisible: true }).catch(() => null)
    Keyboard.setScroll({ isDisabled: false }).catch(() => null)

    // When keyboard shows, scroll the focused input into view
    Keyboard.addListener('keyboardWillShow', () => {
      setTimeout(() => {
        const activeEl = document.activeElement
        if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA')) {
          activeEl.scrollIntoView({ behavior: 'smooth', block: 'center' })
        }
      }, 100)
    })
  }).catch(() => null)
}

// Cross-tab session sync (for web — logout in one tab logs out all)
if (typeof window !== 'undefined' && !Capacitor.isNativePlatform()) {
  window.addEventListener('storage', (event) => {
    if (event.key === 'aura_token' && !event.newValue) {
      clearDashboardSession()
      if (router.currentRoute.value?.name !== 'Login') {
        router.replace({ name: 'Login' }).catch(() => null)
      }
    }
  })
}
