import { createRouter, createWebHistory } from 'vue-router'

const routes = [
    // Auth routes (no layout)
    {
        path: '/',
        name: 'Login',
        component: () => import('@/views/auth/LoginView.vue'),
        meta: { requiresGuest: true },
    },

    // Student dashboard routes (wrapped in AppLayout)
    {
        path: '/dashboard',
        component: () => import('@/layouts/AppLayout.vue'),
        meta: { requiresAuth: true },
        children: [
            {
                path: '',
                name: 'Home',
                component: () => import('@/views/dashboard/HomeView.vue'),
            },
            {
                path: 'profile',
                name: 'Profile',
                component: () => import('@/views/dashboard/ProfileView.vue'),
            },
            {
                path: 'schedule',
                name: 'Schedule',
                component: () => import('@/views/dashboard/ScheduleView.vue'),
            },
            {
                path: 'schedule/:id',
                name: 'EventDetail',
                component: () => import('@/views/dashboard/EventDetailView.vue'),
            },
            {
                path: 'schedule/:id/attendance',
                name: 'Attendance',
                component: () => import('@/views/dashboard/AttendanceView.vue'),
            },
            {
                path: 'analytics',
                name: 'Analytics',
                component: () => import('@/views/dashboard/AnalyticsView.vue'),
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
router.beforeEach((to, _from, next) => {
    const isAuthenticated = !!localStorage.getItem('aura_token')

    if (to.meta.requiresAuth && !isAuthenticated) {
        next({ name: 'Login' })
    } else if (to.meta.requiresGuest && isAuthenticated) {
        next({ name: 'Home' })
    } else {
        next()
    }
})

export default router
