<!--
  Password vault table.

  Usage:
  Renders vault or trash entries, supports multi-select and row context menu
  through events handled by VaultView.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { VaultItem } from '@/api/vault'
import IcIcon from '@/components/common/IcIcon.vue'
import VaultAssetThumb from '@/components/vault_view/VaultAssetThumb.vue'

defineOptions({ name: 'VaultTable' })

const props = defineProps<{
  token: string
  items: VaultItem[]
  selectedIds: Set<string>
  multiSelect: boolean
}>()

const pageIndex = ref(0)
const pageSize = ref(20)

const pageCount = computed(() => Math.max(1, Math.ceil(props.items.length / pageSize.value)))
const visibleItems = computed(() => {
  const start = pageIndex.value * pageSize.value
  return props.items.slice(start, start + pageSize.value)
})
const rangeStart = computed(() => (props.items.length ? pageIndex.value * pageSize.value + 1 : 0))
const rangeEnd = computed(() => Math.min((pageIndex.value + 1) * pageSize.value, props.items.length))

watch(pageSize, () => { pageIndex.value = 0 })
watch(() => props.items.length, () => {
  pageIndex.value = Math.min(pageIndex.value, pageCount.value - 1)
})

const emit = defineEmits<{
  open: [item: VaultItem]
  toggle: [item: VaultItem]
  context: [event: MouseEvent, item: VaultItem]
}>()

const labels = {
  login: '登录',
  card: '支付卡',
  identity: '身份',
  secure_note: '安全笔记',
}

// 与项目其他区域共用已下载的 SVG 图标，避免密码库单独使用 emoji。
const typeIcons: Record<VaultItem['item_type'], string> = {
  login: 'shield',
  card: 'dashboard',
  identity: 'fact-check',
  secure_note: 'edit-note',
}

function iconFor(type: VaultItem['item_type']): string {
  return typeIcons[type]
}

function firstAssetId(item: VaultItem): string {
  const assetIds = item.fields.asset_ids
  if (!Array.isArray(assetIds)) return ''
  const first = assetIds.find((assetId) => typeof assetId === 'string')
  return first ?? ''
}

function formatDate(raw: string): string {
  const date = new Date(raw)
  if (Number.isNaN(date.getTime())) return raw.slice(0, 16)
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`
}

function goToPage(nextPage: number): void {
  pageIndex.value = Math.max(0, Math.min(nextPage, pageCount.value - 1))
}
</script>

<template>
  <div class="vault-table-view">
    <div class="vault-table-shell" :class="{ empty: !visibleItems.length }">
      <table class="vault-table">
        <thead>
          <tr>
            <th v-if="multiSelect" aria-label="选择"></th>
            <th aria-label="项目图标"></th>
            <th>项目名称</th>
            <th>密码类型</th>
            <th>创建时间</th>
            <th>拥有者</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in visibleItems"
            :key="item.item_id"
            :class="{ selected: selectedIds.has(item.item_id) }"
            @dblclick="emit('open', item)"
            @contextmenu.prevent="emit('context', $event, item)"
          >
            <td v-if="multiSelect">
              <input type="checkbox" :checked="selectedIds.has(item.item_id)" @change="emit('toggle', item)" />
            </td>
            <td>
              <VaultAssetThumb
                v-if="firstAssetId(item)"
                :token="token"
                :asset-id="firstAssetId(item)"
                :fallback-icon="iconFor(item.item_type)"
              />
              <span v-else class="type-icon" aria-hidden="true">
                <IcIcon :name="iconFor(item.item_type)" :size="18" />
              </span>
            </td>
            <td class="name-cell">{{ item.name }}</td>
            <td>{{ labels[item.item_type] }}</td>
            <td>{{ formatDate(item.created_at) }}</td>
            <td>{{ item.user_id }}</td>
          </tr>
        </tbody>
      </table>
      <div v-if="!visibleItems.length" class="empty-state">暂无密码库项目</div>
    </div>
    <footer class="table-footer">
      <p class="table-range" aria-live="polite">
        <span>{{ rangeStart }}-{{ rangeEnd }}</span>
        /
        <span>{{ items.length }}</span>
      </p>
      <div class="table-pagination" aria-label="表格分页">
        <button type="button" aria-label="上一页" :disabled="pageIndex === 0" @click="goToPage(pageIndex - 1)">
          <IcIcon name="arrow-left" :size="16" />
        </button>
        <button type="button" aria-label="下一页" :disabled="pageIndex >= pageCount - 1" @click="goToPage(pageIndex + 1)">
          <IcIcon name="arrow-right" :size="16" />
        </button>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.vault-table-view {
  display: flex;
  min-height: 100%;
  flex-direction: column;
  gap: var(--space-12);
}

.vault-table-shell {
  display: flex;
  min-height: 0;
  flex: 1 1 auto;
  flex-direction: column;
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: 18px;
  background: var(--color-surface);
}

.vault-table {
  width: 100%;
  height: 100%;
  border-collapse: separate;
  border-spacing: 0;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
}

.vault-table-shell.empty .vault-table {
  flex: 0 0 auto;
  height: auto;
}

th,
td {
  height: 38px;
  border-bottom: 1px solid var(--color-border);
  padding: 0 var(--space-12);
  text-align: left;
}

th {
  height: 44px;
  background: var(--color-surface);
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
  font-weight: 700;
}

th:first-child,
td:first-child {
  padding-left: var(--space-16);
}

th:last-child,
td:last-child {
  padding-right: var(--space-16);
}

tbody tr {
  cursor: pointer;
  transition: background-color 150ms ease;
}

tbody tr:hover,
tbody tr.selected {
  background: var(--color-primary-softer);
}

.name-cell {
  color: var(--color-text);
  font-weight: 600;
}

input[type='checkbox'] {
  width: 16px;
  height: 16px;
  accent-color: var(--color-primary);
}

.type-icon {
  display: inline-grid;
  place-items: center;
  width: 28px;
  height: 28px;
  border-radius: 8px;
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.empty-state {
  display: grid;
  flex: 1 1 auto;
  min-height: 0;
  place-items: center;
  padding: var(--space-16);
  color: var(--color-text-muted);
  text-align: center;
}

.table-footer {
  display: flex;
  align-items: center;
  gap: var(--space-12);
  min-height: 36px;
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

.table-pagination {
  display: inline-flex;
  align-items: center;
  gap: var(--space-6);
}

.table-range {
  flex: 1 1 auto;
  margin: 0;
  text-align: right;
  white-space: nowrap;
}

.table-range span {
  color: var(--color-text);
}

.table-pagination button {
  display: inline-grid;
  place-items: center;
  width: 36px;
  height: 36px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  cursor: pointer;
}

.table-pagination button:hover:not(:disabled) {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.table-pagination button:disabled {
  cursor: default;
  opacity: 0.4;
}
</style>
