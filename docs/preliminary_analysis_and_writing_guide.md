# 初步分析与协作写作指南

## 当前一句话论点

在 `beta=0.5` 的五聚体自旋链中，现有多重态、实空间关联、弦关联、边缘响应、
纠缠和动力学证据支持由 `alpha=0` 特殊解耦点分隔的两个临界区域；负侧具有慢
代数弦关联与边缘特征，正侧为以 `q=pi` 为主的常规无隙反铁磁区域，但负侧的
gapless SPT 命名和完整二维相图仍需服务器级验证。

## 已完成的证据链

1. 修复孤立五聚体 ED 的简并子空间 `S^2` 分类，确认负 `alpha` 的最低多重态为
   `S=3/2`、正 `alpha` 为 `S=1/2`，`alpha=0` 存在八重低能流形。
2. 完成 `beta=0.5` 的能量、弦序、导数、纠缠、边缘磁化、静态关联和有限尺寸
   标度分析。
3. 用多初态和双向参数延拓识别靠近 `alpha=0` 的高能假收敛分支。
4. 证明负侧低能分支的普通自旋关联为幂律，`eta≈0.89-0.94`。
5. 证明正侧普通关联为幂律，`eta≈0.95-0.98`，主波矢保持 `q=pi`。
6. 完成五点试验性 DSF，未发现 `0.17<alpha<0.30` 的独立第四相证据。
7. 识别负侧 `q≈3pi/5` 到 `q=pi` 的动量重分配，但没有把它误写为相界。
8. 在低能延拓 MPS 上重算负侧弦关联，得到 `eta_str≈0.23-0.28`，指数拟合
   明显差于幂律拟合。
9. 完成 Li 等（2026）范围审计：沿用“多重态—弦关联—纠缠—DSF”证据链，
   不直接移植四聚体相名、弦端点和准粒子名称。

## 当前初步相结构

### 负 `alpha`

- 普通自旋关联代数衰减，是临界体态而非普通有隙 Haldane 相。
- 弦关联也呈缓慢代数衰减，指数显著小于普通自旋关联。
- 存在局域边缘响应和特殊 Schmidt 低能簇。
- 安全名称：`具有弦与边缘特征的临界区域`。
- 候选名称：`gapless SPT-like regime`，目前不能作为确定相名。

### 正 `alpha`

- 能隙外推接近零，普通关联为幂律。
- 静态和动力学低能权重主要位于 `q=pi`。
- `alpha≈0.17` 与 `0.30` 是不同观测量的响应尺度，不是已建立的两条相界。
- 安全名称：`常规无隙反铁磁临界区域`。

### `alpha=0`

- 是孤立单胞八重低能简并的特殊解耦点。
- 两侧低能多重态、弦关联、边缘响应和动量结构在此重组。
- 当前可作为两个临界区域的分隔点写入 `beta=0.5` 截面结论。

### `alpha≈-0.3`

- 主波矢由折叠的 `3pi/5` 转向 `pi`。
- 关联指数连续，双向能量没有稳定滞后。
- 当前只称候选 Lifshitz 或动量重分配尺度，不列为第四相。

## 还缺什么

### 初步组会不需要等待

- 当前证据已经足够制作组会图、写 Results 初稿和向学长汇报。
- 不需要继续追加本机 DMRG 才能开始写作。

### 服务器优先任务

1. 运行 `scripts/run_negative_dsf_validation_server.sh 4`。
2. 计算 `L=80`、`tmax=30` 的
   `alpha=-0.50,-0.10,-0.05,0.23` DSF。
3. 后续扩展 `L=120,160` 的负侧普通关联和临界弦关联。
4. 最后实现虚空间投影对称表示，决定能否使用 gapless SPT 名称。

## 从零开始写论文

### 第一步：先写证据，不写摘要

推荐顺序：

1. 整理最终图和每张图的一句话结论。
2. 写 Methods，记录模型、边界条件、DMRG/TEBD 参数和拟合窗。
3. 按图顺序写 Results。
4. 再写 Discussion，区分直接证据、推断和未解决问题。
5. 最后写 Introduction、Conclusion、Abstract 和 Title。

不要从摘要开始，也不要先决定“这是 Haldane 相”再寻找证据。

### 第二步：建立论文目录

建议在当前仓库中使用：

```text
paper/
  main.tex
  sections/
    introduction.tex
    model_methods.tex
    results.tex
    discussion.tex
    conclusion.tex
  figures/
  bibliography.bib
  notes/
    meeting_notes.md
    claim_evidence.md
```

正文最终使用 LaTeX。日常会议记录、待办和结论—证据表先用 Markdown，因为
Markdown 修改快、冲突少，适合 Git/JJ 协作。不要用 Word 作为唯一主稿。

### 第三步：每个写作任务只解决一个问题

一个合格任务示例：

```text
解释 Fig. 4 中负侧弦关联为何支持慢代数衰减，
只修改 paper/sections/results.tex 和对应图注。
```

不合格任务示例：

```text
把整篇论文写完并顺便重画所有图。
```

## Git 入门流程

### 第一次配置

```powershell
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
git status
```

### 每次开始工作

```powershell
git switch analysis/string-distance
git pull --rebase
git status
```

如果仓库暂时没有远程仓库，跳过 `git pull --rebase`。

### 为一个写作任务创建分支

```powershell
git switch -c writing/negative-string-results
```

分支只做一个主题。计算代码、图和文字若属于同一证据，可以放在同一分支；
无关修改不要混入。

### 写作过程中的最小循环

```powershell
git status --short
git diff
git add paper/sections/results.tex
git add figures/negative_string_continuation_b0.5.pdf
git commit -m "Write negative-side string scaling result"
```

每个提交应当可以用一句话说明，并包含完整的小结论。不要把几十个无关文件一次
提交为 `update`。

### 与学长协作

```powershell
git push -u origin writing/negative-string-results
```

然后在 GitHub/GitLab/Gitee 创建 Pull Request 或 Merge Request，让学长逐行
评论。修改后继续提交并推送，不要删除旧评论对应的历史。

### 合并后继续

```powershell
git switch analysis/string-distance
git pull --rebase
git branch -d writing/negative-string-results
```

## JJ 入门流程

JJ 适合频繁改写历史和并行写作，但它不替代远程托管平台。初学时推荐：

1. 先用 Git 完成两到三个小任务，理解分支、提交和 PR。
2. 再在同一个 Git 仓库中使用 JJ。
3. 远程协作仍通过 GitHub/GitLab/Gitee 的 Git 分支和 PR 完成。

初始化已有 Git 仓库：

```powershell
jj git init --colocate .
jj status
jj log
```

开始一个新修改：

```powershell
jj new -m "Draft negative string scaling result"
```

修改文件后直接查看：

```powershell
jj diff
jj status
```

JJ 会自动跟踪工作区，不需要 `git add`。完成当前修改后：

```powershell
jj describe -m "Draft negative string scaling result"
jj new
```

为准备推送的提交加书签：

```powershell
jj bookmark create writing/negative-string-results -r @-
jj git push --bookmark writing/negative-string-results
```

初期不要在同一时刻混用 Git 命令改历史和 JJ 命令改历史。可以用 Git 查看和
推送，但选择一种工具负责日常提交操作。

## 推荐选择

- 现在先用 Git：资料最多，学长更容易参与，PR 审稿流程直观。
- Markdown 管理会议记录、任务和证据矩阵。
- LaTeX 管理论文主稿、公式、图表编号和参考文献。
- 等你完成第一版 Results 后，再尝试 colocated JJ。

## 下一次写作任务

1. 创建 `paper/` 骨架。
2. 把 `docs/beta_half_results_draft.md` 中已经稳定的英文 Results 拆入
   `paper/sections/results.tex`。
3. 建立 `paper/sections/model_methods.tex`，先写模型和数值参数。
4. 建立 `paper/notes/claim_evidence.md`，复制并持续维护当前证据矩阵。
5. 每完成一个小节提交一次，并通过 PR 请学长审阅。
