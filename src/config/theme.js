import { ref } from 'vue'
import defaultSchoolLogo from '@/data/jrmsu_icon.png'

/**
 * Global Dark Mode State
 */
export const isDarkMode = ref(false)
export const activeAuraLogo = ref('/logos/aura_logo_black.png')
export const surfaceAuraLogo = ref('/logos/aura_logo_black.png')
let currentActiveTheme = null

function updateDocumentThemeColor(color) {
    if (typeof document === 'undefined') return
    const themeMeta = document.querySelector('meta[name="theme-color"]')
    if (themeMeta) {
        themeMeta.setAttribute('content', color)
    }
}

/**
 * School Theme Configuration
 * School IT can customize: primary accent color, logo, and school name.
 * These would be loaded from /school-settings/me endpoint in production.
 */
export const defaultTheme = {
    // Customizable by School IT
    primaryColor: '#AAFF00',       // Lime green - the accent/brand color
    primaryDark: '#88CC00',        // Slightly darker for hover states
    primaryText: '#0A0A0A',        // Text on primary colored backgrounds
    schoolName: 'University Name',
    schoolSlogan: 'Slogan Goes Here',
    schoolLogo: defaultSchoolLogo,

    // Fixed Aura system colors
    background: '#EBEBEB',
    surfaceColor: '#FFFFFF',
    navColor: '#0A0A0A',
    navActiveColor: '#AAFF00',
    textPrimary: '#0A0A0A',
    textSecondary: '#555555',
    textMuted: '#999999',
}

function normalizeHexColor(hex, fallback = '#0A0A0A') {
    if (typeof hex !== 'string') return fallback

    let next = hex.trim()
    if (!next) return fallback

    if (!next.startsWith('#')) next = `#${next}`
    if (next.length === 4) {
        next = `#${next[1]}${next[1]}${next[2]}${next[2]}${next[3]}${next[3]}`
    }
    if (!/^#[0-9A-Fa-f]{6}$/.test(next)) return fallback
    return next.toUpperCase()
}

function hexToRgb(hex) {
    const normalized = normalizeHexColor(hex)
    return {
        r: parseInt(normalized.slice(1, 3), 16),
        g: parseInt(normalized.slice(3, 5), 16),
        b: parseInt(normalized.slice(5, 7), 16),
    }
}

function rgbToHex({ r, g, b }) {
    const toHex = (value) => {
        const clamped = Math.max(0, Math.min(255, Math.round(value)))
        return clamped.toString(16).padStart(2, '0')
    }

    return `#${toHex(r)}${toHex(g)}${toHex(b)}`.toUpperCase()
}

function mixHexColors(baseHex, mixHex, baseWeight = 0.5) {
    const safeBaseWeight = Math.max(0, Math.min(1, baseWeight))
    const mixWeight = 1 - safeBaseWeight
    const base = hexToRgb(baseHex)
    const blend = hexToRgb(mixHex)

    return rgbToHex({
        r: (base.r * safeBaseWeight) + (blend.r * mixWeight),
        g: (base.g * safeBaseWeight) + (blend.g * mixWeight),
        b: (base.b * safeBaseWeight) + (blend.b * mixWeight),
    })
}

/**
 * Load theme - in production, fetches from API and merges school settings.
 */
export function loadTheme(schoolSettings = null) {
    if (!schoolSettings) return defaultTheme

    const primaryColor = normalizeHexColor(
        schoolSettings.primary_color ?? defaultTheme.primaryColor,
        defaultTheme.primaryColor
    )
    const primaryDark = normalizeHexColor(
        schoolSettings.primary_color_dark ?? darkenHex(primaryColor, 18),
        defaultTheme.primaryDark
    )
    const primaryText = normalizeHexColor(
        schoolSettings.primary_text ?? getContrastYIQ(primaryColor),
        defaultTheme.primaryText
    )

    return {
        ...defaultTheme,
        primaryColor,
        primaryDark,
        primaryText,
        schoolName: schoolSettings.school_name ?? defaultTheme.schoolName,
        schoolSlogan: schoolSettings.slogan ?? defaultTheme.schoolSlogan,
        schoolLogo: schoolSettings.logo_url ?? defaultTheme.schoolLogo,
    }
}

/**
 * Darken a hex color by a given percentage
 */
function darkenHex(hex, percent) {
    hex = hex.replace('#', '')
    if (hex.length === 3) hex = hex[0] + hex[0] + hex[1] + hex[1] + hex[2] + hex[2]
    if (hex.length === 8) hex = hex.substring(0, 6) // ignore alpha channel

    let r = parseInt(hex.substring(0, 2), 16)
    let g = parseInt(hex.substring(2, 4), 16)
    let b = parseInt(hex.substring(4, 6), 16)

    const multiplier = 1 - (percent / 100)

    r = Math.max(0, Math.min(255, Math.floor(r * multiplier)))
    g = Math.max(0, Math.min(255, Math.floor(g * multiplier)))
    b = Math.max(0, Math.min(255, Math.floor(b * multiplier)))

    const toHex = (n) => {
        const h = n.toString(16)
        return h.length === 1 ? '0' + h : h
    }

    return '#' + toHex(r) + toHex(g) + toHex(b)
}

/**
 * Calculate the best text color (black or white) for a given hex background
 * using the YIQ luminance formula.
 */
function getContrastYIQ(hexcolor) {
    hexcolor = hexcolor.replace('#', '')
    if (hexcolor.length === 3) {
        hexcolor = hexcolor[0] + hexcolor[0] + hexcolor[1] + hexcolor[1] + hexcolor[2] + hexcolor[2]
    }
    const r = parseInt(hexcolor.substr(0, 2), 16)
    const g = parseInt(hexcolor.substr(2, 2), 16)
    const b = parseInt(hexcolor.substr(4, 2), 16)
    // YIQ formula
    const yiq = ((r * 299) + (g * 587) + (b * 114)) / 1000
    // If luminance is > 128, background is light, use dark text. Otherwise use white text.
    return (yiq >= 128) ? '#0A0A0A' : '#FFFFFF'
}

export function resolveAuraLogoForBackground(backgroundColor) {
    const contrastText = getContrastYIQ(backgroundColor)
    return contrastText === '#FFFFFF'
        ? '/logos/aura_logo_white.png'
        : '/logos/aura_logo_black.png'
}

export function toggleDarkMode() {
    isDarkMode.value = !isDarkMode.value
    if (currentActiveTheme) {
        applyTheme(currentActiveTheme)
    }
}

/**
 * Apply theme CSS variables to the document root.
 */
export function applyTheme(theme) {
    currentActiveTheme = theme
    const root = document.documentElement

    // Dynamic colors based on dark mode state
    let bgColor = theme.background
    let surfaceColor = theme.surfaceColor
    let textPrimary = theme.textPrimary

    if (isDarkMode.value) {
        // Dark mode: background is 96% darker than primary color
        // Example: #AAFF00 -> #070a00
        bgColor = darkenHex(theme.primaryColor, 96)

        // In the dark mode Figma reference:
        // - the main cards (Welcome, Latest Event, Upcoming Events) remain white surfaces
        // - the profile pill remains white
        // - the navigation pill turns slightly light grey
        // - text on the dark body needs to be white, but text inside white cards remains black

        // We keep surfaceColor white for the big cards
        textPrimary = '#FFFFFF' // This applies to body text (like "Home", "Upcoming Events" headers)
    }

    const profileBg = surfaceColor
    const navPillBg = isDarkMode.value ? '#EBEBEB' : surfaceColor
    const bgTextColor = getContrastYIQ(bgColor)
    const surfaceTextColor = getContrastYIQ(surfaceColor)
    const profileTextColor = getContrastYIQ(profileBg)
    const navTextColor = getContrastYIQ(theme.navColor)
    const navPillTextColor = getContrastYIQ(navPillBg)
    const primaryTextColor = normalizeHexColor(theme.primaryText ?? getContrastYIQ(theme.primaryColor), '#0A0A0A')

    const bgSecondaryText = mixHexColors(bgTextColor, bgColor, 0.68)
    const bgMutedText = mixHexColors(bgTextColor, bgColor, 0.48)
    const surfaceSecondaryText = mixHexColors(surfaceTextColor, surfaceColor, 0.68)
    const surfaceMutedText = mixHexColors(surfaceTextColor, surfaceColor, 0.48)
    const navSecondaryText = mixHexColors(navTextColor, theme.navColor, 0.68)
    const softSurfaceBorder = mixHexColors(surfaceTextColor, surfaceColor, 0.1)
    const strongSurfaceBorder = mixHexColors(surfaceTextColor, surfaceColor, 0.22)

    root.style.setProperty('--color-primary', theme.primaryColor)
    root.style.setProperty('--color-primary-dark', theme.primaryDark)
    root.style.setProperty('--color-primary-text', primaryTextColor)
    root.style.setProperty('--color-bg', bgColor)
    root.style.setProperty('--color-surface', surfaceColor) // White cards
    root.style.setProperty('--color-profile-bg', profileBg)
    root.style.setProperty('--color-nav-pill-bg', navPillBg)
    root.style.setProperty('--color-nav', theme.navColor)
    root.style.setProperty('--color-nav-text', navTextColor)
    root.style.setProperty('--color-nav-text-secondary', navSecondaryText)
    root.style.setProperty('--color-nav-pill-text', navPillTextColor)
    root.style.setProperty('--color-nav-active', theme.navActiveColor)
    root.style.setProperty('--color-text-primary', bgTextColor || textPrimary)
    root.style.setProperty('--color-text-secondary', isDarkMode.value ? '#A0A0A0' : bgSecondaryText)
    root.style.setProperty('--color-text-muted', bgMutedText)
    root.style.setProperty('--color-surface-text', surfaceTextColor)
    root.style.setProperty('--color-surface-text-secondary', surfaceSecondaryText)
    root.style.setProperty('--color-surface-text-muted', surfaceMutedText)
    root.style.setProperty('--color-profile-text', profileTextColor)
    root.style.setProperty('--color-surface-border', softSurfaceBorder)
    root.style.setProperty('--color-surface-border-strong', strongSurfaceBorder)

    // Backwards-compatible alias for existing white-card text references.
    root.style.setProperty('--color-text-always-dark', surfaceTextColor)

    // Smart contrast text for the dark/light University Banner
    root.style.setProperty('--color-banner-text', primaryTextColor)

    // Automatically serve the correct Aura logo color based on banner contrast
    activeAuraLogo.value = resolveAuraLogoForBackground(theme.primaryColor)
    surfaceAuraLogo.value = resolveAuraLogoForBackground(surfaceColor)
    updateDocumentThemeColor(bgColor)
}
