import { computed, ref, watch } from 'vue'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { getGovernanceAccess, getCampusSsgSetup } from '@/services/backendApi.js'
import { resolvePreferredGovernanceUnit } from '@/services/governanceScope.js'
import { isStudentCouncilUser, resolveStudentCouncilAcronym } from '@/services/studentCouncilManagement.js'

export function useStudentCouncilAccess() {
  const { dashboardState, apiBaseUrl, token } = useDashboardSession()
  const acronym = ref('')
  const governanceMember = ref(false)

  const isCouncilMember = computed(() => {
    return isStudentCouncilUser(dashboardState.user) || governanceMember.value
  })

  watch(
    [apiBaseUrl, token, () => dashboardState.initialized],
    async ([url, authToken, isInit]) => {
      if (!isInit || !url || !authToken) {
        acronym.value = ''
        governanceMember.value = false
        return
      }

      const knownFromProfile = isStudentCouncilUser(dashboardState.user)
      let accessPayload = null
      let governanceUnit = null

      // Prefer the user's assigned governance unit from backend access over
      // the campus-wide SSG setup so SG officers keep their college scope.
      try {
        accessPayload = await getGovernanceAccess(url, authToken)
        governanceUnit = resolvePreferredGovernanceUnit(accessPayload)

        if (governanceUnit) {
          governanceMember.value = true
          acronym.value = governanceUnit.unit_code || resolveStudentCouncilAcronym(governanceUnit) || ''
        } else if (!knownFromProfile) {
          governanceMember.value = false
          acronym.value = ''
          return
        }
      } catch {
        if (!knownFromProfile) {
          governanceMember.value = false
          acronym.value = ''
          return
        }
      }

      if (governanceUnit) {
        return
      }

      // Fall back to the campus SSG setup only when the user does not have an
      // assigned governance unit in the access payload.
      try {
        const setup = await getCampusSsgSetup(url, authToken)
        if (setup?.unit) {
          acronym.value = resolveStudentCouncilAcronym(setup.unit)
        } else {
          governanceUnit = resolvePreferredGovernanceUnit(accessPayload)
          if (governanceUnit) {
            acronym.value = governanceUnit.unit_code || resolveStudentCouncilAcronym(governanceUnit) || 'SG'
          } else if (dashboardState.user?.ssg_profile) {
            acronym.value = resolveStudentCouncilAcronym(dashboardState.user.ssg_profile)
          } else {
            acronym.value = 'SG'
          }
        }
      } catch {
        if (dashboardState.user?.ssg_profile) {
          acronym.value = resolveStudentCouncilAcronym(dashboardState.user.ssg_profile)
        } else {
          acronym.value = acronym.value || 'SG'
        }
      }
    },
    { immediate: true }
  )

  return {
    isCouncilMember,
    acronym,
  }
}
