"""Plan source ranges and a shared, millisecond-accurate editing timeline.

Planning is independent of FFmpeg and UI state. Renderers consume the same
records; only the rendered video path and source offset differ between outputs.
"""

import os
from decimal import Decimal, InvalidOperation


def seconds_to_milliseconds(seconds):
    try:
        value = Decimal(str(seconds))
        if not value.is_finite() or value < 0:
            raise ValueError("时长必须是有限的非负数")
        return int(value * 1000)
    except (InvalidOperation, TypeError):
        raise ValueError(f"无效的时长: {seconds}") from None


def parse_time_milliseconds(value):
    parts = str(value).strip().replace(",", ".").split(":")
    if len(parts) != 3:
        raise ValueError(f"不支持的时间格式: {value}")
    try:
        hours, minutes = int(parts[0]), int(parts[1])
        seconds = Decimal(parts[2])
        if hours < 0 or not 0 <= minutes < 60 or not seconds.is_finite() or not 0 <= seconds < 60:
            raise ValueError(f"无效的时间: {value}")
        return (hours * 3600 + minutes * 60) * 1000 + seconds_to_milliseconds(seconds)
    except InvalidOperation:
        raise ValueError(f"无效的时间: {value}") from None


def format_time_milliseconds(value):
    seconds, milliseconds = divmod(value, 1000)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def normalize_video_paths(video_origin_path, video_origin_paths=None):
    if isinstance(video_origin_paths, str):
        video_origin_paths = [video_origin_paths]
    paths = [video_origin_path, *(video_origin_paths or [])]
    return list(dict.fromkeys(p.strip() for p in paths if isinstance(p, str) and p.strip()))


def resolve_video_path(item, paths):
    if not paths:
        raise ValueError("视频文件不能为空")
    explicit = (item.get("source_video_path") or item.get("video_origin_path")
                or item.get("origin_video_path"))
    if explicit and os.path.exists(explicit):
        return explicit
    name = os.path.basename(str(item.get("video_name") or item.get("source_video") or "").strip())
    if name:
        for path in paths:
            if os.path.basename(path) == name:
                return path
    try:
        index = int(item.get("video_id") or item.get("video_index"))
        if 1 <= index <= len(paths):
            return paths[index - 1]
    except (ValueError, TypeError):
        pass
    return paths[0]


def build_editing_timeline(script, tts_results, video_origin_path, video_origin_paths=None,
                           *, media_duration=None):
    """Return independent records with source and target ranges, in script order.

    OST 0/2 use the matched TTS duration; OST 1 uses the script range. IDs
    take precedence over timestamps, whose fallback must be unambiguous.
    An optional media-duration reader caps ranges before either output runs.
    Invalid/missing segments fail before any rendering, never silently disappear.
    """
    paths = normalize_video_paths(video_origin_path, video_origin_paths)
    if not paths:
        raise ValueError("视频文件不能为空")
    by_id, by_timestamp = {}, {}
    for result in tts_results or []:
        item_id = result.get("_id")
        if item_id is not None:
            if item_id in by_id:
                raise ValueError(f"重复的配音片段 ID: {item_id}")
            by_id[item_id] = result
        if result.get("timestamp"):
            by_timestamp.setdefault(result["timestamp"], []).append(result)

    timeline, seen, cursor, durations = [], set(), 0, {}
    for item in script:
        item_id = item.get("_id")
        if item_id is None or item_id in seen:
            raise ValueError(f"缺失或重复的脚本片段 ID: {item_id}")
        seen.add(item_id)
        try:
            start_text, end_text = item["timestamp"].split("-", 1)
            start, end = map(parse_time_milliseconds, (start_text, end_text))
            if end <= start:
                raise ValueError("结束时间必须晚于开始时间")
            ost = int(item.get("OST", 0))
            if ost not in (0, 1, 2):
                raise ValueError(f"未知 OST: {ost}")
            tts = {}
            duration = end - start
            if ost in (0, 2):
                tts = by_id.get(item_id)
                if tts is None:
                    matches = by_timestamp.get(item["timestamp"], [])
                    if len(matches) != 1:
                        raise ValueError("缺失配音或时间戳匹配不唯一")
                    tts = matches[0]
                duration = seconds_to_milliseconds(tts.get("duration"))
                if not tts.get("audio_file"):
                    raise ValueError("配音结果缺少音频文件")
            source = resolve_video_path(item, paths)
            if media_duration is not None:
                for media in (source, tts.get("audio_file")):
                    if media and media not in durations:
                        durations[media] = seconds_to_milliseconds(media_duration(media))
                duration = min(duration, max(0, durations[source] - start))
                if tts:
                    duration = min(duration, durations[tts["audio_file"]])
            if duration <= 0:
                raise ValueError("片段没有可用时长")
        except (ValueError, KeyError, TypeError, InvalidOperation) as exc:
            raise ValueError(f"片段 {item_id} 无法建立时间线: {exc}") from exc
        record = dict(item)
        record.update(OST=ost, source_video_path=source, video=source,
                      source_start_time=start / 1000, start_time=start / 1000,
                      duration=duration / 1000, timeline_start_ms=cursor,
                      timeline_end_ms=cursor + duration,
                      sourceTimeRange=f"{format_time_milliseconds(start)}-"
                                      f"{format_time_milliseconds(start + duration)}",
                      editedTimeRange=f"{format_time_milliseconds(cursor)}-"
                                      f"{format_time_milliseconds(cursor + duration)}",
                      audio=tts.get("audio_file", ""), subtitle=tts.get("subtitle_file", ""))
        timeline.append(record)
        cursor += duration
    if not timeline:
        raise ValueError("没有可用的脚本片段")
    return timeline


def attach_rendered_clips(timeline, clips):
    """Attach rendered paths without recovering timeline facts from filenames."""
    missing = [item["_id"] for item in timeline if not clips.get(item["_id"])]
    if missing:
        raise ValueError(f"时间线片段缺少裁剪结果: {missing}")
    return [dict(item, video=clips[item["_id"]], use_source_timerange=False)
            for item in timeline]
