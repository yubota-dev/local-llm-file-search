"""
chunker.py - テキストチャンキング処理モジュール

大きなテキストを指定サイズで学習用チャンクに分割
オーバーラップを設定して検索性を向上
"""

import json
import logging
from typing import List, Dict, Tuple


logger = logging.getLogger(__name__)


class TextChunker:
    """テキストチャンキング処理"""
    
    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50):
        """
        初期化
        
        Args:
            chunk_size: チャンクサイズ（文字数）
            chunk_overlap: オーバーラップサイズ（文字数）
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
    
    def chunk(self, text: str, metadata: Dict = None) -> List[Dict]:
        """
        テキストをチャンキング
        
        Args:
            text: 入力テキスト
            metadata: チャンク共通メタデータ（path など）
        
        Returns:
            チャンク情報リスト
        """
        if not text or len(text) == 0:
            return []
        
        chunks = []
        step = self.chunk_size - self.chunk_overlap
        
        for i in range(0, len(text), step):
            chunk_text = text[i:i + self.chunk_size]
            
            if len(chunk_text) == 0:
                continue
            
            chunk_data = {
                'chunk_id': len(chunks),
                'text': chunk_text,
                'start_char': i,
                'end_char': min(i + self.chunk_size, len(text)),
                'length': len(chunk_text)
            }
            
            if metadata:
                chunk_data.update(metadata)
            
            chunks.append(chunk_data)
        
        return chunks
    
    def chunk_by_sentences(
        self,
        text: str,
        metadata: Dict = None,
        max_chars_per_chunk: int = 512
    ) -> List[Dict]:
        """
        文単位でチャンキング（精密版）
        
        Args:
            text: 入力テキスト
            metadata: チャンク共通メタデータ
            max_chars_per_chunk: チャンク最大文字数
        
        Returns:
            チャンク情報リスト
        """
        # 簡単な文分割（日本語・英語対応）
        sentences = self._split_sentences(text)
        
        chunks = []
        current_chunk = []
        current_length = 0
        char_offset = 0
        
        for sentence in sentences:
            sentence_len = len(sentence)
            
            if current_length + sentence_len > max_chars_per_chunk and current_chunk:
                # チャンク確定
                chunk_text = ''.join(current_chunk)
                chunk_data = {
                    'chunk_id': len(chunks),
                    'text': chunk_text,
                    'start_char': char_offset - current_length,
                    'end_char': char_offset,
                    'length': current_length,
                    'sentence_count': len(current_chunk)
                }
                
                if metadata:
                    chunk_data.update(metadata)
                
                chunks.append(chunk_data)
                current_chunk = []
                current_length = 0
            
            current_chunk.append(sentence)
            current_length += sentence_len
            char_offset += sentence_len
        
        # 残りをチャンク化
        if current_chunk:
            chunk_text = ''.join(current_chunk)
            chunk_data = {
                'chunk_id': len(chunks),
                'text': chunk_text,
                'start_char': char_offset - current_length,
                'end_char': char_offset,
                'length': current_length,
                'sentence_count': len(current_chunk)
            }
            
            if metadata:
                chunk_data.update(metadata)
            
            chunks.append(chunk_data)
        
        return chunks
    
    def _split_sentences(self, text: str) -> List[str]:
        """
        テキストを文単位に分割
        
        Args:
            text: 入力テキスト
        
        Returns:
            文のリスト
        """
        # 簡易実装：日本語・英語の句点で分割
        sentences = []
        current = []
        
        for char in text:
            current.append(char)
            
            # 句点判定
            if char in ['。', '！', '？', '.', '!', '?']:
                sentences.append(''.join(current))
                current = []
            
            # 改行も文の区切りとする
            elif char == '\n' and current and current[-2:] != ['', '\n']:
                if ''.join(current).strip():
                    sentences.append(''.join(current))
                current = []
        
        # 残り
        if current and ''.join(current).strip():
            sentences.append(''.join(current))
        
        return sentences


if __name__ == '__main__':
    import sys
    
    sample_text = "これはサンプルテキストです。複数の文を含んでいます。" * 10
    
    chunker = TextChunker(chunk_size=100, chunk_overlap=20)
    
    print("=== Simple Chunking ===")
    chunks = chunker.chunk(sample_text, metadata={'path': '/test/file.txt'})
    for chunk in chunks[:3]:
        print(f"Chunk {chunk['chunk_id']}: {chunk['text'][:50]}...")
    
    print(f"\nTotal chunks: {len(chunks)}")
