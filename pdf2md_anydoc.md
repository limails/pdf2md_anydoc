# pdf2md_anydoc 使用文档

> 用 [anydoc](https://github.com/firecrawl/anydoc) 把一个目录下的所有 PDF 批量转成 Markdown。
> 零第三方依赖，只用 Python 标准库。

---

## 目录

1. [快速开始](#1-快速开始)
2. [它做什么 / 不做什么](#2-它做什么--不做什么)
3. [命令行接口](#3-命令行接口)
4. [设计思路](#4-设计思路)
5. [实现方法](#5-实现方法)
6. [环境依赖与安装](#6-环境依赖与安装)
7. [使用注意点](#7-使用注意点)
8. [已知限制](#8-已知限制)
9. [故障排查](#9-故障排查)
10. [验收清单](#10-验收清单)
11. [相关程序](#11-相关程序)

---

## 1. 快速开始

```powershell
# 前置：全局安装 anydoc（不要用 npx，见 7.1）
npm install -g @firecrawl/anydoc

# 把当前目录下所有 PDF 转成 Markdown，输出到 .\<目录名>_md\
python pdf2md_anydoc.py <目录>
```

举例：

```
输入  F:\work\rtest\papers\        （含 3 个 PDF）
输出  F:\work\rtest\papers_md\     （自动新建）

F:\work\rtest\papers\JBJS英文.pdf  →  F:\work\rtest\papers_md\JBJS英文.md
F:\work\rtest\papers\中文表格.pdf  →  F:\work\rtest\papers_md\中文表格.md
F:\work\rtest\papers\大文件.pdf    →  F:\work\rtest\papers_md\大文件.md
```

运行输出：

```
pdf2md_anydoc 1.0.0 | anydoc: C:\Users\...\AppData\Roaming\npm\anydoc.CMD
输入 C:\...\papers（3 个 PDF） -> 输出 C:\...\papers_md
----------------------------------------------------------------------
  [成功] JBJS英文.pdf                                 0.1s  13,012 B -> JBJS英文.md
  [成功] 中文表格.pdf                                 0.1s   4,143 B -> 中文表格.md
  [成功] 大文件.pdf                                   0.1s  40,232 B -> 大文件.md
----------------------------------------------------------------------
成功 3 个，失败 0 个，共 3 个，输出合计 57,387 B
```

---

## 2. 它做什么 / 不做什么

### 做

- 遍历指定目录**本层**（不递归）的所有 `.pdf`
- 逐个调用 `anydoc <pdf> -o <输出路径>` 转换成 Markdown
- 输出到 `<原目录名>_md\`（与原目录同级）
- 文件名与源文件同名，仅扩展名不同
- 单个文件失败不中断整批，末尾汇总并打印失败清单
- 已存在的同名 `.md` 直接覆盖

### 不做

| 不做的事 | 原因 / 替代方案 |
| --- | --- |
| **递归子目录** | 按需求约定只处理本层。需要递归请对每个子目录分别调用 |
| **任何后处理** | 输出的是 anydoc 原始结果，不删图片、不清标签、不改格式。清洗版见 [pdf2md_mineru.py](pdf2md_mineru.py) |
| **OCR** | anydoc 本地不做 OCR。扫描件会以退出码 3 失败，见 [7.2](#72-扫描件会失败) |
| **保留 PDF 里的小节顺序调整** | 完全交给 anydoc，程序不介入 |
| **移动 / 修改源 PDF** | 源文件全程只读 |
| **图片导出** | anydoc 对 PDF 内嵌图片输出 alt 文本，不导出图片文件 |

---

## 3. 命令行接口

```
pdf2md_anydoc.py <目录> [选项]
```

### 位置参数

| 参数 | 说明 |
| --- | --- |
| `<目录>` | 包含 PDF 的目录。必须是**已存在的目录**，传文件会报错退出 2 |

### 选项

| 选项 | 默认 | 说明 |
| --- | --- | --- |
| `--output 目录` | `<原目录名>_md` | 输出目录。不指定则与原目录同级；指定了则按给的来（相对/绝对路径都行） |
| `--anydoc 路径` | 自动定位 | 指定 anydoc 可执行文件，或它所在的目录 |
| `--timeout N` | `300` | 单个文件的转换超时秒数 |
| `--version` | — | 打印版本号后退出 |
| `--help` | — | 打印帮助后退出 |

### 退出码

| 码 | 含义 |
| --- | --- |
| `0` | 全部成功，**或**目录内没有 PDF 文件 |
| `1` | 有文件转换失败（已处理完其余文件） |
| `2` | 用法错误：路径不存在、传了文件而非目录、`--anydoc` / `ANYDOC_EXE` 无效、无法创建输出目录 |

---

## 4. 设计思路

理解这几条比读代码更重要。

### 4.1 为什么不自己解析 PDF

anydoc 已经解决了 PDF 转 Markdown 里最难的部分：字形编码反查、Type1/TrueType 字体差异、表格结构推断、阅读顺序判定。自己写等于重造一个 PDF 库。

本程序的价值**只在批量调度**：找文件、起进程、管超时、记失败、汇总报告。这正是 `anydoc` CLI 不提供的部分。

### 4.2 为什么不做后处理

同一份 PDF 换引擎输出差别很大（见 [11. 相关程序](#11-相关程序)）。如果本程序也做清洗，就没法用它和 MinerU 版对拍，判断清洗步骤各值多少。

所以职责切得很干净：

```
pdf2md_anydoc.py   调度层，不碰内容
pdf2md_mineru.py   调度层 + 5 步后处理
```

需要干净输出就用 MinerU 版；需要看引擎原始行为、或需要快（anydoc 单文件约 0.1s，MinerU 约 5~9s），用本程序。

### 4.3 为什么输出到独立目录

`papers` → `papers_md` 而不是就地生成 `papers\*.md`，有三个理由：

1. **可整体删除重建**。重跑时输出目录里的孤儿 `.md` 可以直接清空，不会和源文件混在一起
2. **源目录保持纯净**。批量处理时不会往源目录里塞几十个生成物
3. **命名无歧义**。`X.pdf` 和 `X.md` 同名，一旦就地生成，工具链里同时存在两者容易搞混哪个是产物

### 4.4 为什么覆盖而不报错

批量重跑是主要使用场景。若每次都因同名文件中断，跑第二遍就得先手动清理。加上 `--force` 之类的开关又增加心智负担。直接覆盖，配合独立输出目录，可预期。

### 4.5 为什么不中断

一个损坏的 PDF 不应该让整批 50 个文件白跑。失败记录进清单，末尾统一报，退出码 1 供脚本判断。

### 4.6 失败必须可诊断

anydoc 的原始报错要透传。它输出带 ANSI 红色（`\x1b[31m...`），直接打印会污染日志，所以先剥颜色码，再剥掉 `anydoc: ` 前缀，只留有信息量的部分。

---

## 5. 实现方法

### 5.1 整体流程

```
入口（一个目录）
  │
  ├─ 1. 校验参数
  │     路径存在？是目录？                    否 -> 退出码 2
  │
  ├─ 2. 收集目标
  │     iterdir() 本层，筛 .pdf（忽略大小写）
  │     跳过 ~$ 开头的 Word 锁文件
  │     为空 -> 提示并退出码 0（不建输出目录）
  │
  ├─ 3. 确定输出目录
  │     --output 或 <原目录名>_md            mkdir(parents=True, exist_ok=True)
  │
  ├─ 4. 定位 anydoc                          见 5.3
  │
  └─ 5. 逐个转换（失败不中断）
        ├─ subprocess.run([anydoc, pdf, -o, dest], timeout=N)
        ├─ 退出码 != 0 -> 记入失败清单，继续下一个
        ├─ 退出码 == 0 但产物不存在 -> 记为失败（防御性检查）
        └─ 成功 -> 打印字节数与用时
  │
  └─ 6. 汇总：成功 N / 失败 M；有失败则打印清单并返回 1
```

### 5.2 关键实现点

| 点 | 做法 |
| --- | --- |
| **启动外部进程** | `subprocess.run(cmd, capture_output=True)`。不用 shell，避免路径含空格/中文时的引号问题 |
| **anydoc 的输出** | 用 `-o` 指定文件路径，而非重定向 stdout。anydoc 的 `-o` **不会自动建父目录**，所以输出目录必须先 `mkdir` |
| **超时** | `subprocess.run(timeout=)`。超时抛 `TimeoutExpired`，捕获后记为该文件失败 |
| **中文输出花屏** | `main()` 里调 `force_utf8_stdout()`，把 stdout/stderr `reconfigure(encoding="utf-8", errors="replace")`。Windows 控制台默认 GBK，不设会花屏 |
| **环境变量兜底** | 所有 `os.environ.get(...)` 都带默认值（`APPDATA`、`ANYDOC_EXE`），因为换机器时这些变量未必存在 |
| **字节数格式化** | 千分位（`13,012`），批量输出时更易扫读 |

### 5.3 anydoc 的定位策略

按优先级依次尝试，命中即用：

| 优先级 | 途径 | 说明 |
| --- | --- | --- |
| 1 | `--anydoc 路径` | 显式指定，**无效时立即报错退出 2，不静默回退** |
| 2 | 环境变量 `ANYDOC_EXE` | 适合非标准位置，无需改代码。无效时同样报错 |
| 3 | PATH（`shutil.which`） | 常规途径，命中 `anydoc` / `anydoc.cmd` / `anydoc.exe` |
| 4 | `%APPDATA%\npm\` | npm 全局安装目录，`npm config get prefix` 的典型值 |
| 5 | 脚本目录 `node_modules\.bin\` | 项目内安装的情况 |
| 6 | 有限广搜 | 脚本目录、用户目录，深度 ≤ 3，跳过 `node_modules`、`.git`、`site-packages` 等 |

全部未命中时，错误信息会**列出所有已尝试的路径**，并给出三条解决办法（全局安装 / 设环境变量 / 本次指定），而不是只说「找不到 anydoc」。

> 为什么 `--anydoc` 和 `ANYDOC_EXE` 无效时要报错而不回退：静默回退会让使用者以为指定生效了，实际跑的是另一个副本，排查起来很费时间。

### 5.4 文件筛选规则

```python
p.suffix.lower() == ".pdf"        # 忽略大小写，.PDF / .Pdf 都收
not p.name.startswith("~$")      # 跳过 Word 锁文件
p.is_file()                      # 不含子目录
```

用 `iterdir()` 而非 `rglob()`，实现「只处理本层」。

---

## 6. 环境依赖与安装

| 依赖 | 要求 | 验证命令 |
| --- | --- | --- |
| 操作系统 | Windows（代码跨平台，但验证环境是 Windows 11） | — |
| Python | 3.8+ | `python --version` |
| Python 第三方包 | **无** | — |
| Node.js | 必需（anydoc 是 npm 包） | `node --version` |
| anydoc | 必需，**必须全局安装** | `anydoc --version` |

安装 anydoc：

```powershell
npm install -g @firecrawl/anydoc
anydoc --version     # 应输出形如 0.2.4
```

验证环境：Windows 11、Python 3.13.1、Node v24.13.1、anydoc 0.2.4。

---

## 7. 使用注意点

### 7.1 必须全局安装，不能用 npx

**这是最容易踩的坑。**

```powershell
npx @firecrawl/anydoc a.pdf          # ❌ 失败
npm install -g @firecrawl/anydoc     # ✅ 可用
```

`npx` 会报：

```
Error: Cannot find native binding.
npm has a bug related to optional dependencies (npm/cli#4828)
```

原因：anydoc 的主包通过 `optionalDependencies` 声明 7 个平台二进制
（`anydoc-win32-x64-msvc`、`anydoc-linux-x64-gnu` 等）。`npx` 把主包解压到
临时缓存时没把平台二进制一起拉下来，于是找不到 8.3MB 的原生 DLL。

**解法**：用全局安装。本程序定位到的正是 `%APPDATA%\npm\anydoc.CMD`。

### 7.2 扫描件会失败

anydoc **本地不做 OCR**。纯图片 / 扫描版 PDF 会以退出码 3 失败，程序会打印：

```
  [失败] scan.pdf   0.4s  PDF 有页面需要 OCR（本工具不做 OCR）：...
```

这不是程序缺陷，是 anydoc 的设计。可选出路：

1. 换 [pdf2md_mineru.py](pdf2md_mineru.py)（MinerU 自带 OCR）
2. 先用 OCR 工具处理成有文字层的 PDF，再喂进来
3. anydoc 支持 `--ocr hosted` 上传到 Firecrawl Parse 云端 —— 但本程序**不暴露这个选项**，因为那意味着数据离开本机

> Word 导出的 PDF 通常有文字层，可正常转换。实测一份 Word 生成的申报表 PDF 转换正常。

### 7.3 输出是引擎原始结果

本程序不改内容，所以 anydoc 的已知缺陷会**原样出现在产物里**：

| 现象 | 实测（某英文期刊 PDF） |
| --- | --- |
| 段落被合并成大块 | 59 个段落块 → 17 个，最长一行 2911 字符 |
| 标题层级丢失 | 4 个 `##` → 1 个，`## Abstract` 被拍平成正文 `Abstract Background: ...` |
| 图片全丢 | PDF 里有 1 张图，输出 0 处引用 |
| 变音符脱落 | `Frölke` → `Fr¨olke`（PDF 缺 ToUnicode 表所致，anydoc 与 MinerU 都有此问题） |

**如果你要的是能直接喂 LLM 的文本，用 `pdf2md_mineru.py`。**

### 7.4 `~$` 开头的文件会被跳过

Word 打开文档时会在同目录生成 `~$文件名.docx` 锁文件。虽然不是 PDF，但已排除，避免误处理。

### 7.5 输出目录名带 `_md` 后缀

`src.with_name(stem + "_md")`，其中 `stem = src.name.rstrip(" .")`。

- `papers` → `papers_md`
- `papers\` → `papers_md`（尾部反斜杠由 `pathlib` 归一化）
- `我的资料.` → `我的资料_md`（尾部空格点被剥掉，避免生成非法目录名）

目录已存在时 `exist_ok=True`，直接复用。

### 7.6 同名不同扩展名不冲突

`.PDF` 和 `.pdf` 在 Windows 上是同一个文件，不会出现。若目录里同时有 `a.pdf` 和 `a.PDF`（Linux 挂载可能出现），两者都映射到 `a.md`，后者覆盖前者。

### 7.7 重复运行会覆盖

同名 `.md` 直接覆盖，不提示、不备份。**手改过的产物会在重跑时丢失**，重要文件请自行备份或用 `--output` 输出到别处。

### 7.8 单文件耗时

anydoc 是纯 Rust 实现，中位转换时间约 4.4ms/文档（项目 benchmark 数据），实测本机单文件约 **0.1s**（含进程启动）。

对比 MinerU 版：单文件约 **5~9s**（要加载模型）。文件多时差异显著。

---

## 8. 已知限制

以下是已确认存在、当前接受不修的不足。

1. **不递归子目录。** 按需求约定。需要递归时对每个子目录分别调用，或改 `collect_pdfs` 用 `rglob("*")` 并自行设计输出布局。

2. **不暴露 `--ocr hosted`。** anydoc 支持把需要 OCR 的文档传到 Firecrawl Parse 云端，但那意味着文件离开本机。本程序刻意不开这个口。确有需要请直接调 anydoc。

3. **不暴露 anydoc 的 `--format`。** anydoc 靠文件内容嗅探格式，扩展名错标也能正确识别，本程序不需要这个选项。

4. **不传 stdin。** anydoc 支持 `anydoc -` 从管道读，批量场景用不上。

5. **`--timeout` 只管单文件。** 没有整批的总超时。极端情况下（大目录 + 全部卡住）需要 Ctrl+C。

6. **PDF 里嵌的图表会被丢成 alt 文本。** anydoc 不导出图片文件。这是引擎行为，不是本程序的取舍。

---

## 9. 故障排查

| 症状 | 原因 | 处理 |
| --- | --- | --- |
| `找不到 anydoc。已尝试：...` | 没装，或没装到 PATH | `npm install -g @firecrawl/anydoc`；或 `--anydoc` 指定；或设 `ANYDOC_EXE` |
| `Cannot find native binding` | 用了 npx / npm optional deps bug | 全局安装，见 [7.1](#71-必须全局安装不能用-npx) |
| `不是目录：xxx.pdf` | 位置参数传了文件 | 本程序只接受目录。单文件请直接用 `anydoc x.pdf -o x.md` |
| `路径不存在：xxx` | 路径拼错或相对路径基准不对 | 确认当前工作目录 |
| `[失败] xxx.pdf ... malformed document` | 文件不是真 PDF（改过扩展名）或已损坏 | 确认文件真实格式 |
| `[失败] xxx.pdf ... PDF 有页面需要 OCR` | 扫描件 | 见 [7.2](#72-扫描件会失败) |
| `[失败] xxx.pdf ... 转换超时` | 文件异常大或 anydoc 卡住 | 调大 `--timeout`；单独试 `anydoc xxx.pdf` |
| 输出中文花屏 | PowerShell 用了 GBK 解码 UTF-8 | 终端先执行 `[Console]::OutputEncoding=[Text.Encoding]::UTF8`（只影响显示，不影响 `.md` 文件内容） |
| `.md` 文件中文乱码 | 用错编码打开 | 产物是标准 UTF-8 无 BOM，用 UTF-8 打开 |

诊断技巧：加 `--output` 输出到别处，或直接手动调 anydoc 对比。

```powershell
anydoc "某个.pdf"                        # 看 anydoc 自己的行为
anydoc "某个.pdf" -o "t.md"; echo $LASTEXITCODE   # 看退出码
```

---

## 10. 验收清单

自测时逐项确认。样本目录里应有：中文文件名 PDF、英文 PDF、损坏文件、
`~$` 锁文件、`.txt`、子目录各一个。

| # | 检查项 | 期望 |
| --- | --- | --- |
| 1 | 退出码（全部成功） | `0` |
| 2 | 退出码（有失败） | `1`，且末尾有失败清单 |
| 3 | 退出码（路径不存在 / 传文件 / `--anydoc` 无效） | `2` |
| 4 | 输出目录名 | `<原目录名>_md`，与原目录同级 |
| 5 | `.md` 文件名 | 与源 PDF 同名，仅扩展名不同 |
| 6 | 子目录里的 PDF | **未**被处理 |
| 7 | `.txt` / 无扩展名文件 | 未被处理 |
| 8 | `~$` 锁文件 | 未被处理 |
| 9 | `.PDF` 大写扩展名 | 被处理 |
| 10 | 中文文件名 | 正常处理 |
| 11 | 损坏 PDF | 记为失败，不中断后续文件 |
| 12 | 重复运行 | 覆盖，无报错 |
| 13 | 空目录 | 提示「目录内没有 PDF 文件」，退出 `0`，**不创建** `_md` 目录 |
| 14 | `--output` 指定 | 输出到指定位置，产物与默认位置逐字节一致 |
| 15 | 源 PDF 是否被修改 | 否 |
| 16 | 产物编码 | UTF-8 无 BOM |

---

## 11. 相关程序

同一台机器上还有两个姊妹程序，定位不同，可对拍：

| 程序 | 引擎 | 输入 | 输出 | 后处理 | 单文件耗时 |
| --- | --- | --- | --- | --- | --- |
| **pdf2md_anydoc.py**（本程序） | anydoc 0.2.4 | 目录，不递归 | `<目录名>_md\` | 无 | ~0.1s |
| pdf2md_mineru.py | MinerU 4.0.8 | 文件或目录（递归） | 源文件同目录同名 `.md` | 5 步 | ~5~9s |
| docx2md.py | pandoc | `.doc` / `.docx` | 源文件同目录 + `.media\` | 4 步 | — |

三者互不依赖，可独立运行。

### 该选哪个

```
需要能直接喂 LLM 的干净文本？      -> pdf2md_mineru.py
需要最快 / 想看引擎原始输出？      -> pdf2md_anydoc.py（本程序）
有 .docx 源文件？                 -> docx2md.py（别绕 PDF，PDF 只记录每个字的坐标，逆向重建必然有损）
```

### 同源 PDF 的实测对比

对同一份英文期刊 PDF（4 页、1 张图）：

| 检查项 | anydoc（本程序） | MinerU 版 |
| --- | --- | --- |
| 输出体积 | 13 KB | 12.9 KB（清洗后）/ 54 KB（原始） |
| 段落块数 | **17** | **59** |
| 二级标题数 | **1** | **4** |
| 图片 | **0** | 1（原始为 base64，清洗后为 `[图片 1]`） |
| 残留 CMS 标签 | **0** | 清洗后 0（原始 18 个） |
| Markdown 列表语法 | **22 个 `- `** | 清洗后 22 个 |

**结论：给 LLM 用，MinerU 版胜在段落粒度和标题层级**（分块质量的关键指标）。
anydoc 胜在快一个数量级、输出无标签噪音。
