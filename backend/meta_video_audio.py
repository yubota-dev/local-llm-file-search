"""
meta_video_audio.py - 動画・音声メタデータ抽出モジュール

ffprobe を使用して以下を抽出：
- duration, codec, bitrate, sample_rate, channels
- width, height, fps (動画)
- tags (artist, title など)

ffprobe が無い場合は graceful に失敗

【Phase 1 design constraints】
- This module extracts ONLY technical metadata (duration, resolution, codec, bitrate).
- Media content analysis (speech, visual features, etc.) is NOT performed.
- File content decoding for understanding purposes is not allowed.
- Codec and format information are for indexing purposes only, not interpretation.
"""

import subprocess
import json
import logging
from typing import Dict, Optional
from pathlib import Path


logger = logging.getLogger(__name__)


class VideoAudioMetaExtractor:
    """ffprobe 使用メタデータ抽出器"""
    
    def __init__(self):
        """ffprobe の可用性をチェック"""
        self.ffprobe_available = self._check_ffprobe()
    
    def _check_ffprobe(self) -> bool:
        """ffprobe コマンドが利用可能か確認"""
        try:
            subprocess.run(
                ['ffprobe', '-version'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            logger.info("ffprobe is available")
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            logger.warning("ffprobe not found - will use fallback metadata extraction")
            return False
    
    def extract(self, filepath: str) -> Dict:
        """
        ビデオ・オーディオファイルのメタを抽出
        
        Args:
            filepath: ファイルパス
        
        Returns:
            メタデータ辞書
        """
        meta = {
            'ffprobe_available': self.ffprobe_available,
            'error': None
        }
        
        if not self.ffprobe_available:
            meta['error'] = "ffprobe not available"
            return meta
        
        try:
            result = subprocess.run(
                [
                    'ffprobe',
                    '-v', 'quiet',
                    '-print_format', 'json',
                    '-show_format',
                    '-show_streams',
                    filepath
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                meta['error'] = result.stderr
                return meta
            
            data = json.loads(result.stdout)
            self._parse_ffprobe_output(data, meta)
            
        except json.JSONDecodeError as e:
            meta['error'] = f"JSON parse error: {e}"
        except subprocess.TimeoutExpired:
            meta['error'] = "ffprobe timeout"
        except Exception as e:
            meta['error'] = str(e)
        
        return meta
    
    def _parse_ffprobe_output(self, data: Dict, meta: Dict) -> None:
        """
        ffprobe 出力を解析
        
        Args:
            data: ffprobe JSON 出力
            meta: 格納先メタデータ辞書（更新される）
        """
        # format 情報（全般）
        fmt = data.get('format', {})
        if 'duration' in fmt:
            meta['duration_sec'] = float(fmt['duration'])
        
        tags = fmt.get('tags', {})
        if tags:
            meta['tags'] = {
                'title': tags.get('title'),
                'artist': tags.get('artist'),
                'album': tags.get('album'),
                'date': tags.get('date')
            }
        
        # ストリーム情報（動画・オーディオ）
        streams = data.get('streams', [])
        
        for stream in streams:
            codec_type = stream.get('codec_type')
            
            if codec_type == 'video':
                meta['video'] = {
                    'codec': stream.get('codec_name'),
                    'width': stream.get('width'),
                    'height': stream.get('height'),
                    'fps': self._calculate_fps(stream),
                    'bitrate': stream.get('bit_rate')
                }
            
            elif codec_type == 'audio':
                if 'audio' not in meta:
                    meta['audio'] = []
                
                meta['audio'].append({
                    'codec': stream.get('codec_name'),
                    'sample_rate': stream.get('sample_rate'),
                    'channels': stream.get('channels'),
                    'bitrate': stream.get('bit_rate'),
                    'language': stream.get('tags', {}).get('language')
                })
    
    def _calculate_fps(self, stream: Dict) -> Optional[float]:
        """
        フレームレートを計算
        
        Args:
            stream: ffprobe ストリーム情報
        
        Returns:
            FPS（小数）
        """
        r_frame_rate = stream.get('r_frame_rate')
        if not r_frame_rate or '/' not in r_frame_rate:
            return None
        
        try:
            num, den = map(int, r_frame_rate.split('/'))
            return num / den if den != 0 else None
        except:
            return None


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python meta_video_audio.py <filepath>")
        sys.exit(1)
    
    extractor = VideoAudioMetaExtractor()
    meta = extractor.extract(sys.argv[1])
    print(json.dumps(meta, indent=2, ensure_ascii=False))
