"""
vision.py - LLaVA による画像内容説明生成

Phase 2: 画像の中身をテキスト化してインデックス対象に追加
設計思想：LLMは「説明・提示」のみ。判断は人間が行う。
"""

import logging
import base64
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp', '.tiff', '.heic'}


class VisionAnalyzer:
    """LLaVA を使った画像内容説明クラス"""

    def __init__(self, model: str = "llava:13b",
                 ollama_url: str = "http://localhost:11434"):
        self.model = model
        self.ollama_url = ollama_url

    def _image_to_base64(self, file_path: str) -> Optional[str]:
        """画像をbase64エンコード"""
        try:
            with open(file_path, 'rb') as f:
                return base64.b64encode(f.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            return None

    def describe(self, file_path: str) -> Optional[str]:
        """
        画像の内容を説明テキストとして返す

        Args:
            file_path: 対象画像ファイルパス

        Returns:
            説明テキスト。失敗時はNone
        """
        path = Path(file_path)

        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            logger.warning(f"Unsupported extension: {path.suffix}")
            return None

        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        image_b64 = self._image_to_base64(file_path)
        if not image_b64:
            return None

        try:
            logger.info(f"Analyzing image: {path.name}")

            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": (
                        "この画像に何が写っているか、日本語で簡潔に説明してください。"
                        "人物・物体・場所・テキスト・色・雰囲気などを含めて説明してください。"
                        "推測や判断はせず、見えているものだけを説明してください。"
                    ),
                    "images": [image_b64],
                    "stream": False
                },
                timeout=120
            )

            if response.status_code == 200:
                result = response.json().get('response', '').strip()
                logger.info(f"Vision analysis complete: {path.name}")
                return result if result else None
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Vision analysis failed for {file_path}: {e}")
            return None


if __name__ == '__main__':
    import sys
    logging.basicConfig(level=logging.INFO)

    target = sys.argv[1] if len(sys.argv) > 1 else None

    if not target:
        # test_mediaの最初のpngを使う
        import glob
        pngs = glob.glob("F:/test_media/*.png")
        if pngs:
            target = pngs[0]
        else:
            print("画像ファイルが見つかりません")
            sys.exit(1)

    analyzer = VisionAnalyzer()
    result = analyzer.describe(target)

    if result:
        print(f"\n=== 画像説明 ===\n{result}")
    else:
        print("画像認識失敗")