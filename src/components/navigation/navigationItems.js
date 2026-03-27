import {
    Building2,
    CalendarDays,
    House,
    PieChart,
    Settings,
    ShieldCheck,
    UserRound,
    UsersRound,
} from 'lucide-vue-next'

export const dashboardNavigationItems = [
    { name: 'Home', route: '/dashboard', icon: House },
    { name: 'Schedule', route: '/dashboard/schedule', icon: CalendarDays },
    { name: 'Analytics', route: '/dashboard/analytics', icon: PieChart },
    { name: 'Profile', route: '/dashboard/profile', icon: UserRound },
]

export const schoolItNavigationItems = [
    { name: 'Home', route: '/workspace', icon: House },
    { name: 'Users', route: '/workspace/users', icon: UsersRound, matchPrefixes: ['/workspace/student-council'] },
    { name: 'Schedule', route: '/workspace/schedule', icon: CalendarDays },
    { name: 'Settings', route: '/workspace/settings', icon: Settings },
    { name: 'Profile', route: '/workspace/profile', icon: UserRound },
]

export const exposedSchoolItNavigationItems = [
    { name: 'Home', route: '/exposed/workspace', icon: House },
    { name: 'Users', route: '/exposed/workspace/users', icon: UsersRound, matchPrefixes: ['/exposed/workspace/student-council'] },
    { name: 'Schedule', route: '/exposed/workspace/schedule', icon: CalendarDays },
    { name: 'Settings', route: '/exposed/workspace/settings', icon: Settings },
    { name: 'Profile', route: '/exposed/workspace/profile', icon: UserRound },
]

export const exposedDashboardNavigationItems = [
    { name: 'Home', route: '/exposed/dashboard', icon: House },
    { name: 'Schedule', route: '/exposed/dashboard/schedule', icon: CalendarDays },
    { name: 'Analytics', route: '/exposed/dashboard/analytics', icon: PieChart },
    { name: 'Profile', route: '/exposed/dashboard/profile', icon: UserRound },
]

export const adminNavigationItems = [
    { name: 'Home', route: '/admin', icon: House },
    { name: 'Schools', route: '/admin/schools', icon: Building2 },
    { name: 'Accounts', route: '/admin/accounts', icon: UsersRound },
    { name: 'Oversight', route: '/admin/oversight', icon: ShieldCheck },
    { name: 'Profile', route: '/admin/profile', icon: UserRound },
]

export const exposedAdminNavigationItems = [
    { name: 'Home', route: '/exposed/admin', icon: House },
    { name: 'Schools', route: '/exposed/admin/schools', icon: Building2 },
    { name: 'Accounts', route: '/exposed/admin/accounts', icon: UsersRound },
    { name: 'Oversight', route: '/exposed/admin/oversight', icon: ShieldCheck },
    { name: 'Profile', route: '/exposed/admin/profile', icon: UserRound },
]

export const sgNavigationItems = [
    { name: 'Home', route: '/sg', icon: House },
    { name: 'Events', route: '/sg/events', icon: CalendarDays },
    { name: 'Members', route: '/sg/members', icon: UsersRound },
    { name: 'Profile', route: '/dashboard/profile', icon: UserRound },
]

export const exposedSgNavigationItems = [
    { name: 'Home', route: '/exposed/sg', icon: House },
    { name: 'Events', route: '/exposed/sg/events', icon: CalendarDays },
    { name: 'Members', route: '/exposed/sg/members', icon: UsersRound },
    { name: 'Profile', route: '/exposed/dashboard/profile', icon: UserRound },
]

const NAVIGATION_CONTEXT_ITEMS = {
    dashboard: dashboardNavigationItems,
    dashboard_preview: exposedDashboardNavigationItems,
    workspace: schoolItNavigationItems,
    workspace_preview: exposedSchoolItNavigationItems,
    admin: adminNavigationItems,
    admin_preview: exposedAdminNavigationItems,
    sg: sgNavigationItems,
    sg_preview: exposedSgNavigationItems,
}

function normalizeNavigationContext(value = '') {
    return String(value || '')
        .trim()
        .toLowerCase()
        .replace(/[\s-]+/g, '_')
}

function resolveNavigationContextFromPath(path = '') {
    const normalizedPath = String(path || '')

    if (normalizedPath.startsWith('/exposed/admin')) {
        return 'admin_preview'
    }
    if (normalizedPath.startsWith('/exposed/workspace')) {
        return 'workspace_preview'
    }
    if (normalizedPath.startsWith('/exposed/sg')) {
        return 'dashboard_preview'
    }
    if (normalizedPath.startsWith('/exposed/dashboard')) {
        return 'dashboard_preview'
    }
    if (normalizedPath.startsWith('/admin')) {
        return 'admin'
    }
    if (normalizedPath.startsWith('/workspace')) {
        return 'workspace'
    }
    if (normalizedPath.startsWith('/sg')) {
        return 'dashboard'
    }

    return 'dashboard'
}

export function getNavigationItemsForContext(context = '') {
    const normalizedContext = normalizeNavigationContext(context)
    return NAVIGATION_CONTEXT_ITEMS[normalizedContext] || dashboardNavigationItems
}

export function resolveNavigationContext(route = null) {
    const matchedRecords = Array.isArray(route?.matched) ? [...route.matched].reverse() : []
    const matchedContext = matchedRecords
        .map((record) => normalizeNavigationContext(record?.meta?.primaryNavContext))
        .find(Boolean)

    if (matchedContext) {
        return matchedContext
    }

    const metaContext = normalizeNavigationContext(route?.meta?.primaryNavContext)
    if (metaContext) {
        return metaContext
    }

    return resolveNavigationContextFromPath(route?.path || route || '')
}

export function getNavigationItemsForRoute(route = null) {
    return getNavigationItemsForContext(resolveNavigationContext(route))
}

export function getNavigationItemsForPath(path = '') {
    return getNavigationItemsForContext(resolveNavigationContextFromPath(path))
}
