<!--
  Vditor editor wrapper.

  Usage:
  Owns the imperative Vditor instance and exposes a simple v-model API to the
  Vue editor pane.
-->
<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Vditor from 'vditor'

const props = defineProps<{
  modelValue: string
  toolbarVisible: boolean
}>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
  save: []
}>()

const host = ref<HTMLDivElement | null>(null)
let instance: Vditor | null = null
let internalUpdate = false

function disableEditorCache() {
  instance?.disabledCache()
  instance?.clearCache()
}

onMounted(() => {
  if (!host.value) {
    return
  }
  instance = new Vditor(host.value, {
    value: props.modelValue,
    height: '100%',
    // Edit mode must stay wysiwyg so headings hide their Markdown markers and
    // code/math/diagram blocks use Vditor's compiled preview behavior.
    mode: 'wysiwyg',
    cache: { enable: false },
    toolbar: [],
    preview: {
      // Do not change this to "both": Preview/Split uses MarkdownPreview.vue's
      // separate Vditor instance, while Edit should not leak an internal pane.
      mode: 'editor',
      markdown: {
        codeBlockPreview: true,
        mathBlockPreview: true,
      },
    },
    after() {
      disableEditorCache()
      if (instance?.getValue() !== props.modelValue) {
        instance?.setValue(props.modelValue, true)
      }
    },
    input(value: string) {
      internalUpdate = true
      emit('update:modelValue', value)
      internalUpdate = false
    },
  })
})

function handleKeydown(event: KeyboardEvent) {
  const hasCommandModifier = event.ctrlKey || event.metaKey
  if (!hasCommandModifier) {
    return
  }

  const key = event.key.toLowerCase()
  if (key === 'z' && !event.altKey && !event.isComposing) {
    event.preventDefault()
    event.stopPropagation()
    if (event.shiftKey) {
      redo()
    } else {
      undo()
    }
    return
  }

  if (key === 'y' && !event.shiftKey && !event.altKey && !event.isComposing) {
    event.preventDefault()
    event.stopPropagation()
    redo()
    return
  }

  if (key === 's') {
    event.preventDefault()
    emit('save')
  }
}

function undo() {
  const vditor = instance?.vditor
  if (vditor?.undo) {
    vditor.undo.undo(vditor)
  }
}

function redo() {
  const vditor = instance?.vditor
  if (vditor?.undo) {
    vditor.undo.redo(vditor)
  }
}

defineExpose({ undo, redo })

watch(
  () => props.modelValue,
  (value) => {
    if (!instance || internalUpdate || instance.getValue() === value) {
      return
    }
    try {
      instance.setValue(value)
    } catch (err) {
      console.warn('[VditorEditor] setValue failed:', err)
    }
  },
)

onBeforeUnmount(() => {
  try {
    instance?.destroy()
  } catch (err) {
    console.warn('[VditorEditor] destroy failed:', err)
  }
  instance = null
})
</script>

<template>
  <div
    ref="host"
    class="vditor-host"
    :class="{ 'show-toolbar': props.toolbarVisible }"
    @keydown.capture="handleKeydown"
  ></div>
</template>

<style scoped>
.vditor-host {
  width: 100%;
  height: 100%;
  min-height: 0;
}
</style>
