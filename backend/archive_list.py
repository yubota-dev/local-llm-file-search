"""
archive_list.py - アーカイブファイル中身一覧抽出モジュール

対応形式：
- zip   （Python 標準 zipfile）
- tar/gz（Python 標準 tarfile）
- 7z/rar（外部コマンドがあれば対応。無ければ未対応）

Phase 1: 展開しない。中身をリストするのみ

安全対策：
- 最大エントリ数制限
- 合計サイズ推定
- パストラバーサル検出
"""

import os
import subprocess
import json
import logging
from typing import Dict, List, Optional
from pathlib import Path

try:
    import zipfile
    ZIPFILE_AVAILABLE = True
except ImportError:
    ZIPFILE_AVAILABLE = False

try:
    import tarfile
    TARFILE_AVAILABLE = True
except ImportError:
    TARFILE_AVAILABLE = False


logger = logging.getLogger(__name__)


class ArchiveListExtractor:
    """アーカイブ中身一覧抽出器"""
    
    def __init__(self, config: dict):
        """
        初期化
        
        Args:
            config: config.yaml から metadata セクション
        """
        self.config = config
        self.max_entries = config.get('archive_max_entries', 50000)
        self.max_size_gb = config.get('archive_max_size_gb', 50)
        self.max_size_bytes = self.max_size_gb * 1024 * 1024 * 1024
    
    def extract(self, filepath: str) -> Dict:
        """
        アーカイブの中身を一覧化
        
        Args:
            filepath: アーカイブファイルパス
        
        Returns:
            アーカイブ情報メタデータ
        """
        ext = os.path.splitext(filepath)[1].lower()
        
        meta = {
            'is_archive': True,
            'format': ext,
            'entries': [],
            'entry_count': 0,
            'total_size_bytes': 0,
            'warnings': [],
            'error': None
        }
        
        try:
            if ext == '.zip':
                return self._extract_zip(filepath, meta)
            
            elif ext in ['.tar', '.gz', '.tgz']:
                return self._extract_tar(filepath, meta)
            
            elif ext in ['.7z', '.rar']:
                return self._extract_external_command(filepath, ext, meta)
            
            else:
                meta['error'] = f"Unsupported archive format: {ext}"
        
        except Exception as e:
            meta['error'] = str(e)
            logger.warning(f"Error extracting archive {filepath}: {e}")
        
        return meta
    
    def _extract_zip(self, filepath: str, meta: Dict) -> Dict:
        """
        ZIP ファイルを処理
        
        Args:
            filepath: ZIP ファイルパス
            meta: メタデータ辞書（更新される）
        
        Returns:
            メタデータ辞書
        """
        if not ZIPFILE_AVAILABLE:
            meta['error'] = "zipfile module not available"
            return meta
        
        try:
            with zipfile.ZipFile(filepath, 'r') as zf:
                infolist = zf.infolist()
                
                for i, info in enumerate(infolist[:self.max_entries]):
                    entry = {
                        'name': info.filename,
                        'size': info.file_size,
                        'is_dir': info.is_dir(),
                        'compressed_size': info.compress_size
                    }
                    
                    # パストラバーサル検出
                    if self._has_path_traversal(info.filename):
                        entry['warning'] = "Possible path traversal"
                        meta['warnings'].append(f"Path traversal in: {info.filename}")
                    
                    meta['entries'].append(entry)
                    meta['total_size_bytes'] += info.file_size
                
                if len(infolist) > self.max_entries:
                    meta['warnings'].append(
                        f"Archive truncated: {len(infolist)} entries, showing {self.max_entries}"
                    )
                
                if meta['total_size_bytes'] > self.max_size_bytes:
                    meta['warnings'].append(
                        f"Large archive: {meta['total_size_bytes'] / (1024**3):.1f} GB"
                    )
                
                meta['entry_count'] = min(len(infolist), self.max_entries)
        
        except Exception as e:
            meta['error'] = str(e)
        
        return meta
    
    def _extract_tar(self, filepath: str, meta: Dict) -> Dict:
        """
        TAR ファイルを処理
        
        Args:
            filepath: TAR/TGZ ファイルパス
            meta: メタデータ辞書（更新される）
        
        Returns:
            メタデータ辞書
        """
        if not TARFILE_AVAILABLE:
            meta['error'] = "tarfile module not available"
            return meta
        
        try:
            # 圧縮形式を自動判定
            mode = 'r:*' if filepath.endswith(('.tar.gz', '.tgz')) else 'r:*'
            
            with tarfile.open(filepath, mode) as tf:
                members = tf.getmembers()
                
                for i, member in enumerate(members[:self.max_entries]):
                    entry = {
                        'name': member.name,
                        'size': member.size,
                        'is_dir': member.isdir()
                    }
                    
                    # パストラバーサル検出
                    if self._has_path_traversal(member.name):
                        entry['warning'] = "Possible path traversal"
                        meta['warnings'].append(f"Path traversal in: {member.name}")
                    
                    meta['entries'].append(entry)
                    meta['total_size_bytes'] += member.size
                
                if len(members) > self.max_entries:
                    meta['warnings'].append(
                        f"Archive truncated: {len(members)} entries, showing {self.max_entries}"
                    )
                
                if meta['total_size_bytes'] > self.max_size_bytes:
                    meta['warnings'].append(
                        f"Large archive: {meta['total_size_bytes'] / (1024**3):.1f} GB"
                    )
                
                meta['entry_count'] = min(len(members), self.max_entries)
        
        except Exception as e:
            meta['error'] = str(e)
        
        return meta
    
    def _extract_external_command(self, filepath: str, ext: str, meta: Dict) -> Dict:
        """
        外部コマンド（7z, rar）で処理
        
        Args:
            filepath: アーカイブファイルパス
            ext: ファイル拡張子
            meta: メタデータ辞書（更新される）
        
        Returns:
            メタデータ辞書
        """
        if ext == '.7z':
            return self._extract_7z(filepath, meta)
        elif ext == '.rar':
            return self._extract_rar(filepath, meta)
        else:
            meta['error'] = f"Unknown external format: {ext}"
            return meta
    
    def _extract_7z(self, filepath: str, meta: Dict) -> Dict:
        """7z コマンドで処理"""
        # 実装例：外部の 7z コマンドを呼び出す
        # Phase 1では基本的なサポートのみ
        try:
            result = subprocess.run(
                ['7z', 'l', filepath],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # パースロジック（簡略版）
                meta['format'] = '.7z'
                meta['info'] = "7z listing available"
                # 本来はパースして entries を埋める
            else:
                meta['error'] = "7z command failed"
        except FileNotFoundError:
            meta['error'] = "7z command not found"
        except Exception as e:
            meta['error'] = str(e)
        
        return meta
    
    def _extract_rar(self, filepath: str, meta: Dict) -> Dict:
        """RAR コマンドで処理"""
        # unrar コマンドを使用
        try:
            result = subprocess.run(
                ['unrar', 'l', filepath],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                # パースロジック（簡略版）
                meta['format'] = '.rar'
                meta['info'] = "rar listing available"
                # 本来はパースして entries を埋める
            else:
                meta['error'] = "unrar command failed"
        except FileNotFoundError:
            meta['error'] = "unrar command not found"
        except Exception as e:
            meta['error'] = str(e)
        
        return meta
    
    def _has_path_traversal(self, path: str) -> bool:
        """
        パストラバーサル（../）の検出
        
        Args:
            path: ファイルパス
        
        Returns:
            疑わしい場合は True
        """
        return '..' in path or path.startswith('/')


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python archive_list.py <filepath>")
        sys.exit(1)
    
    config = {'archive_max_entries': 50000, 'archive_max_size_gb': 50}
    extractor = ArchiveListExtractor(config)
    meta = extractor.extract(sys.argv[1])
    print(json.dumps(meta, indent=2, ensure_ascii=False))
