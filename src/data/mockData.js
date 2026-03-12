/**
33 * Mock Data - Mirrors backend API response shapes EXACTLY.
 * Replace with real API calls when backend is connected.
 *
 * API Endpoints:
 *   GET /users/me                  → mockCurrentUser  (UserWithRelations schema)
 *   GET /events/                   → mockEvents       (Event schema)
 *   GET /school-settings/me        → mockSchoolSettings (SchoolSettingsResponse schema)
 */

// ─── User ────────────────────────────────────────────────────────────────────
// Matches: UserWithRelations schema from GET /users/me
// Key fields: id, email, first_name, last_name, middle_name, school_id,
//             is_active, created_at, roles[], ssg_profile, student_profile
// School 1 Student (RTU)
export const mockRtuUser = {
    id: 101,
    email: 'zann@example.edu',
    first_name: 'Zann',
    last_name: 'Cute',
    middle_name: null,
    is_active: true,
    created_at: '2026-03-11T08:00:00Z',
    school_id: 1, // RTU
    roles: [
        { role: { id: 2, name: 'student' } },
    ],
    ssg_profile: null,
    student_profile: {
        id: 55,
        student_id: 'CS-2026-001',
        department_id: 3,
        program_id: 7,
        year_level: 2,
        attendances: [],
    },
}

// 👉 To test the other school's login, change 'mockRtuUser' below to 'mockJrmsuUser'
export const mockCurrentUser = mockRtuUser

// ─── Events ──────────────────────────────────────────────────────────────────
// Matches: Event schema
// Key fields: id, name, location, start_datetime, end_datetime, status,
//             school_id, department_ids[], program_ids[], ssg_member_ids[],
//             geo_latitude, geo_longitude, geo_radius_m, geo_required,
//             geo_max_accuracy_m, late_threshold_minutes
export const mockEvents = [
    {
        id: 1,
        name: 'Foundation Day Celebration',
        location: 'Main Gymnasium, Building A',
        start_datetime: '2026-03-15T08:00:00Z',
        end_datetime: '2026-03-15T17:00:00Z',
        status: 'upcoming',
        school_id: 1,
        department_ids: [1],
        program_ids: [],
        ssg_member_ids: [1, 2],
        departments: [{ id: 1, name: 'All Departments' }],
        programs: [],
        ssg_members: [],
        geo_latitude: 8.657256484910368,
        geo_longitude: 123.42312902908029,
        geo_radius_m: 120,
        geo_required: false,
        geo_max_accuracy_m: null,
        late_threshold_minutes: null,
    },
    {
        id: 2,
        name: 'Engineering Week Summit',
        location: 'College of Engineering Amphitheater',
        start_datetime: '2026-03-20T09:00:00Z',
        end_datetime: '2026-03-22T18:00:00Z',
        status: 'upcoming',
        school_id: 1,
        department_ids: [2],
        program_ids: [],
        ssg_member_ids: [],
        departments: [{ id: 2, name: 'College of Engineering' }],
        programs: [],
        ssg_members: [],
        geo_latitude: null,
        geo_longitude: null,
        geo_radius_m: null,
        geo_required: false,
        geo_max_accuracy_m: null,
        late_threshold_minutes: null,
    },
    {
        id: 3,
        name: 'IT Skills Competition',
        location: 'Computer Laboratory 3',
        start_datetime: '2026-03-25T13:00:00Z',
        end_datetime: '2026-03-25T17:00:00Z',
        status: 'upcoming',
        school_id: 1,
        department_ids: [3],
        program_ids: [7],
        ssg_member_ids: [],
        departments: [{ id: 3, name: 'College of IT' }],
        programs: [{ id: 7, name: 'BSCS', department_ids: [3] }],
        ssg_members: [],
        geo_latitude: null,
        geo_longitude: null,
        geo_radius_m: null,
        geo_required: false,
        geo_max_accuracy_m: null,
        late_threshold_minutes: null,
    },
    {
        id: 4,
        name: 'Freshmen Orientation',
        location: 'Main Auditorium',
        start_datetime: '2026-02-15T08:00:00Z',
        end_datetime: '2026-02-15T12:00:00Z',
        status: 'completed',
        school_id: 1,
        department_ids: [],
        program_ids: [],
        ssg_member_ids: [],
        departments: [],
        programs: [],
        ssg_members: [],
        geo_latitude: null,
        geo_longitude: null,
        geo_radius_m: null,
        geo_required: false,
        geo_max_accuracy_m: null,
        late_threshold_minutes: null,
    },
    {
        id: 5,
        name: 'Intramurals Opening',
        location: 'University Oval',
        start_datetime: '2026-03-12T07:00:00Z',
        end_datetime: '2026-03-12T17:00:00Z',
        status: 'ongoing',
        school_id: 1,
        department_ids: [],
        program_ids: [],
        ssg_member_ids: [],
        departments: [],
        programs: [],
        ssg_members: [],
        geo_latitude: 8.657256484910368,
        geo_longitude: 123.42312902908029,
        geo_radius_m: 120,
        geo_required: true,
        geo_max_accuracy_m: 25,
        late_threshold_minutes: 10,
    }
]

// ─── School Settings ─────────────────────────────────────────────────────────
// Matches: SchoolSettingsResponse schema from GET /school-settings/me
// School 1 (Default Lime Green Theme)
export const mockRtuSettings = {
    school_id: 1,
    school_name: 'Jose Rizal Memorial State University',
    primary_color: '#ffff00ff', // Lime Green
    secondary_color: '#0A0A0A',
    accent_color: '#88CC00',
    logo_url: '/src/data/jrmsu_icon.png',
}

// School 2 (Example Blue/Gold Theme)
export const mockJrmsuSettings = {
    school_id: 2,
    school_name: 'Unibirsedad ng Pilipinas',
    primary_color: '#001B5E', // Deep Blue
    secondary_color: '#FFFFFF',
    accent_color: '#FFB81C', // Gold
    logo_url: '/src/data/up.png',
}

/**
 * School settings lookup map — keyed by school_id.
 * Mirrors the real backend: GET /school-settings/me returns the settings
 * for the school the authenticated user belongs to.
 *
 * When connecting the backend:
 *   - Remove this map entirely
 *   - Call GET /school-settings/me after login
 *   - Pass the response to applyTheme()
 */
export const mockSchoolSettingsMap = {
    [mockRtuSettings.school_id]: mockRtuSettings,
    [mockJrmsuSettings.school_id]: mockJrmsuSettings,
}

// Auto-derives from the logged-in user's school_id — no hardcoding.
// Changing mockCurrentUser's school_id automatically picks the correct theme.
export const mockSchoolSettings = mockSchoolSettingsMap[mockCurrentUser.school_id] ?? mockRtuSettings

// ─── Announcements ───────────────────────────────────────────────────────────
// Flexible shape — endpoint TBD in backend (for future connection)
