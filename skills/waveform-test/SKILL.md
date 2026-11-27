---
name: waveform-test
description: 一次调用完成示波器采集或已有波形回放、原生标定、幅度与频率分析，并交付图片、文字说明和 Excel。
---

# 波形测试

用户说“测试波形”“开始捕获”时，调用唯一的 MCP 工具 `run_waveform_test`。未指定输入时直接采集 CH1，默认创建新目录。已有采集可传 csv_file、同帧 screen_file 和 capture_file；已复核的采用值可传 durations_file 与 profile_file。具备终端的客户端也可以执行同一流程 `waveform-test run`。

按[数据规范](../../waveform_test/数据规范.md)核对同帧截图、周期复现、停顿、幅频口径和采用值。长记录分辨不清时说明所需补采条件。没有原生截图的回放会标明采样重绘。

当 status 为 complete，将 description 及 files 中的周期标记图、幅频趋势图、文字和 Excel 文件直接交给用户；可预览图片时展示两张图。若 status 为 needs_review，说明 reason，给出 data_directory 并使用已保存的数据复核。
