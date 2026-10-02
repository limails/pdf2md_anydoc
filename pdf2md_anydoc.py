#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pdf2md_anydoc —— 用 anydoc 把一个目录下的所有 PDF 批量转成 Markdown。

用法：
    pdf2md_anydoc.py <目录>
    pdf2md_anydoc.py ./papers --output ./out
    pdf2md_anydoc.py ./papers --anydoc "C:\\...\\anydoc.cmd"

输出：
    输入 D:\\papers\\in\\      ->  输出 D:\\papers\\in_md\\
    每个 X.pdf 生成同名 X.md，文件名与源文件一致。

与 pdf2md_mineru.py 的区别：那个用 MinerU 并做后处理（去 base64 图片、
清 CMS 标签、修变音符）；这个直接输出 anydoc 的原始结果，不做任何
改写，便于对拍两者的差异。

零第三方依赖，只用 Python 标准库。
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

VERSION = "1.0.0"
DEFAULT_TIMEOUT = 300

EXIT_OK = 0
EXIT_PARTIAL = 1
EXIT_USAGE = 2

ANSI = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")

# anydoc 的退出码含义（见 anydoc --help）
ANYDOC_EXIT = {
    0: "成功",
    1: "文件无法读取或转换",
    2: "用法错误",
    3: "PDF 有页面需要 OCR（本工具不做 OCR）",
}


def die(code, msg):
    sys.stderr.write("错误：%s\n" % msg)
    sys.exit(code)


def force_utf8_stdout():
    """Windows 控制台默认 GBK，中文进度信息会花屏。强制 UTF-8 并容错。"""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def human(n):
    return "{:,}".format(n)


def clean_err(text):
    """剥掉 anydoc 输出的 ANSI 颜色码，压成单行便于展示。"""
    text = ANSI.sub("", text or "")
    lines = [x.strip() for x in text.strip().splitlines() if x.strip()]
    if not lines:
        return ""
    # anydoc 的错误形如 "anydoc: malformed document: ..."
    msg = lines[-1]
    for prefix in ("anydoc: ", "Error: "):
        if msg.startswith(prefix):
            msg = msg[len(prefix):]
    return msg


# ---------------------------------------------------------------- 定位 anydoc

def _is_anydoc(p):
    """文件名像不像 anydoc 命令垫片。"""
    return Path(p).stem.lower() == "anydoc"


def find_anydoc(explicit):
    """按优先级定位 anydoc 可执行垫片。

    注意：不能用 npx —— 已知 npm optional-dependencies bug 会导致
    平台二进制缺失，报 "Cannot find native binding"。必须用全局安装。
    """
    tried = []

    def hit(p):
        return str(p) if p else None

    if explicit:
        p = Path(explicit)
        if p.is_dir():
            for cand in ("anydoc.cmd", "anydoc.ps1", "anydoc.exe", "anydoc"):
                c = p / cand
                if c.is_file():
                    return str(c)
            die(EXIT_USAGE, "--anydoc 指定的目录里没有 anydoc 命令：%s" % explicit)
        if not p.is_file():
            die(EXIT_USAGE, "--anydoc 指定的路径无效（不存在或不是文件）：%s" % explicit)
        return str(p)

    env = os.environ.get("ANYDOC_EXE", "").strip()
    if env:
        p = Path(env)
        if p.is_dir():
            for cand in ("anydoc.cmd", "anydoc.ps1", "anydoc.exe", "anydoc"):
                c = p / cand
                if c.is_file():
                    return str(c)
        elif p.is_file():
            return str(p)
        die(EXIT_USAGE, "环境变量 ANYDOC_EXE 指向的路径无效：%s" % env)

    found = shutil.which("anydoc") or shutil.which("anydoc.cmd") or shutil.which("anydoc.exe")
    if found:
        return found

    here = Path(__file__).resolve().parent
    appdata = os.environ.get("APPDATA", "")
    candidates = []
    if appdata:
        candidates += [
            Path(appdata) / "npm" / "anydoc.cmd",
            Path(appdata) / "npm" / "anydoc",
            Path(appdata) / "npm" / "anydoc.ps1",
        ]
    candidates += [
        here / "node_modules" / ".bin" / "anydoc.cmd",
        here / "node_modules" / "@firecrawl" / "anydoc" / "cli.js",
    ]
    for c in candidates:
        tried.append(str(c))
        if c.is_file():
            return str(c)

    # 有限广搜：深度 <= 3，只找名字像 anydoc 的可执行文件
    skip = {"node_modules", ".git", "AppData", "site-packages", "__pycache__"}
    roots = [here, Path.home()]
    if appdata:
        roots.append(Path(appdata) / "npm")
    for base in roots:
        if not base.is_dir():
            continue
        base_depth = len(base.parts)
        for root, dirs, files in os.walk(str(base)):
            rp = Path(root)
            dirs[:] = [d for d in dirs if d not in skip]
            if len(rp.parts) - base_depth > 3:
                dirs[:] = []
                continue
            for f in files:
                if _is_anydoc(f) and os.path.splitext(f)[1].lower() in (".cmd", ".exe", ".ps1", ""):
                    return str(rp / f)

    msg = ["找不到 anydoc。已尝试：",
           "  1. --anydoc 显式指定",
           "  2. 环境变量 ANYDOC_EXE",
           "  3. PATH",
           "  - npm 全局目录（%APPDATA%\\npm）",
           "  - 脚本所在目录的 node_modules\\.bin"]
    for t in tried:
        msg.append("  - " + t)
    msg += [
        "",
        "解决办法：",
        "  a. 全局安装（不要用 npx）：npm install -g @firecrawl/anydoc",
        "  b. 设环境变量：setx ANYDOC_EXE \"%APPDATA%\\npm\\anydoc.cmd\"",
        "  c. 本次运行指定：pdf2md_anydoc.py <目录> --anydoc \"<路径>\"",
    ]
    die(EXIT_USAGE, "\n".join(msg))


# ---------------------------------------------------------------- 单文件转换

def convert_one(pdf, anydoc, dest_dir, timeout):
    """转换单个 PDF。返回 (输出 .md 路径, 字节数, 用时秒, 错误信息)。"""
    dest = dest_dir / (pdf.stem + ".md")
    cmd = [anydoc, str(pdf), "-o", str(dest)]
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, 0, time.time() - t0, "转换超时（超过 %d 秒）" % timeout
    except OSError as e:
        return None, 0, time.time() - t0, "无法启动 anydoc：%s" % e
    elapsed = time.time() - t0

    if proc.returncode != 0:
        detail = clean_err(proc.stderr) or clean_err(proc.stdout) or "无错误输出"
        reason = ANYDOC_EXIT.get(proc.returncode, "未知退出码")
        return None, 0, elapsed, "%s：%s" % (reason, detail)

    if not dest.is_file():
        return None, 0, elapsed, "anydoc 退出码为 0 但未生成 %s" % dest.name

    return dest, dest.stat().st_size, elapsed, None


# ---------------------------------------------------------------- 入口

def collect_pdfs(directory):
    out = []
    for p in sorted(directory.iterdir()):
        if not p.is_file():
            continue
        if p.suffix.lower() != ".pdf":
            continue
        if p.name.startswith("~$"):
            continue
        out.append(p)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="pdf2md_anydoc.py",
        description="用 anydoc 把一个目录下的所有 PDF 批量转成 Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  pdf2md_anydoc.py .\\papers\n"
               "  输出：.\\papers_md\\\n"
               "  pdf2md_anydoc.py .\\papers --output .\\out\n"
               "  pdf2md_anydoc.py .\\papers --anydoc \"%APPDATA%\\npm\\anydoc.cmd\"\n",
    )
    ap.add_argument("directory", help="包含 PDF 的目录（只处理本层，不递归）")
    ap.add_argument("--output", metavar="目录", default="",
                    help="输出目录，默认 <原目录名>_md，与原目录同级")
    ap.add_argument("--anydoc", metavar="路径", default="",
                    help="指定 anydoc 可执行文件（或其所在目录）")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, metavar="N",
                    help="单文件转换超时秒数，默认 %d" % DEFAULT_TIMEOUT)
    ap.add_argument("--version", action="version",
                    version="pdf2md_anydoc %s" % VERSION)
    args = ap.parse_args(argv)

    force_utf8_stdout()

    src = Path(args.directory)
    if not src.exists():
        die(EXIT_USAGE, "路径不存在：%s" % src)
    if not src.is_dir():
        die(EXIT_USAGE, "不是目录：%s" % src)

    pdfs = collect_pdfs(src)
    if not pdfs:
        print("目录内没有 PDF 文件：%s" % src)
        return EXIT_OK

    if args.output:
        dest_dir = Path(args.output)
    else:
        stem = src.name.rstrip(" .")
        dest_dir = src.with_name(stem + "_md")
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        die(EXIT_USAGE, "无法创建输出目录 %s：%s" % (dest_dir, e))

    anydoc = find_anydoc(args.anydoc)
    print("pdf2md_anydoc %s | anydoc: %s" % (VERSION, anydoc))
    print("输入 %s（%d 个 PDF） -> 输出 %s" % (src, len(pdfs), dest_dir))
    print("-" * 68)

    ok, failures, total_bytes = 0, [], 0
    for pdf in pdfs:
        dest, size, elapsed, err = convert_one(pdf, anydoc, dest_dir, args.timeout)
        if dest is None:
            print("  [失败] %-40s %5.1fs  %s" % (pdf.name, elapsed, err))
            failures.append((pdf, err))
            continue
        ok += 1
        total_bytes += size
        print("  [成功] %-40s %5.1fs  %s B -> %s"
              % (pdf.name, elapsed, human(size), dest.name))

    print("-" * 68)
    print("成功 %d 个，失败 %d 个，共 %d 个，输出合计 %s B"
          % (ok, len(failures), len(pdfs), human(total_bytes)))
    if failures:
        print("失败清单：")
        for pdf, err in failures:
            print("  %s —— %s" % (pdf.name, err))
        return EXIT_PARTIAL
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
