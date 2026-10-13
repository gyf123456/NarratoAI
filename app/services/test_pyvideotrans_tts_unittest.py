import io
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock

from app.services import pyvideotrans_tts as api


def json_response(data=None, code=0, msg="ok"):
    result = Mock()
    result.json.return_value = {"code": code, "msg": msg, "data": data}
    return result


def wav_bytes():
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\0\0" * 1600)
    return buffer.getvalue()


class PyVideoTransTests(unittest.TestCase):
    def test_local_qwen_voices_match_customvoice_ids_instead_of_cloud_catalog(self):
        session = Mock()
        voices = api.list_voices("http://host:9011", 1, session=session)
        self.assertEqual({item["name"] for item in voices}, {
            "Vivian", "Serena", "Uncle_fu", "Dylan", "Eric",
            "Ryan", "Aiden", "Ono_anna", "Sohee",
        })
        session.get.assert_not_called()

    def setUp(self):
        self.session = Mock()
        self.session.post.side_effect = [
            json_response({"filepath": "/host/upload/text.srt"}),
            json_response({"task_id": "task1"}),
        ]

    def test_full_task_wait_and_audio_download_without_shared_filesystem(self):
        audio = Mock(content=wav_bytes())
        self.session.get.side_effect = [
            json_response({"status": "running"}), json_response({"status": "done"}),
            json_response([{"path": "/host/output/audio.wav", "size": len(audio.content)}]), audio,
        ]
        sleep = Mock()
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voice.wav"
            api.synthesize("你好", output, "http://host.docker.internal:9011/", 1, "Vivian",
                           speed=1.2, session=self.session, sleep=sleep)
            self.assertEqual(output.read_bytes(), audio.content)
        payload = self.session.post.call_args.kwargs["json"]
        self.assertEqual(payload["name"], "/host/upload/text.srt")
        self.assertEqual(payload["voice_rate"], "+20%")
        self.assertFalse(payload["align_sub_audio"])
        self.assertFalse(payload["voice_autorate"])
        sleep.assert_called_once_with(2)
        self.assertEqual(self.session.get.call_args.kwargs["params"], {"path": "/host/output/audio.wav"})

    def test_model_error_is_shown(self):
        self.session.get.return_value = json_response({"status": "error", "error": "缺少模型权重"})
        with self.assertRaisesRegex(api.PyVideoTransError, "缺少模型权重"):
            api.synthesize("你好", "/unused.wav", "http://host:9011", 1, "Vivian", session=self.session)

    def test_service_error_is_shown(self):
        self.session.post.side_effect = [json_response(code=1, msg="上传失败")]
        with self.assertRaisesRegex(api.PyVideoTransError, "上传失败"):
            api.synthesize("你好", "/unused.wav", "http://host:9011", 1, "Vivian", session=self.session)

    def test_missing_qwen_dependency_gives_extra_aware_startup_command(self):
        self.session.get.return_value = json_response({"status": "error", "error": "No module named 'qwen_tts'"})
        with self.assertRaisesRegex(api.PyVideoTransError, "uv run --extra qwen-tts python web_api.py"):
            api.synthesize("你好", "/unused.wav", "http://host:9011", 1, "Vivian", session=self.session)

    def test_timeout_does_not_wait_forever(self):
        self.session.get.return_value = json_response({"status": "running"})
        with self.assertRaisesRegex(api.PyVideoTransError, "等待超时"):
            api.synthesize("你好", "/unused.wav", "http://host:9011", 1, "Vivian", timeout=1,
                           session=self.session, clock=Mock(side_effect=[0, 0, 2]), sleep=Mock())

    def test_invalid_audio_is_not_saved(self):
        self.session.get.side_effect = [json_response({"status": "done"}),
            json_response([{"path": "/host/output/audio.wav", "size": 99}]), Mock(content=b"error page")]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voice.wav"
            with self.assertRaisesRegex(api.PyVideoTransError, "有效的 WAV"):
                api.synthesize("你好", output, "http://host:9011", 1, "Vivian", session=self.session)
            self.assertFalse(output.exists())

    def test_clone_is_rejected_before_starting_task(self):
        with self.assertRaises(api.PyVideoTransError):
            api.synthesize("你好", "/unused.wav", "http://host:9011", 1, "clone", session=self.session)
        self.session.post.assert_not_called()


if __name__ == "__main__":
    unittest.main()
