# AI 反思日志

## 基本信息

|字段|内容|
|-|-|
|姓名|陈宇豪|
|负责模块|Editor 前端（EditorWorkspace 三栏布局、知识图谱 Canvas 渲染、Vditor 编辑器集成、文件树面板、Agent 聊天面板、Pinia 状态管理）|



## AI 帮忙解决了什么

### 1\. 知识图谱 Canvas 2D 渲染的分层架构设计

AI 在架构层面给出了将知识图谱拆分为四个独立模块的建议：graphTypes.ts定义框架无关的节点与边的接口契约，fileTreeGraphAdapter.ts 负责将业务数据（KnowledgeFileNode）转换为图数据模型，layeredForceLayout.ts 基于 D3 force 计算环形分层坐标，graphRenderer.ts 在 Canvas 2D 上下文上执行纯绘制逻辑。这个分层使 KnowledgeGraphCanvas.vue 自身仅承担 Vue 生命周期与指针事件的胶水角色，不再混杂渲染细节。最初的设计倾向是将绘制代码内联在 SFC 中，AI 指出了这对复用性的影响——如果未来需要将图谱嵌入到控制台或 Dashboard 页面，内联版本几乎需要重写。

**关键代码：** editor/src/components/knowledge\_graph/graphTypes.ts 第 17-136 行定义了全部接口，editor/src/components/knowledge\_graph/graphRenderer.ts 第 203-224 行是纯函数入口

### 2\. D3 力导向布局的环形分层与溢出处理

AI 给出了基于父节点为圆心、子节点按环形分布的目标坐标算法。核心思路是：同级节点按 maxNodesPerRing（基础值 14，随深度递增 2）分组，超出容量的节点溢出到下一环（ringGap: 68 像素），偶数深度层附加 Math.PI、itemsInRing 的角度偏移以避免相邻层节点视觉重叠。这个方案在 prepareLayeredTargets 中递归执行，从根节点开始逐层向下计算 targetX、targetY，然后将这些目标坐标注入 D3 的 forceX / forceY 中作为弱锚点（anchorStrength: 0.085），配合 forceManyBody 的负电荷（chargeStrength: -72）让节点在目标位置附近自然散开。

**关键代码：** editor/src/components/knowledge\_graph/layeredForceLayout.ts 第 57-102 行

### 3\. Vditor 编辑器的 v-model 双向绑定与内部更新防护

Vditor 是一个命令式 API 的第三方编辑器，AI 帮助设计了将其封装为 Vue 3 v-model 组件的方案。关键细节是 internalUpdate 守卫标志：当 input 回调被 Vditor 内部触发时，先将 internalUpdate 置为 true，emit update:modelValue 后再恢复为 false；而在 watch 监听 props.modelValue 变化时，如果 internalUpdate 为 true 或 Vditor 当前值已与目标值一致，则跳过 setValue 调用。这个模式避免了 Vditor → input 回调 → emit → watch → setValue → input 回调的无限循环。此外，after 生命周期中显式调用 disabledCache() 和 clearCache() 确保了浏览器 localStorage 中不会残留过期的编辑缓存。

**关键代码：** editor/src/components/editor\_workspace/VditorEditor.vue 第 24 行的 internalUpdate 标志，第 58-62 行的 input 回调，第 113-121 行的 watch
### 4\. CSS Grid 可拖拽三栏布局的 Custom Properties 方案

EditorWorkspace 的核心布局挑战在于：文件树和 Agent 侧栏需要可拖拽调整宽度，同时布局需要在不借助 JavaScript 计算的情况下保持稳定。AI 给出的方案是将面板宽度写入 CSS Custom Properties（--file-col-width、--agent-col-width），通过 workspaceGridStyle 这个 computed 属性动态注入到 workspace-grid 元素上。Grid 模板列定义为 40px var(--file-col-width) var(--file-resizer-width) minmax(0, 1fr) var(--agent-resizer-width) var(--agent-col-width)，其中编辑器区域使用 minmax(0, 1fr) 自动填充剩余空间。拖拽手柄使用 PointerEvent（而非 MouseEvent）以同时支持触摸和鼠标，COLLAPSE\_THRESHOLD 设为 150px 实现了折叠逻辑：当拖拽宽度低于阈值时自动隐藏面板，避免产生极窄但未关闭的中间状态。

**关键代码：** editor/src/views/EditorWorkspace.vue 第 61-68 行的 workspaceGridStyle，第 256-259 行的 grid-template-columns，第 124-150 行的 handleResizeMove
### 5\. Pinia Workspace Store 的文件树操作与去重命名逻辑

Workspace Store（约 1050 行）是 Editor 前端的核心状态中枢。AI 协助设计了文件树操作的完整链路：创建、重命名、复制、剪切、粘贴、删除、拖拽移动，每个操作都遵循"乐观更新 → API 调用 → 重新加载树"的模式。其中 uniquePathInDirectoryWithReserved 实现了文件名去重：先检查首选名称是否已被占用，如冲突则追加  2、 3 等序号，上限 1000 次后回退到时间戳方案。rewriteOpenPaths 在重命名或移动时同步更新所有已打开的标签页路径和内容缓存，包括 selectedPath 和 contentByPath 的键名迁移。ignoreNextTreeEvent 计数器则防止了本地操作触发 SSE 的 tree\_dirty 事件后错误地将标签页标记为 dirty。

**关键代码：** editor/src/stores/workspace.ts 第 929-947 行的 uniquePathInDirectoryWithReserved，第 949-968 行的 rewriteOpenPaths


## AI 没帮上忙 / 做错了什么

### 1\. Vditor 预览模式与自定义 MarkdownPreview 组件的职责重叠

AI 最初的方案是让 Vditor 同时管理编辑区和预览区（通过 preview.mode: 'both'），这在技术上更简洁。但在 Split 模式下，Vditor 的内置预览面板会与 MarkdownPreview.vue（一个独立的、使用 marked + highlight.js 渲染的 Vue 组件）产生双重渲染：Vditor 内部编译一份 HTML，MarkdownPreview 又根据内容重新编译一份，两份渲染结果在代码高亮和 DOMPurify 清洗策略上不完全一致。我最终将 Vditor 的 preview mode 限制为 'editor'，让 EditorPane.vue 在 Edit 和 Split 模式下分别挂载 <VditorEditor> 和 <MarkdownPreview> 作为两个独立的 Grid 子区域，各自管理自己的渲染管线。这避免了冲突，但确实增加了一个额外的组件需要维护。

### 2\. 文件树 SSE 事件中 ignoreNextTreeEvent 的粒度问题

AI 建议使用 ignoreNextTreeEvent 计数器来防止本地写操作触发的 tree\_dirty SSE 事件将标签页误标为 dirty。这个思路是对的，但初始实现中计数器的递减逻辑只在 tree\_dirty 事件处理器中执行，没有考虑到一个本地操作可能触发多次服务端文件事件（如先创建文件、再写入内容导致两次 inotify 事件）。当一次 saveFileByPath 操作对应三次 tree\_dirty 推送而计数器只加了 3 时，多出的推送仍会将标签页错误标记为 dirty。后来将增量从 += 1 调整为 += 3 作为经验缓冲值，并确保在 SSE 的 markOpenTabsDirty 中只有当 ignoreNextTreeEvent 降为 0 时才触发标记，缓解了这个问题。但这个方案仍然是基于猜测的事件次数而非精确匹配。

### 3\. 知识图谱 Viewport 缩放手势在触控板上的行为偏差

handleWheel 方法使用固定的缩放因子（1.12 / 0.89）处理滚轮事件，在鼠标滚轮的逐格滚动场景下表现良好。但在触控板上，双指捏合手势会产生高频、小增量的 wheel 事件，固定因子导致缩放步进过大，体验不够顺滑。AI 最初没有区分鼠标滚轮和触控板捏合手势的场景。正确的做法是检测 event.ctrlKey（macOS 上触控板捏合会设置此标志）并使用基于 event.deltaY 比例的连续缩放因子，但由于时间限制，这个优化被推迟到了后续迭代中。

### 4\. Electron 桌面桥的类型声明缺失导致编译器告警

window.agentEditorDesktop 是 Electron preload 脚本注入的全局对象，用于暴露原生功能（目录选择器、文件系统剪贴板、外部程序打开等）。AI 在没有声明全局类型的情况下，在 workspace.ts、FileTreePanel.vue 等多处直接使用了 window.agentEditorDesktop?.selectDirectory() 等调用。TypeScript 编译器对 Window 类型上不存在的属性持续报错，虽然不影响运行时行为，但在 CI 中会触发类型检查失败。后来需要手动在 src/types/ 下补充 declare global { interface Window { ... } } 声明，并确保所有可选链调用（?.）都有合理的 fallback 路径。



## 踩过的坑

### 1\. Vditor 的 after 回调中调用 setValue 触发 input 导致初始化死循环

Vditor 的 after 生命周期在编辑器 DOM 挂载完成后执行。在 after 中检查 instance.getValue() 是否等于 props.modelValue，如果不等则调用 setValue(value, true) 同步内容。问题在于 setValue 的第二个参数 true 表示触发 input 事件，而 input 回调中会 emit update:modelValue。如果父组件的 modelValue 在初始化阶段恰好与 Vditor 默认值不同，这个链路会形成一次额外的更新循环。虽然 internalUpdate 守卫最终阻断了无限递归，但问题排查花费了大量时间：最初怀疑是 watch 的 immediate 选项或 onMounted 的时序问题，通过 console.trace 才定位到 after → setValue → input → emit → watch → setValue → ... 的完整调用链。

教训：第三方编辑器的初始化流程需要在三个时间点（after 回调、onMounted 之后、watch 首次触发）之间建立清晰的协调协议，仅靠 internalUpdate 一个布尔标志是不够自解释的。在 after 中使用 setValue(value, true) 的第二个参数应改为 false（静默设置），让初始化阶段的内容同步不触发变更通知。

### 2\. PointerEvent 的 pointerleave 在拖拽时意外触发导致悬停节点丢失

KnowledgeGraphCanvas.vue 使用 PointerEvent 处理节点的拖拽、平移和悬停检测。在拖拽文件节点时（pointerMode === 'node'），如果鼠标移动速度较快，偶尔会触发 Canvas 元素的 pointerleave 事件。handlePointerLeave 方法在 pointerMode 不等于 'none' 时跳过了 hoveredNodeId 的清空，目的是防止拖拽中途悬停状态丢失。但当用户快速拖拽并松开时，pointerup 有时会在 pointerleave 之后才到达（或被浏览器丢弃），导致 pointerMode 卡在 'node' 状态，draggedNode 的 fx/fy 无法被清除，节点被永久固定在拖拽位置。

教训：在 pointerleave 和 pointercancel 处理中，应当执行与 pointerup 相同的清理逻辑（draggedNode.fx = null; draggedNode.fy = null; pointerMode = 'none'），而非仅仅跳过。Pointer Events API 的规范明确允许浏览器在指针离开元素时提前结束捕获，依赖 pointerup 一定会触发是不安全的。

### 3\. ResizeObserver 在 Canvas 初始化时触发导致力模拟重新启动

KnowledgeGraphCanvas.vue 的 onMounted 中同时执行了 resizeObserver.observe(hostRef) 和 startSimulation()。在某些浏览器（尤其是 Firefox）中，ResizeObserver 会在 observe 调用后立即同步触发一次回调，这意味着 resizeCanvas() 和 startSimulation(false) 会在 onMounted 的 startSimulation(true) 执行之前被调用一次。第一次调用创建了一个模拟并立即被第二次调用停止和替换，导致节点在初始化时出现短暂的闪烁。此外，startSimulation(false) 传入 false 参数跳过了 fitToView，但 startSimulation(true) 又会执行 fitToView，两次布局计算的结果视图范围不一致。

教训：ResizeObserver 的回调不能假设只在元素尺寸实际变化时才触发——它的初始化行为是同步报告当前尺寸。在使用 ResizeObserver 与手动初始化并存的设计中，应当使用一个 initialized 标志或 nextTick 来确保 ResizeObserver 的首次回调在手动初始化完成之后才具有完整的数据上下文。

### 4\. Canvas 在高 DPI 屏幕上的 devicePixelRatio 缩放导致文本与节点模糊

KnowledgeGraphCanvas.vue 的 resizeCanvas 方法将 Canvas 的物理像素设置为 width \* pixelRatio，并在每次 draw 之前调用 context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0) 进行缩放。这在高 DPI 屏幕上（如 Retina 显示屏 devicePixelRatio = 2）是正确的。但在 requestAnimationFrame 的 tick 回调中，D3 模拟的 tick 事件调用了 requestDraw，而 requestDraw 内通过 requestAnimationFrame 触发 draw。在 draw 函数中，setTransform 使用的是调用时的 devicePixelRatio。如果在模拟运行期间用户将浏览器窗口拖到了不同 DPI 的显示器上（如从笔记本屏幕拖到外接显示器），devicePixelRatio 会发生变化，但 Canvas 的 width/height 属性（物理像素）仍然是旧值，导致文本出现模糊或过采样。

教训：应使用 ResizeObserver 统一管理所有与尺寸相关的更新（包括 devicePixelRatio 变化的响应），将 resizeCanvas 作为唯一的尺寸入口。在 draw 函数中，应从 canvas.width / canvas.height 反推当前有效的 pixelRatio，而非重新读取 window.devicePixelRatio。



## 学到的经验

### 1\. 框架无关的渲染架构能够在不同宿主环境中复用

知识图谱模块的拆分是本轮开发中架构收益最高的决策。graphTypes.ts 定义的节点和链接接口不导入任何 Vue、D3 或 Canvas 相关的依赖，仅描述数据形态；graphRenderer.ts 接收一个 CanvasRenderingContext2D 和纯数据对象，不感知自己运行在哪个框架中；layeredForceLayout.ts 同理，只依赖 d3-force 的 Simulation 接口。这种分层意味着如果需要将图谱嵌入到控制台前端（使用不同的构建工具和组件库）或在 Electron 主进程中做服务端渲染，只需要重新实现适配器层，渲染和布局代码可以原样保留。文件头部的 JSDoc 注释（"keep this file free of Vue and MetaWeave store imports"）在后续协作中起到了关键的约束作用。

### 2\. PointerEvent 统一了鼠标和触控的交互模型

在 Canvas 交互中，同时使用 mousedown/mousemove/mouseup 和 touchstart/touchmove/touchend 会导致事件处理逻辑重复且容易遗漏边界情况。PointerEvent API 将两者统一为一组事件（pointerdown、pointermove、pointerup、pointercancel），配合 setPointerCapture 可以在指针离开元素后仍持续接收事件（这对拖拽场景至关重要）。在 KnowledgeGraphCanvas.vue 中，pointerMode 状态机（'none' / 'pan' / 'node'）只在 PointerEvent 的回调中流转，不再需要维护两套并行的鼠标和触摸逻辑。activePointerId 的追踪确保了多点触摸场景下不会混淆来自不同手指的事件流。

### 3\. CSS Grid 的 minmax(0, 1fr) 是编辑器布局防止溢出的关键

在 Flexbox 布局中，弹性子项的默认 min-width 是 auto（即内容的最小尺寸），这意味着如果 Vditor 的编辑区域内部有一个很宽的代码块或表格，Flexbox 子项会被撑开到超过父容器宽度，导致侧边栏被挤出视口。CSS Grid 搭配 minmax(0, 1fr) 的行为不同：0 作为最小尺寸意味着 Grid 子项可以收缩到零，而不会被迫保持内容的最小宽度。EditorWorkspace 的 workspace-grid 使用 grid-template-columns: 40px var(--file-col-width) var(--file-resizer-width) minmax(0, 1fr) var(--agent-resizer-width) var(--agent-col-width) 将编辑器核心区域定义为 minmax(0, 1fr)，确保了无论 Vditor 内部渲染了多少宽内容，编辑区都不会溢出，而是出现水平滚动条。这个差异在响应式布局中尤为关键。

### 4\. Pinia Composition API 模式下的大型 Store 需要明确的内部函数分层

workspace.ts 约 1050 行的规模在 Composition API 模式下容易退化为一组互不关联的 ref 和 function。本项目中逐渐形成的组织惯例是：工具函数（如 normalizeTreePath、joinTreePath、getParentPath）放在 defineStore 之外作为模块级纯函数，数据获取函数（如 loadKnowledgeTree、loadFileContent）在 Store 内部负责异步 API 调用和状态更新，用户动作函数（如 selectFile、deleteNode）编排多个获取函数和状态变更，计算属性只做派生数据转换不做副作用。这种分层在排查问题时很有用：当标签页的 dirty 状态不正确时，可以直接定位到 markOpenTabsDirty（工具函数层）和 SSE 事件处理器（数据获取层）之间的交互，而无需阅读整个 Store。

### 5\. WYSIWYG 编辑器的缓存机制在知识管理场景中弊大于利

Vditor 默认启用了基于 localStorage 的缓存机制：编辑器内容会被序列化并存储在浏览器本地存储中，以便用户刷新页面后恢复未保存的内容。在知识管理编辑器的场景中，这个机制引入了两个问题。第一，文件内容是服务端持久化的（通过 writeKnowledgeFile API），localStorage 的缓存版本可能与服务端版本不一致，用户在刷新后看到的是过期的本地副本而非服务端的最新内容。第二，当用户切换到另一个文件时，Vditor 的缓存内容被替换为新文件的内容，再切回旧文件时，localStorage 中可能还残留着新文件的缓存，导致显示错误。disableEditorCache 方法在 after 回调中同时调用 disabledCache() 和 clearCache()，并在每次切换文件时通过 setValue 将正确内容推入编辑器，彻底绕过了 Vditor 的缓存层。这个经验可以推广到其他基于 localStorage 做状态缓存的第三方库：在服务端是唯一真实数据源的应用中，前端缓存层往往制造的同步问题多于它解决的加载速度问题。