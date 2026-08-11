<!--
  Password vault filter panel.

  Usage:
  Displays search, recent tags, type filters, and a compact CSS pie chart fed
  by VaultView list counts.
-->
<script setup lang="ts">
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
  create: []
}>()

const typeLabels: Record<VaultItemType, string> = {
  login: '登录',
  card: '支付卡',
  identity: '身份',
  secure_note: '安全笔记',
}

function pieStyle() {
  const total = Object.values(props.counts).reduce((sum, value) => sum + Number(value || 0), 0) || 1
  const login = Math.round(((props.counts.login || 0) / total) * 100)
  const card = login + Math.round(((props.counts.card || 0) / total) * 100)
  const identity = card + Math.round(((props.counts.identity || 0) / total) * 100)
  return {
    background: `conic-gradient(var(--color-primary) 0 ${login}%, var(--color-accent) ${login}% ${card}%, var(--color-success) ${card}% ${identity}%, var(--color-warning) ${identity}% 100%)`,
  }
}
</script>

<template>
  <aside class="filter-panel">
    <h3>筛选</h3>
    <input
      class="search-pill"
      type="search"
      :value="query"
      placeholder="搜索"
      @input="emit('update:query', ($event.target as HTMLInputElement).value)"
    />
    <button class="new-password-btn" type="button" @click="emit('create')">+ New Password</button>
    <hr />
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
      {{ label }}
    </button>
    <hr />
    <div class="pie-row">
      <div class="pie" :style="pieStyle()"></div>
      <div class="pie-legend">
        <span v-for="(label, key) in typeLabels" :key="key">{{ label }} {{ counts[key] || 0 }}</span>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.filter-panel {
  display: grid;
  align-content: start;
  gap: 12px;
  flex: 0 0 25%;
  min-width: 240px;
  max-width: 340px;
  margin: 14px;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
  box-shadow: var(--shadow-window);
}

h3 {
  margin: 0;
  color: var(--color-text);
  font-size: calc(16px * var(--font-scale));
}

.search-pill,
.new-password-btn,
.type-filter {
  height: 34px;
  border-radius: 999px;
}

.search-pill {
  border: 1px solid var(--color-border);
  background: var(--color-canvas);
  color: var(--color-text);
  padding: 0 12px;
  outline: 0;
}

.new-password-btn,
.type-filter {
  border: 0;
  background: transparent;
  color: var(--color-text-secondary);
  text-align: left;
  padding: 0 12px;
  cursor: pointer;
}

.new-password-btn:hover,
.type-filter:hover,
.type-filter.active {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

hr {
  width: 100%;
  border: 0;
  border-top: 1px solid var(--color-border);
}

.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-pill {
  max-width: 140px;
  min-height: 26px;
  border: 0;
  border-radius: 999px;
  background: var(--color-primary-soft);
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

.pie-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.pie {
  width: 74px;
  height: 74px;
  border-radius: 50%;
  border: 6px solid var(--color-canvas);
}

.pie-legend {
  display: grid;
  gap: 4px;
  color: var(--color-text-muted);
  font-size: calc(11px * var(--font-scale));
}
</style>
