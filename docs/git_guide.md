# Git 手动操作笔记

本文档记录本项目常用的 Git 操作。命令默认在项目根目录运行。

## 查看状态

```powershell
git status
```

简洁版：

```powershell
git status --short --branch
```

常见标记：

- `M`：已修改。
- `??`：新文件，还没有加入版本管理。
- `A`：已加入暂存区的新文件。

## 查看改动

查看所有文本改动：

```powershell
git diff
```

只看某个文件：

```powershell
git diff README.md
```

查看改动统计：

```powershell
git diff --stat
```

## 暂存文件

暂存单个文件：

```powershell
git add README.md
```

暂存多个文件：

```powershell
git add README.md docs/git_guide.md .gitignore
```

暂存当前目录下所有未忽略文件：

```powershell
git add .
```

如果目录里有大量计算结果，建议不要直接 `git add .`，先用 `git status --short` 检查。

## 提交

```powershell
git commit -m "Update project documentation"
```

提交信息建议用一句话说明本次改动。例如：

- `Update README and Git guide`
- `Add dense phase diagram scripts`
- `Refresh DSF plotting outputs`

## 推送到远端

```powershell
git push
```

如果本地分支还没有关联远端：

```powershell
git push -u origin main
```

## 常用完整流程

```powershell
git status --short --branch
git diff --stat
git add README.md docs/git_guide.md .gitignore
git status --short
git commit -m "Update README and Git guide"
git push
```

## 取消暂存

只是不想把文件放进这次提交，但保留文件内容：

```powershell
git restore --staged README.md
```

取消所有暂存：

```powershell
git restore --staged .
```

## 放弃本地修改

这个命令会丢掉文件的本地修改，使用前要确认：

```powershell
git restore README.md
```

不建议随手对整个项目运行 `git restore .`，容易误删自己刚写的内容。

## 本项目建议

- 代码、文档、绘图脚本适合提交。
- 小型 CSV、DAT、SVG、PDF、PNG 结果可以按需要提交。
- 大型中间数据、临时下载目录和日志不建议提交。
- 提交前先跑 `julia --project=. test\runtests.jl`。
