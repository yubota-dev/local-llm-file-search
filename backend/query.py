"""
query.py - メディアファイル検索クエリ処理モジュール（ReadOnly）

Chroma ベクトデータベースから読み取り専用で検索を実行
データベースへの書き込みは indexer.py のみが行う

【Phase 1 design constraints】
- This module performs read-only search against existing Chroma collection
- No indexing, no writing to database
- No content analysis or inference
- Returns metadata-based search results only
- LLM is NOT called in Phase 1 (deferred to Phase 2+)
"""

import json
import logging
import os
from typing import Dict, List, Optional

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


logger = logging.getLogger(__name__)


class MediaSearchQuery:
    """
    メディアファイル検索クラス（ReadOnly）
    
    Phase 1: Chroma collection から読み取り検索のみ
    データベースへの書き込みは indexer.py のみが行う
    """
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初期化（config.yaml のみ読む）
        
        Args:
            config_path: config.yaml のパス
        """
        if not YAML_AVAILABLE:
            raise ImportError("pyyaml is required")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
        
        self.persist_dir = self.config['vectordb']['persist_directory']
        self.collection = None
        
        # Chroma collection に接続（読み取り専用）
        self._connect_to_collection()
    
    def _connect_to_collection(self) -> None:
        """Chroma collection に読み取り専用で接続"""
        try:
            import chromadb
            client = chromadb.PersistentClient(path=self.persist_dir)
            self.collection = client.get_collection(name="media_metadata")
            logger.info(f"Connected to Chroma collection at {self.persist_dir}")
        except Exception as e:
            logger.warning(f"Collection not found or error: {e}")
            # コレクションが存在しない（インデックス未作成）
            self.collection = None
    
    def query(self, question: str, top_k: int = 5) -> Dict:
        """
        ベクトル検索を実行（読み取り専用・LLM なし）
        
        【Phase 1 constraint】
        - No indexing, no writing
        - Search only from existing Chroma collection
        - No external API calls
        
        Args:
            question: 検索質問
            top_k: 返却結果数
        
        Returns:
            検索結果
        """
        # インデックスが存在するかチェック
        if not self.collection:
            return {
                'error': 'Index not found. Run: python backend/indexer.py',
                'question': question,
                'search_results_count': 0,
                'candidates': []
            }
        
        try:
            # Chroma から検索実行（読み取りのみ）
            results = self.collection.query(
                query_texts=[question],
                n_results=top_k
            )
            
            return self._format_search_results(question, results)
        
        except Exception as e:
            logger.error(f"Search error: {e}")
            return {
                'error': str(e),
                'question': question,
                'search_results_count': 0,
                'candidates': []
            }
    
    def _format_search_results(self, question: str, results: Dict) -> Dict:
        """
        Chroma の検索結果をフォーマット
        
        Args:
            question: 検索質問
            results: Chroma の raw 検索結果
        
        Returns:
            フォーマット済み結果
        """
        candidates = []
        
        if results.get('ids') and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                meta = results['metadatas'][0][i] if results.get('metadatas') else {}
                
                candidate = {
                    'path': meta.get('path', 'unknown'),
                    'kind': meta.get('kind', 'unknown'),
                    'size': meta.get('size', 'unknown'),
                    'mtime': meta.get('mtime', 'unknown'),
                    'similarity': round(results['distances'][0][i], 3) if results.get('distances') else 0,
                    'source_type': meta.get('source_type', 'metadata')
                }
                candidates.append(candidate)
        
        return {
            'question': question,
            'search_results_count': len(candidates),
            'candidates': candidates
        }


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python query.py \"<question>\"")
        sys.exit(1)
    
    question = ' '.join(sys.argv[1:])
    
    # 検索エンジンを初期化（indexer 不要）
    print(f"[INFO] Initializing search engine...")
    try:
        searcher = MediaSearchQuery()
    except Exception as e:
        print(f"[ERROR] Failed to initialize: {e}")
        sys.exit(1)
    
    # 検索実行
    print(f"[INFO] Searching for: {question}")
    result = searcher.query(question)
    
    # エラー結果表示
    if 'error' in result and result['error']:
        print(f"[ERROR] {result['error']}")
        sys.exit(1)
    
    # 結果表示
    print(f"\n[RESULTS]")
    print(f"Query: {result.get('question', 'N/A')}")
    print(f"Found: {result.get('search_results_count', 0)} items")
    
    if result.get('search_results_count', 0) == 0:
        print("No results found")
    else:
        print(f"\nCandidates:")
        for i, candidate in enumerate(result.get('candidates', []), 1):
            print(f"  [{i}] {candidate.get('path')}")
            print(f"      kind: {candidate.get('kind')}, size: {candidate.get('size')}")
            print(f"      similarity: {candidate.get('similarity')}")
            print(f"      source_type: {candidate.get('source_type')}")
    
    print("[INFO] Done")

