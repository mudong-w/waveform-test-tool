# 波形测试工具

连接 UNI-T UTD2202CEX+ 的 CH1，让屏幕铺满多个周期。启用插件后说 **“测试这个波形，把标记图、幅频图和说明给我”**。插件通过一个工具 `run_waveform_test` 获取长记录和同帧截图，调用内置原版标定页导出周期标记图，处理幅度和频率，最后返回文字及文件路径。

## 安装和启用

在连接仪器的电脑上安装 Python 3.10+、可用的 NI-VISA 和 Edge、Chrome 或 Chromium。下载发行页的 waveform-test-plugin.zip 并解压。在解压目录中运行 `python -m pip install 安装包/waveform_test_tool-0.3.1-py3-none-any.whl`。也可以在解压的仓库根目录运行 `python -m pip install .`。确保客户端可找到该环境中的 `waveform-test-mcp` 可执行文件。[发行下载](https://github.com/mudong-w/waveform-test-tool/releases/latest)

插件仓库自带 MCP 配置和波形测试技能。支持本地插件的客户端加载仓库目录后启用 waveform-test。其他 MCP 客户端添加一个本地 stdio 服务，命令填写 `waveform-test-mcp` 或其完整路径，参数留空。工具列表应只有 `run_waveform_test`。启用后按用户请求采集。

## 一次运行

```shell
waveform-test run --out runs/test-01
```

默认选择唯一受支持的设备，冻结并保存 CH1 和同帧原生截图，恢复采集状态并完成报告。也可指定 `--resource`。默认识别阈值为相对基线的绝对电压第 99.9 百分位的 20%，实际阈值写入报告数据。用 `--threshold`、`--baseline`、`--stage-gap`、`--packet-gap` 和 `--stages` 可按波形调整。自动周期识别适用于具有可辨空闲间隔和可见复现的重复脉冲列。

已有记录使用同一个入口。采集器标准目录中的 waveform.csv 会自动配对同目录的 screen-original.bmp 和 capture.json。其他命名请显式指定：

```shell
waveform-test run --csv trace.csv --screen same-frame.bmp --capture-file capture.json --out runs/replay
```

仅有 CSV 时周期图标明采样重绘。驱动标定页的浏览器可用环境变量 `WAVEFORM_BROWSER` 指定。原生图使用内置的[示波器标定画图工具](waveform_test/annotator/示波器标定画图工具.html)导出，报告中的标注工程可在同一编辑器中重新打开。

## 数据规范与采用值

[数据规范](waveform_test/数据规范.md)随源码和安装包发布，覆盖测量口径、分段与复现、同排标记、双栏趋势和交付核对。用 `--durations` 传入已复核的时长，例如 `{"gap1":1.0,"t1":3.0}`。经复核的幅频曲线用 `--profile` 提供，例如下列合成平台。MCP 对应参数为 durations_file 和 profile_file。

```json
{"t1":{"amplitude_vpp":[[0,20],[1,20]],"frequency_hz":[[0,100],[1,100]]}}
```

逐脉冲频率、组内脉冲频率、组重复频率分别保存。提供采用值时，图、表和文字共用该组参数，保留实测与组间停顿。只提供原始采样时，趋势显示测量结果。已确认的分组波形在每组内取峰峰值并保留静默，长组分窗统计，原始逐窗证据同时保留。未确认的名义参数需要另行复核。

## 用户收到的结果

| 文件 | 内容 |
|---|---|
| cycle.png | 一轮原生周期标记及右侧复现，或注明来源的采样重绘 |
| trends.png | 整轮幅度与脉冲频率 |
| 说明.txt | 分段时长、幅度、频率及可确认的组重复频率 |
| 汇总表.xlsx | 参数和与交付图一致的内嵌图 |
| 数据/ | 原始采样、同帧底图、采集参数（如有）、标注工程和实测统计 |

MCP 直接返回说明正文和四个文件的绝对路径。周期复现不足或原生标定失败时，返回需要复核的原因并保留已取得的原始记录。已有命令行脚本仍可调用单步子命令，面向用户的工作流始终使用 `run`。许可为 MIT。
