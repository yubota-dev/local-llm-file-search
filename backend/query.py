"""
query.py - LLM 統合検索クエリ処理モジュール

質問 → ベクトル検索 top-k → LLM に渡す

LLM は説明のみ（推測禁止）
必ず path と source_type を含める
見つからない場合は「見つかりません」と明言
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
        検索結果から証拠文を準備
        
        Args:
            search_results: ベクトル検索結果
        
        Returns:
            証拠テキスト
        """
        evidence_parts = []
        
        for i, result in enumerate(search_results, 1):
            meta = result.get('metadata', {})
            path = meta.get('path', 'unknown')
            kind = meta.get('kind', 'unknown')
            score = result.get('score', 0)
            
            evidence_parts.append(
                f"候補 {i}: [{kind}] {path} (類似度: {score:.2f})"
            )
        
        return '\n'.join(evidence_parts)
    
    def _call_llm(self, question: str, evidence: str, search_results: List[Dict]) -> str:
        """
        Ollama LLM を呼び出し
        
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
        LLM プロンプトを構築
        
        Args:
            question: ユーザー質問
            evidence: 証拠テキスト
            search_results: 検索結果
        
        Returns:
            プロンプト文字列
        """
        prompt = f"""あなたは、パソコンのメディアファイル検索システムのアシスタントです。

ユーザーの質問：
{question}

以下は、ローカル検索システムから該当しそうなファイルの候補です：
{evidence}

重要なルール：
1. 上記の検索結果の中から、ユーザーの質問に最も合う候補を提示してください。
2. 推測や仮定は一切しないでください。必ず検索結果に基づいてください。
3. 各ファイルについて、ファイルパス（path）とファイル種別（kind）を明記してください。
4. 見つからない場合は「該当するファイルが見つかりません」と明言してください。
5. 複数の候補がある場合はすべて列挙し、最も可能性が高い順で提示してください。

回答："""
        
        return prompt
    
    def _format_candidates(self, search_results: List[Dict]) -> List[Dict]:
        """
        候補をフォーマット
        
        Args:
            search_results: 検索結果
        
        Returns:
            フォーマット済み候補リスト
        """
        candidates = []
        
        for result in search_results:
            meta = result.get('metadata', {})
            candidates.append({
                'path': meta.get('path', 'unknown'),
                'kind': meta.get('kind', 'unknown'),
                'size': meta.get('size', 'unknown'),
                'mtime': meta.get('mtime', 'unknown'),
                'similarity': result.get('score', 0)
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
