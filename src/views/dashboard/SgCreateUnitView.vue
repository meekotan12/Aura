<template>
  <section class="sg-sub-page">
    <header class="sg-sub-header dashboard-enter dashboard-enter--1">
      <button class="sg-sub-back" type="button" @click="goBack">
        <ArrowLeft :size="20" />
      </button>
      <h1 class="sg-sub-title">{{ pageTitle }}</h1>
    </header>

    <div v-if="isCreated" class="sg-sub-card sg-create-success dashboard-enter dashboard-enter--2">
      <h2 class="sg-create-success-title">{{ childTypeName }} created!</h2>
      <p class="sg-create-success-copy">{{ createdUnit?.unit_name || '' }} has been created successfully.</p>
      <div class="sg-create-success-actions">
        <button class="sg-sub-action" type="button" @click="resetForm">Create Another</button>
        <button class="sg-create-back" type="button" @click="goBack">Back to Dashboard</button>
      </div>
    </div>

    <template v-else>
      <div class="sg-sub-card dashboard-enter dashboard-enter--2">
        <StudentCouncilSetupStage
          :draft="draft"
          :submit-label="submitLabel"
          :submit-disabled="submitDisabled"
          @update:draft="draft = $event"
          @submit="handleCreate"
        />
      </div>

      <p v-if="formError" class="sg-create-error dashboard-enter dashboard-enter--3">{{ formError }}</p>
    </template>
  </section>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft } from 'lucide-vue-next'
import StudentCouncilSetupStage from '@/components/council/StudentCouncilSetupStage.vue'
import { useDashboardSession } from '@/composables/useDashboardSession.js'
import { useSgDashboard } from '@/composables/useSgDashboard.js'
import { getGovernanceAccess, createGovernanceUnit } from '@/services/backendApi.js'
import { resolvePreferredGovernanceUnit } from '@/services/governanceScope.js'
import { createEmptyCouncilDraft } from '@/services/studentCouncilManagement.js'

const router = useRouter()
const { apiBaseUrl } = useDashboardSession()
const { permissionCodes, isLoading: sgLoading } = useSgDashboard()

const draft = ref(createEmptyCouncilDraft())
const isSaving = ref(false)
const formError = ref('')
const isCreated = ref(false)
const createdUnit = ref(null)
const parentUnitId = ref(null)

// Determine child type from permission codes:
// create_sg → creates SG unit (SSG context)
// create_org → creates ORG unit (SG context)
const childType = computed(() => {
  const codes = new Set(permissionCodes.value)
  if (codes.has('create_sg')) return 'SG'
  if (codes.has('create_org')) return 'ORG'
  return null
})

const childTypeName = computed(() => {
  if (childType.value === 'SG') return 'College-Level Council'
  if (childType.value === 'ORG') return 'Organization'
  return 'Unit'
})

const pageTitle = computed(() => `Create ${childTypeName.value}`)
const submitLabel = computed(() => isSaving.value ? 'Creating...' : `Create ${childTypeName.value}`)
const submitDisabled = computed(() => {
  if (isSaving.value || !childType.value) return true
  const d = draft.value
  return !d?.acronym?.trim() || !d?.name?.trim()
})

function goBack() { router.push('/sg') }

watch(
  [apiBaseUrl, () => sgLoading.value, childType],
  async ([url]) => {
    if (!url || sgLoading.value || !childType.value) return
    await resolveParent(url)
  },
  { immediate: true }
)

async function resolveParent(url) {
  parentUnitId.value = null
  try {
    const token = localStorage.getItem('aura_token') || ''
    const access = await getGovernanceAccess(url, token)
    const parentUnit = resolvePreferredGovernanceUnit(access, {
      requiredPermissionCode: childType.value === 'SG' ? 'create_sg' : 'create_org',
    })
    parentUnitId.value = Number(parentUnit?.governance_unit_id) || null
  } catch { /* ignore */ }
}

function resetForm() {
  draft.value = createEmptyCouncilDraft()
  formError.value = ''
  isCreated.value = false
  createdUnit.value = null
}

async function handleCreate() {
  if (submitDisabled.value) return
  isSaving.value = true
  formError.value = ''
  const token = localStorage.getItem('aura_token') || ''
  try {
    const result = await createGovernanceUnit(apiBaseUrl.value, token, {
      unit_code: draft.value.acronym.trim(),
      unit_name: draft.value.name.trim(),
      description: (draft.value.description || '').trim() || null,
      unit_type: childType.value,
      parent_unit_id: parentUnitId.value || null,
    })
    createdUnit.value = result
    isCreated.value = true
  } catch (e) {
    formError.value = e?.message || `Unable to create ${childTypeName.value}.`
  } finally { isSaving.value = false }
}
</script>

<style scoped>
@import '@/assets/css/sg-sub-views.css';

.sg-create-success { text-align: center; padding: 32px 24px; }
.sg-create-success-title { font-size: 20px; font-weight: 800; color: var(--color-primary); margin-bottom: 6px; }
.sg-create-success-copy { font-size: 14px; color: var(--color-text-muted); margin-bottom: 20px; }
.sg-create-success-actions { display: flex; gap: 12px; justify-content: center; }
.sg-create-back { background: none; border: none; color: var(--color-text-muted); font-size: 13px; font-weight: 600; cursor: pointer; }
.sg-create-error { color: #e74c3c; font-size: 13px; text-align: center; }
</style>
