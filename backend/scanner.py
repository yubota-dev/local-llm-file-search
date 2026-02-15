"""
scanner.py - メディア＆アーカイブ走査モジュール

指定ドライブ/フォルダを再帰走査し、対象拡張子のメディアファイルを検出。
同名の付随ファイル（字幕・メモ・メタ）も自動紐づけ。

主要メタ：path, name, ext, size, mtime（タイムスタンプ）

【Phase 1 design constraints】
- This module does NOT analyze media file contents.
- Only file metadata (path, size, mtime), filenames, folder names are extracted.
- Sidecar files (subtitles, notes, metadata) are indexed as file lists only.
- Media content understanding is intentionally deferred to Phase 2+.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import yaml


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MediaScanner:
    """メディア走査エンジン"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初期化
        
        Args:
            config_path: config.yaml のパス
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        # 対象拡張子を統合
        self.target_extensions = {}
        for kind, exts in self.config['scan']['extensions'].items():
            for ext in exts:
                self.target_extensions[ext.lower()] = kind
        
        self.root_path = self.config['scan']['root_path']
        self.all_files = []
        self.metadata_list = []
    
    def scan(self) -> List[Dict]:
        """
        ドライブ/フォルダを再帰走査
        
        Returns:
            メタデータのリスト
        """
        logger.info(f"Scanning: {self.root_path}")
        
        if not os.path.exists(self.root_path):
            logger.error(f"Path not found: {self.root_path}")
            return []
        
        for root, dirs, files in os.walk(self.root_path):
            for filename in files:
                filepath = os.path.join(root, filename)
                self._process_file(filepath)
        
        logger.info(f"Found {len(self.metadata_list)} media files")
        return self.metadata_list
    
    def _process_file(self, filepath: str) -> None:
        """
        単一ファイルのメタデータ取得
        
        Args:
            filepath: ファイルパス
        """
        try:
            ext = os.path.splitext(filepath)[1].lower()
            
            # 対象拡張子かチェック
            if ext not in self.target_extensions:
                return
            
            # 基本情報
            stat = os.stat(filepath)
            basename = os.path.basename(filepath)
            name_without_ext = os.path.splitext(basename)[0]
            
            meta = {
                'path': filepath,
                'name': basename,
                'name_without_ext': name_without_ext,
                'ext': ext,
                'size': stat.st_size,
                'mtime': datetime.fromtimestamp(stat.st_mtime).isoformat(),
                'kind': self.target_extensions[ext],
                'sidecar_files': {}
            }
            
            # 同名の付随ファイルを探す
            self._find_sidecar_files(os.path.dirname(filepath), name_without_ext, meta)
            
            self.metadata_list.append(meta)
            
        except Exception as e:
            logger.warning(f"Error processing {filepath}: {e}")
    
    def _find_sidecar_files(self, dirname: str, basename: str, meta: Dict) -> None:
        """
        同名の付随ファイル（字幕・メモ・メタ）を探す
        
        Args:
            dirname: ディレクトリパス
            basename: ファイル名（拡張子なし）
            meta: メタデータ辞書（更新される）
        """
        sidecar_patterns = {
            'subtitle': ['.srt', '.vtt', '.ass'],
            'note': ['.txt', '.md'],
            'meta': ['.nfo', '.json', '.xml']
        }
        
        for sidecar_type, exts in sidecar_patterns.items():
            for ext in exts:
                sidecar_path = os.path.join(dirname, f"{basename}{ext}")
                if os.path.exists(sidecar_path):
                    try:
                        size = os.path.getsize(sidecar_path)
                        meta['sidecar_files'][sidecar_type + ext] = {
                            'path': sidecar_path,
                            'size': size,
                            'type': sidecar_type
                        }
                    except Exception as e:
                        logger.warning(f"Error reading sidecar {sidecar_path}: {e}")
    
    def save_metadata(self, output_path: str = "data/raw/metadata.json") -> None:
        """
        メタデータを JSON に保存
        
        Args:
            output_path: 出力ファイルパス
        """
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.metadata_list, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Metadata saved: {output_path}")


if __name__ == '__main__':
    scanner = MediaScanner()
    metadata = scanner.scan()
    scanner.save_metadata()
    
    # サマリー出力
    by_kind = {}
    for item in metadata:
        kind = item['kind']
        by_kind[kind] = by_kind.get(kind, 0) + 1
    
    print("\n=== Scan Summary ===")
    for kind, count in sorted(by_kind.items()):
        print(f"{kind}: {count}")
    print(f"Total: {len(metadata)}")
