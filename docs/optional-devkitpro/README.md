# optional-devkitpro · 官方 devkitPro 路线（当前网络下不可用）

这个目录里的两个文件是**官方 devkitPro 路线**的产物，被你当前的网络环境挡住了，
所以本工程默认不用它们。留在这里供你以后有可用代理/VPN 时切换。

## 里面的东西

| 文件 | 说明 |
|---|---|
| `install-devkitpro.ps1` | 下载并静默安装 devkitPro 工具链，然后安装 `gba-dev` 包（devkitARM + libtonc + grit + gbafix） |
| `Makefile` | 官方 libtonc 模板的 Makefile，配合 devkitARM 使用 |
| `build-with-make.ps1` | 用 devkitPro 自带的 MSYS2 + make 来构建的脚本（本工程早期版本，路线不同） |

## 为什么当前用不了

| 环节 | 结果 |
|---|---|
| 下载安装器（`objects.githubusercontent.com`） | ❌ 连接超时 |
| 安装器取软件包（`pkg.devkitpro.org`） | ❌ Cloudflare 返回 403 "Sorry, you have been blocked" |

两处都过不去，所以不是"慢"，是拿不到。

## 如果以后要切过来

```powershell
# 1. 确认代理/VPN 已生效，然后：
.\docs\optional-devkitpro\install-devkitpro.ps1

# 2. 把官方 Makefile 复制回工程根目录
Copy-Item .\docs\optional-devkitpro\Makefile .\Makefile

# 3. 之后就可以用官方工作流（需要 devkitPro 自带的 MSYS2 环境）
```

切过去之后多出来的能力：

- **`grit`**：官方的 PNG → tile / 调色板 / 地图转换工具。本工程目前没有等价工具，
  需要做 tile 背景时我们得另写一个 Python 转换器（见 `docs\04-学习路线.md` 的 M3）。
- **`maxmod` 音频库**（`-lmm`）：做背景音乐方便很多。
- 与绝大多数 Tonc 教程的环境完全一致。

## 现在这套为什么不影响你学 GBA

代码层面用的是同一个 `libtonc`，`REG_DISPCNT`、`vid_mem`、`key_poll()` 这些
写法完全通用——它们来自 libtonc 库，而不是来自构建系统。
差别只在"怎么编译"这一步，而那一步已经由 `build.ps1` 替你做好了。
