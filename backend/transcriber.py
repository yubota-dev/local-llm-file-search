"""
transcriber.py - faster-whisper による音声・動画文字起こし

Phase 2: ファイルの中身（音声）をテキスト化してインデックス対象に追加
設計思想：LLMは文字起こし結果の提示のみ。判断は人間が行う。
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

AUDIO_EXTENSIONS = {'.mp3', '.flac', '.wav', '.m4a', '.aac', '.ogg', '.opus', '.wma'}
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.mov', '.avi', '.wmv', '.flv', '.webm', '.m4v'}
SUPPORTED_EXTENSIONS = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


class Transcriber:
    """faster-whisper を使った音声・動画文字起こしクラス"""

    def __init__(self, model_size: str = "large-v3", device: str = "cuda",
                 compute_type: str = "float16"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.model = None

    def _load_model(self):
        """モデルの遅延ロード（初回呼び出し時のみ）"""
        if self.model is None:
            from faster_whisper import WhisperModel
            logger.info(f"Loading Whisper model: {self.model_size} on {self.device}")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type
            )
            logger.info("Whisper model loaded")

    def transcribe(self, file_path: str, language: str = "ja") -> Optional[str]:
        """
        音声・動画ファイルを文字起こし

        Args:
            file_path: 対象ファイルパス
            language: 言語コード（ja=日本語, en=英語, None=自動検出）

        Returns:
            文字起こし結果テキスト。失敗時はNone
        """
        path = Path(file_path)

        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            logger.warning(f"Unsupported extension: {path.suffix}")
            return None

        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        try:
            self._load_model()
            logger.info(f"Transcribing: {path.name}")

            segments, info = self.model.transcribe(
                str(path),
                language=language,
                beam_size=5,
                vad_filter=True,      # 無音区間をスキップ
                vad_parameters={"min_silence_duration_ms": 500}
            )

            # セグメントを結合してテキスト化
            text = " ".join(segment.text.strip() for segment in segments)

            logger.info(
                f"Transcribed: {path.name} "
                f"(lang={info.language}, prob={info.language_probability:.2f})"
            )
            return text if text.strip() else None

        except Exception as e:
            logger.error(f"Transcription failed for {file_path}: {e}")
            return None


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO)

    target = sys.argv[1] if len(sys.argv) > 1 else "F:/test_media/0036234497.flac"

    transcriber = Transcriber()
    result = transcriber.transcribe(target)

    if result:
        print(f"\n=== 文字起こし結果 ===\n{result}")
    else:
        print("文字起こし失敗")