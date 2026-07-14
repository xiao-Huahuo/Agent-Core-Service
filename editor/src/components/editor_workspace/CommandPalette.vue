<!--
  Command palette overlay.

  Usage:
  Shows keyboard-centered editor actions. Actual backend actions are mocked
  through workspace store until the API layer is wired.
-->
<script setup lang="ts">
import { computed, ref } from 'vue'
import { Search } from 'lucide-vue-next'

import { useSettingsStore } from '@/stores/settings'
import { useWorkspaceStore } from '@/stores/workspace'
import type { CommandAction } from '@/types/knowledge'

const settingsStore = useSettingsStore()
const workspaceStore = useWorkspaceStore()
const query = ref('')

const filteredCommands = computed(() => {
  const normalized = query.value.trim().toLowerCase()
  if (!normalized) {
    return workspaceStore.commands
  }
  return workspaceStore.commands.filter((command) => {
    return `${command.label} ${command.description}`.toLowerCase().includes(normalized)
  })
})

function runCommand(command: CommandAction) {
  if (command.id === 'toggle-theme') {
    settingsStore.toggleTheme()
  }
  if (command.id === 'run-index') {
    workspaceStore.markIndexing()
  }
  if (command.id === 'open-settings') {
    workspaceStore.setMainView('settings')
  }
  if (command.id === 'open-graph') {
    workspaceStore.setMainView('graph')
  }
  workspaceStore.closeCommandPalette()
}
</script>

<template>
  <Teleport to="body">
    <div v-if="workspaceStore.commandPaletteOpen" class="palette-overlay" @click="workspaceStore.closeCommandPalette">
      <section class="palette" @click.stop>
        <div class="palette-search">
          <Search :size="18" />
          <input v-model="query" autofocus placeholder="Type a command" />
        </div>
        <div class="command-list">
          <button
            v-for="command in filteredCommands"
            :key="command.id"
            class="command-row"
            type="button"
            @click="runCommand(command)"
          >
            <span>
              <strong>{{ command.label }}</strong>
              <small>{{ command.description }}</small>
            </span>
            <kbd v-if="command.shortcut">{{ command.shortcut }}</kbd>
          </button>
        </div>
      </section>
    </div>
  </Teleport>
</template>

<style scoped>
.palette-overlay {
  position: fixed;
  z-index: 30;
  inset: 0;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding-top: 12vh;
  background: var(--color-overlay);
}

.palette {
  width: min(640px, calc(100vw - 32px));
  overflow: hidden;
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-lg);
  background: var(--color-surface);
}

.palette-search {
  display: flex;
  align-items: center;
  gap: var(--space-10);
  padding: var(--space-12);
  border-bottom: 1px solid var(--color-border);
}

.palette-search input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  color: var(--color-text);
  font-size: 16px;
}

.command-list {
  max-height: 360px;
  overflow: auto;
  padding: var(--space-8);
}

.command-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-12);
  width: 100%;
  padding: var(--space-10);
  border: 0;
  border-radius: var(--radius-md);
  background: transparent;
  color: var(--color-text);
  text-align: left;
}

.command-row:hover {
  background: var(--color-surface-active);
}

.command-row strong,
.command-row small {
  display: block;
}

.command-row small {
  margin-top: var(--space-4);
  color: var(--color-text-muted);
}

kbd {
  padding: 2px 6px;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  color: var(--color-text-muted);
  font-family: var(--font-code);
  font-size: 11px;
}
</style>
