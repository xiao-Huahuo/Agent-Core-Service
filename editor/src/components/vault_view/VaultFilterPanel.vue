<!--
  Password vault filter panel.

  Usage:
  Displays search, recent tags, type filters, and a compact CSS pie chart fed
  by VaultView list counts.
-->
<script setup lang="ts">
import IcIcon from '@/components/common/IcIcon.vue'
import type { VaultItemType, VaultTag } from '@/api/vault'

defineOptions({ name: 'VaultFilterPanel' })

const props = defineProps<{
  query: string
  tag: string
  itemType: string
  tags: VaultTag[]
  counts: Record<string, number>
}>()

const emit = defineEmits<{
  'update:query': [value: string]
  'update:tag': [value: string]
  'update:itemType': [value: string]
}>()

const typeLabels: Record<VaultItemType, string> = {
  login: '登录',
  card: '支付卡',
  identity: '身份',
  secure_note: '安全笔记',
}

const typeIcons: Record<VaultItemType, string> = { login: 'shield', card: 'dashboard', identity: 'fact-check', secure_note: 'edit-note' }
</script>

<template>
  <aside class="filter-panel">
    <div class="panel-heading"><IcIcon name="filter" :size="16" /><span>筛选</span></div>
    <label class="filter-search">
      <IcIcon name="search" :size="15" />
      <input
        :value="query"
        type="search"
        placeholder="搜索密码库"
        @input="emit('update:query', ($event.target as HTMLInputElement).value)"
      />
    </label>
    <p class="section-label">类型</p>
    <button class="type-filter" :class="{ active: !itemType }" type="button" @click="emit('update:itemType', '')"><IcIcon name="layers" :size="16" /><span>全部项目</span><small>{{ Object.values(counts).reduce((sum, count) => sum + count, 0) }}</small></button>
    <div class="tag-list">
      <button
        v-for="tagItem in tags.slice(0, 10)"
        :key="tagItem.tag_id"
        class="tag-pill"
        :class="{ active: tag === tagItem.name }"
        type="button"
        @click="emit('update:tag', tag === tagItem.name ? '' : tagItem.name)"
      >
        {{ tagItem.name }}
      </button>
    </div>
    <hr />
    <button
      v-for="(label, key) in typeLabels"
      :key="key"
      class="type-filter"
      :class="{ active: itemType === key }"
      type="button"
      @click="emit('update:itemType', itemType === key ? '' : key)"
    >
      <IcIcon :name="typeIcons[key]" :size="16" /><span>{{ label }}</span><small>{{ counts[key] || 0 }}</small>
    </button>
  </aside>
</template>

<style scoped>
.filter-panel {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  align-content: start;
  gap: var(--space-4);
  flex: 0 0 216px;
  width: 216px;
  min-width: 216px;
  max-width: 216px;
  overflow: hidden;
  margin: var(--space-12);
  padding: var(--space-12);
  border: 0;
  border-radius: 18px;
  background: var(--color-surface);
  box-shadow: 0 14px 36px rgba(0, 0, 0, 0.14);
  font-family: var(--font-ui);
  font-size: calc(14px * var(--font-scale));
}

.panel-heading {
  display: inline-flex;
  align-items: center;
  gap: var(--space-6);
  height: 28px;
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
  font-weight: 600;
}

.panel-heading svg { color: var(--color-primary); }
.section-label { margin: var(--space-8) var(--space-6) var(--space-2); color: var(--color-text-muted); font-size: calc(11px * var(--font-scale)); font-weight: 600; }

.filter-search {
  display: flex;
  align-items: center;
  gap: var(--space-6);
  min-width: 0;
  width: 100%;
  max-width: 100%;
  height: 30px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface);
  color: var(--color-text-muted);
}

.filter-search:focus-within {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.filter-search input {
  min-width: 0;
  width: 100%;
  flex: 1;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
}

.type-filter {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-8);
  height: 30px;
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--color-text-secondary);
  text-align: left;
  padding: 0 var(--space-6);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
}

.type-filter:hover,
.type-filter.active {
  background: var(--color-selection-blue-soft);
  color: var(--color-text);
}

.type-filter.active { color: var(--color-primary); }
.type-filter small { color: var(--color-text-muted); font-size: calc(11px * var(--font-scale)); }
hr { width: 100%; margin: var(--space-8) 0; border: 0; border-top: 1px solid var(--color-border); }

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-6);
}

.tag-pill {
  max-width: 140px;
  min-height: 24px;
  border: 0;
  border-radius: 999px;
  background: color-mix(in srgb, var(--color-primary) 20%, transparent);
  color: var(--color-primary);
  padding: 0 9px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
}

.tag-pill.active {
  background: var(--color-primary);
  color: #fff;
}

</style>
