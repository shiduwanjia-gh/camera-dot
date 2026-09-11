# Camera Dot 摄像头小红点指示器

一个轻量的 Windows 托盘小工具：在系统后台静默运行，**当摄像头被任何程序（微信、Zoom、浏览器等）占用时，在屏幕右上角显示一个醒目的红色圆点**，像硬件摄像头指示灯一样，随时提醒你"摄像头正在使用中"。

## ✨ 特性

- 🚫 **无任务栏图标** —— 隐藏在系统托盘，右键可退出
- 🔴 **屏幕右上角红点提醒** —— 无边框、置顶、透明背景，不占任务栏
- ⚡ **纯 Python + OpenCV**，无重型依赖，单文件 exe 不到 15MB
- 🎯 **精准判断** —— 通过 PnP 设备枚举区分"摄像头不存在"和"摄像头被占用"
- 👆 点击红点可临时隐藏；占用结束后红点自动消失
- 🔧 可配置：红点大小、监控的摄像头序号、探测间隔

## 📸 截图

（运行后打开任意视频会议软件即可看到右上角红点）

## 🚀 快速开始

### 直接运行

```bash
pip install pystray opencv-python pillow
python camera_dot.py
```

### 打包成无控制台 exe

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --clean camera_dot.py
```

生成的 `dist\camera_dot.exe` 即最终程序。如需开机自启，将其放入启动文件夹（`Win+R` 输入 `shell:startup` 回车）。

## ⚙️ 配置

在 `camera_dot.py` 顶部修改：

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `CAMERA_INDICES` | `(0, 1, 2)` | 要监控的摄像头序号 |
| `POLL_INTERVAL` | `1.5` | 探测间隔（秒），指示灯闪烁可调大 |
| `DOT_SIZE` | `32` | 红点直径（像素） |
| `DOT_MARGIN` | `10` | 红点距屏幕右上角的边距 |

## 🔍 工作原理

后台线程每隔一段时间用 DirectShow（`cv2.CAP_DSHOW`）尝试打开摄像头：

- **能打开** → 摄像头空闲，立即释放
- **打不开但设备存在**（通过 PowerShell 的 `Get-PnpDevice -Class Camera` 确认设备确实存在）→ 判定为被占用，显示红点

使用 DirectShow 后端探测速度快，且不会点亮摄像头的硬件指示灯。

## ⚠️ 说明

- 仅支持 Windows（依赖 PnP 设备枚举和 DirectShow）
- 每次探测会极短暂地初始化摄像头，个别设备可能出现指示灯微闪，调大 `POLL_INTERVAL` 可缓解
- Windows 10/11 自带右下角相机指示灯，本工具将其"挪"到更显眼的右上角
- 仅供隐私提醒用途，请勿用于任何违法场景

## 📄 许可证

MIT License
