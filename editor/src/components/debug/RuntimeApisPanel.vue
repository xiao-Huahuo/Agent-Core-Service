<!--
  Runtime API registry panel.

  Usage:
  Renders backend-reported REST routes and gRPC methods. Every detail comes
  from FastAPI OpenAPI data or protobuf descriptors returned by the backend.
-->
<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ChevronDown, RefreshCw } from 'lucide-vue-next'

import { fetchRuntimeApis, type RuntimeApiInfo, type RuntimeSchemaNode } from '@/api/debug'
import SchemaTree from '@/components/debug/SchemaTree.vue'

const apis = ref<RuntimeApiInfo[]>([])
const loading = ref(false)
const errorText = ref('')
const activeProtocol = ref<'rest' | 'grpc'>('rest')
const expandedKeys = ref<Set<string>>(new Set())

const restApis = computed(() => apis.value.filter((api) => api.kind === 'rest'))
const grpcApis = computed(() => apis.value.filter((api) => api.kind === 'grpc'))
const visibleApis = computed(() => activeProtocol.value === 'rest' ? restApis.value : grpcApis.value)

function apiKey(api: RuntimeApiInfo): string {
  return `${api.kind}:${api.method}:${api.path}`
}

function toggleApi(api: RuntimeApiInfo) {
  const key = apiKey(api)
  const next = new Set(expandedKeys.value)
  if (next.has(key)) {
    next.delete(key)
  } else {
    next.add(key)
  }
  expandedKeys.value = next
}

function isExpanded(api: RuntimeApiInfo): boolean {
  return expandedKeys.value.has(apiKey(api))
}

function streamLabel(api: RuntimeApiInfo): string {
  if (api.client_streaming && api.server_streaming) return 'bidi stream'
  if (api.server_streaming) return 'server stream'
  if (api.client_streaming) return 'client stream'
  return api.method
}

function contentTypes(content?: Record<string, unknown>): string {
  const keys = Object.keys(content ?? {})
  return keys.length > 0 ? keys.join(', ') : 'none'
}

function schemaNodes(node?: RuntimeSchemaNode | null): RuntimeSchemaNode[] {
  return node ? [node] : []
}

function contentSchemaType(content?: Record<string, { schema_tree?: RuntimeSchemaNode | null }>): string {
  const node = Object.values(content ?? {}).find((item) => item.schema_tree)?.schema_tree
  return node?.type ?? '-'
}

async function loadApis() {
  loading.value = true
  errorText.value = ''
  try {
    const payload = await fetchRuntimeApis()
    apis.value = payload.apis
  } catch (error) {
    errorText.value = error instanceof Error ? error.message : 'API 信息加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void loadApis()
})
</script>

<template>
  <section class="runtime-apis-panel">
    <div class="api-card">
      <header class="panel-heading api-heading">
        <div class="title-summary">
          <h2>API</h2>
          <span>{{ visibleApis.length }} / {{ apis.length }} endpoints</span>
        </div>
        <div class="protocol-tabs" role="tablist" aria-label="API protocol">
          <button class="protocol-tab" :class="{ active: activeProtocol === 'rest' }" type="button" @click="activeProtocol = 'rest'">
            REST
          </button>
          <button class="protocol-tab" :class="{ active: activeProtocol === 'grpc' }" type="button" @click="activeProtocol = 'grpc'">
            gRPC
          </button>
        </div>
        <button class="icon-button" type="button" title="刷新 API 信息" :disabled="loading" @click="loadApis">
          <RefreshCw :size="15" />
        </button>
      </header>

      <div class="panel-surface">
        <p v-if="errorText" class="error-line">{{ errorText }}</p>
        <div v-if="loading" class="empty-state">$ 正在读取后端 API</div>
        <div v-else class="api-table">
          <div class="api-row api-head">
            <span></span>
            <span>接口</span>
            <span>方法</span>
            <span>路径</span>
            <span>请求</span>
            <span>响应</span>
            <span>状态</span>
          </div>

          <template v-for="api in visibleApis" :key="apiKey(api)">
            <button class="api-row api-button" type="button" @click="toggleApi(api)">
              <ChevronDown class="chevron" :class="{ expanded: isExpanded(api) }" :size="14" />
              <span class="api-name">{{ api.name }}</span>
              <code>{{ streamLabel(api) }}</code>
              <code class="path-cell">{{ api.path }}</code>
              <code class="type-cell">{{ api.request }}</code>
              <code class="type-cell">{{ api.response }}</code>
              <span class="status-pill" :class="api.status">{{ api.status }}</span>
            </button>

            <Transition name="expand">
              <div v-if="isExpanded(api)" class="api-detail">
                <div class="detail-grid">
                  <div class="detail-item">
                    <span>服务</span>
                    <code>{{ api.service }}</code>
                  </div>
                  <div class="detail-item">
                    <span>调用目标</span>
                    <code>{{ api.call?.url || api.call?.method || api.path }}</code>
                  </div>
                  <div v-if="api.operation_id" class="detail-item">
                    <span>Operation ID</span>
                    <code>{{ api.operation_id }}</code>
                  </div>
                  <div v-if="api.tags?.length" class="detail-item">
                    <span>Tags</span>
                    <code>{{ api.tags.join(', ') }}</code>
                  </div>
                </div>

                <p v-if="api.summary || api.description" class="summary-line">
                  {{ api.summary || api.description }}
                </p>

                <template v-if="api.kind === 'rest'">
                  <section class="detail-section">
                    <h4>参数</h4>
                    <div v-if="api.parameters?.length" class="mini-table parameter-table">
                      <div class="mini-row mini-head">
                        <span>名称</span>
                        <span>位置</span>
                        <span>必填</span>
                        <span>类型</span>
                        <span>说明</span>
                      </div>
                      <div v-for="parameter in api.parameters" :key="`${parameter.in}:${parameter.name}`" class="mini-row">
                        <code>{{ parameter.name }}</code>
                        <span>{{ parameter.in }}</span>
                        <span>{{ parameter.required ? 'yes' : 'no' }}</span>
                        <code>{{ parameter.schema_tree?.type || '-' }}</code>
                        <span>{{ parameter.description || '-' }}</span>
                      </div>
                    </div>
                    <div v-for="parameter in api.parameters?.filter((item) => item.schema_tree?.children?.length)" :key="`tree:${parameter.in}:${parameter.name}`" class="parameter-schema-block">
                      <h5>{{ parameter.name }}</h5>
                      <SchemaTree :nodes="schemaNodes(parameter.schema_tree)" />
                    </div>
                    <div v-if="!api.parameters?.length" class="empty-detail">无参数</div>
                  </section>

                  <section class="detail-section">
                    <h4>请求体</h4>
                    <div v-if="api.request_body" class="detail-grid">
                      <div class="detail-item">
                        <span>Content-Type</span>
                        <code>{{ contentTypes(api.request_body.content) }}</code>
                      </div>
                      <div class="detail-item">
                        <span>必填</span>
                        <code>{{ api.request_body.required ? 'yes' : 'no' }}</code>
                      </div>
                    </div>
                    <div v-else class="empty-detail">无请求体</div>
                    <SchemaTree v-if="api.request_schema_tree" :nodes="schemaNodes(api.request_schema_tree)" />
                  </section>

                  <section class="detail-section">
                    <h4>返回</h4>
                    <div class="mini-table response-table">
                      <div class="mini-row mini-head">
                        <span>状态码</span>
                        <span>Content-Type</span>
                        <span>Schema</span>
                        <span>说明</span>
                      </div>
                      <div v-for="(response, status) in api.responses" :key="status" class="mini-row">
                        <code>{{ status }}</code>
                        <span>{{ contentTypes(response.content) }}</span>
                        <code>{{ contentSchemaType(response.content) }}</code>
                        <span>{{ response.description || '-' }}</span>
                      </div>
                    </div>
                    <SchemaTree v-if="api.response_schema_tree?.length" :nodes="api.response_schema_tree" />
                  </section>
                </template>

                <template v-else>
                  <section class="detail-section">
                    <h4>gRPC 调用</h4>
                    <div class="detail-grid">
                      <div class="detail-item">
                        <span>Target</span>
                        <code>{{ api.call?.target || api.base_url }}</code>
                      </div>
                      <div class="detail-item">
                        <span>Method</span>
                        <code>{{ api.call?.method || api.path }}</code>
                      </div>
                      <div class="detail-item">
                        <span>Streaming</span>
                        <code>{{ streamLabel(api) }}</code>
                      </div>
                    </div>
                  </section>

                  <section class="detail-section">
                    <h4>请求消息 {{ api.input_type }}</h4>
                    <SchemaTree v-if="api.input_schema_tree" :nodes="schemaNodes(api.input_schema_tree)" />
                  </section>

                  <section class="detail-section">
                    <h4>返回消息 {{ api.output_type }}</h4>
                    <SchemaTree v-if="api.output_schema_tree" :nodes="schemaNodes(api.output_schema_tree)" />
                  </section>
                </template>
              </div>
            </Transition>
          </template>

          <div v-if="visibleApis.length === 0" class="empty-state">$ 没有后端 API 信息</div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.runtime-apis-panel {
  display: flex;
  flex: 1;
  width: 100%;
  height: 100%;
  min-height: 0;
  min-width: 0;
  padding: var(--space-10);
  overflow: hidden;
}

.api-card {
  display: flex;
  flex: 1;
  width: 100%;
  min-height: 0;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-6);
}

.panel-heading {
  min-height: 24px;
  padding: 0 2px;
}

.api-heading {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: var(--space-8);
}

.panel-surface {
  display: flex;
  flex: 1;
  min-height: 0;
  min-width: 0;
  flex-direction: column;
  overflow: hidden;
  background: transparent;
}

.title-summary {
  display: flex;
  align-items: baseline;
  gap: var(--space-8);
  min-width: 0;
  font-family: var(--font-ui);
}

.title-summary h2 {
  margin: 0;
  color: var(--color-text-primary);
  font-size: var(--font-size-sm);
  font-weight: var(--font-weight-semibold);
}

.title-summary span,
.error-line,
.empty-state,
.api-row,
.api-detail,
.protocol-tab {
  font-family: var(--font-ui);
}

.title-summary span {
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.protocol-tabs {
  display: inline-flex;
  gap: 2px;
  padding: 2px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface-raised);
}

.protocol-tab {
  min-width: 56px;
  height: 24px;
  border: 1px solid transparent;
  border-radius: 999px;
  background: transparent;
  color: var(--color-text-tertiary);
  font-size: var(--font-size-xs);
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.protocol-tab:hover {
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
}

.protocol-tab.active {
  color: var(--color-primary);
  border-color: color-mix(in srgb, var(--color-primary) 32%, var(--color-border));
  background: var(--color-primary-soft);
}

.icon-button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 30px;
  height: 30px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  transition: color var(--transition-fast), border-color var(--transition-fast), background var(--transition-fast);
}

.icon-button:hover:not(:disabled) {
  color: var(--color-primary);
  border-color: color-mix(in srgb, var(--color-primary) 32%, var(--color-border));
  background: var(--color-primary-soft);
}

.icon-button:disabled {
  cursor: default;
  opacity: 0.45;
}

.error-line {
  margin: var(--space-10);
  color: var(--color-danger);
  font-size: var(--font-size-xs);
}

.empty-state {
  padding: var(--space-16);
  color: var(--color-text-muted);
  font-size: var(--font-size-xs);
}

.api-table {
  display: grid;
  flex: 1;
  min-height: 0;
  min-width: 0;
  align-content: start;
  padding: 0;
  border-radius: 8px;
  overflow: auto;
}

.api-row {
  display: grid;
  grid-template-columns: 24px minmax(150px, 1fr) 112px minmax(240px, 1.4fr) minmax(160px, 1fr) minmax(120px, 0.8fr) 96px;
  gap: var(--space-8);
  align-items: center;
  min-height: 34px;
  padding: 0 var(--space-10);
  border: 1px solid var(--color-border);
  border-bottom: 0;
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
  text-align: left;
}

.api-row:last-child {
  border-bottom: 1px solid var(--color-border);
  border-bottom-right-radius: 8px;
  border-bottom-left-radius: 8px;
}

.api-head {
  position: sticky;
  top: 0;
  z-index: 2;
  color: var(--color-text-muted);
  background: var(--color-surface-raised);
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
}

.api-button {
  width: 100%;
  background: transparent;
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.api-button:hover {
  background: var(--color-bg-hover);
}

.chevron {
  color: var(--color-text-muted);
  transition: transform var(--transition-fast);
}

.chevron.expanded {
  transform: rotate(180deg);
}

.api-name {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

code {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  font-family: var(--font-text);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.path-cell {
  color: var(--color-primary);
}

.type-cell {
  color: var(--color-text-secondary);
}

.status-pill {
  width: fit-content;
  padding: 2px 8px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  color: var(--color-text-muted);
}

.status-pill.running {
  border-color: color-mix(in srgb, var(--color-primary) 36%, var(--color-border));
  color: var(--color-primary);
}

.api-detail {
  display: flex;
  flex-direction: column;
  gap: var(--space-12);
  padding: var(--space-12);
  border: 1px solid var(--color-border);
  border-bottom: 0;
  background: var(--color-surface-raised);
  color: var(--color-text-secondary);
  font-size: var(--font-size-xs);
}

.api-detail:last-child {
  border-bottom: 1px solid var(--color-border);
  border-bottom-right-radius: 8px;
  border-bottom-left-radius: 8px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-8);
}

.detail-item {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 3px;
}

.detail-item span,
.detail-section h4 {
  color: var(--color-text-muted);
}

.summary-line {
  margin: 0;
  color: var(--color-text-secondary);
}

.detail-section {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-6);
}

.detail-section h4 {
  margin: 0;
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
}

.parameter-schema-block {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: var(--space-6);
}

.parameter-schema-block h5 {
  margin: 0;
  color: var(--color-text-muted);
  font-family: var(--font-ui);
  font-size: var(--font-size-xs);
  font-weight: var(--font-weight-semibold);
}

.mini-table {
  display: grid;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  overflow: hidden;
}

.mini-row {
  display: grid;
  gap: var(--space-8);
  align-items: center;
  min-height: 30px;
  padding: 0 var(--space-8);
  border-bottom: 1px solid var(--color-border);
}

.mini-row:last-child {
  border-bottom: 0;
}

.mini-head {
  color: var(--color-text-muted);
  background: var(--color-surface-raised);
}

.parameter-table .mini-row {
  grid-template-columns: minmax(120px, 1fr) 80px 60px minmax(120px, 1fr) minmax(160px, 1.2fr);
}

.response-table .mini-row {
  grid-template-columns: 80px minmax(160px, 1fr) minmax(180px, 1fr) minmax(180px, 1.2fr);
}

.empty-detail {
  color: var(--color-text-muted);
}

.expand-enter-active,
.expand-leave-active {
  overflow: hidden;
  transition: opacity 160ms ease, transform 160ms ease;
}

.expand-enter-from,
.expand-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}

@media (max-width: 1100px) {
  .api-row {
    grid-template-columns: 24px minmax(130px, 1fr) 96px minmax(180px, 1.3fr) 84px;
  }

  .api-row code:nth-child(5),
  .api-row code:nth-child(6),
  .api-head span:nth-child(5),
  .api-head span:nth-child(6) {
    display: none;
  }
}
</style>

