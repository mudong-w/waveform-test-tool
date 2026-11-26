# 波形测试工具

保存示波器当前的长记录，从间隔起点找出一个完整的脉冲输出周期，用下一轮可见的波形复核，再生成周期标记图、幅度与频率趋势、文字说明和带图的 Excel 汇总表。

同一套程序提供命令行、MCP 和 AI 技能入口。USB 采集适配 **UNI-T UTD2202CEX+ 的 CH1**。其他仪器可导出等间隔采样的 CSV，使用离线分析功能。识别算法面向有明确空闲间隔、重复输出的脉冲序列。

## 五分钟试用

需要 Python 3.10 或以上版本。在克隆的仓库目录运行下列命令。建议在独立的 Python 虚拟环境中安装。

```shell
python -m pip install .
waveform-test demo --out runs/demo
waveform-test analyze runs/demo/waveform.csv --threshold 3 --out runs/demo-report
```

示例由程序合成。每轮 4 s，组内脉冲 100 Hz，脉冲组每秒重复 5 次，双极性输出为 20 Vpp。记录从一段间隔的中途开始，用于检验程序能否跳过残段。运行后打开 `runs/demo-report/汇总表.xlsx`。

## 从仪器采集

### 离线标定画图工具

[下载独立标定工具 ZIP](https://github.com/mudong-w/waveform-test-tool/releases/download/v0.1.1/waveform-annotator.zip)，解压后双击 **示波器标定画图工具.html** 即可使用。也可以直接打开源码中的 [HTML 文件](waveform_test/annotator/示波器标定画图工具.html)。安装 Python 插件后，运行 `waveform-test annotate` 打开同一工具，或用 `waveform-test annotate --path` 查看位置。

使用 `--screen` 分析成功后，先在标定工具里导入报告 `data/` 下的原生截图，再载入同目录的 **标注工程.json**。间隔、t1 等分段和整轮 T 的标记都可以拖动和改字。手动编辑后可导出新的 PNG 和工程 JSON。工程的横轴按实测时间标定；需要测量电压时，可用截图上的电压刻度标定纵轴。[标定工具使用说明](waveform_test/annotator/使用说明.md)

### USB 连接和采集

在连接示波器的电脑上安装可用的 VISA 后端。该机型开发流程使用 Windows 和 NI-VISA。USB A–B 数据线接示波器设备口。将待测波形接 CH1，在仪器上确认探头倍率和垂直量程，让记录覆盖多个周期。

```shell
python -m pip install ".[usb]"
waveform-test devices
waveform-test capture --out runs/capture-01
waveform-test analyze runs/capture-01/waveform.csv --screen runs/capture-01/screen-original.bmp --threshold 3 --out runs/report-01
```

`capture` 冻结当前采集，读取原生 BMP、波形字节与换算系数，保存时间、电压和 ADC 码，随后恢复波形传输配置与原运行状态。该适配器使用仪器当前的 RAW 读取范围。检查 `capture.json` 的点数、记录时长、ADC 满量程样本数及 ASCII 电压交叉检查结果。多台设备可加 `--resource` 指定枚举得到的地址。需要选用特定 VISA 库时可设置环境变量 `WAVEFORM_VISA_LIBRARY`。

原生标记目前适用于 **800 × 480、全宽时间轴、青色 CH1** 的同帧图像。程序检查屏幕活动边缘和采样边缘是否对齐；校准失败时给出原因。省略 `--screen` 可以单独复核采样数据，周期图会明确显示为采样重绘。

## 分析判断与参数

1. **先保存长记录。** 标记从完整起始间隔到下一轮相同位置的一轮，右侧应看到下一轮开始输出。当前算法从最长的重复段间停顿选起点，检查复现段的持续时间、活动占比和幅度。没有明显起始间隔、连续正弦或每轮次序改变的波形，需要人工判断。对称子周期可能有多种解释，可按已知协议指定 `--stages 4`。
2. **分开三个时间尺度。** `--threshold` 是相对空闲基线的活动阈值（V），基线可用 `--baseline` 指定。`--stage-gap` 是区分两个输出段的最短静默时间（默认 0.35 s）。`--packet-gap` 是区分两个脉冲组的最小同极性脉冲间距（默认 0.05 s）。根据被测信号选择阈值，避免把低频脉冲拆成单独的组。
3. **分别看幅度和两种频率。** 幅度趋势为 0.1 s 窗内峰峰值，分段表保留整段极值。频率散点由同极性阈值上跳的相邻脉冲间距计算，组间停顿会断开频率点。组重复频率取相邻脉冲组起点的间距。脉冲频率中位采样间距少于 4 个样点时，程序省略该段脉冲频率。削顶、噪声、混叠和脉冲漏采都可能影响结果，应以较高采样率的局部记录复核；不能仅凭稀疏数据区分线性扫频和小台阶。
4. **保留实测值，统一报告值。** 每段采用时长默认等于实测时长。比如经复核希望 t3 采用 20.0 s，新建 UTF-8 文件 `durations.json`，内容为 `{"t3": 20.0}`，运行分析时加 `--durations durations.json`。程序重算所有后续时间点和整轮周期。原生图上箭头仍对准实际边缘，趋势图按采用时长映射。显示四舍五入不影响数据文件的精度。
5. **检查交付。** 确认周期起点、右侧复现、幅度单位和频率含义，再核对 Excel 中的参数及两张图。每次写入新的输出目录。

## 输出文件

| 文件 | 内容 |
|---|---|
| `cycle.png` | 单周期标记与后续复现。使用原生截图或明确注明的采样重绘 |
| `trends.png` | 完整周期的幅度、脉冲频率及 t1、t2 等分段 |
| `说明.txt`、`汇总表.xlsx` | 分段说明、采用与实测时长、幅度和频率、内嵌图 |
| `data/` | 原始 CSV、输入的原生截图、分段表、趋势点和带识别参数的 JSON |

自己的 CSV 使用 UTF-8 编码，至少包含 `time_s,CH1_V` 两列，分别为秒和伏特，采样时间严格递增且等间隔。其他列可以保留。

## 供其他 AI 使用

**MCP 客户端**可以通过本机标准输入输出调用工具。执行 `python -m pip install ".[usb,mcp]"`，在客户端的 MCP 配置中添加下例；如果客户端不能继承终端的 PATH，将 command 改成虚拟环境中该可执行文件的绝对路径。

```json
{
  "mcpServers": {
    "waveform-test": {
      "command": "waveform-test-mcp",
      "args": []
    }
  }
}
```

MCP 提供 `list_scopes`、`capture_record` 和 `analyze_record`。传入的是运行服务那台电脑上的文件路径。导入 CSV 做离线分析时，仅需安装 `.[mcp]`。支持 Agent Skills 的助手可以加载 [波形测试技能](skills/waveform-test/SKILL.md)。使用 Claude Code 时也可从本地克隆目录运行 `claude --plugin-dir .`。可执行命令的其他 AI 可以直接使用 CLI。

给助手的示例请求：**“读取我保存的长记录，先确认一个完整周期和下一轮复现，再按 t1、t2 标记。把两张图、分段表和文字说明存进一个新目录。”**

## 许可

MIT。仓库示例为合成信号。VISA 驱动由使用者从相应厂商安装。
