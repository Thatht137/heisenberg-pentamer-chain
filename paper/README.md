# 中文 LaTeX 论文使用说明

## 编译

在仓库根目录运行：

```powershell
powershell -ExecutionPolicy Bypass -File paper/build.ps1
```

输出：

```text
paper/build/main.pdf
```

也可以进入 `paper/` 后直接运行：

```powershell
latexmk -xelatex -interaction=nonstopmode -halt-on-error main.tex
```

清理编译缓存：

```powershell
powershell -ExecutionPolicy Bypass -File paper/clean.ps1
```

## 文件职责

| 文件 | 用途 |
|---|---|
| `main.tex` | 宏包、标题、摘要和章节顺序 |
| `sections/introduction.tex` | 研究背景、问题和贡献 |
| `sections/model_methods.tex` | 模型、算法、参数和观测量 |
| `sections/results.tex` | 只写数据直接支持的结果 |
| `sections/discussion.tex` | 解释、比较、限制和后续问题 |
| `sections/conclusion.tex` | 收束主要结论 |
| `bibliography.bib` | BibTeX/BibLaTeX 文献库 |
| `latexmkrc` | XeLaTeX 自动编译配置 |

## 日常写作循环

1. 只选择一个小节或一张图作为本次任务。
2. 修改对应的 `sections/*.tex`。
3. 运行 `paper/build.ps1`。
4. 打开 `paper/build/main.pdf` 检查公式、图、图注和分页。
5. 运行 `git diff` 检查实际修改。
6. 完成一个小结论后提交一次 Git。

## 常用 LaTeX

章节：

```latex
\section{结果}
\subsection{负侧弦关联}
```

行内公式：

```latex
负侧指数为 $\eta_{\mathrm{str}}\approx0.27$。
```

独立公式：

```latex
\begin{equation}
C(r)\propto r^{-\eta}.
\label{eq:power-law}
\end{equation}
```

引用公式：

```latex
由\cref{eq:power-law}可知……
```

插图：

```latex
\begin{figure}[tb]
  \centering
  \includegraphics[width=0.85\textwidth]{example.pdf}
  \caption{图注先写直接观测，再写参数和限制。}
  \label{fig:example}
\end{figure}
```

引用图片：

```latex
如\cref{fig:example}所示……
```

三线表：

```latex
\begin{table}[tb]
  \centering
  \caption{有限尺寸拟合结果。}
  \label{tab:fits}
  \begin{tabular}{ccc}
    \toprule
    $L$ & $\eta$ & 拟合窗口 \\
    \midrule
    60 & 0.24 & $3\le d\le7$ \\
    80 & 0.27 & $3\le d\le9$ \\
    \bottomrule
  \end{tabular}
\end{table}
```

引用文献：

```latex
Li 等研究了四聚体链的弦关联与激发谱\cite{li2026tetramer}。
```

## 中文到英文的正确流程

1. 中文阶段先稳定论点、证据、图和结论边界。
2. 不逐句翻译零散笔记，而是按完整段落翻译。
3. 每段保持一个任务：观察、标度、解释或限制。
4. 术语统一后再翻译标题、摘要和图注。
5. 英译完成后保留 Git 提交，便于与中文版本逐段比较。

不建议同时维护两套长期分叉的中文和英文主稿。推荐在中文 Results 稳定后创建
一个翻译分支，将各小节原位替换为英文。
