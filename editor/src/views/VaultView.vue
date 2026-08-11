<!--
  Password vault page.

  Usage:
  Fourth knowledge-menu surface for a Bitwarden-like vault. It keeps a vault
  token in sessionStorage for the 30-minute unlock window and clears only that
  token when the user locks the vault.
-->
<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

import {
  createVaultItem,
  exportVaultItems,
  getVaultItem,
  getVaultStatus,
  importVaultItems,
  listVaultItems,
  listVaultTags,
  lockVaultToken,
  purgeVaultItems,
  restoreVaultItems,
  setupVault,
  trashVaultItems,
  unlockVault,
  updateVaultItem,
  type VaultItem,
  type VaultItemType,
  type VaultTag,
} from '@/api/vault'
import VaultFilterPanel from '@/components/vault_view/VaultFilterPanel.vue'
import VaultItemEditor from '@/components/vault_view/VaultItemEditor.vue'
import VaultTable from '@/components/vault_view/VaultTable.vue'
import VaultUnlockPanel from '@/components/vault_view/VaultUnlockPanel.vue'
import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'

defineOptions({ name: 'VaultView' })

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()

const configured = ref(false)
const loading = ref(false)
const token = ref('')
const expiresAt = ref('')
const items = ref<VaultItem[]>([])
const tags = ref<VaultTag[]>([])
const query = ref('')
const selectedTag = ref('')
const selectedType = ref('')
const inTrash = ref(false)
const multiSelect = ref(false)
const selectedIds = ref<Set<string>>(new Set())
const editorOpen = ref(false)
const editingItem = ref<VaultItem | null>(null)
const contextItem = ref<VaultItem | null>(null)
const contextOpen = ref(false)
const contextStyle = ref({ left: '0px', top: '0px' })
const typeCounts = ref<Record<string, number>>({ login: 0, card: 0, identity: 0, secure_note: 0 })

const tokenKey = computed(() => `metaweave_vault_token_${settingsStore.profile.userId}`)
const selectedItemIds = computed(() => [...selectedIds.value])

watch([query, selectedTag, selectedType, inTrash], () => {
  if (token.value) void refresh()
})

onMounted(async () => {
  await loadStatus()
  restoreToken()
  if (token.value) await refresh()
  document.addEventListener('click', closeContext)
})

onUnmounted(() => {
  document.removeEventListener('click', closeContext)
})

async function loadStatus() {
  if (!settingsStore.profile.userId) return
  const status = await getVaultStatus(settingsStore.profile.userId)
  configured.value = status.configured
}

function restoreToken() {
  try {
    const raw = sessionStorage.getItem(tokenKey.value)
    if (!raw) return
    const payload = JSON.parse(raw) as { token: string; expires_at: string }
    if (new Date(payload.expires_at).getTime() > Date.now()) {
      token.value = payload.token
      expiresAt.value = payload.expires_at
    } else {
      sessionStorage.removeItem(tokenKey.value)
    }
  } catch {
    sessionStorage.removeItem(tokenKey.value)
  }
}

function saveToken(nextToken: string, nextExpiresAt: string) {
  token.value = nextToken
  expiresAt.value = nextExpiresAt
  sessionStorage.setItem(tokenKey.value, JSON.stringify({ token: nextToken, expires_at: nextExpiresAt }))
}

async function unlock(password: string) {
  if (!settingsStore.profile.userId) return
  loading.value = true
  try {
    const response = await unlockVault(settingsStore.profile.userId, password)
    saveToken(response.token, response.expires_at)
    await refresh()
  } catch (error) {
    workspaceStore.showToast(error instanceof Error ? error.message : '解锁失败')
  } finally {
    loading.value = false
  }
}

async function setup(password: string) {
  if (!settingsStore.profile.userId) return
  loading.value = true
  try {
    const response = await setupVault(settingsStore.profile.userId, password)
    configured.value = true
    saveToken(response.token, response.expires_at)
    await refresh()
  } catch (error) {
    workspaceStore.showToast(error instanceof Error ? error.message : '设置失败')
  } finally {
    loading.value = false
  }
}

async function lockVault() {
  if (token.value) {
    await lockVaultToken(token.value).catch(() => {})
  }
  token.value = ''
  expiresAt.value = ''
  items.value = []
  selectedIds.value = new Set()
  sessionStorage.removeItem(tokenKey.value)
}

async function refresh() {
  if (!token.value) return
  loading.value = true
  try {
    const [itemResponse, tagResponse] = await Promise.all([
      listVaultItems(token.value, {
        query: query.value,
        tag: selectedTag.value,
        itemType: selectedType.value,
        trash: inTrash.value,
      }),
      listVaultTags(token.value),
    ])
    items.value = itemResponse.items
    tags.value = tagResponse.tags
    typeCounts.value = itemResponse.type_counts
    selectedIds.value = new Set([...selectedIds.value].filter((id) => itemResponse.items.some((item) => item.item_id === id)))
  } catch (error) {
    await lockVault()
    workspaceStore.showToast(error instanceof Error ? error.message : '密码库已锁定')
  } finally {
    loading.value = false
  }
}

function openNew() {
  editingItem.value = null
  editorOpen.value = true
}

async function openEdit(item: VaultItem) {
  if (!token.value) return
  const response = await getVaultItem(token.value, item.item_id)
  editingItem.value = response.item
  editorOpen.value = true
}

async function saveItem(payload: { item_type: VaultItemType; fields: Record<string, unknown>; tags: string[]; asset_ids: string[] }) {
  if (!token.value) return
  if (editingItem.value) {
    await updateVaultItem(token.value, editingItem.value.item_id, payload)
  } else {
    await createVaultItem(token.value, payload)
  }
  editorOpen.value = false
  editingItem.value = null
  await refresh()
}

function toggleItem(item: VaultItem) {
  const next = new Set(selectedIds.value)
  if (next.has(item.item_id)) next.delete(item.item_id)
  else next.add(item.item_id)
  selectedIds.value = next
}

function openContext(event: MouseEvent, item: VaultItem) {
  contextItem.value = item
  contextOpen.value = true
  contextStyle.value = {
    left: `${Math.min(event.clientX, window.innerWidth - 220)}px`,
    top: `${Math.min(event.clientY, window.innerHeight - 220)}px`,
  }
}

function closeContext() {
  contextOpen.value = false
}

async function copyText(value: string) {
  await navigator.clipboard?.writeText(value)
  workspaceStore.showToast('已复制')
}

async function deleteSelected() {
  if (!token.value || selectedItemIds.value.length === 0) return
  if (inTrash.value) {
    await purgeVaultItems(token.value, selectedItemIds.value)
  } else {
    await trashVaultItems(token.value, selectedItemIds.value)
  }
  selectedIds.value = new Set()
  await refresh()
}

async function restoreSelected() {
  if (!token.value || selectedItemIds.value.length === 0) return
  await restoreVaultItems(token.value, selectedItemIds.value)
  selectedIds.value = new Set()
  await refresh()
}

async function exportSelected(ids: string[] = selectedItemIds.value) {
  if (!token.value) return
  if (!window.confirm('导出的 JSON 将包含密码库敏感明文。确认继续?')) return
  const payload = await exportVaultItems(token.value, ids)
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `metaweave-vault-${Date.now()}.json`
  link.click()
  URL.revokeObjectURL(url)
}

function importJson() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = 'application/json,.json'
  input.onchange = async () => {
    const file = input.files?.[0]
    if (!file || !token.value) return
    const payload = JSON.parse(await file.text()) as { items?: Record<string, unknown>[] } | Record<string, unknown>[]
    const rawItems = Array.isArray(payload) ? payload : payload.items ?? []
    const result = await importVaultItems(token.value, rawItems)
    workspaceStore.showToast(`导入 ${result.imported} 项, 转为安全笔记 ${result.converted_to_secure_note} 项, 失败 ${result.failed} 项`)
    await refresh()
  }
  input.click()
}

async function contextCopyName() {
  if (!contextItem.value) return
  await copyText(contextItem.value.name)
}

async function contextCopySecret() {
  const item = contextItem.value
  if (!item || !token.value) return
  const detail = (await getVaultItem(token.value, item.item_id)).item
  const value = detail.item_type === 'card' ? detail.fields.security_code : detail.fields.password
  await copyText(String(value ?? ''))
}

async function contextDelete() {
  const item = contextItem.value
  closeContext()
  if (!item || !token.value) return
  if (inTrash.value) await purgeVaultItems(token.value, [item.item_id])
  else await trashVaultItems(token.value, [item.item_id])
  await refresh()
}
</script>

<template>
  <VaultUnlockPanel
    v-if="!token"
    :configured="configured"
    :loading="loading"
    @unlock="unlock"
    @setup="setup"
  />
  <section v-else class="vault-view">
    <header class="vault-topbar">
      <div>
        <h2>你的密码库</h2>
        <p>{{ items.length }} 个密码</p>
      </div>
      <div class="top-actions">
        <button class="new-btn" type="button" @click="openNew">+ New</button>
        <div class="toggle">
          <button :class="{ active: !inTrash }" type="button" @click="inTrash = false">密码库</button>
          <button :class="{ active: inTrash }" type="button" @click="inTrash = true">回收站</button>
        </div>
        <button type="button" title="导出" @click="exportSelected([])">Export</button>
        <button type="button" title="导入" @click="importJson">Import</button>
        <button class="avatar" type="button" title="锁定" @click="lockVault">{{ settingsStore.profile.userId.slice(0, 1).toUpperCase() }}</button>
      </div>
    </header>
    <div class="vault-main">
      <VaultFilterPanel
        v-model:query="query"
        v-model:tag="selectedTag"
        v-model:item-type="selectedType"
        :tags="tags"
        :counts="typeCounts"
        @create="openNew"
      />
      <main class="table-area">
        <div class="table-tools">
          <button type="button" :class="{ active: multiSelect }" @click="multiSelect = !multiSelect">多选</button>
          <button type="button" :disabled="selectedIds.size === 0" @click="deleteSelected">{{ inTrash ? '永久删除' : '删除' }}</button>
          <button v-if="inTrash" type="button" :disabled="selectedIds.size === 0" @click="restoreSelected">恢复</button>
          <button type="button" :disabled="selectedIds.size === 0" @click="exportSelected()">导出 JSON</button>
        </div>
        <VaultTable
          :token="token"
          :items="items"
          :selected-ids="selectedIds"
          :multi-select="multiSelect"
          @open="openEdit"
          @toggle="toggleItem"
          @context="openContext"
        />
      </main>
    </div>
    <ul v-if="contextOpen && contextItem" class="context-menu" :style="contextStyle" @click.stop>
      <li @click="contextCopyName">复制项目名称</li>
      <li v-if="contextItem.item_type === 'login' || contextItem.item_type === 'card'" @click="contextCopySecret">复制密码</li>
      <li @click="openEdit(contextItem); closeContext()">编辑</li>
      <li @click="exportSelected([contextItem.item_id]); closeContext()">导出</li>
      <li class="danger" @click="contextDelete">删除</li>
    </ul>
    <VaultItemEditor :open="editorOpen" :item="editingItem" :token="token" @close="editorOpen = false" @save="saveItem" />
  </section>
</template>

<style scoped>
.vault-view {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
  width: 100%;
  height: 100%;
  background: var(--color-canvas);
  font-family: var(--font-ui);
}

.vault-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 58px;
  padding: 10px 16px;
  border-bottom: 1px solid var(--color-border);
  background: var(--color-surface-raised);
}

h2,
p {
  margin: 0;
}

h2 {
  color: var(--color-text);
  font-size: calc(18px * var(--font-scale));
}

p {
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

.top-actions,
.table-tools,
.toggle {
  display: flex;
  align-items: center;
  gap: 8px;
}

button {
  min-height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text-secondary);
  padding: 0 12px;
  cursor: pointer;
}

button:disabled {
  opacity: 0.45;
  cursor: default;
}

.new-btn,
.toggle button.active,
button.active {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}

.toggle {
  padding: 3px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
}

.toggle button {
  border: 0;
  background: transparent;
}

.avatar {
  width: 34px;
  padding: 0;
}

.vault-main {
  display: flex;
  flex: 1 1 auto;
  min-height: 0;
}

.table-area {
  flex: 1 1 auto;
  min-width: 0;
  overflow: auto;
  padding: 14px;
}

.table-tools {
  justify-content: flex-end;
  margin-bottom: 10px;
}

.context-menu {
  position: fixed;
  z-index: 120;
  display: grid;
  min-width: 190px;
  padding: 6px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-canvas);
  box-shadow: var(--shadow-window);
  list-style: none;
  margin: 0;
}

.context-menu li {
  min-height: 30px;
  border-radius: 5px;
  color: var(--color-text-secondary);
  padding: 7px 10px;
  cursor: pointer;
}

.context-menu li:hover {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.context-menu li.danger:hover {
  background: color-mix(in srgb, var(--color-danger) 12%, transparent);
  color: var(--color-danger);
}

@media (max-width: 860px) {
  .vault-main {
    flex-direction: column;
  }

  .vault-topbar,
  .top-actions {
    align-items: flex-start;
    flex-wrap: wrap;
  }
}
</style>
