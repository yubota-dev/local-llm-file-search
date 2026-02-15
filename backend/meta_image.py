"""
meta_image.py - 画像メタデータ抽出モジュール

Pillow で画像情報、EXIF で以下を取得（可能な範囲）：
- width, height, format
- 撮影日時、機種、向き、GPS（取得可能な場合）

Phase 1では基本情報が中心。物体認識はPhase 2以降

【Phase 1 design constraints】
- This module extracts ONLY image metadata (dimensions, format, basic EXIF).
- Image content analysis (object detection, scene understanding) is NOT performed.
- EXIF data is indexed for metadata search only, not for image interpretation.
- Visual feature extraction is intentionally deferred to Phase 2+.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional

try:
    from PIL import Image
    from PIL.ExifTags import TAGS
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    logging.warning("Pillow not installed - image metadata extraction will be limited")


logger = logging.getLogger(__name__)


class ImageMetaExtractor:
    """画像メタデータ抽出器"""
    
    def __init__(self):
        """初期化"""
        self.pil_available = PIL_AVAILABLE
    
    def extract(self, filepath: str) -> Dict:
        """
        画像ファイルのメタを抽出
        
        Args:
            filepath: ファイルパス
        
        Returns:
            メタデータ辞書
        """
        meta = {
            'pil_available': self.pil_available,
            'error': None
        }
        
        if not self.pil_available:
            meta['error'] = "Pillow not available"
            return meta
        
        try:
            with Image.open(filepath) as img:
                # 基本情報
                meta['format'] = img.format
                meta['width'] = img.width
                meta['height'] = img.height
                meta['mode'] = img.mode
                
                # EXIF データ（あれば）
                exif_data = self._extract_exif(img)
                if exif_data:
                    meta['exif'] = exif_data
        
        except Exception as e:
            meta['error'] = str(e)
            logger.warning(f"Error extracting image metadata from {filepath}: {e}")
        
        return meta
    
    def _extract_exif(self, img: 'Image.Image') -> Optional[Dict]:
        """
        EXIF データを抽出
        
        Args:
            img: PIL Image オブジェクト
        
        Returns:
            EXIF 辞書（なければ None）
        """
        try:
            exif_data = img._getexif()
            if not exif_data:
                return None
            
            result = {}
            
            for tag_id, value in exif_data.items():
                tag_name = TAGS.get(tag_id, tag_id)
                
                # 主要な EXIF タグのみを抽出
                if tag_name in [
                    'DateTime',
                    'DateTimeOriginal',
                    'Model',
                    'Make',
                    'Orientation',
                    'GPSInfo',
                    'Software'
                ]:
                    try:
                        result[tag_name] = str(value)
                    except:
                        pass
            
            return result if result else None
        
        except Exception as e:
            logger.debug(f"EXIF extraction error: {e}")
            return None


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python meta_image.py <filepath>")
        sys.exit(1)
    
    extractor = ImageMetaExtractor()
    meta = extractor.extract(sys.argv[1])
    print(json.dumps(meta, indent=2, ensure_ascii=False))
