# AI 反思日志

## 基本信息

| 字段 | 内容 |
|------|------|
| 姓名 | 徐光修 |
| 负责模块 | 知识库基础设施：文件树（递归文件树构建与前端联动）、搜索框（全文搜索+语义搜索+文件名搜索三路联合）、知识图谱（Canvas 可视化+力导向布局+文件树适配器）、知识库文件管理系统（CRUD + 上传 + 路径安全） |

---

## AI 帮忙解决了什么

### 1. 递归文件树构建与前端节点的数据格式对齐

写 `KnowledgeLibraryService._path_to_node()` 时需要设计一个前端可以直接消费的树节点结构。AI 给出了包含 `name`、`path`、`isDir`、`mtime`、`size`、`indexStatus`、`children` 的递归结构，其中 `children` 只在 `isDir=true` 时出现。`_sort_path` 的排序键设计（`0 if dir else 1` + 名称小写）也是 AI 建议的——文件夹排在文件前面，同级按名称字典序。这个格式和前端 `KnowledgeFileNode` 类型直接对应，几乎不需要额外转换。

### 2. 搜索片段构建的边界处理

`_build_search_snippet()` 需要在匹配位置前后各取 80 个字符作为上下文片段，但要处理三种边界情况：靠前（`position < 80`，不加 `...` 前缀）、靠后（`position + query_length + 80 > content_length`，不加 `...` 后缀）、查询词本身为空（`query_length = 0` 直接处理）。AI 给出的三行核心逻辑覆盖了全部边界，比我最初手写的 `if-else` 金字塔简洁得多。

### 3. `fileTreeGraphAdapter.ts` 中文件树到图谱的映射

把嵌套的 `KnowledgeFileNode[]` 文件树转换为扁平的 `KnowledgeGraphModel`（nodes + links）时，需要同时处理三个问题：合成根节点的创建、文件夹/文件的区分样式（radius 随 depth 递减）、中文排序。AI 给出的 `appendTreeNodes` 递归方案用 `sortedChildren` 做了中文排序（`localeCompare(..., 'zh-Hans-CN')`），`createLink` 用 `parentId → node.path` 构建边。`nodeRadius` 函数让文件夹直径比文件大，深层节点比浅层小，视觉层次清晰。

### 4. Canvas 图谱的视口变换与命中检测

`KnowledgeGraphCanvas.vue` 中需要实现缩放/平移/节点拖拽/双击聚焦。AI 建议的方案是 `screenToWorld` / `worldToScreen` 两个坐标变换函数配合 `viewport = { x, y, scale }` 状态对象。`handleWheel` 中以鼠标位置为锚点缩放（而不是以画布原点），代码也就 6 行。`hitTestNode` 用世界坐标下的圆形命中检测，长宽比 `1:1` 以内视为命中。这些函数在 `graphGeometry.ts` 中集中维护，画布组件只调度不计算。

### 5. 路径穿越防护的统一模式

`KnowledgeLibraryService` 中有多处需要把用户传入的相对路径解析为绝对路径（读文件、写文件、删除、重命名），每处都要防止路径穿越攻击。AI 建议了 `_resolve_child_path` / `_resolve_child_dir` + `_is_relative_to` 的统一模式：先用 `(root / relative_path).resolve()` 展开所有 `..` 和符号链接，然后 `candidate.relative_to(root)` 检查是否还在根目录内。这个模式复用了 6 处，每处都是 3 行代码。

---

## AI 没帮上忙 / 做错了什么

### 1. `_path_to_node` 对大目录的性能问题

AI 最初的实现是每次调用 `list_files()` 时`Path.iterdir()` 后对每个子路径递归调用 `_path_to_node`，而 `_path_to_node` 里又调了两次 `path.stat()`（一次 `is_dir()`、一次 `stat.st_size` / `st_mtime`）。对于深层嵌套目录，这导致大量 `stat` 系统调用。我手动改成了一次 `path.stat()` 拿到全部元信息再分发，不过 `path.is_dir()` 和 `path.stat()` 之间还是有重复。后续应该考虑用 `os.scandir()` 或者 `pathlib.Path` 的缓存。

### 2. 搜索框对二进制文件的处理

AI 的 `search_file_contents()` 直接 `path.read_text(encoding="utf-8")`，但如果知识库里混入了二进制文件（例如上传时漏过滤），`read_text()` 会抛出 `UnicodeDecodeError`。AI 没有处理这个异常。后来我手动加了 `except (OSError, UnicodeDecodeError): continue` 跳过不可读文件。同样地，文件后缀白名单过滤也是在测试中发现 PDF 被包含进来后才加的——`supported_suffixes` 默认包含 `.pdf`，但 `read_text` 读不了 PDF。

### 3. 图谱 Canvas 的 DPI 适配

AI 给的 Canvas 绘制代码在普通屏幕上正常，但在 Retina/HiDPI 显示器上模糊。原因是没有考虑 `window.devicePixelRatio`。我手动加了第 120-121 行 `context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0)` 和第 147-149 行 `canvas.width = floor(width * pixelRatio)` 的适配代码，才在 MacBook 的外接 4K 显示器上清晰。

### 4. 力导向布局初始位置聚类

`createLayeredForceSimulation` 分层布局如果初始 node 位置都集中在原点，d3-force 的 `alpha` 衰减完之前展开不完全，出现节点堆叠。AI 没处理初始位置分布，我手动在每个节点的 `targetX`/`targetY` 上按环半径预分布了一下（虽然最终 `fitGraphToViewport` 会重置视口，但布局质量确实改善了）。

---

## 踩过的坑

### 1. `pathlib.Path.stat()` 缓存问题

坑：`_path_to_node` 中先调 `path.is_dir()` 再调 `path.stat().st_size`，但 `is_dir()` 内部实际执行了一次 `lstat`。然后再调 `stat()` 又是一次系统调用。在高延迟文件系统（网络挂载）上，一个包含 2000 个文件的目录列出文件树耗时 3 秒多。

教训：`Path.stat()` 返回的 `stat_result` 包含了 `st_mode`（可以判断文件类型），不应该分开调 `is_dir()` 和 `stat()`。但 `pathlib` 没有提供"取一次 stat 然后复用"的原生方式。可以用 `os.scandir()` 替代迭代。

### 2. 前端 `watch` 的深度响应问题

坑：`KnowledgeGraphCanvas.vue` 通过 `watch(() => props.model, () => startSimulation())` 监听文件树变化后重绘。但 `props.model` 是作为一个普通 prop 传入的，父组件如果直接修改已有对象的属性（而不是替换整个对象），Vue 的 `watch` 不会触发。结果用户在编辑器里新增文件后，图谱没有自动刷新。

教训：父组件必须用展开替换（`model = { ...newModel }`）而不是修改属性（`model.nodes.push(xxx)`）。同时加了一个 `reheatLayout()` 的暴露方法做手动兜底。

### 3. `_is_relative_to` 在 Windows 上的大小写问题

坑：`_is_relative_to` 内部用 `path.relative_to(root)` 判断子路径。在 Windows 上，路径比较默认大小写不敏感（文件系统是 NTFS，不区分大小写），但 Python 的 `relative_to` 是字符串比较，`C:\Users\Foo` 和 `C:\users\foo` 路径语义相同但 `relative_to` 认为不相同。

教训：Windows 上需要在比较前统一用 `Path.resolve()` 展开大小写。目前代码里已经做了 `.resolve()`，但因为文件系统本身不区分大小写，所以解析后的大小写由实际磁盘决定。这个问题还没有完全解决，后续应该用 `Path.samefile()` 做兼容判断。

### 4. 知识图谱 Canvas 在组件卸载时的事件清理

坑：`window.requestAnimationFrame` 在 `onBeforeUnmount` 中调了 `cancelAnimationFrame`，但如果在 `unmount` 和动画帧回调之间进了 `requestDraw`，新的 `animationFrame` ID 没有记录，导致泄露。

教训：应该在 `stopSimulation` 里同时清理动画帧，或者用 `shallowRef` 管理生命周期状态，`requestDraw` 入口先检查组件是否还挂载。

---

## 学到的经验

### 1. "三路搜索"比单一方案鲁棒得多

`search_knowledge` 这个内置工具同时做了文件名匹配、全文内容搜索和语义搜索三路。设计理念是：**文件名搜索最快但可能改名了找不到、全文搜索最全面但大目录慢、语义搜索能搜到语义相近但字面不匹配的内容**。三路联合的结果交给 LLM 去综合判断。实际测试中，用户问"帮我找一下关于海洋酸化的文档"，即使文件名不含"海洋酸化"（比如叫 `ocean.txt`），全文匹配也能命中。

### 2. 知识库文件管理最容易被忽视的是安全

`KnowledgeLibraryService` 看似简单的 CRUD，安全细节非常多：
- 路径穿越：`_resolve_child_path` + `_is_relative_to` 防止 `../../etc/passwd`
- 上传文件名清洗：`Path(filename).name` 去掉目录部分，防止 `../../../evil.txt`
- 编码安全：`write_text(encoding="utf-8")` 显式指定编码，避免跨平台乱码
- 竞争条件：复制时检查 `target.exists()` 防止覆盖，但 `check-then-act` 不是原子操作

### 3. Canvas 2D 相比 SVG 在大规模节点上的性能优势

知识图谱最初用 SVG + DOM 实现，500 个节点时拖拽就卡顿了。换成 Canvas 2D 后 2000 个节点仍然流畅。关键差异：Canvas 的 `requestAnimationFrame` + 增量重绘模式，把布局计算和绘制分离。d3-force 的 `simulation.on('tick')` 只更新 node 位置，`requestDraw` 合并多次 tick 为一次绘制帧。这种"计算和渲染解耦"的模式值得在其他前端性能场景中复用。

### 4. 文件事件监听的双路径策略

`/knowledge/files/events` SSE 端点同时支持 watchdog（Linux/macOS 上的 `inotify`/`FSEvents`）和轮询（Windows 上 watchdog 可能不可用）两种模式。这是我从 ChromaDB 回退策略学到的方法论：**优先用最高效的方案，但永远准备一个兜底**。`_polling_event_stream` 每 1.5 秒比对文件树签名，虽然不如 watch 实时，但保证功能完整可用。
