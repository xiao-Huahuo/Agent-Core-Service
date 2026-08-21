<!--
  AgentConfig 全局常量只读注册表。

  使用说明:
  配置类对应工具注册表的分类,常量对应工具条目,右侧展示选中常量的介绍、
  类型与完整值。组件与 ToolRegistryPanel 共用 registry-panel.css 规格。
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchGlobalConstants, type GlobalConfigInfo, type GlobalConstantInfo } from '@/api/debug'
import IcIcon from '@/components/common/IcIcon.vue'

interface SelectedConstant {
  config: GlobalConfigInfo
  constant: GlobalConstantInfo
}

const configs = ref<GlobalConfigInfo[]>([])
const constantCount = ref(0)
const selectedId = ref('')
const query = ref('')
const loading = ref(false)
const errorText = ref('')
const collapsedCategories = ref<Set<string>>(new Set())

/** 按配置类、常量名、说明、类型和值过滤注册表,保持配置类分组结构。 */
const filteredConfigs = computed<GlobalConfigInfo[]>(() => {
  const normalizedQuery = query.value.trim().toLowerCase()
  if (!normalizedQuery) return configs.value
  return configs.value
    .map(config => {
      const groupMatches = `${config.key} ${config.name} ${config.description}`
        .toLowerCase()
        .includes(normalizedQuery)
      const constants = groupMatches
        ? config.constants
        : config.constants.filter(constant => constantSearchText(constant).includes(normalizedQuery))
      return constants.length > 0 ? { ...config, constants } : null
    })
    .filter((config): config is GlobalConfigInfo => config !== null)
})

const visibleConstantCount = computed(() => {
  return filteredConfigs.value.reduce((total, config) => total + config.constants.length, 0)
})

/** 解析选中常量；搜索隐藏当前项时与工具注册表一致回退到首个可见条目。 */
const selectedConstant = computed<SelectedConstant | null>(() => {
  for (const config of filteredConfigs.value) {
    const constant = config.constants.find(item => constantId(config, item) === selectedId.value)
    if (constant) return { config, constant }
  }
  const config = filteredConfigs.value[0]
  const constant = config?.constants[0]
  return config && constant ? { config, constant } : null
})

/** 加载当前进程的只读 AgentConfig 快照。 */
async function loadConstants() {
  loading.value = true
  errorText.value = ''
  try {
    const payload = await fetchGlobalConstants()
    configs.value = payload.configs ?? []
    constantCount.value = payload.constant_count ?? 0
    const firstConfig = configs.value[0]
    const firstConstant = firstConfig?.constants[0]
    if (!selectedId.value && firstConfig && firstConstant) {
      selectedId.value = constantId(firstConfig, firstConstant)
    }
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : '全局常量加载失败'
  } finally {
    loading.value = false
  }
}

/** 展开或折叠一个 AgentConfig 配置类。 */
function toggleCategory(category: string) {
  const next = new Set(collapsedCategories.value)
  if (next.has(category)) next.delete(category)
  else next.add(category)
  collapsedCategories.value = next
}

/** 选择单个常量进入右侧详情。 */
function selectConstant(config: GlobalConfigInfo, constant: GlobalConstantInfo) {
  selectedId.value = constantId(config, constant)
}

/** 生成配置类内稳定且唯一的常量标识。 */
function constantId(config: GlobalConfigInfo, constant: GlobalConstantInfo): string {
  return `${config.key}.${constant.name}`
}

/** 将任意 JSON 值格式化为只读代码文本。 */
function formatValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (value === null) return 'null'
  if (typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

/** 生成详情元数据行中的紧凑值预览。 */
function valuePreview(value: unknown): string {
  const normalizedValue = formatValue(value).replace(/\s+/g, ' ').trim()
  return normalizedValue.length > 72 ? `${normalizedValue.slice(0, 72)}…` : normalizedValue
}

/** 汇总单个常量的全部可检索文本。 */
function constantSearchText(constant: GlobalConstantInfo): string {
  return `${constant.name} ${constant.type} ${constant.description} ${formatValue(constant.value)}`.toLowerCase()
}

onMounted(() => {
  void loadConstants()
})
</script>

<template>
  <div class="global-constants-panel registry-panel">
    <section class="registry-card">
      <div class="panel-heading registry-heading">
        <div class="title-summary">
          <h2>全局常量</h2>
          <span>{{ configs.length }} configs</span>
          <span>{{ constantCount }} constants</span>
          <span>{{ visibleConstantCount }} visible</span>
        </div>
        <div class="registry-search">
          <IcIcon name="search" :size="14" />
          <input v-model="query" type="text" placeholder="搜索常量" />
        </div>
        <button class="icon-button" type="button" title="刷新" :disabled="loading" @click="loadConstants">
          <IcIcon name="refresh" :size="15" />
        </button>
      </div>

      <div class="panel-surface">
        <p v-if="errorText" class="error-line">{{ errorText }}</p>

        <div class="registry-grid">
          <aside class="tool-list" aria-label="AgentConfig 常量列表">
            <div v-if="loading" class="empty-state"><span>$ 正在读取</span></div>
            <template v-for="config in filteredConfigs" :key="config.key">
              <div class="category-header" @click="toggleCategory(config.key)">
                <IcIcon
                  name="chevron-down"
                  :size="14"
                  class="collapse-icon"
                  :class="{ collapsed: collapsedCategories.has(config.key) }"
                />
                <span class="category-name">{{ config.name }}</span>
                <span class="category-count">{{ config.constants.length }}</span>
              </div>
              <div v-if="!collapsedCategories.has(config.key)" class="category-tools">
                <div
                  v-for="constant in config.constants"
                  :key="constant.name"
                  class="tool-list-item"
                  :class="{ active: selectedConstant && constantId(config, constant) === constantId(selectedConstant.config, selectedConstant.constant) }"
                >
                  <button class="tool-row" type="button" @click="selectConstant(config, constant)">
                    <span class="tool-name">{{ constant.name }}</span>
                    <span class="tool-meta">{{ constant.type }}</span>
                  </button>
                </div>
              </div>
            </template>
            <div v-if="!loading && filteredConfigs.length === 0" class="empty-state">
              <span>$ 没有匹配的常量</span>
            </div>
          </aside>

          <main class="tool-detail">
            <div v-if="loading" class="empty-state"><span>$ 正在读取最终全局常量</span></div>
            <template v-else-if="selectedConstant">
              <div class="detail-title">
                <span class="detail-display">{{ selectedConstant.constant.name }}</span>
                <code>AgentConfig.{{ selectedConstant.config.name }}.{{ selectedConstant.constant.name }}</code>
              </div>
              <p class="detail-description">{{ selectedConstant.constant.description || '无说明' }}</p>
              <div class="arg-table">
                <div class="arg-row arg-head">
                  <span>配置类</span>
                  <span>类型</span>
                  <span>当前值</span>
                </div>
                <div class="arg-row">
                  <span class="arg-name">{{ selectedConstant.config.name }}</span>
                  <span>{{ selectedConstant.constant.type }}</span>
                  <span :title="formatValue(selectedConstant.constant.value)">
                    {{ valuePreview(selectedConstant.constant.value) }}
                  </span>
                  <p class="arg-desc">{{ selectedConstant.config.description || '无说明' }}</p>
                </div>
              </div>
              <pre class="schema-block">{{ formatValue(selectedConstant.constant.value) }}</pre>
            </template>
            <div v-else class="empty-state"><span>$ 全局常量为空</span></div>
          </main>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped src="@/assets/registry-panel.css"></style>
