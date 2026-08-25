<!-- Local Agent patch detail drawer with compact three-line context. -->
<script setup lang="ts">
import { computed } from 'vue'
import IcIcon from '@/components/common/IcIcon.vue'
import ChangeDiff from '@/components/editor_workspace/agent_chat/ChangeDiff.vue'
import type { AgentChangeSnapshot } from '@/api/agentChanges'

defineOptions({ name: 'ChangeDetailDrawer' })
const props = defineProps<{ snapshot: AgentChangeSnapshot | null }>()
const emit = defineEmits<{ close: [] }>()
const files = computed(() => props.snapshot?.files ?? [])

</script>

<template>
  <aside v-if="snapshot" class="change-detail" aria-label="变更明细">
    <header><span>变更明细</span><button type="button" @click="emit('close')"><IcIcon name="close" :size="15" /></button></header>
    <section v-for="file in files" :key="file.path"><div class="file-head"><span>{{ file.path }}</span><b>+{{ file.additions }}</b><i>-{{ file.deletions }}</i></div><article v-for="(edit, index) in file.edits" :key="index"><ChangeDiff :before="edit.before" :after="edit.after" :show-line-numbers="true" /></article></section>
  </aside>
</template>

<style scoped>
.change-detail{box-sizing:border-box;flex:0 0 min(390px,36vw);width:min(390px,36vw);max-width:min(390px,36vw);min-width:0;padding:var(--space-10);overflow:auto;background:var(--color-surface-raised);font-size:calc(11px * var(--font-scale));opacity:1;transform:translateX(0);transition:flex-basis 240ms cubic-bezier(.4,0,.2,1),width 240ms cubic-bezier(.4,0,.2,1),max-width 240ms cubic-bezier(.4,0,.2,1),padding 240ms cubic-bezier(.4,0,.2,1),opacity 180ms ease,transform 240ms cubic-bezier(.4,0,.2,1)}
.change-detail-slide-enter-active,.change-detail-slide-leave-active{overflow:hidden}
.change-detail-slide-enter-from,.change-detail-slide-leave-to{flex-basis:0;width:0;max-width:0;padding-right:0;padding-left:0;opacity:0;transform:translateX(28px)}
header,.file-head{display:flex;align-items:center;gap:var(--space-8)}header{justify-content:space-between;margin-bottom:var(--space-10);color:var(--color-text-primary);font-weight:650}button{border:0;background:transparent;color:inherit;cursor:pointer}section{margin-bottom:var(--space-12)}.file-head{padding:5px 0;color:var(--color-text-secondary)}.file-head span{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.file-head b{margin-left:auto;color:var(--color-success)}.file-head i{font-style:normal;color:var(--color-danger)}article{margin-top:var(--space-6);overflow:hidden;border-radius:var(--radius-sm)}
</style>
