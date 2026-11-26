<template>
  <section class="handoff-panel" :data-testid="`handoff-panel-${mode}`">
    <header class="handoff-head">
      <div>
        <h3>{{ mode === 'board' ? '建档交接视图' : '代理键待办' }}</h3>
        <p class="handoff-desc">
          {{ mode === 'board'
            ? '维度提交后同步生成的交接回执，展示待领人与可填写对象。'
            : '在此领取交接并直接继续对应维度的分段登记；列表标明可继续分段还是必须先补正。' }}
        </p>
      </div>
      <button class="btn ghost" type="button" data-testid="handoff-reload" @click="reload">刷新</button>
    </header>

    <table class="data-table">
      <thead>
        <tr>
          <th>交接编号</th>
          <th>维度名称</th>
          <template v-if="mode === 'board'">
            <th>提交人</th>
            <th>待领人</th>
            <th>可填写对象</th>
          </template>
          <template v-else>
            <th>可填写对象</th>
            <th>领取人</th>
            <th>分段进度</th>
            <th>沿用标记</th>
          </template>
          <th>当前状态</th>
          <th>办理提示</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :data-testid="`handoff-row-${row.id}`" :data-status="String(row.status)">
          <td>{{ row['交接编号'] }}</td>
          <td>{{ row['维度名称'] }}</td>
          <template v-if="mode === 'board'">
            <td>{{ row['提交人'] || '—' }}</td>
            <td>{{ row['待领人'] || '—' }}</td>
            <td>{{ row['可填写对象'] || '—' }}</td>
          </template>
          <template v-else>
            <td>{{ row['可填写对象'] || '—' }}</td>
            <td>{{ row['领取人'] || '—' }}</td>
            <td>{{ row['分段进度'] || '—' }}</td>
            <td>{{ row['沿用标记'] || '—' }}</td>
          </template>
          <td>{{ row.status }}</td>
          <td>{{ row['办理提示'] || '—' }}</td>
          <td class="row-actions">
            <template v-if="mode === 'todo'">
              <button
                v-if="row.status === '待领取'"
                class="link" type="button"
                :data-testid="`handoff-claim-${row.id}`"
                @click="openClaim(row)"
              >领取交接</button>
              <button
                v-if="continuable(row)"
                class="link" type="button"
                :data-testid="`handoff-segment-${row.id}`"
                @click="openSegment(row)"
              >登记分段</button>
              <button
                v-if="continuable(row)"
                class="link" type="button"
                :data-testid="`handoff-return-${row.id}`"
                @click="openReturn(row)"
              >退回补正</button>
              <button
                v-if="row.status === '分段登记中'"
                class="link" type="button"
                :data-testid="`handoff-complete-${row.id}`"
                @click="completeHandoff(row)"
              >完成交接</button>
            </template>
            <button
              v-if="mode === 'board' && row.status === '已退回'"
              class="link" type="button"
              :data-testid="`handoff-resubmit-${row.id}`"
              @click="resubmit(row)"
            >补正重提</button>
            <button
              class="link" type="button"
              :data-testid="`handoff-detail-${row.id}`"
              @click="openReceipt(row)"
            >查看回执</button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td colspan="9" class="empty-state">暂无交接待办，值班员提交维度后自动同步生成</td>
        </tr>
      </tbody>
    </table>

    <p v-if="message" class="handoff-message" :class="{ failed: messageFailed }" data-testid="handoff-message">
      {{ message }}
    </p>

    <div v-if="claimRow" class="modal-backdrop" data-testid="handoff-claim-modal">
      <form class="modal" @submit.prevent="submitClaim">
        <h3>领取交接 {{ claimRow['交接编号'] }}</h3>
        <label class="create-field">
          <span>领取人（待领人：{{ claimRow['待领人'] }}）</span>
          <select v-model="claimOperator" data-testid="handoff-claim-operator" required>
            <option value="" disabled>请选择领取人</option>
            <option v-for="name in claimCandidates" :key="name" :value="name">{{ name }}</option>
          </select>
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="claimRow = null">取消</button>
          <button class="btn primary" data-testid="handoff-claim-submit" type="submit" :disabled="acting">
            {{ acting ? '提交中…' : '确认领取' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="segmentRow" class="modal-backdrop" data-testid="handoff-segment-modal">
      <form class="modal" @submit.prevent="submitSegment">
        <h3>登记分段 {{ segmentRow['交接编号'] }}（{{ segmentRow['维度名称'] }}）</h3>
        <label class="create-field">
          <span>分段说明</span>
          <input v-model="segmentNote" data-testid="handoff-segment-note" placeholder="例如：门店键段 6000-6999" required />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="segmentRow = null">取消</button>
          <button class="btn primary" data-testid="handoff-segment-submit" type="submit" :disabled="acting">
            {{ acting ? '提交中…' : '确认登记' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="returnRow" class="modal-backdrop" data-testid="handoff-return-modal">
      <form class="modal" @submit.prevent="submitReturn">
        <h3>退回补正 {{ returnRow['交接编号'] }}</h3>
        <p class="handoff-desc">退回原提交人 {{ returnRow['提交人'] || '值班员' }} 补正。</p>
        <label class="create-field">
          <span>退回原因</span>
          <input v-model="returnReason" data-testid="handoff-return-reason" placeholder="例如：登记不完整" required />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="returnRow = null">取消</button>
          <button class="btn primary" data-testid="handoff-return-submit" type="submit" :disabled="acting">
            {{ acting ? '提交中…' : '确认退回' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="receiptRow" class="modal-backdrop" data-testid="handoff-receipt">
      <div class="modal">
        <h3>交接回执 {{ receiptRow['交接编号'] }}</h3>
        <dl class="detail-list">
          <dt>维度</dt><dd>{{ receiptRow['维度编号'] }} · {{ receiptRow['维度名称'] }}</dd>
          <dt>提交人</dt><dd>{{ receiptRow['提交人'] || '—' }}</dd>
          <dt>待领人</dt><dd>{{ receiptRow['待领人'] || '—' }}</dd>
          <dt>可填写对象</dt><dd>{{ receiptRow['可填写对象'] || '—' }}</dd>
          <dt>领取人</dt><dd>{{ receiptRow['领取人'] || '—' }}</dd>
          <dt>当前状态</dt><dd>{{ receiptRow.status }}</dd>
          <dt>办理提示</dt><dd>{{ receiptRow['办理提示'] || '—' }}</dd>
          <dt>分段进度</dt><dd>{{ receiptRow['分段进度'] || '—' }}</dd>
          <dt>沿用标记</dt><dd>{{ receiptRow['沿用标记'] || '—' }}</dd>
          <dt>退回原因</dt><dd>{{ receiptRow['退回原因'] || '—' }}</dd>
          <dt>分段说明</dt>
          <dd>
            <ul v-if="segmentNotes.length" data-testid="handoff-receipt-segments">
              <li v-for="(note, i) in segmentNotes" :key="i">{{ note }}</li>
            </ul>
            <span v-else>—</span>
          </dd>
          <dt>历次交接</dt>
          <dd>
            <ul data-testid="handoff-receipt-history">
              <li v-for="(item, i) in handoffHistory" :key="i">{{ item }}</li>
            </ul>
          </dd>
        </dl>
        <div class="page-actions">
          <button class="btn" type="button" data-testid="handoff-receipt-close" @click="receiptRow = null">关闭</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { listEntries, runAction } from '@/api/backend-service'
import type { EntryRow } from '@/data/types'

const props = withDefaults(defineProps<{ mode: 'board' | 'todo'; reloadToken?: number }>(), {
  reloadToken: 0,
})

const MODULE_KEY = 'entry_handoff'
const rows = ref<EntryRow[]>([])
const message = ref('')
const messageFailed = ref(false)
const acting = ref(false)

const claimRow = ref<EntryRow | null>(null)
const claimOperator = ref('')
const segmentRow = ref<EntryRow | null>(null)
const segmentNote = ref('')
const returnRow = ref<EntryRow | null>(null)
const returnReason = ref('')
const receiptRow = ref<EntryRow | null>(null)

const claimCandidates = computed(() =>
  String(claimRow.value?.['待领人'] ?? '')
    .split(/[、,，/]/)
    .map((name) => name.trim())
    .filter(Boolean),
)
const segmentNotes = computed(() => {
  const value = receiptRow.value?.['分段说明列表']
  return Array.isArray(value) ? (value as string[]) : []
})
const handoffHistory = computed(() => {
  const value = receiptRow.value?.['交接履历']
  return Array.isArray(value) ? (value as string[]) : []
})

function continuable(row: EntryRow): boolean {
  return row.status === '已领取' || row.status === '分段登记中'
}

function notice(text: string, failed: boolean) {
  message.value = text
  messageFailed.value = failed
}

async function reload() {
  try {
    const payload = await listEntries(MODULE_KEY, {})
    rows.value = payload.items
  } catch (error) {
    notice(error instanceof Error ? error.message : '交接待办读取失败', true)
  }
}

function openClaim(row: EntryRow) {
  claimOperator.value = ''
  claimRow.value = row
}

function openSegment(row: EntryRow) {
  segmentNote.value = ''
  segmentRow.value = row
}

function openReturn(row: EntryRow) {
  returnReason.value = ''
  returnRow.value = row
}

function openReceipt(row: EntryRow) {
  receiptRow.value = row
}

async function act(row: EntryRow, action: string, remark?: string) {
  acting.value = true
  try {
    const result = await runAction(MODULE_KEY, Number(row.id), action, remark)
    notice(result.message, !result.ok)
    await reload()
    return result.ok
  } catch (error) {
    notice(error instanceof Error ? error.message : '操作失败', true)
    return false
  } finally {
    acting.value = false
  }
}

async function submitClaim() {
  if (!claimRow.value) return
  const ok = await act(claimRow.value, '领取交接', claimOperator.value)
  if (ok) claimRow.value = null
}

async function submitSegment() {
  if (!segmentRow.value) return
  const ok = await act(segmentRow.value, '登记分段', segmentNote.value)
  if (ok) segmentRow.value = null
}

async function submitReturn() {
  if (!returnRow.value) return
  const ok = await act(returnRow.value, '退回补正', returnReason.value)
  if (ok) returnRow.value = null
}

async function resubmit(row: EntryRow) {
  await act(row, '补正重提')
}

async function completeHandoff(row: EntryRow) {
  await act(row, '完成交接')
}

watch(() => props.reloadToken, () => void reload())
onMounted(reload)
</script>
