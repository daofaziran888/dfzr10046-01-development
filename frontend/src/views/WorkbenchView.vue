<template>
  <section class="page" :data-module="meta.key">
    <header class="page-head">
      <div>
        <h2>{{ meta.name }}</h2>
        <p class="page-desc">{{ meta.desc }}</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="open-create" type="button" @click="openCreate">
          登记{{ meta.entity }}
        </button>
        <button class="btn" data-testid="export" type="button" @click="exportRows">
          导出{{ meta.name }}清单
        </button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p class="status-legend">
      <span v-for="item in statusSummary" :key="item.status" class="legend-item">
        {{ item.status }}：{{ item.count }}
      </span>
    </p>

    <HandoffPanel
      v-if="meta.key === 'dim_entry'"
      mode="board"
      :reload-token="handoffTick"
    />
    <HandoffPanel
      v-if="meta.key === 'surrogate_key'"
      mode="todo"
      :reload-token="handoffTick"
    />

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :data-testid="`filter-${field}`" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" data-testid="query" type="submit">查询</button>
      <button class="btn ghost" data-testid="reset" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in meta.fields" :key="column">{{ column }}</th>
          <th>当前状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :data-testid="`row-${row.id}`" :data-status="String(row.status)">
          <td v-for="column in meta.fields" :key="column">{{ row[column] ?? '—' }}</td>
          <td>{{ row.status }}</td>
          <td class="row-actions">
            <button
              v-for="action in meta.actions"
              :key="action"
              class="link"
              type="button"
              :data-testid="`action-${row.id}-${action}`"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <button
              class="link"
              type="button"
              :data-testid="`detail-${row.id}`"
              @click="openDetail(row)"
            >
              详情
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="meta.fields.length + 2" class="empty-state">
            暂无{{ meta.name }}数据，可先登记{{ meta.entity }}
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="showCreate" class="modal-backdrop" data-testid="create-modal">
      <form class="modal" @submit.prevent="submitCreate">
        <h3>登记{{ meta.entity }}</h3>
        <label v-for="field in createFormFields" :key="field" class="create-field">
          <span>{{ field }}</span>
          <input v-model="createValues[field]" :data-testid="`create-${field}`" required />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="showCreate = false">取消</button>
          <button class="btn primary" data-testid="submit-create" type="submit" :disabled="creating">
            {{ creating ? '提交中…' : '确认登记' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="remarkAction" class="modal-backdrop" data-testid="remark-modal">
      <form class="modal" @submit.prevent="submitRemarkAction">
        <h3>{{ remarkAction.action }}</h3>
        <label class="create-field">
          <span>{{ remarkAction.label }}</span>
          <input v-model="remarkValue" data-testid="remark-input" required />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="remarkAction = null">取消</button>
          <button class="btn primary" data-testid="remark-submit" type="submit" :disabled="acting">
            {{ acting ? '提交中…' : '确认' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="detailRow" class="modal-backdrop" data-testid="detail-modal">
      <div class="modal">
        <h3>{{ meta.entity }}详情</h3>
        <dl class="detail-list">
          <template v-for="entry in detailEntries" :key="entry[0]">
            <dt>{{ entry[0] }}</dt>
            <dd>
              <ul v-if="Array.isArray(entry[1])">
                <li v-for="(item, index) in entry[1]" :key="index">{{ item }}</li>
              </ul>
              <span v-else>{{ formatDetailValue(entry[1]) }}</span>
            </dd>
          </template>
        </dl>
        <div class="page-actions">
          <button class="btn" type="button" data-testid="detail-close" @click="detailRow = null">关闭</button>
        </div>
      </div>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条{{ meta.name }}记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  createEntry,
  downloadEntries,
  listEntries,
  moduleMeta,
  runAction as applyAction,
} from '@/api/backend-service'
import HandoffPanel from '@/components/HandoffPanel.vue'
import type { EntryRow } from '@/data/types'

const props = defineProps<{ moduleKey: string }>()
const meta = moduleMeta(props.moduleKey)
const rows = ref<EntryRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = meta.fields.slice(0, 3)
const showCreate = ref(false)
const creating = ref(false)
const createValues = ref<Record<string, string>>({})
const handoffTick = ref(0)
const remarkAction = ref<{ action: string; row: EntryRow; label: string } | null>(null)
const remarkValue = ref('')
const acting = ref(false)
const detailRow = ref<EntryRow | null>(null)
const createFormFields = meta.createFields ?? meta.fields
const detailEntries = computed(() =>
  Object.entries(detailRow.value ?? {}).filter(([key]) => !['pending', 'abnormal'].includes(key)),
)
const stats = computed(() => [
  { label: meta.metrics[0], value: total.value },
  { label: meta.metrics[1], value: rows.value.filter((row) => row.status === meta.statuses[1]).length },
  {
    label: meta.metrics[2],
    value: rows.value.filter((row) => row.status === meta.statuses[meta.statuses.length - 1]).length,
  },
])
const statusSummary = computed(() =>
  meta.statuses.map((status) => ({
    status,
    count: rows.value.filter((row) => String(row.status) === status).length,
  })),
)

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  try {
    await downloadEntries(meta.key, filters.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导出失败'
  }
}

function openCreate() {
  createValues.value = Object.fromEntries(createFormFields.map((field) => [field, '']))
  errorMessage.value = ''
  showCreate.value = true
}

async function submitCreate() {
  creating.value = true
  errorMessage.value = ''
  try {
    const result = await createEntry(meta.key, createValues.value)
    if (!result.ok) throw new Error(result.message)
    showCreate.value = false
    handoffTick.value += 1
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登记失败'
  } finally {
    creating.value = false
  }
}

function runAction(action: string, row: EntryRow) {
  const label = meta.actionRemarks?.[action]
  if (label) {
    remarkAction.value = { action, row, label }
    remarkValue.value = ''
    return
  }
  void applyRowAction(action, row)
}

async function submitRemarkAction() {
  if (!remarkAction.value) return
  const { action, row } = remarkAction.value
  const ok = await applyRowAction(action, row, remarkValue.value)
  if (ok) remarkAction.value = null
}

async function applyRowAction(action: string, row: EntryRow, remark?: string): Promise<boolean> {
  acting.value = true
  errorMessage.value = ''
  try {
    const result = await applyAction(meta.key, Number(row.id), action, remark)
    if (!result.ok) throw new Error(result.message)
    handoffTick.value += 1
    await reload()
    return true
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
    return false
  } finally {
    acting.value = false
  }
}

function openDetail(row: EntryRow) {
  detailRow.value = row
}

function formatDetailValue(value: unknown): string {
  if (value === '' || value === null || value === undefined) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

async function reload() {
  errorMessage.value = ''
  try {
    const payload = await listEntries(meta.key, filters.value)
    rows.value = payload.items
    total.value = payload.total
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '业务列表读取失败'
  }
}

onMounted(reload)
</script>
