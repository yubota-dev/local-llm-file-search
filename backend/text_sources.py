"""
text_sources.py - テキストソース抽出モジュール

以下のファイルからテキストを抽出：
- 字幕：.srt, .vtt, .ass
- メモ：<same_name>.txt / .md
- メタ：.nfo, .json, .xml

文字コード失敗時は errors="ignore" で続行

【Phase 1 design constraints】
- This module extracts text from sidecar files only (subtitles, notes, metadata files).
- Text extraction is for SEARCH INDEXING purposes only.
- Text content understanding and semantic analysis are NOT performed.
- Language interpretation and meaning extraction are deferred to Phase 2+.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path


logger = logging.getLogger(__name__)


class TextSourceExtractor:
    """テキストソース抽出器"""
    
    # テキストソース種別ごとの拡張子
    SOURCE_TYPES = {
        'subtitle': ['.srt', '.vtt', '.ass'],
        'note': ['.txt', '.md'],
        'meta': ['.nfo', '.json', '.xml']
    }
    
    def __init__(self, config: dict):
        """
        初期化
        
        Args:
            config: config.yaml から metadata セクション
        """
        self.config = config
        self.text_max_size = config.get('text_max_size_bytes', 1048576)  # 1MB
        self.text_encoding_errors = config.get('text_encoding_errors', 'ignore')
    
    def extract_from_sidecar(self, sidecar_info: Dict) -> Dict:
        """
        付随ファイルからテキストを抽出
        
        Args:
            sidecar_info: scanner.py から得た sidecar_files 情報
        
        Returns:
            テキスト抽出メタデータ
        """
        result = {
            'text_sources': [],
            'total_text_size': 0,
            'extraction_errors': []
        }
        
        for sidecar_id, sidecar_file in sidecar_info.items():
            path = sidecar_file.get('path')
            source_type = sidecar_file.get('type')
            
            if not path or not os.path.exists(path):
                continue
            
            try:
                # サイズチェック
                size = os.path.getsize(path)
                if size > self.text_max_size:
                    result['extraction_errors'].append(
                        f"{sidecar_id}: file too large ({size} bytes)"
                    )
                    continue
                
                # テキスト読込
                text = self._read_text_file(path)
                
                if text:
                    result['text_sources'].append({
                        'source_type': source_type,
                        'filename': os.path.basename(path),
                        'extension': os.path.splitext(path)[1].lower(),
                        'size': size,
                        'text': text[:1000]  # 最初の1000文字のみプレビュー
                    })
                    result['total_text_size'] += len(text)
            
            except Exception as e:
                result['extraction_errors'].append(f"{sidecar_id}: {str(e)}")
        
        return result
    
    def extract_from_path(self, media_path: str) -> Dict:
        """
        メディアファイルと同名の付随ファイルからテキストを抽出
        
        Args:
            media_path: メディアファイルパス
        
        Returns:
            テキスト抽出メタデータ
        """
        result = {
            'text_sources': [],
            'total_text_size': 0,
            'extraction_errors': []
        }
        
        dirname = os.path.dirname(media_path)
        basename = os.path.splitext(os.path.basename(media_path))[0]
        
        for source_type, extensions in self.SOURCE_TYPES.items():
            for ext in extensions:
                sidecar_path = os.path.join(dirname, f"{basename}{ext}")
                
                if not os.path.exists(sidecar_path):
                    continue
                
                try:
                    size = os.path.getsize(sidecar_path)
                    
                    if size > self.text_max_size:
                        result['extraction_errors'].append(
                            f"{os.path.basename(sidecar_path)}: file too large"
                        )
                        continue
                    
                    text = self._read_text_file(sidecar_path)
                    
                    if text:
                        result['text_sources'].append({
                            'source_type': source_type,
                            'filename': os.path.basename(sidecar_path),
                            'extension': ext.lower(),
                            'size': size,
                            'text_length': len(text)
                        })
                        result['total_text_size'] += len(text)
                
                except Exception as e:
                    result['extraction_errors'].append(
                        f"{os.path.basename(sidecar_path)}: {str(e)}"
                    )
        
        return result
    
    def _read_text_file(self, filepath: str) -> Optional[str]:
        """
        テキストファイルを読み込む
        
        Args:
            filepath: ファイルパス
        
        Returns:
            ファイルの内容（読込失敗時は None）
        """
        encodings = ['utf-8', 'utf-8-sig', 'shift_jis', 'cp1252', 'latin-1']
        
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding, errors=self.text_encoding_errors) as f:
                    return f.read()
            except (UnicodeDecodeError, LookupError):
                continue
            except Exception as e:
                logger.debug(f"Error reading {filepath} with {encoding}: {e}")
        
        # すべてのエンコーディングで失敗
        logger.warning(f"Could not decode {filepath} with any encoding")
        return None
    
    def extract_subtitle_text(self, subtitle_path: str) -> Dict:
        """
        字幕ファイルからテキストのみを抽出（特化版）
        
        Args:
            subtitle_path: 字幕ファイルパス
        
        Returns:
            字幕テキストメタデータ
        """
        result = {
            'format': os.path.splitext(subtitle_path)[1].lower(),
            'text': '',
            'lines': 0,
            'error': None
        }
        
        try:
            ext = os.path.splitext(subtitle_path)[1].lower()
            
            # SRT, VTT はシンプル
            if ext in ['.srt', '.vtt']:
                text = self._read_text_file(subtitle_path)
                if text:
                    # VTT/SRT では先頭のメタ（時刻など）を除く
                    result['text'] = text
                    result['lines'] = text.count('\n')
            
            # ASS はより複雑（スクリプト情報などを除く）
            elif ext == '.ass':
                text = self._read_text_file(subtitle_path)
                if text:
                    # [Events] セクションのみを抽出
                    lines = text.split('\n')
                    events = []
                    in_events = False
                    
                    for line in lines:
                        if line.startswith('[Events]'):
                            in_events = True
                            continue
                        if in_events and line.startswith('Dialogue:'):
                            # "Dialogue: ..." から最後のコンマ以降のテキストを抽出
                            parts = line.split(',', 9)  # 最大10分割
                            if len(parts) > 9:
                                text_part = parts[9].strip()
                                events.append(text_part)
                    
                    result['text'] = '\n'.join(events)
                    result['lines'] = len(events)
        
        except Exception as e:
            result['error'] = str(e)
        
        return result


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python text_sources.py <filepath>")
        sys.exit(1)
    
    config = {
        'text_max_size_bytes': 1048576,
        'text_encoding_errors': 'ignore'
    }
    
    extractor = TextSourceExtractor(config)
    
    # 同名の付随ファイルを抽出
    result = extractor.extract_from_path(sys.argv[1])
    print(json.dumps(result, indent=2, ensure_ascii=False))
