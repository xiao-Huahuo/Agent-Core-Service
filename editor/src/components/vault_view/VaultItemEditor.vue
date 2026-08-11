<!--
  Password vault item editor.

  Usage:
  Used by VaultView for both creating and editing login, card, identity, and
  secure note entries. It only emits data when the user explicitly saves.
-->
<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import { uploadVaultAsset, type VaultItem, type VaultItemType } from '@/api/vault'

defineOptions({ name: 'VaultItemEditor' })

const props = defineProps<{
  open: boolean
  item: VaultItem | null
  token: string
}>()

const emit = defineEmits<{
  close: []
  save: [payload: { item_type: VaultItemType; fields: Record<string, unknown>; tags: string[]; asset_ids: string[] }]
}>()

const itemType = ref<VaultItemType>('login')
const fields = ref<Record<string, string>>({})
const tagsText = ref('')
const customFieldsText = ref('')
const assetIds = ref<string[]>([])
const uploadingImage = ref(false)

const title = computed(() => props.item ? '编辑密码' : '+ New')

watch(
  () => props.item,
  (item) => {
    itemType.value = item?.item_type ?? 'login'
    const source = (item?.fields ?? {}) as Record<string, unknown>
    fields.value = Object.fromEntries(Object.entries(source).map(([key, value]) => [key, Array.isArray(value) ? '' : String(value ?? '')]))
    tagsText.value = item?.tags.join(', ') ?? ''
    customFieldsText.value = JSON.stringify(source.custom_fields ?? [], null, 2)
    assetIds.value = Array.isArray(source.asset_ids) ? source.asset_ids.map((value) => String(value)) : []
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
  try {
    payloadFields.custom_fields = customFieldsText.value.trim() ? JSON.parse(customFieldsText.value) : []
  } catch {
    payloadFields.custom_fields = []
  }
  emit('save', {
    item_type: itemType.value,
    fields: payloadFields,
    tags: tagsText.value.split(',').map((tag) => tag.trim()).filter(Boolean),
    asset_ids: assetIds.value,
  })
}
</script>

<template>
  <div v-if="open" class="editor-backdrop" @click.self="emit('close')">
    <section class="editor-panel">
      <header>
        <h3>{{ title }}</h3>
        <button type="button" @click="emit('close')">×</button>
      </header>
      <select v-model="itemType" class="vault-field">
        <option value="login">登录</option>
        <option value="card">支付卡</option>
        <option value="identity">身份</option>
        <option value="secure_note">安全笔记</option>
      </select>
      <input v-model="fields.name" class="vault-field" placeholder="项目名称" />
      <template v-if="itemType === 'login'">
        <input v-model="fields.username" class="vault-field" placeholder="用户名" />
        <input v-model="fields.password" class="vault-field" type="password" placeholder="密码" />
        <input v-model="fields.uri" class="vault-field" placeholder="网站 URI" />
      </template>
      <template v-else-if="itemType === 'card'">
        <input v-model="fields.cardholder_name" class="vault-field" placeholder="持卡人姓名" />
        <input v-model="fields.number" class="vault-field" placeholder="号码" />
        <select v-model="fields.brand" class="vault-field">
          <option value="">品牌</option>
          <option>UnionPay银联</option>
          <option>Visa</option>
          <option>Mastercard</option>
          <option>American Express</option>
          <option>JCB</option>
          <option>Discover</option>
          <option>Diners Club</option>
          <option>Maestro</option>
          <option>RuPay</option>
          <option>其他</option>
        </select>
        <input v-model="fields.security_code" class="vault-field" type="password" placeholder="安全码" />
      </template>
      <template v-else-if="itemType === 'identity'">
        <select v-model="fields.title" class="vault-field">
          <option value="">称呼</option>
          <option>先生</option>
          <option>夫人</option>
          <option>女士</option>
          <option>Mx</option>
          <option>博士</option>
        </select>
        <input v-model="fields.first_name" class="vault-field" placeholder="名字" />
        <input v-model="fields.username" class="vault-field" placeholder="用户名" />
        <input v-model="fields.company" class="vault-field" placeholder="公司" />
        <input v-model="fields.email" class="vault-field" placeholder="电子邮箱" />
        <input v-model="fields.phone" class="vault-field" placeholder="电话" />
        <input v-model="fields.country" class="vault-field" placeholder="国" />
        <input v-model="fields.province" class="vault-field" placeholder="省" />
        <input v-model="fields.city" class="vault-field" placeholder="市" />
        <input v-model="fields.address1" class="vault-field" placeholder="地址 1" />
        <input v-model="fields.address2" class="vault-field" placeholder="地址 2" />
        <input v-model="fields.address3" class="vault-field" placeholder="地址 3" />
        <input v-model="fields.postal_code" class="vault-field" placeholder="邮政编码" />
      </template>
      <textarea v-else v-model="fields.note" class="vault-area" placeholder="笔记内容"></textarea>
      <textarea v-model="fields.notes" class="vault-area" placeholder="备注"></textarea>
      <label class="image-upload">
        <input type="file" accept="image/*" :disabled="uploadingImage" @change="uploadImage" />
        <span>{{ uploadingImage ? '上传中' : '上传图片' }}</span>
        <small v-if="assetIds.length">{{ assetIds.length }} 张图片已绑定</small>
      </label>
      <input v-model="tagsText" class="vault-field" placeholder="标签, 用逗号分隔" />
      <textarea v-model="customFieldsText" class="vault-area" placeholder="自定义字段 JSON 数组"></textarea>
      <footer>
        <button type="button" @click="emit('close')">取消</button>
        <button class="save-btn" type="button" @click="save">保存</button>
      </footer>
    </section>
  </div>
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
  gap: 10px;
  width: min(720px, calc(100vw - 32px));
  max-height: calc(100vh - 48px);
  overflow: auto;
  padding: 16px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-surface);
}

header,
footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

h3 {
  margin: 0;
}

.vault-field,
.vault-area,
.image-upload {
  border: 1px solid var(--color-border);
  border-radius: 8px;
  background: var(--color-canvas);
  color: var(--color-text);
  padding: 9px 11px;
}

.vault-field {
  height: 36px;
}

.vault-area {
  min-height: 82px;
  resize: vertical;
}

.image-upload {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  min-height: 72px;
  cursor: pointer;
}

.image-upload input {
  max-width: 180px;
}

.image-upload small {
  color: var(--color-text-muted);
}

button {
  min-height: 32px;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  background: var(--color-canvas);
  color: var(--color-text-secondary);
  padding: 0 14px;
  cursor: pointer;
}

.save-btn {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: #fff;
}
</style>
