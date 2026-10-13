"""Reuse a host pyvideotrans Web API for speech synthesis."""

import time
import uuid
from pathlib import Path

import requests


class PyVideoTransError(RuntimeError):
    pass


def _json(response):
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("code") != 0:
        raise PyVideoTransError(str(payload.get("msg", "服务返回无效数据")) if isinstance(payload, dict) else "服务返回无效数据")
    return payload.get("data")


def _get(session, url, **kwargs):
    return session.get(url, timeout=30, proxies={"http": "", "https": ""}, **kwargs)


def list_providers(api_url, session=requests):
    result = _json(_get(session, f"{api_url.rstrip('/')}/api/providers/tts"))
    if not isinstance(result, list) or not result or not all(
        isinstance(item, dict) and isinstance(item.get("id"), int) and item.get("name") for item in result
    ):
        raise PyVideoTransError("宿主机服务返回无效的配音引擎列表")
    return result


def list_voices(api_url, tts_type, language="zh-cn", session=requests):
    # The host's local Qwen3 implementation accepts these CustomVoice IDs.
    # Some host versions return the cloud Qwen voice catalog for provider 1;
    # those names fall into the Base-model branch and cannot use CustomVoice.
    if int(tts_type) == 1:
        return [{"name": name} for name in (
            "Vivian", "Serena", "Uncle_fu", "Dylan", "Eric",
            "Ryan", "Aiden", "Ono_anna", "Sohee",
        )]
    result = _json(_get(session, f"{api_url.rstrip('/')}/api/voices", params={"tts_type": tts_type, "language": language}))
    if not isinstance(result, list) or not all(isinstance(item, dict) and item.get("name") for item in result):
        raise PyVideoTransError("宿主机服务返回无效的音色列表")
    return result


def synthesize(text, output_file, api_url, tts_type, voice_role, language="zh-cn", speed=1.0,
               timeout=1200, session=requests, sleep=time.sleep, clock=time.monotonic):
    if not text.strip() or not voice_role or voice_role in {"No", "clone"}:
        raise PyVideoTransError("请填写文本并选择普通音色；此接口暂不支持逐片段参考音频克隆")
    base_url = api_url.strip().rstrip("/")
    if not base_url.startswith(("http://", "https://")):
        raise PyVideoTransError("请填写完整的 pyvideotrans Web API 地址")
    # A temporary one-cue SRT lets the server run its full TTS workflow.
    # The server returns audio through HTTP, so host filesystem paths need no mount.
    srt = f"1\n00:00:00,000 --> 00:00:01,000\n{text.strip()}\n"
    options = {"timeout": 30, "proxies": {"http": "", "https": ""}}
    uploaded = _json(session.post(
        f"{base_url}/api/upload",
        files={"file": (f"narrato-{uuid.uuid4().hex}.srt", srt.encode("utf-8"), "application/x-subrip")},
        **options,
    ))
    if not isinstance(uploaded, dict) or not uploaded.get("filepath"):
        raise PyVideoTransError("宿主机服务没有返回字幕文件路径")
    task = _json(session.post(f"{base_url}/api/task", json={
        "task": "tts", "name": uploaded["filepath"], "tts_type": int(tts_type),
        "voice_role": voice_role, "voice_rate": f"{round((float(speed) - 1) * 100):+d}%",
        "target_language_code": language, "voice_autorate": False, "align_sub_audio": False,
        "is_cuda": False,
    }, **options))
    if not isinstance(task, dict) or not task.get("task_id"):
        raise PyVideoTransError("宿主机服务没有返回任务编号")
    task_id = task["task_id"]
    deadline = clock() + timeout
    while clock() < deadline:
        status = _json(_get(session, f"{base_url}/api/task/{task_id}"))
        if not isinstance(status, dict):
            raise PyVideoTransError("宿主机服务返回无效任务状态")
        if status.get("status") == "error":
            error = str(status.get("error") or "宿主机配音任务失败")
            if "No module named 'qwen_tts'" in error:
                error = (
                    "宿主机 pyvideotrans 缺少 Qwen3-TTS 依赖。请在 pyvideotrans 目录执行 "
                    "uv sync --extra qwen-tts，然后使用 "
                    "uv run --extra qwen-tts python web_api.py --host 0.0.0.0 --port 9011 重启服务。"
                )
            raise PyVideoTransError(error)
        if status.get("status") == "done":
            break
        sleep(2)
    else:
        raise PyVideoTransError(f"宿主机配音任务等待超时（任务 {task_id}），可在 pyvideotrans 中查看进度")
    files = _json(_get(session, f"{base_url}/api/files", params={"task_id": task_id}))
    if not isinstance(files, list):
        raise PyVideoTransError("宿主机服务返回无效输出文件列表")
    audio_files = [entry for entry in files if isinstance(entry, dict)
                   and str(entry.get("path", "")).lower().endswith(".wav") and entry.get("size", 0) > 0]
    if len(audio_files) != 1:
        raise PyVideoTransError(f"宿主机任务应返回一个 WAV 音频，实际找到 {len(audio_files)} 个")
    response = _get(session, f"{base_url}/api/files/download", params={"path": audio_files[0]["path"]})
    response.raise_for_status()
    if not response.content.startswith(b"RIFF") or response.content[8:12] != b"WAVE":
        raise PyVideoTransError("宿主机返回的文件不是有效的 WAV 音频")
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    Path(output_file).write_bytes(response.content)
    return str(output_file)
