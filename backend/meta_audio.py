"""
meta_audio.py - 音声タグ抽出モジュール

mutagen または ffprobe を使用して音声ファイルのタグ情報を抽出：
- artist, title, album, date, genre
- 基本情報：duration, bitrate, sample_rate, channels

mutagen が無い場合は ffprobe でフォールバック
"""

import json
import logging
from typing import Dict, Optional

try:
    from mutagen import File as MutagenFile
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False
    logging.warning("Mutagen not installed - audio tag extraction will fallback to ffprobe")

from .meta_video_audio import VideoAudioMetaExtractor


logger = logging.getLogger(__name__)


class AudioMetaExtractor:
    """音声ファイルメタデータ抽出器"""
    
    def __init__(self):
        """初期化"""
        self.mutagen_available = MUTAGEN_AVAILABLE
        self.ffprobe = VideoAudioMetaExtractor()
    
    def extract(self, filepath: str) -> Dict:
        """
        音声ファイルのメタを抽出
        
        Args:
            filepath: ファイルパス
        
        Returns:
            メタデータ辞書
        """
        meta = {
            'mutagen_available': self.mutagen_available,
            'error': None
        }
        
        # mutagen を試す（優先度高）
        if self.mutagen_available:
            try:
                tag_data = self._extract_with_mutagen(filepath)
                if tag_data:
                    meta.update(tag_data)
                    return meta
            except Exception as e:
                logger.debug(f"Mutagen extraction failed: {e}")
        
        # ffprobe でフォールバック
        ffprobe_meta = self.ffprobe.extract(filepath)
        meta.update(ffprobe_meta)
        
        return meta
    
    def _extract_with_mutagen(self, filepath: str) -> Optional[Dict]:
        """
        mutagen で タグを抽出
        
        Args:
            filepath: ファイルパス
        
        Returns:
            メタデータ辞書
        """
        try:
            audio = MutagenFile(filepath)
            
            if audio is None:
                return None
            
            meta = {}
            
            # タグ情報
            if hasattr(audio, 'tags') and audio.tags:
                meta['tags'] = {
                    'title': self._get_tag(audio.tags, ['TIT2', 'Title', '\xa9nam']),
                    'artist': self._get_tag(audio.tags, ['TPE1', 'Artist', '\xa9ART']),
                    'album': self._get_tag(audio.tags, ['TALB', 'Album', '\xa9alb']),
                    'date': self._get_tag(audio.tags, ['TDRC', 'Date', '\xa9day']),
                    'genre': self._get_tag(audio.tags, ['TCON', 'Genre', '\xa9gen'])
                }
            
            # オーディオ情報（info 属性がある場合）
            if hasattr(audio, 'info'):
                info = audio.info
                meta['info'] = {
                    'duration_sec': getattr(info, 'length', None),
                    'bitrate': getattr(info, 'bitrate', None),
                    'sample_rate': getattr(info, 'sample_rate', None),
                    'channels': getattr(info, 'channels', None)
                }
            
            return meta if (meta.get('tags') or meta.get('info')) else None
        
        except Exception as e:
            logger.debug(f"Mutagen error: {e}")
            return None
    
    def _get_tag(self, tags: dict, keys: list) -> Optional[str]:
        """
        複数キー候補から タグ値を取得
        
        Args:
            tags: タグ辞書
            keys: キー候補のリスト
        
        Returns:
            タグ値（見つからない場合は None）
        """
        for key in keys:
            if key in tags:
                value = tags[key]
                # タグ値が リスト/オブジェクトの場合がある
                if isinstance(value, list) and value:
                    return str(value[0])
                return str(value)
        return None


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python meta_audio.py <filepath>")
        sys.exit(1)
    
    extractor = AudioMetaExtractor()
    meta = extractor.extract(sys.argv[1])
    print(json.dumps(meta, indent=2, ensure_ascii=False))
