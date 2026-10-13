#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""
@Project: 影视解说-文案画面匹配
@File   : script_matching.py
@Description: 将用户审核后的影视解说文案匹配到字幕时间戳并生成最终剪辑脚本
"""

from ..base import ParameterizedPrompt, PromptMetadata, ModelType, OutputFormat


class ScriptMatchingPrompt(ParameterizedPrompt):
    """影视解说文案画面匹配提示词"""

    def __init__(self):
        metadata = PromptMetadata(
            name="script_matching",
            category="film_tv_narration",
            version="v1.0",
            description="将审核后的影视解说文案按叙事节奏拆分，并匹配到字幕时间戳生成最终剪辑JSON",
            model_type=ModelType.TEXT,
            output_format=OutputFormat.JSON,
            tags=["影视", "画面匹配", "剪辑脚本", "时间戳", "用户文案"],
            parameters=[
                "drama_name",
                "drama_genre",
                "plot_analysis",
                "subtitle_content",
                "narration_copy",
                "narration_language",
                "original_sound_ratio",
            ],
        )
        super().__init__(
            metadata,
            required_parameters=["drama_name", "subtitle_content", "narration_copy"],
        )

        self._system_prompt = (
            "你是一位懂影视叙事节奏的剪辑师。你必须严格输出JSON，"
            "核心任务是把用户审核后的解说文案按完整剧情段落匹配到原视频时间戳，保持因果和场景连续。"
        )

    def get_template(self) -> str:
        return """# 影视解说文案画面匹配任务

## 目标
用户已经审核并修改了解说文案。请根据这份文案和原始字幕，生成最终可剪辑 JSON 脚本。

## 作品名
${drama_name}

## 剧情理解材料
<plot>
${plot_analysis}
</plot>

## 用户审核后的解说文案
<narration_copy>
${narration_copy}
</narration_copy>

## 原始字幕（含视频编号和局部时间戳）
<subtitles>
${subtitle_content}
</subtitles>

## 输出语言
<narration_language>
${narration_language}
</narration_language>

## 用户选择的影视类型
<drama_genre>
${drama_genre}
</drama_genre>

## 用户选择的原片占比
<original_sound_ratio>
${original_sound_ratio}%
</original_sound_ratio>

## 匹配流程
1. 先按完整事件和人物线组织解说文案，得到剧情段落；句号不是剪切点，不要一句解说就换一个场景。
2. 逗号只在明显分割两个动作、场景、观点或描述对象时切分；不要切出没有独立意义的碎片。
3. 不要求每个候选句都单独输出为 OST=0；可以合并、压缩相邻候选句作为剧情桥段，但不能改变用户文案的核心意思。
4. 严禁把解说文案匹配到片头、片尾、演职员表、版权声明、平台水印展示、下集预告、花絮、赞助口播、商品露出、贴片广告、中插广告、片中广告或任何与主线剧情无关的推广片段；这些内容绝对不能进入最终 items。
5. 如果字幕或画面文字出现“广告”“赞助”“推广”“片头”“片尾”“预告”“下集”“扫码”“购买”“会员”“关注”等明显非剧情信号，必须跳过对应时间段，不得用作 OST=0 或 OST=1。
6. 为每个解说片段寻找最匹配的原始字幕画面，优先选择能表达该句核心含义、人物状态或信息转折的画面。
7. 使用“解说字数 / 4”粗估正常中文朗读时长，并为停顿、转场留出余量。其他语言按正常朗读速度估算；不得靠加快语速或截断解说适配过短画面。
8. 相邻解说句属于同一事件时，优先合并并使用同一场景的连续画面；确需拆分时也应在事件内部顺接。解说片段通常为 8-20 秒，只有明确的短动作或情绪停顿可以更短，禁止大量 1-3 秒碎片串联。
9. timestamp 必须使用对应 video_id 内部局部时间戳，不得换算为多个视频拼接后的累计时间。
10. 同一 video_id 内时间段不得交叉或重叠。
11. 第一段必须是 OST=0 解说钩子，不能直接播放原片。
12. OST=1 原声片段的总时长占比要尽量接近用户选择的 ${original_sound_ratio}%。这里按最终 items 的 timestamp 总时长估算，不按片段数量估算。
13. 不要自行判断或改写影视类型；画面匹配和 picture 描述要服务用户选择的 ${drama_genre} 叙事重点。
14. 人物线按段落分组，一条线推进到阶段性结果后再切换；同一场景尽量保持时间顺序，跨地点或跨时间时先用解说说明转场，避免无解释地前后跳跃。
15. 原声必须是一句完整对白或一个完整动作，不能只截取半句话。解说负责交代背景、动机和后果，不要先逐字转述一句对白再播放同义原声。
16. 仅凭字幕无法确认画面细节时，picture 只写可确认的场景和人物信息，不得虚构镜头、动作或道具。扩大镜头范围必须仍在字幕支持的同一场景内，不得为了凑够时长跨入无关场景。
17. 背景说明和作者观点也是已审核文案的一部分，不得在匹配画面时删成纯剧情复述。抽象判断应配到支持该判断的人物选择、对话或局势变化，不必为每个抽象词寻找独立镜头。
18. 评论较长时优先保留同一剧情段落的完整画面和正常朗读停顿；时间不足时才合并或压缩重复表述，不能把观点句拆成碎片或靠变速塞进镜头。

## 原片占比规则
- ${original_sound_ratio}% = 0% 时，不要输出 OST=1，全部使用解说承接。
- ${original_sound_ratio}% 在 10%-30% 时，只保留关键对白、信息反转、情绪爆发或名场面原声。
- ${original_sound_ratio}% 在 40%-60% 时，解说负责串联因果，原片负责承载关键场面和对白。
- ${original_sound_ratio}% 在 70%-90% 时，以原片对白和表演为主，解说只做开场钩子、转场桥和必要补充。
- 如果原片占比与“第一段必须 OST=0”冲突，优先保证第一段是 OST=0，然后在后续片段提高 OST=1 时长占比。
- 选择高原片占比时，可以把用户文案合并成更少的 OST=0 桥段，不要为了逐句使用文案而压低原片占比。

## 字段规则
- _id：从 1 开始连续递增。
- video_id：来自字幕分段标题，例如“视频 2”就填 2。
- video_name：对应视频文件名，必须从字幕分段标题提取。
- timestamp：格式为 "HH:MM:SS,mmm-HH:MM:SS,mmm"。
- picture：描述匹配画面中人物、动作、情绪、场景和关键道具。
- narration：OST=0 时填写用户文案片段；OST=1 时填写“播放原片+_id”。
- OST：解说片段填 0，原声片段填 1。

## 输出格式
只输出严格 JSON：

{
  "items": [
    {
      "_id": 1,
      "video_id": 1,
      "video_name": "1.mp4",
      "timestamp": "00:00:01,000-00:00:06,000",
      "picture": "主角站在走廊尽头，回头看向紧闭的房门",
      "narration": "他以为自己终于逃出了那间房，可真正的危险，其实才刚刚醒来。",
      "OST": 0
    }
  ]
}

现在请基于用户审核后的解说文案生成最终剪辑脚本。"""
