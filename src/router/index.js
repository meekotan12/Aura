import { createRouter, createWebHistory } from 'vue-router'
import {
    clearDashboardSession,
    getDefaultAuthenticatedRoute,
    hasSessionToken,
    initializeDashboardSession,
    isAdminSession,
    isPrivilegedSession,
    isSchoolItSession,
    sessionNeedsFaceRegistration,
} from '@/composables/useDashboardSession.js'
import { hasPrivilegedPendingFace, needsStoredPasswordChange } from '@/services/localAuth.js'
import { setNavigationPending } from '@/services/navigationState.js'
import SchoolItProgramStudentsView from '@/views/dashboard/SchoolItProgramStudentsView.vue'

const AppLayout = () => import('@/layouts/AppLayout.vue')
const HomeView = () => import('@/views/dashboard/HomeView.vue')
const ProfileView = () => import('@/views/dashboard/ProfileView.vue')
const ScheduleView = () => import('@/views/dashboard/ScheduleView.vue')
const EventDetailView = () => import('@/views/dashboard/EventDetailView.vue')
const AttendanceView = () => import('@/views/dashboard/AttendanceView.vue')
const AnalyticsView = () => import('@/views/dashboard/AnalyticsView.vue')

const routes = [
    // Auth routes (no layout)
    {
        path: '/',
        name: 'Login',
        component: () => import('@/views/auth/LoginView.vue'),
        meta: { requiresGuest: true },
    },
    {
        path: '/quick-attendance',
        name: 'QuickAttendance',
        component: () => import('@/views/auth/QuickAttendanceView.vue'),
    },
    {
        path: '/api-lab',
        name: 'ApiLab',
        component: () => import('@/views/tools/ApiLabView.vue'),
    },
    {
        path: '/face-registration',
        name: 'FaceRegistration',
        component: () => import('@/views/auth/FaceRegistrationView.vue'),
        meta: {
            requiresAuth: true,
            allowWithoutFaceEnrollment: true,
        },
    },
    {
        path: '/change-password',
        name: 'ChangePassword',
        component: () => import('@/views/auth/ChangePasswordView.vue'),
        props: { flow: 'required' },
        meta: {
            requiresAuth: true,
            allowWithoutFaceEnrollment: true,
        },
    },
    {
        path: '/privileged-face',
        name: 'PrivilegedFaceVerification',
        component: () => import('@/views/auth/PrivilegedFaceVerificationView.vue'),
        meta: {
            requiresAuth: true,
            allowWithoutFaceEnrollment: true,
            allowPrivilegedPendingFace: true,
        },
    },
    {
        path: '/profile/security',
        name: 'ProfileSecurity',
        component: () => import('@/views/dashboard/ProfileSecurityView.vue'),
        meta: {
            requiresAuth: true,
            allowWithoutFaceEnrollment: true,
        },
    },
    {
        path: '/profile/security/password',
        name: 'ProfileSecurityPassword',
        component: () => import('@/views/auth/ChangePasswordView.vue'),
        props: { flow: 'settings' },
        meta: {
            requiresAuth: true,
            allowWithoutFaceEnrollment: true,
        },
    },
    {
        path: '/profile/security/face',
        name: 'ProfileSecurityFace',
        component: () => import('@/views/dashboard/ProfileFaceUpdateView.vue'),
        meta: {
            requiresAuth: true,
            allowWithoutFaceEnrollment: true,
        },
    },
    {
        path: '/privileged',
        name: 'PrivilegedDashboard',
        component: () => import('@/views/dashboard/PrivilegedComingSoonView.vue'),
        meta: {
            requiresAuth: true,
            allowWithoutFaceEnrollment: true,
        },
    },
    {
        path: '/admin',
        component: AppLayout,
        meta: {
            requiresAuth: true,
            allowWithoutFaceEnrollment: true,
            primaryNavContext: 'admin',
            workspaceContext: 'admin',
        },
        children: [
            {
                path: '',
                name: 'AdminHome',
                component: () => import('@/views/dashboard/AdminWorkspaceView.vue'),
                props: { section: 'overview' },
            },
            {
                path: 'schools',
                name: 'AdminSchools',
                component: () => import('@/views/dashboard/AdminWorkspaceView.vue'),
                props: { section: 'schools' },
            },
            {
                path: 'accounts',
                name: 'AdminAccounts',
                component: () => import('@/views/dashboard/AdminWorkspaceView.vue'),
                props: { section: 'accounts' },
            },
            {
                path: 'oversight',
                name: 'AdminOversight',
                component: () => import('@/views/dashboard/AdminWorkspaceView.vue'),
                props: { section: 'oversight' },
            },
            {
                path: 'profile',
                name: 'AdminProfile',
                component: () => import('@/views/dashboard/AdminWorkspaceView.vue'),
                props: { section: 'profile' },
            },
        ],
    },
    {
        path: '/exposed/admin',
        component: AppLayout,
        meta: {
            primaryNavContext: 'admin_preview',
            workspaceContext: 'admin_preview',
        },
        children: [
            {
                path: '',
                name: 'PreviewAdminHome',
                component: () => import('@/views/dashboard/AdminWorkspaceView.vue'),
                props: { preview: true, section: 'overview' },
            },
            {
                path: 'schools',
                name: 'PreviewAdminSchools',
                component: () => import('@/views/dashboard/AdminWorkspaceView.vue'),
                props: { preview: true, section: 'schools' },
            },
            {
                path: 'accounts',
                name: 'PreviewAdminAccounts',
                component: () => import('@/views/dashboard/AdminWorkspaceView.vue'),
                props: { preview: true, section: 'accounts' },
            },
            {
                path: 'oversight',
                name: 'PreviewAdminOversight',
                component: () => import('@/views/dashboard/AdminWorkspaceView.vue'),
                props: { preview: true, section: 'oversight' },
            },
            {
                path: 'profile',
                name: 'PreviewAdminProfile',
                component: () => import('@/views/dashboard/AdminWorkspaceView.vue'),
                props: { preview: true, section: 'profile' },
            },
        ],
    },
    {
        path: '/workspace',
        component: AppLayout,
        meta: {
            requiresAuth: true,
            allowWithoutFaceEnrollment: true,
            primaryNavContext: 'workspace',
            workspaceContext: 'workspace',
        },
        children: [
            {
                path: '',
                name: 'SchoolItHome',
                component: () => import('@/views/dashboard/SchoolItHomeView.vue'),
            },
            {
                path: 'users',
                name: 'SchoolItUsers',
                component: () => import('@/views/dashboard/SchoolItUsersView.vue'),
            },
            {
                path: 'users/import',
                name: 'SchoolItImportStudents',
                component: () => import('@/views/dashboard/SchoolItImportStudentsView.vue'),
            },
            {
                path: 'users/department/:departmentId',
                name: 'SchoolItDepartmentPrograms',
                component: () => import('@/views/dashboard/SchoolItDepartmentProgramsView.vue'),
            },
            {
                path: 'users/department/:departmentId/program/:programId',
                name: 'SchoolItProgramStudents',
                component: SchoolItProgramStudentsView,
            },
            {
                path: 'users/unassigned',
                name: 'SchoolItUnassignedStudents',
                component: () => import('@/views/dashboard/SchoolItUnassignedStudentsView.vue'),
            },
            {
                path: 'student-council',
                name: 'SchoolItStudentCouncil',
                component: () => import('@/views/dashboard/SchoolItStudentCouncilView.vue'),
            },
            {
                path: 'schedule',
                name: 'SchoolItSchedule',
                component: () => import('@/views/dashboard/SchoolItScheduleView.vue'),
                props: {
                    title: 'Schedule',
                    description: 'School IT schedule controls will live here once the event operations UI is ready.',
                },
            },
            {
                path: 'schedule/monitor',
                name: 'SchoolItAttendanceMonitor',
                component: () => import('@/views/dashboard/SchoolItAttendanceMonitorView.vue'),
            },
            {
                path: 'schedule/reports',
                name: 'SchoolItEventReports',
                component: () => import('@/views/dashboard/SchoolItEventReportsView.vue'),
            },
            {
                path: 'schedule/:id',
                name: 'SchoolItEventDetail',
                component: EventDetailView,
            },
            {
                path: 'settings',
                name: 'SchoolItSettings',
                component: () => import('@/views/dashboard/SchoolItSettingsView.vue'),
            },
            {
                path: 'profile',
                name: 'SchoolItProfile',
                component: ProfileView,
            },
        ],
    },
    {
        path: '/exposed/workspace',
        component: AppLayout,
        meta: {
            primaryNavContext: 'workspace_preview',
            workspaceContext: 'workspace_preview',
        },
        children: [
            {
                path: '',
                name: 'PreviewSchoolItHome',
                component: () => import('@/views/dashboard/SchoolItHomeView.vue'),
                props: { preview: true },
            },
            {
                path: 'users',
                name: 'PreviewSchoolItUsers',
                component: () => import('@/views/dashboard/SchoolItUsersView.vue'),
                props: { preview: true },
            },
            {
                path: 'users/import',
                name: 'PreviewSchoolItImportStudents',
                component: () => import('@/views/dashboard/SchoolItImportStudentsView.vue'),
                props: { preview: true },
            },
            {
                path: 'users/department/:departmentId',
                name: 'PreviewSchoolItDepartmentPrograms',
                component: () => import('@/views/dashboard/SchoolItDepartmentProgramsView.vue'),
                props: { preview: true },
            },
            {
                path: 'users/department/:departmentId/program/:programId',
                name: 'PreviewSchoolItProgramStudents',
                component: SchoolItProgramStudentsView,
                props: { preview: true },
            },
            {
                path: 'users/unassigned',
                name: 'PreviewSchoolItUnassignedStudents',
                component: () => import('@/views/dashboard/SchoolItUnassignedStudentsView.vue'),
                props: { preview: true },
            },
            {
                path: 'student-council',
                name: 'PreviewSchoolItStudentCouncil',
                component: () => import('@/views/dashboard/SchoolItStudentCouncilView.vue'),
                props: { preview: true },
            },
            {
                path: 'schedule',
                name: 'PreviewSchoolItSchedule',
                component: () => import('@/views/dashboard/SchoolItScheduleView.vue'),
                props: { preview: true },
            },
            {
                path: 'schedule/monitor',
                name: 'PreviewSchoolItAttendanceMonitor',
                component: () => import('@/views/dashboard/SchoolItAttendanceMonitorView.vue'),
                props: { preview: true },
            },
            {
                path: 'schedule/reports',
                name: 'PreviewSchoolItEventReports',
                component: () => import('@/views/dashboard/SchoolItEventReportsView.vue'),
                props: { preview: true },
            },
            {
                path: 'schedule/:id',
                name: 'PreviewSchoolItEventDetail',
                component: EventDetailView,
                props: { preview: true },
            },
            {
                path: 'settings',
                name: 'PreviewSchoolItSettings',
                component: () => import('@/views/dashboard/SchoolItSettingsView.vue'),
                props: { preview: true },
            },
            {
                path: 'profile',
                name: 'PreviewSchoolItProfile',
                component: () => import('@/views/dashboard/WorkspacePlaceholderView.vue'),
                props: {
                    title: 'Profile',
                    description: 'Profile controls will stay on the real authenticated workspace once the backend is available again.',
                },
            },
        ],
    },
    {
        path: '/exposed/dashboard',
        component: AppLayout,
        meta: {
            primaryNavContext: 'dashboard_preview',
            workspaceContext: 'dashboard_preview',
        },
        children: [
            {
                path: '',
                name: 'PreviewHome',
                component: HomeView,
                props: { preview: true },
            },
            {
                path: 'schedule',
                name: 'PreviewDashboardSchedule',
                component: ScheduleView,
                props: { preview: true },
            },
            {
                path: 'schedule/:id',
                name: 'PreviewEventDetail',
                component: EventDetailView,
                props: { preview: true },
            },
            {
                path: 'analytics',
                name: 'PreviewDashboardAnalytics',
                component: AnalyticsView,
                props: { preview: true },
            },
            {
                path: 'profile',
                name: 'PreviewDashboardProfile',
                component: ProfileView,
                props: { preview: true },
            },
        ],
    },
    // SG Dashboard routes
    {
        path: '/sg',
        component: AppLayout,
        meta: {
            requiresAuth: true,
            allowWithoutFaceEnrollment: true,
            primaryNavContext: 'dashboard',
            workspaceContext: 'sg',
        },
        children: [
            {
                path: '',
                name: 'SgDashboard',
                component: () => import('@/views/dashboard/SgDashboardView.vue'),
            },
            {
                path: 'members',
                name: 'SgMembers',
                component: () => import('@/views/dashboard/SgMembersView.vue'),
            },
            {
                path: 'students',
                name: 'SgStudents',
                component: () => import('@/views/dashboard/SgStudentsView.vue'),
            },
            {
                path: 'announcements',
                name: 'SgAnnouncements',
                component: () => import('@/views/dashboard/SgAnnouncementsView.vue'),
            },
            {
                path: 'create-unit',
                name: 'SgCreateUnit',
                component: () => import('@/views/dashboard/SgCreateUnitView.vue'),
            },
            {
                path: 'events',
                name: 'SgEvents',
                component: () => import('@/views/dashboard/SgEventsView.vue'),
            },
            {
                path: 'events/:id',
                name: 'SgEventDetail',
                component: EventDetailView,
            },
            {
                path: 'attendance',
                name: 'SgAttendance',
                component: () => import('@/views/dashboard/SgAttendanceView.vue'),
            },
        ],
    },
    {
        path: '/exposed/sg',
        component: AppLayout,
        meta: {
            primaryNavContext: 'dashboard_preview',
            workspaceContext: 'sg_preview',
        },
        children: [
            {
                path: '',
                name: 'PreviewSgDashboard',
                component: () => import('@/views/dashboard/SgDashboardView.vue'),
                props: { preview: true },
            },
        ],
    },
    // Student dashboard routes (wrapped in AppLayout)
    {
        path: '/dashboard',
        component: AppLayout,
        meta: {
            requiresAuth: true,
            primaryNavContext: 'dashboard',
            workspaceContext: 'dashboard',
        },
        children: [
            {
                path: '',
                name: 'Home',
                component: HomeView,
            },
            {
                path: 'profile',
                name: 'Profile',
                component: ProfileView,
            },
            {
                path: 'schedule',
                name: 'Schedule',
                component: ScheduleView,
            },
            {
                path: 'schedule/:id',
                name: 'EventDetail',
                component: EventDetailView,
            },
            {
                path: 'schedule/:id/attendance',
                name: 'Attendance',
                component: AttendanceView,
            },
            {
                path: 'analytics',
                name: 'Analytics',
                component: AnalyticsView,
            },
        ],
    },
]

const router = createRouter({
    history: createWebHistory(import.meta.env.BASE_URL),
    routes,
    scrollBehavior() {
        return { left: 0, top: 0 }
    },
})

// Navigation guard
router.beforeEach(async (to) => {
    setNavigationPending(true)
    const isAuthenticated = hasSessionToken()
    const mustChangePassword = needsStoredPasswordChange()
    const privilegedPendingFace = hasPrivilegedPendingFace()

    if (to.meta.requiresAuth && !isAuthenticated) {
        return { name: 'Login' }
    }

    if (to.name === 'PrivilegedFaceVerification') {
        if (!isAuthenticated) {
            return { name: 'Login' }
        }

        if (privilegedPendingFace) {
            return true
        }

        if (mustChangePassword) {
            return { name: 'ChangePassword' }
        }

        try {
            await initializeDashboardSession()
            return sessionNeedsFaceRegistration()
                ? { name: 'FaceRegistration' }
                : getDefaultAuthenticatedRoute()
        } catch {
            clearDashboardSession()
            return { name: 'Login' }
        }
    }

    if (isAuthenticated && privilegedPendingFace) {
        if (to.meta.allowPrivilegedPendingFace) {
            return true
        }
        return { name: 'PrivilegedFaceVerification' }
    }

    if (isAuthenticated && mustChangePassword && to.name !== 'ChangePassword') {
        return { name: 'ChangePassword' }
    }

    if (to.name === 'ChangePassword') {
        if (!isAuthenticated) {
            return { name: 'Login' }
        }

        if (!mustChangePassword) {
            try {
                await initializeDashboardSession()
                return sessionNeedsFaceRegistration()
                    ? { name: 'FaceRegistration' }
                    : getDefaultAuthenticatedRoute()
            } catch {
                clearDashboardSession()
                return { name: 'Login' }
            }
        }

        return true
    }

    if (to.meta.requiresGuest && isAuthenticated) {
        try {
            await initializeDashboardSession()
            return sessionNeedsFaceRegistration()
                ? { name: 'FaceRegistration' }
                : getDefaultAuthenticatedRoute()
        } catch {
            clearDashboardSession()
            return { name: 'Login' }
        }
    }

    if (to.meta.requiresAuth && isAuthenticated) {
        try {
            await initializeDashboardSession()
            const defaultRoute = getDefaultAuthenticatedRoute()
            const adminSession = isAdminSession()
            const privilegedSession = isPrivilegedSession()
            const schoolItSession = isSchoolItSession()
            const needsFaceRegistration = sessionNeedsFaceRegistration()
            if (needsFaceRegistration && !to.meta.allowWithoutFaceEnrollment) {
                return { name: 'FaceRegistration' }
            }
            if (!needsFaceRegistration && to.name === 'FaceRegistration') {
                return defaultRoute
            }
            if (schoolItSession && to.name === 'PrivilegedDashboard') {
                return defaultRoute
            }
            if (schoolItSession && to.path.startsWith('/dashboard')) {
                return defaultRoute
            }
            if (adminSession && (to.path.startsWith('/dashboard') || to.path.startsWith('/workspace') || to.name === 'PrivilegedDashboard')) {
                return defaultRoute
            }
            if (!adminSession && to.path.startsWith('/admin')) {
                return defaultRoute
            }
            if (!schoolItSession && to.path.startsWith('/workspace')) {
                return defaultRoute
            }
            if (privilegedSession && to.path.startsWith('/dashboard')) {
                return defaultRoute
            }
            if (!privilegedSession && to.name === 'PrivilegedDashboard') {
                return defaultRoute
            }
        } catch {
            clearDashboardSession()
            return { name: 'Login' }
        }
    }

    return true
})

router.afterEach(() => {
    setNavigationPending(false)
})

router.onError(() => {
    setNavigationPending(false)
})

export default router
