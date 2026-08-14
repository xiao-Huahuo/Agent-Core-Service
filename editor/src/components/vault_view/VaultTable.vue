<!--
  Password vault table.

  Usage:
  Renders vault or trash entries, supports multi-select and row context menu
  through events handled by VaultView.
-->
<script setup lang="ts">
import type { VaultItem } from '@/api/vault'
import IcIcon from '@/components/common/IcIcon.vue'
import VaultAssetThumb from '@/components/vault_view/VaultAssetThumb.vue'

defineOptions({ name: 'VaultTable' })

defineProps<{
  token: string
  items: VaultItem[]
  selectedIds: Set<string>
  multiSelect: boolean
}>()

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
</script>

<template>
  <table class="vault-table">
    <thead>
      <tr>
        <th v-if="multiSelect"></th>
        <th aria-label="项目图标"></th>
        <th>项目名称</th>
        <th>密码类型</th>
        <th>创建时间</th>
        <th>拥有者</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="item in items"
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
        <td>{{ item.name }}</td>
        <td>{{ labels[item.item_type] }}</td>
        <td>{{ formatDate(item.created_at) }}</td>
        <td>{{ item.user_id }}</td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.vault-table {
  width: 100%;
  border-collapse: collapse;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
}

th,
td {
  height: 42px;
  border-bottom: 1px solid var(--color-border);
  padding: 0 12px;
  text-align: left;
}

th {
  color: var(--color-text-muted);
  font-weight: 700;
}

tbody tr {
  cursor: default;
}

tbody tr:hover,
tbody tr.selected {
  background: var(--color-primary-softer);
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
</style>
