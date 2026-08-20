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

const props = withDefaults(defineProps<{
  query: string
  tag: string
  itemType: string
  tags: VaultTag[]
  counts: Record<string, number>
  title?: string
  titleIcon?: string
}>(), {
  title: '密码库',
  titleIcon: 'shield',
})

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
    <div class="sidebar-title"><IcIcon :name="titleIcon" :size="17" /><span>{{ title }}</span></div>
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
  display: flex;
  flex-direction: column;
  align-content: start;
  gap: var(--space-10);
  min-width: 0;
  min-height: 0;
  overflow: hidden;
  margin: var(--space-12);
  padding: var(--space-16) var(--space-12);
  border: 1px solid var(--color-border);
  border-radius: 28px;
  background: var(--color-surface);
  box-shadow: 0 0 0 4px var(--library-form-ring);
  font-family: var(--font-ui);
  font-size: calc(14px * var(--font-scale));
}

.sidebar-title {
  display: flex;
  align-items: center;
  gap: var(--space-8);
  min-height: 32px;
  padding: 0 var(--space-10);
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
  font-weight: 700;
}

.sidebar-title svg { color: var(--color-primary); }
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
  position: relative;
  display: grid;
  grid-template-columns: 20px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--space-8);
  width: 100%;
  min-height: 36px;
  overflow: hidden;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--color-text-secondary);
  text-align: left;
  padding: 0 var(--space-10);
  font: inherit;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
  transition:
    background-color 150ms ease,
    color 150ms ease;
}

.type-filter::before {
  position: absolute;
  top: 7px;
  bottom: 7px;
  left: 0;
  width: 3px;
  border-radius: 999px;
  background: var(--color-primary);
  content: '';
  transform: scaleY(0);
  transition: transform 180ms cubic-bezier(0.23, 1, 0.32, 1);
}

.type-filter:hover,
.type-filter.active {
  background: var(--color-primary-soft);
  color: var(--color-text);
}

.type-filter.active { color: var(--color-primary); }
.type-filter.active::before { transform: scaleY(1); }
.type-filter small { color: var(--color-text-muted); font-size: calc(11px * var(--font-scale)); }
hr { width: 100%; margin: var(--space-8) 0; border: 0; border-top: 1px solid var(--color-border); }

.tag-list {
  display: grid;
  gap: var(--space-6);
}

.tag-pill {
  position: relative;
  display: flex;
  align-items: center;
  width: 100%;
  min-height: 36px;
  overflow: hidden;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: var(--color-tag-pill-text);
  padding: 0 var(--space-10);
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  transition:
    background-color 150ms ease,
    color 150ms ease;
}

.tag-pill::before {
  position: absolute;
  top: 7px;
  bottom: 7px;
  left: 0;
  width: 3px;
  border-radius: 999px;
  background: var(--color-primary);
  content: '';
  transform: scaleY(0);
  transition: transform 180ms cubic-bezier(0.23, 1, 0.32, 1);
}

.tag-pill:hover,
.tag-pill.active {
  background: var(--color-primary-soft);
  color: var(--color-tag-pill-text);
}

.tag-pill.active::before { transform: scaleY(1); }

@media (max-width: 860px) {
  .filter-panel {
    flex-direction: row;
    overflow-x: auto;
    margin: var(--space-8);
    padding: var(--space-8);
    gap: var(--space-8);
  }

  .sidebar-title,
  .section-label,
  .filter-panel hr {
    display: none;
  }

  .filter-search {
    flex: 0 0 164px;
  }

  .tag-list {
    display: flex;
  }

  .tag-pill,
  .type-filter {
    width: auto;
    min-width: max-content;
  }
}

</style>
