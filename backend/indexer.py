"""
indexer.py - ベクトルDB インデックス化モジュール

メタデータと付随テキストを文章化してベクトル化
Chroma / FAISS に保存

必須メタ：path, kind, mtime, size
オプション：duration, resolution, artist, tags など

【Phase 1 design constraints】
- This module indexes METADATA and SIDECAR TEXT ONLY (no content analysis).
- Metadata documents are created for search purposes (file name, format, resolution, etc.).
- Vector embeddings represent structured metadata, NOT content understanding.
- Content-based features (visual, audio, semantic) are deferred to Phase 2+.
- Indexing structure is designed to support future content layers without modification.
"""

import json
import logging
import os
from typing import Dict, List, Optional
from datetime import datetime
from pathlib import Path

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logging.warning("chromadb not installed")

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


logger = logging.getLogger(__name__)


class MediaIndexer:
    """メディアファイルインデック化エンジン"""
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初期化
        
        Args:
            config_path: config.yaml のパス
        """
        if not YAML_AVAILABLE:
            raise ImportError("pyyaml is required")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.persist_dir = self.config['vectordb']['persist_directory']
        os.makedirs(self.persist_dir, exist_ok=True)
        
        self.db = None
        if CHROMADB_AVAILABLE:
            self._init_chromadb()
    
    def _init_chromadb(self) -> None:
        """Chroma DB を初期化"""
        settings = Settings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=self.persist_dir,
            anonymized_telemetry=False,
        )
        
        self.db = chromadb.Client(settings)
        logger.info(f"Chroma DB initialized at {self.persist_dir}")
    
    def index_metadata(self, metadata_list: List[Dict]) -> None:
        """
        メタデータリストをインデックス化
        
        Args:
            metadata_list: scanner.py から得たメタデータリスト
        """
        if not CHROMADB_AVAILABLE:
            logger.error("chromadb not available - skipping indexing")
            return
        
        for i, meta in enumerate(metadata_list):
            try:
                # メディア情報を文章化
                document = self._create_document(meta)
                
                # メタデータを整理
                metadata_dict = self._extract_metadata(meta)
                
                # Chroma に追加
                self.db.add(
                    documents=[document],
                    metadatas=[metadata_dict],
                    ids=[f"media_{i}"]
                )
                
                if (i + 1) % 100 == 0:
                    logger.info(f"Indexed {i + 1} items")
            
            except Exception as e:
                logger.warning(f"Error indexing {meta.get('path')}: {e}")
        
        # 永続化
        self.db.persist()
        logger.info(f"Indexed {len(metadata_list)} items successfully")
    
    def _create_document(self, meta: Dict) -> str:
        """
        メタデータを検索用ドキュメント文章に変換
        
        【Phase 1 constraint】
        Documents are created from metadata ONLY (filename, resolution, duration, tags, etc.).
        No content analysis or semantic interpretation is performed.
        Document text is designed for search indexing, NOT for understanding file content.
        
        Args:
            meta: メタデータ
        
        Returns:
            ドキュメント文字列
        """
        parts = []
        
        # 基本情報
        parts.append(f"type: {meta.get('kind', 'unknown')}")
        parts.append(f"name: {meta.get('name', '')}")
        parts.append(f"path: {meta.get('path', '')}")
        parts.append(f"size: {meta.get('size', 0)} bytes")
        
        # 動画メタ
        if meta.get('kind') == 'video' and 'video_meta' in meta:
            vmeta = meta['video_meta']
            if 'duration_sec' in vmeta:
                parts.append(f"duration: {vmeta['duration_sec']} seconds")
            if 'video' in vmeta:
                v = vmeta['video']
                if v.get('width') and v.get('height'):
                    parts.append(f"resolution: {v['width']}x{v['height']}")
                if v.get('fps'):
                    parts.append(f"fps: {v['fps']}")
                if v.get('codec'):
                    parts.append(f"codec: {v['codec']}")
            
            if 'tags' in vmeta and vmeta['tags']:
                if vmeta['tags'].get('title'):
                    parts.append(f"title: {vmeta['tags']['title']}")
                if vmeta['tags'].get('artist'):
                    parts.append(f"artist: {vmeta['tags']['artist']}")
        
        # 画像メタ
        elif meta.get('kind') == 'image' and 'image_meta' in meta:
            imeta = meta['image_meta']
            if imeta.get('width') and imeta.get('height'):
                parts.append(f"resolution: {imeta['width']}x{imeta['height']}")
            if imeta.get('format'):
                parts.append(f"format: {imeta['format']}")
            if 'exif' in imeta:
                if 'DateTime' in imeta['exif']:
                    parts.append(f"date: {imeta['exif']['DateTime']}")
                if 'Model' in imeta['exif']:
                    parts.append(f"camera: {imeta['exif']['Model']}")
        
        # 音声メタ
        elif meta.get('kind') == 'audio' and 'audio_meta' in meta:
            ameta = meta['audio_meta']
            if 'duration_sec' in ameta:
                parts.append(f"duration: {ameta['duration_sec']} seconds")
            if 'tags' in ameta and ameta['tags']:
                if ameta['tags'].get('title'):
                    parts.append(f"title: {ameta['tags']['title']}")
                if ameta['tags'].get('artist'):
                    parts.append(f"artist: {ameta['tags']['artist']}")
                if ameta['tags'].get('album'):
                    parts.append(f"album: {ameta['tags']['album']}")
        
        # アーカイブメタ
        elif meta.get('kind') == 'archive' and 'archive_meta' in meta:
            ameta = meta['archive_meta']
            parts.append(f"contains: {ameta.get('entry_count', 0)} items")
            
            # 最初の数件のエントリを記載
            if 'entries' in ameta:
                top_entries = [e['name'] for e in ameta['entries'][:10]]
                parts.append(f"entries: {', '.join(top_entries)}")
        
        # 付随テキスト
        if 'text_sources' in meta:
            text_sources = meta['text_sources']
            if text_sources:
                source_types = [t['source_type'] for t in text_sources]
                parts.append(f"has_text: {', '.join(set(source_types))}")
        
        return ' | '.join(parts)
    
    def _extract_metadata(self, meta: Dict) -> Dict:
        """
        チロマDB用メタデータを抽出（Phase 1: source_type を明示）
        
        Args:
            meta: 元メタデータ
        
        Returns:
            チロマDB用メタデータ（各情報の出所を記録）
        """
        result = {
            'kind': str(meta.get('kind', 'unknown')),
            'path': str(meta.get('path', '')),
            'size': str(meta.get('size', 0)),
            'mtime': str(meta.get('mtime', '')),
            'source_type': 'metadata'  # Phase 1: データ出所を明示
        }
        
        # 動画
        if meta.get('kind') == 'video' and 'video_meta' in meta:
            vmeta = meta['video_meta']
            if 'video' in vmeta and vmeta['video'].get('width'):
                result['resolution'] = f"{vmeta['video']['width']}x{vmeta['video']['height']}"
            if 'duration_sec' in vmeta:
                result['duration'] = str(vmeta['duration_sec'])
            if 'tags' in vmeta and vmeta['tags']:
                if vmeta['tags'].get('title'):
                    result['title'] = str(vmeta['tags']['title'])
                if vmeta['tags'].get('artist'):
                    result['artist'] = str(vmeta['tags']['artist'])
        
        # 画像
        elif meta.get('kind') == 'image' and 'image_meta' in meta:
            imeta = meta['image_meta']
            if imeta.get('width'):
                result['resolution'] = f"{imeta['width']}x{imeta['height']}"
            if imeta.get('format'):
                result['format'] = str(imeta['format'])
        
        # 音声
        elif meta.get('kind') == 'audio' and 'audio_meta' in meta:
            ameta = meta['audio_meta']
            if 'duration_sec' in ameta:
                result['duration'] = str(ameta['duration_sec'])
            if 'tags' in ameta and ameta['tags']:
                if ameta['tags'].get('title'):
                    result['title'] = str(ameta['tags']['title'])
                if ameta['tags'].get('artist'):
                    result['artist'] = str(ameta['tags']['artist'])
        
        # アーカイブ
        elif meta.get('kind') == 'archive' and 'archive_meta' in meta:
            ameta = meta['archive_meta']
            result['entries'] = str(ameta.get('entry_count', 0))
            result['format'] = str(ameta.get('format', 'unknown'))
        
        # 付随テキスト情報
        if 'text_sources' in meta and meta['text_sources']:
            text_types = [t.get('source_type', 'unknown') for t in meta['text_sources']]
            result['has_text'] = ','.join(set(text_types))  # 重複排除
        
        return result
    
    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """
        ベクトル検索を実行
        
        Args:
            query: 質問文
            top_k: 返却件数
        
        Returns:
            検索結果リスト
        """
        if not self.db:
            logger.error("Database not initialized")
            return []
        
        try:
            results = self.db.query(
                query_texts=[query],
                n_results=top_k
            )
            
            return self._format_results(results)
        
        except Exception as e:
            logger.error(f"Search error: {e}")
            return []
    
    def _format_results(self, results: Dict) -> List[Dict]:
        """
        検索結果をフォーマット
        
        Args:
            results: Chroma の raw 結果
        
        Returns:
            フォーマット済み結果
        """
        formatted = []
        
        if not results['ids'] or not results['ids'][0]:
            return formatted
        
        for i, doc_id in enumerate(results['ids'][0]):
            result = {
                'id': doc_id,
                'score': results['distances'][0][i] if results['distances'] else 0,
                'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                'path': results['metadatas'][0][i].get('path') if results['metadatas'] else ''
            }
            formatted.append(result)
        
        return formatted


if __name__ == '__main__':
    # テスト実行
    indexer = MediaIndexer()
    
    # ダミーメタデータ
    sample_metadata = [
        {
            'path': '/media/sample.mp4',
            'name': 'sample.mp4',
            'ext': '.mp4',
            'size': 1024000,
            'mtime': datetime.now().isoformat(),
            'kind': 'video',
            'video_meta': {
                'duration_sec': 3600,
                'video': {'width': 1920, 'height': 1080, 'fps': 30, 'codec': 'h264'},
                'tags': {'title': 'Sample Video', 'artist': 'Creator'}
            }
        }
    ]
    
    indexer.index_metadata(sample_metadata)
    print("Indexing complete")
