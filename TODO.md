# 最高优先级规则：对用户提供的 TODO，必须**逐句**建立可验证的实现与验收对应关系,**必须**自己根据TODO反复逐句修改,**绝对禁止**自己随便实现一个长得像TODO但不符合用户的TODO的某一句的事情发生,每一句用户TODO都要在代码中有迹可循,每一句TODO都要遵守开发规范。禁止将任何一项降级为 MVP、替代实现或视觉近似；如无法复用用户指定组件，必须先说明阻塞并征得用户同意。完成前必须逐项进行实际界面冒烟验证，并报告未完成项。

- 题外话: MHS,Anthropic发明的新接口体系,使得AI物联网成为现实,可能成为和MCP同等级的AI统一化接口.

### UI/UX
- [ ] 工作区大卡片响应式布局优化: 主要测试手段是打开联网搜索侧边栏然后拽住左边拖动,此时工作区大卡片就会左右坍缩,根据当前宽度实现响应式布局:

### TODOs
- [ ] 给readme加badge(![显示名称](https://img.shields.io/badge/左边文字-右边文字-颜色),或者可跳转的[![Release](https://img.shields.io/badge/release-v1.8.0-brightgreen)](https://github.com/你的用户名/你的仓库/releases),或者动态badge![Stars](https://img.shields.io/github/stars/OWNER/REPO))
### IDEAs
- [ ] DSH Adapter的实现
  - 文档位于`docs/ADAPTER_DESIGN.md`
### BUGs
