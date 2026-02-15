"""
query.py - LLM 統合検索クエリ処理モジュール

質問 → ベクトル検索 top-k → LLM に渡す

LLM は説明のみ（推測禁止）
必ず path と source_type を含める
見つからない場合は「見つかりません」と明言

【Phase 1 design constraints】
- This module retrieves search results and formats them for LLM explanation.
- LLM is used for METADATA EXPLANATION ONLY (why files were retrieved).
- File content understanding, inference, and guessing are STRICTLY PROHIBITED.
- LLM must never conclude what files actually contain.
- If evidence is insufficient, LLM MUST state "Not found" instead of guessing.
- This design intentionally defers semantic understanding to Phase 2+.
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

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


logger = logging.getLogger(__name__)


class LocalLLMQueryEngine:
    """ローカル LLM 統合クエリエンジン"""
    
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
        
        self.ollama_url = self.config['ollama']['base_url']
        self.model = self.config['ollama']['model']
        self.temperature = self.config['ollama']['temperature']
        
        # インデックャーは別途初期化が必要
        self.indexer = None
    
    def set_indexer(self, indexer):
        """
        インデックャーを設定
        
        Args:
            indexer: MediaIndexer インスタンス
        """
        self.indexer = indexer
    
    def query(self, question: str, top_k: int = 5) -> Dict:
        """
        クエリを実行
        
        【Phase 1 enforcement】
        This method retrieves files based on metadata/filename/folder matches only.
        LLM explains retrieval reasons, never guesses content.
        
        Args:
            question: ユーザーの質問
            top_k: 検索候補数
        
        Returns:
            回答メタデータ
        """
        if not self.indexer:
            return {
                'error': 'Indexer not initialized',
                'answer': '申し訳ありません。システムが初期化されていません。'
            }
        
        # ステップ 1: ベクトル検索
        search_results = self.indexer.search(question, top_k=top_k)
        
        if not search_results:
            return {
                'question': question,
                'answer': '指定の条件に合うファイルが見つかりません。',
                'candidates': []
            }
        
        # ステップ 2: 証拠を準備
        evidence = self._prepare_evidence(search_results)
        
        # ステップ 3: LLM に送信
        llm_response = self._call_llm(question, evidence, search_results)
        
        return {
            'question': question,
            'answer': llm_response,
            'candidates': self._format_candidates(search_results),
            'search_results_count': len(search_results)
        }
    
    def _prepare_evidence(self, search_results: List[Dict]) -> str:
        """
        検索結果から根拠付き証拠文を準備（Phase 1: 推測なし）
        
        【Phase 1 constraint】
        Evidence must include ONLY:
        - Extracted metadata (resolution, duration, artist, tags, etc.)
        - Filename and folder name matches
        - Sidecar text references
        NO speculation or content inference.
        
        Args:
            search_results: ベクトル検索結果
        
        Returns:
            証拠テキスト（一致情報のみ）
        """
        evidence_parts = []
        
        for i, result in enumerate(search_results, 1):
            meta = result.get('metadata', {})
            path = meta.get('path', 'unknown')
            kind = meta.get('kind', 'unknown')
            score = result.get('score', 0)
            source_type = meta.get('source_type', 'metadata')
            
            # 根拠を構築
            reasons = []
            
            # メタデータフィールの一致情報
            for key in ['title', 'artist', 'album', 'resolution', 'duration', 'format', 'entries']:
                if key in meta:
                    reasons.append(f"{key}={meta[key]}")
            
            # テキスト情報
            if 'has_text' in meta:
                reasons.append(f"has_text:{meta['has_text']}")
            
            reason_str = ' | '.join(reasons) if reasons else '(基本メタデータのみ)'
            
            evidence_parts.append(
                f"[候補 {i}] (種別:{kind})\n"
                f"  パス: {path}\n"
                f"  一致情報: {reason_str}\n"
                f"  データ出所: {source_type}\n"
                f"  類似度: {score:.3f}"
            )
        
        return '\n'.join(evidence_parts)
    
    def _call_llm(self, question: str, evidence: str, search_results: List[Dict]) -> str:
        """
        Ollama LLM を呼び出し
        
        IMPORTANT: Phase 1 constraint enforcement point.
        LLM MUST NOT guess, infer, or conclude file content.
        LLM MUST ONLY explain why each file was retrieved.
        
        Args:
            question: ユーザー質問
            evidence: 検索結果の証拠
            search_results: 検索結果詳細
        
        Returns:
            LLM からの回答
        """
        if not REQUESTS_AVAILABLE:
            return "requests ライブラリが必要です。インストールしてください。"
        
        # LLM プロンプト構築
        prompt = self._build_prompt(question, evidence, search_results)
        
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "temperature": self.temperature
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get('response', '回答を生成できませんでした。')
            else:
                logger.error(f"LLM error: {response.status_code}")
                return f"LLM エラー: {response.status_code}"
        
        except requests.exceptions.ConnectionError:
            return (
                "Ollama に接続できません。"
                f"確認してください：{self.ollama_url}"
            )
        except requests.exceptions.Timeout:
            return "LLM のレスポンスがタイムアウトしました。"
        except Exception as e:
            logger.error(f"LLM call error: {e}")
            return f"エラーが発生しました：{str(e)}"
    
    def _build_prompt(self, question: str, evidence: str, search_results: List[Dict]) -> str:
        """
        LLM プロンプトを構築（Phase 1: 判断・断定禁止）
        
        【Phase 1 enforcement point】
        This prompt STRICTLY enforces:
        - LLM must NOT guess file content or meaning.
        - LLM must ONLY explain why files were retrieved.
        - No speculation, inference, or guessing allowed.
        - If evidence is insufficient, respond "Not found".
        
        Args:
            question: ユーザー質問
            evidence: 証拠テキスト
            search_results: 検索結果
        
        Returns:
            プロンプト文字列
        """
        prompt = f"""あなたは、パソコンのメディアファイル検索システムのアシスタントです。

ユーザーの検索条件：
{question}

以下は、検索条件に一致・近いファイル候補の一覧です：
{evidence}

【絶対ルール】Phase 1では以下を厳格に守ってください。

1. ⚠️ 推測・判断・断定をしない
   - 「この画像は〇〇っぽい」は言わない
   - 「きっとxxxだろう」は言わない
   - ファイルの内容から意味を想像しない

2. ✅ 一致・近い根拠だけを述べる
   - 「ファイル名に『xxx』が含まれる」
   - 「メタデータで『artist=yyy』」
   - 「付随メモに『zzz』という語が含まれる」

3. ✅ 候補が合う理由を必ず示す
   - どの情報（ファイル名/フォルダ名/メタ/テキスト）に一致したか

4. ❌ 見つからない場合
   - 「見つかりません」と明言する
   - 推測や曖昧な候補を出さない

回答フォーマット：
- 各候補について、「パス」→「一致根拠」を記載
- 複数候補があればすべて列挙（ただし根拠がない推測は含めない）

回答："""
        
        return prompt
    
    def _format_candidates(self, search_results: List[Dict]) -> List[Dict]:
        """
        候補をフォーマット（根拠を明示）
        
        【Phase 1 constraint】
        All candidates must include explicit reasons (which metadata/filename/text matched).
        No unsubstantiated candidates are returned.
        
        Args:
            search_results: 検索結果
        
        Returns:
            フォーマット済み候補リスト
        """
        candidates = []
        
        for result in search_results:
            meta = result.get('metadata', {})
            
            # 根拠を構築（どの情報に一致したか）
            reasons = []
            
            # ファイル名
            if meta.get('filename_match'):
                reasons.append(f"ファイル名: {meta['filename_match']}")
            
            # メタデータフィールド
            if meta.get('resolution'):
                reasons.append(f"解像度: {meta['resolution']}")
            if meta.get('duration'):
                reasons.append(f"長さ: {meta['duration']}")
            if meta.get('artist'):
                reasons.append(f"アーティスト: {meta['artist']}")
            if meta.get('title'):
                reasons.append(f"タイトル: {meta['title']}")
            if meta.get('entries'):
                reasons.append(f"アーカイブ内容: {meta['entries']} 件")
            
            # テキスト情報
            if meta.get('has_text'):
                reasons.append(f"付随テキスト: {meta['has_text']}")
            
            # source_type を記載（データ出所）
            source_type = meta.get('source_type', 'metadata')
            
            candidates.append({
                'path': meta.get('path', 'unknown'),
                'kind': meta.get('kind', 'unknown'),
                'size': meta.get('size', 'unknown'),
                'mtime': meta.get('mtime', 'unknown'),
                'similarity': round(result.get('score', 0), 3),
                'reasons': reasons,  # 一致根拠
                'source_type': source_type  # データ出所
            })
        
        return candidates


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python query.py \"<question>\"")
        sys.exit(1)
    
    question = ' '.join(sys.argv[1:])
    
    engine = LocalLLMQueryEngine()
    
    # インデックャーの初期化が必要
    # from indexer import MediaIndexer
    # indexer = MediaIndexer()
    # engine.set_indexer(indexer)
    
    result = engine.query(question)
    print(json.dumps(result, indent=2, ensure_ascii=False))
