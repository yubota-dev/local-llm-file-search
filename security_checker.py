"""
security_checker.py - コードセキュリティスキャナー

セキュリティの一般的な問題をスキャンします。
"""

import os
import re
import logging
from typing import List, Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SecurityChecker:
    """セキュリティチェッカー"""
    
    # セキュリティチェックルール
    PATTERNS = {
        'shell_injection': r'subprocess\.(?:call|run|Popen)\([^,]*,\s*shell\s*=\s*True',
        'yaml_unsafe': r'yaml\.(?:load|unsafe_load)',
        'pickle_unsafe': r'pickle\.(?:load|loads)',
        'eval_dangerous': r'(?:eval|exec|compile)\(',
        'hardcoded_path': r'["\'](?:[a-zA-Z]:)?[/\\][^"\']*["\']',
        'sql_concat': r"(?:execute|query)\([^)]*\+[^)]*\)",
        'credentials_hardcoded': r"(?:password|api_key|secret)\s*=\s*[\"'][^\"']{8,}",
    }
    
    def __init__(self):
        """初期化"""
        self.issues = []
    
    def scan_directory(self, directory: str) -> List[Dict]:
        """
        ディレクトリ内の全Pythonファイルをスキャン
        
        Args:
            directory: スキャン対象ディレクトリ
        
        Returns:
            検出されたセキュリティ問題のリスト
        """
        self.issues = []
        
        for root, dirs, files in os.walk(directory):
            # 除外ディレクトリ
            dirs[:] = [d for d in dirs if d not in ['__pycache__', '.git', 'venv', '.venv']]
            
            for filename in files:
                if filename.endswith('.py'):
                    filepath = os.path.join(root, filename)
                    self._scan_file(filepath)
        
        return self.issues
    
    def _scan_file(self, filepath: str) -> None:
        """
        単一ファイルをスキャン
        
        Args:
            filepath: ファイルパス
        """
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.split('\n')
        except Exception as e:
            logger.warning(f"Cannot read {filepath}: {e}")
            return
        
        # パターンマッチング
        for pattern_name, pattern_regex in self.PATTERNS.items():
            matches = re.finditer(pattern_regex, content, re.IGNORECASE)
            
            for match in matches:
                # 行番号を計算
                line_num = content[:match.start()].count('\n') + 1
                line_content = lines[line_num - 1].strip()
                
                issue = {
                    'file': filepath,
                    'line': line_num,
                    'pattern': pattern_name,
                    'code': line_content,
                    'severity': self._get_severity(pattern_name)
                }
                
                self.issues.append(issue)
    
    @staticmethod
    def _get_severity(pattern_name: str) -> str:
        """パターン名から重大度を取得"""
        high = ['shell_injection', 'eval_dangerous', 'pickle_unsafe']
        medium = ['sql_concat', 'credentials_hardcoded']
        low = ['hardcoded_path']
        
        if pattern_name in high:
            return 'HIGH'
        elif pattern_name in medium:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def print_report(self) -> None:
        """レポート出力"""
        if not self.issues:
            logger.info("✅ セキュリティ問題は検出されませんでした")
            return
        
        print("\n" + "="*70)
        print("🔒 セキュリティチェック レポート")
        print("="*70)
        
        # 重大度でグループ化
        by_severity = {}
        for issue in self.issues:
            severity = issue['severity']
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(issue)
        
        # 高→低の順で出力
        for severity in ['HIGH', 'MEDIUM', 'LOW']:
            if severity not in by_severity:
                continue
            
            severity_emoji = {'HIGH': '🔴', 'MEDIUM': '🟡', 'LOW': '🟢'}
            print(f"\n{severity_emoji[severity]} {severity} 優先度 ({len(by_severity[severity])}件)")
            print("-" * 70)
            
            for issue in by_severity[severity]:
                print(f"  📄 {issue['file']}:{issue['line']}")
                print(f"     パターン: {issue['pattern']}")
                print(f"     コード: {issue['code'][:60]}")
                print()


if __name__ == '__main__':
    import sys
    
    target_dir = sys.argv[1] if len(sys.argv) > 1 else './backend'
    
    checker = SecurityChecker()
    issues = checker.scan_directory(target_dir)
    checker.print_report()
    
    print(f"\n合計: {len(issues)} 件のセキュリティ問題が検出されました\n")

