<!--
  Password vault item editor.

  Usage:
  Used by VaultView for both creating and editing login, card, identity, and
  secure note entries. It only emits data when the user explicitly saves.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import IcIcon from '@/components/common/IcIcon.vue'
import LibraryTagPicker from '@/components/library_view/LibraryTagPicker.vue'
import { uploadVaultAsset, type VaultItem, type VaultItemType, type VaultTag } from '@/api/vault'

defineOptions({ name: 'VaultItemEditor' })

const props = defineProps<{
  open: boolean
  item: VaultItem | null
  token: string
  availableTags: VaultTag[]
}>()

const emit = defineEmits<{
  close: []
  save: [payload: { item_type: VaultItemType; fields: Record<string, unknown>; tags: string[]; asset_ids: string[] }]
}>()

const itemType = ref<VaultItemType>('login')
const fields = ref<Record<string, string>>({})
const tags = ref<string[]>([])
const customFields = ref<unknown[]>([])
const assetIds = ref<string[]>([])
const uploadingImage = ref(false)
const passwordVisible = ref(false)
const typeMenuOpen = ref(false)
const extraMenuOpen = ref(false)
const visibleExtras = ref<Set<string>>(new Set())

const typeLabels: Record<VaultItemType, string> = { login: '登录', card: '支付卡', identity: '身份', secure_note: '安全笔记' }
const title = computed(() => typeLabels[itemType.value])
const typeIcons: Record<VaultItemType, string> = { login: 'shield', card: 'dashboard', identity: 'fact-check', secure_note: 'edit-note' }
const fieldIcons: Record<string, string> = {
  name: 'title', password: 'shield', number: 'dashboard', first_name: 'group', note: 'edit-note', notes: 'edit-note', tags: 'label',
  username: 'group', uri: 'link', cardholder_name: 'group', brand: 'dashboard', security_code: 'shield', title: 'fact-check',
  company: 'hub', email: 'send', phone: 'forum', country: 'language', province: 'language', city: 'language',
  address1: 'home', address2: 'home', address3: 'home', postal_code: 'location-on',
}
const allOptionalFields = computed<[string, string][]>(() => [
  ...({
    login: [['username', '用户名'], ['uri', '网站 URI']],
    card: [['cardholder_name', '持卡人姓名'], ['brand', '品牌'], ['security_code', '安全码']],
    identity: [['title', '称呼'], ['username', '用户名'], ['company', '公司'], ['email', '电子邮箱'], ['phone', '电话'], ['country', '国家'], ['province', '省'], ['city', '城市'], ['address1', '地址 1'], ['address2', '地址 2'], ['address3', '地址 3'], ['postal_code', '邮政编码']],
    secure_note: [],
  }[itemType.value] as [string, string][]),
  ['notes', '备注'],
  ['tags', '标签'],
])
const optionalFields = computed(() => allOptionalFields.value.filter(([key]) => !visibleExtras.value.has(key)))

watch(
  () => props.item,
  (item) => {
    itemType.value = item?.item_type ?? 'login'
    const source = (item?.fields ?? {}) as Record<string, unknown>
    fields.value = Object.fromEntries(Object.entries(source).map(([key, value]) => [key, Array.isArray(value) ? '' : String(value ?? '')]))
    tags.value = [...(item?.tags ?? [])]
    customFields.value = Array.isArray(source.custom_fields) ? source.custom_fields : []
    assetIds.value = Array.isArray(source.asset_ids) ? source.asset_ids.map((value) => String(value)) : []
    visibleExtras.value = new Set([
      ...Object.keys(source).filter((key) => !['name', 'password', 'number', 'first_name', 'note', 'custom_fields', 'asset_ids'].includes(key) && String(source[key] ?? '').trim()),
      ...(item?.tags?.length ? ['tags'] : []),
    ])
  },
  { immediate: true },
)

async function uploadImage(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file || !props.token) return
  uploadingImage.value = true
  try {
    const response = await uploadVaultAsset(props.token, file)
    assetIds.value = [...assetIds.value, response.asset.asset_id]
  } finally {
    uploadingImage.value = false
    ;(event.target as HTMLInputElement).value = ''
  }
}

function save() {
  const payloadFields: Record<string, unknown> = { ...fields.value }
  payloadFields.asset_ids = assetIds.value
  payloadFields.custom_fields = customFields.value
  emit('save', {
    item_type: itemType.value,
    fields: payloadFields,
    tags: tags.value,
    asset_ids: assetIds.value,
  })
}

function chooseType(type: string) {
  if (!['login', 'card', 'identity', 'secure_note'].includes(type)) return
  itemType.value = type as VaultItemType
  typeMenuOpen.value = false
  extraMenuOpen.value = false
}

function addExtra(key: string) {
  visibleExtras.value = new Set([...visibleExtras.value, key])
  extraMenuOpen.value = false
}

function fieldIcon(key: string) {
  return fieldIcons[key] ?? 'text-fields'
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="editor-backdrop" @click.self="emit('close')">
      <section class="editor-panel">
      <header class="editor-head">
        <h3>{{ title }}</h3>
        <button class="icon-btn" type="button" title="关闭" @click="emit('close')"><IcIcon name="close" :size="16" /></button>
      </header>
      <section class="upper-grid">
        <div class="metadata-zone">
          <div class="field"><span><IcIcon name="layers" :size="14" />类型</span><div class="field-menu"><button class="pill-trigger" type="button" :aria-expanded="typeMenuOpen" @click="typeMenuOpen = !typeMenuOpen">{{ typeLabels[itemType] }}<IcIcon name="chevron-down" :size="15" /></button><div v-if="typeMenuOpen" class="field-menu-list"><button v-for="(label, type) in typeLabels" :key="type" type="button" @click="chooseType(type)"><IcIcon :name="typeIcons[type]" :size="16" /><span>{{ label }}</span><IcIcon v-if="itemType === type" class="menu-selected" name="check" :size="16" /></button></div></div></div>
          <label class="field required"><span><IcIcon :name="fieldIcon('name')" :size="14" />项目名称</span><input v-model="fields.name" placeholder="项目名称" /></label>
          <label v-if="itemType === 'login'" class="field required"><span><IcIcon :name="fieldIcon('password')" :size="14" />密码</span><div class="secret-input"><input v-model="fields.password" :type="passwordVisible ? 'text' : 'password'" placeholder="密码" /><button type="button" :title="passwordVisible ? '隐藏密码' : '显示密码'" @click="passwordVisible = !passwordVisible"><IcIcon :name="passwordVisible ? 'visibility-off' : 'visibility'" :size="17" /></button></div></label>
          <label v-else-if="itemType === 'card'" class="field required"><span><IcIcon :name="fieldIcon('number')" :size="14" />卡号</span><input v-model="fields.number" placeholder="号码" /></label>
          <label v-else-if="itemType === 'identity'" class="field required"><span><IcIcon :name="fieldIcon('first_name')" :size="14" />名字</span><input v-model="fields.first_name" placeholder="名字" /></label>
          <label v-else class="field required"><span><IcIcon :name="fieldIcon('note')" :size="14" />笔记内容</span><textarea v-model="fields.note" rows="5" placeholder="笔记内容"></textarea></label>
          <template v-for="[key, label] in allOptionalFields.filter(([key]) => visibleExtras.has(key))" :key="key">
            <label v-if="key === 'notes'" class="field"><span><IcIcon :name="fieldIcon(key)" :size="14" />备注</span><textarea v-model="fields.notes" rows="3" placeholder="备注"></textarea></label>
            <div v-else-if="key === 'tags'" class="field"><span><IcIcon :name="fieldIcon(key)" :size="14" />标签</span><LibraryTagPicker v-model="tags" :available-tags="availableTags.map((tag) => tag.name)" /></div>
            <label v-else class="field"><span><IcIcon :name="fieldIcon(key)" :size="14" />{{ label }}</span><select v-if="key === 'brand'" v-model="fields.brand"><option value="">品牌</option><option>UnionPay银联</option><option>Visa</option><option>Mastercard</option><option>American Express</option><option>JCB</option><option>Discover</option><option>Diners Club</option><option>Maestro</option><option>RuPay</option><option>其他</option></select><select v-else-if="key === 'title'" v-model="fields.title"><option value="">称呼</option><option>先生</option><option>夫人</option><option>女士</option><option>Mx</option><option>博士</option></select><input v-else v-model="fields[key]" :type="key === 'security_code' ? 'password' : 'text'" :placeholder="label" /></label>
          </template>
        </div>
        <div class="cover-zone"><label class="cover-drop"><input type="file" accept="image/*" :disabled="uploadingImage" @change="uploadImage" /><IcIcon name="add-photo" :size="30" /><span>{{ uploadingImage ? '上传中' : '点击上传图片' }}</span><small>{{ assetIds.length ? `${assetIds.length} 张图片已绑定` : '可作为项目图片' }}</small></label></div>
      </section>
      <footer class="dialog-actions">
        <div class="field-menu extra-menu"><button class="pill-trigger" type="button" :aria-expanded="extraMenuOpen" @click="extraMenuOpen = !extraMenuOpen">+ 添加字段<IcIcon name="chevron-up" :size="14" /></button><div v-if="extraMenuOpen" class="field-menu-list extra-menu-list"><button v-for="[key, label] in optionalFields" :key="key" type="button" @click="addExtra(key)"><IcIcon :name="fieldIcon(key)" :size="16" /><span>{{ label }}</span></button><span v-if="!optionalFields.length">没有可添加字段</span></div></div>
        <button type="button" @click="emit('close')">取消</button>
        <button class="save-btn" type="button" @click="save">保存</button>
      </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.editor-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: grid;
  place-items: center;
  background: rgba(0, 0, 0, 0.32);
}

.editor-panel {
  display: grid;
  gap: 0;
  width: min(760px, calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  overflow: auto;
  border: 1px solid var(--color-border);
  border-radius: 28px;
  background: var(--color-surface);
  font-family: var(--font-ui);
  font-size: calc(14px * var(--font-scale));
}

.editor-head,
.dialog-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 7px 16px;
}

h3 {
  margin: 0;
  font-size: calc(15px * var(--font-scale));
}

.upper-grid {
  display: grid;
  grid-template-columns: 5fr 3fr;
  gap: 14px;
  padding: 16px 16px 0;
}

.metadata-zone {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.field {
  display: grid;
  gap: 7px;
  color: var(--color-text-secondary);
  font-size: calc(12px * var(--font-scale));
}

.field > span {
  display: inline-flex;
  align-items: center;
  gap: 5px;
}

.field input,
.field select,
.field textarea {
  width: 100%;
  border: 1px solid var(--color-border);
  background: var(--color-canvas);
  color: var(--color-text);
  font-family: var(--font-ui);
  font-size: calc(13px * var(--font-scale));
  outline: 0;
}

.secret-input { position: relative; display: block; }
.secret-input input { padding-right: 42px; }
.secret-input button { position: absolute; top: 1px; right: 4px; display: grid; place-items: center; width: 34px; height: 34px; border: 0; border-radius: 50%; background: transparent; color: var(--color-text-muted); cursor: pointer; }
.secret-input button:hover { color: var(--color-primary); }

.field input,
.field select {
  height: 36px;
  border-radius: 999px;
  padding: 0 14px;
}

.field textarea {
  border-radius: 28px;
  padding: 10px 14px;
  resize: vertical;
}

.field input:focus,
.field select:focus,
.field textarea:focus {
  border-color: var(--color-primary);
}

.field.required > span::after {
  margin-left: 3px;
  color: var(--color-danger);
  content: '*';
}

.field-menu {
  position: relative;
}

.pill-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  width: 100%;
  height: 36px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text);
  padding: 0 14px;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast), color var(--transition-fast);
}

.pill-trigger[aria-expanded="true"] {
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.pill-trigger :deep(svg) {
  transition: transform var(--transition-fast);
}

.pill-trigger[aria-expanded="true"] :deep(svg) {
  transform: rotate(180deg);
}

.field-menu-list {
  position: absolute;
  z-index: 3;
  display: grid;
  gap: 0;
  min-width: 172px;
  margin-top: 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-canvas);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.18);
  overflow: hidden;
  padding: var(--space-6);
  animation: sort-menu-pop 140ms ease-out both;
  transform-origin: top center;
}

.field-menu-list button {
  display: grid;
  grid-template-columns: 16px minmax(0, 1fr) 16px;
  align-items: center;
  gap: var(--space-6);
  height: 30px;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--color-text-secondary);
  padding: 0 var(--space-6);
  text-align: left;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
  opacity: 0;
  transform: translateY(-4px);
  animation: sort-row-drop 150ms ease-out both;
}

.field-menu-list button:nth-of-type(1) { animation-delay: 20ms; }
.field-menu-list button:nth-of-type(2) { animation-delay: 38ms; }
.field-menu-list button:nth-of-type(3) { animation-delay: 56ms; }
.field-menu-list button:nth-of-type(4) { animation-delay: 74ms; }
.field-menu-list button:nth-of-type(5) { animation-delay: 92ms; }

.field-menu-list button:hover {
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.menu-selected { justify-self: end; color: var(--color-primary); }

.cover-zone {
  display: flex;
  min-width: 0;
}

.cover-drop {
  display: flex;
  flex: 1;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 184px;
  border: 1px dashed var(--color-border-strong);
  border-radius: 28px;
  background: var(--color-surface-raised);
  color: var(--color-text-muted);
  padding: 12px;
  text-align: center;
  cursor: pointer;
}

.cover-drop:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-softer);
  color: var(--color-primary);
}

.cover-drop input {
  display: none;
}

.cover-drop span {
  color: var(--color-text);
  font-size: calc(13px * var(--font-scale));
  font-weight: 500;
}

.cover-drop small {
  color: var(--color-text-muted);
  font-size: calc(12px * var(--font-scale));
}

.icon-btn {
  display: grid;
  place-items: center;
  width: 28px;
  min-height: 28px;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--color-text-muted);
  padding: 0;
}

.icon-btn:hover {
  background: color-mix(in srgb, var(--color-text-secondary) 10%, transparent);
  color: var(--color-text);
}

.dialog-actions {
  position: relative;
  justify-content: flex-end;
  padding: 16px;
}

.extra-menu {
  margin-right: auto;
}

.extra-menu .pill-trigger {
  width: auto;
}

.extra-menu-list {
  bottom: calc(100% + 6px);
  left: 0;
  width: max-content;
  min-width: 160px;
  margin: 0;
  transform-origin: bottom left;
}

.extra-menu-list span {
  color: var(--color-text-muted);
  padding: 6px 9px;
  font-size: calc(12px * var(--font-scale));
}

@keyframes sort-menu-pop {
  from { transform: translateY(-6px); }
  to { transform: translateY(0); }
}

@keyframes sort-row-drop {
  from { transform: translateY(-6px); opacity: 0; }
  to { transform: translateY(0); opacity: 1; }
}

.dialog-actions > button {
  min-height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-surface-raised);
  color: var(--color-text);
  padding: 0 16px;
  font-size: calc(13px * var(--font-scale));
  cursor: pointer;
}

.save-btn {
  border-color: var(--color-primary) !important;
  background: var(--color-primary) !important;
  color: #fff !important;
}

@media (max-width: 720px) {
  .upper-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}

</style>
