# セキュリティ分析レポート

## 📋 概要
本ドキュメントは、`local-llm-file-search` プロジェクトのPythonコードに対するセキュリティ分析を記載しています。

---

## ⚠️ 検出されたセキュリティ問題

### 1. **🔴 高優先度**

#### 1.1 パストラバーサル攻撃の不完全な検出 (archive_list.py)

**ファイル**: [backend/archive_list.py](backend/archive_list.py)

**問題**: 
- `_has_path_traversal()` メソッドが定義されていないが、使用されている
- ZIP/TAR ファイルのエントリ名が十分に検証されていない可能性
- Windows でのパス区切り文字 `\` の処理が不十分

**コード位置**:
```python
if self._has_path_traversal(info.filename):
    entry['warning'] = "Possible path traversal"
```

**リスク**: 悪意あるアーカイブファイルから異なるディレクトリへのファイルアクセスが可能

**推奨対応**:
```python
def _has_path_traversal(self, path: str) -> bool:
    """パストラバーサル攻撃を検出"""
    # 相対パスコンポーネントをチェック
    parts = Path(path).parts
    if '..' in parts or path.startswith(('/', '\\')):
        return True
    # Windows 絶対パスをチェック
    if len(path) > 1 and path[1] == ':':
        return True
    return False
```

---

#### 1.2 YAML ファイルの悪意あるコマンド実行リスク (複数ファイル)

**ファイル**: 全ファイル（`yaml.safe_load()` 使用）

**現在の実装** (安全):
```python
with open(config_path, 'r', encoding='utf-8') as f:
    self.config = yaml.safe_load(f)  # ✅ 安全
```

**評価**: ✅ 現在は `yaml.safe_load()` を使用しており、安全です。
- `yaml.load()` に変更しないこと

---

#### 1.3 外部コマンド実行のリスク (archive_list.py)

**ファイル**: [backend/archive_list.py](backend/archive_list.py) - `_extract_external_command()` メソッド

**問題**:
```python
def _extract_external_command(self, filepath: str, ext: str, meta: Dict) -> Dict:
    # 外部コマンド実行が予想されるが、詳細が不明
```

**潜在的なリスク**:
- `subprocess` でコマンド実行する場合、ファイルパスが適切に引用されていない可能性
- ユーザー入力が直接コマンドラインに渡される場合、シェルインジェクション攻撃の対象

**推奨対応**:
```python
# ❌ 危険: シェルインジェクション可能
subprocess.run(f"7z x {filepath}", shell=True)

# ✅ 安全: リスト形式 + shell=False
subprocess.run(["7z", "x", filepath], shell=False, capture_output=True)
```

---

#### 1.4 JSON デシリアライゼーション (indexer.py, scanner.py)

**ファイル**: 
- [backend/scanner.py](backend/scanner.py)
- [backend/indexer.py](backend/indexer.py)

**コード**:
```python
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(self.metadata_list, f, ...)

with open(filepath, 'r', encoding='utf-8') as f:
    metadata_list = json.load(f)
```

**評価**: ✅ JSON は `json.load/dump` を使用しており、デシリアライゼーション攻撃から保護されている

---

### 2. **🟡 中優先度**

#### 2.1 ファイルシステムアクセスの権限確認不足

**ファイル**: [backend/scanner.py](backend/scanner.py)

**問題**:
```python
for root, dirs, files in os.walk(self.root_path):
    for filename in files:
        filepath = os.path.join(root, filename)
```

**リスク**:
- システムファイルやセキュアなディレクトリへのアクセス権な失敗時、エラーログに詳細情報が出力される可能性
- 権限がないファイルへのアクセス試行が適切に処理されていない

**推奨対応**:
```python
if not os.access(self.root_path, os.R_OK):
    logger.error(f"No read permission for: {self.root_path}")
    return []

# ファイルアクセス失敗をキャッチ
try:
    stat = os.stat(filepath)
except PermissionError:
    logger.debug(f"Permission denied: {filepath}")
    return
except Exception as e:
    logger.debug(f"Cannot access {filepath}: {e}")
    return
```

---

#### 2.2 設定ファイルのハードコードされたパス (config/config.yaml)

**ファイル**: [config/config.yaml](config/config.yaml)

**問題**:
```yaml
root_path: "F:\\"  # Windows ドライブパス
```

**リスク**:
- 設定ファイルがバージョン管理されている場合、本番環境へのドライブ情報が公開される
- 環境に応じた動的な設定が難しい

**推奨対応**:
```yaml
# 環境変数をサポート
root_path: ${SCAN_PATH:-"./data/raw"}
# または
root_path: null  # 起動時に環境変数またはコマンドライン引数で指定
```

---

#### 2.3 エラーメッセージのレスポンス暴露

**ファイル**: [backend/query.py](backend/query.py)

**コード**:
```python
except Exception as e:
    logger.error(f"Search error: {e}")
    return {
        'error': str(e),  # スタックトレース情報が含まれる可能性
        ...
    }
```

**リスク**:
- 詳細なエラー情報により、システム内部構造が推測される可能性
- Debug 情報が本番環境で公開される

**推奨対応**:
```python
except Exception as e:
    logger.error(f"Search error: {e}", exc_info=True)  # ログには詳細記録
    return {
        'error': 'Search failed. Please try again.',  # ユーザーに対しては汎用エラー
        'question': question,
        ...
    }
```

---

#### 2.4 テンポラリファイルの安全でない処理

**ファイル**: 全ファイル

**問題**:
- テンポラリファイルが使用される場合、保護されていない可能性
- キャッシュディレクトリのパーミッション設定不足

**推奨対応**:
```python
import tempfile

# ✅ 安全: OS が secure にテンポラリディレクトリを作成
with tempfile.TemporaryDirectory(prefix='llm_search_') as tmpdir:
    # 処理
    pass
```

---

### 3. **🟢 低優先度 / 情報**

#### 3.1 依存パッケージのバージョン管理 (requirements.txt)

**ファイル**: [requirements.txt](requirements.txt)

**現在**:
```
chromadb>=0.4.0
pyyaml>=6.0
pillow>=10.0.0
```

**推奨**:
```
# より厳密なバージョン固定
chromadb>=0.4.0,<1.0.0
pyyaml>=6.0,<7.0.0
pillow>=10.0.0,<11.0.0
ollama>=0.1.0,<1.0.0
requests>=2.28.0,<3.0.0
python-dotenv>=1.0.0,<2.0.0
mutagen>=1.46.0,<2.0.0
```

**理由**: メジャーバージョンの不意な更新によるセキュリティリスク、互換性問題

---

#### 3.2 ロギングの不適切なレベル設定

**ファイル**: 複数ファイル

**問題**:
```python
logging.basicConfig(level=logging.INFO)
```

**リスク**:
- DEBUG モードで機密情報がログに出力される可能性
- ログファイルのパーミッション設定未確認

**推奨対応**:
```python
# 環境に応じたログレベル
log_level = os.getenv('LOG_LEVEL', 'INFO')
logging.basicConfig(
    level=log_level,
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)

# ログファイルのパーミッション設定
import stat
os.chmod('logs/app.log', stat.S_IRUSR | stat.S_IWUSR)  # 0o600
```

---

#### 3.3 入力値のサニタイズ (query.py)

**ファイル**: [backend/query.py](backend/query.py)

**問題**:
```python
def query(self, question: str, top_k: int = 5) -> Dict:
    # question, top_k が直接チャンディングなしで使用
```

**推奨対応**:
```python
def query(self, question: str, top_k: int = 5) -> Dict:
    # 入力値の検証
    if not isinstance(question, str) or len(question) > 10000:
        return {'error': 'Invalid question length'}
    
    if not isinstance(top_k, int) or top_k < 1 or top_k > 100:
        return {'error': 'Invalid top_k value'}
    
    # サニタイズ
    question = question.strip()
    if not question:
        return {'error': 'Empty question'}
```

---

#### 3.4 メモリ制限とDDoS対策

**ファイル**: [backend/archive_list.py](backend/archive_list.py)

**現在の対策**:
```python
self.max_entries = config.get('archive_max_entries', 50000)
self.max_size_bytes = self.max_size_gb * 1024 * 1024 * 1024
```

**評価**: ✅ 良好 - メモリ使用量に対する制限がある

---

## 📊 セキュリティ優先度一覧

| 優先度 | 問題 | ファイル | 対応状況 |
|--------|------|--------|--------|
| 🔴 高 | パストラバーサル検出不完全 | archive_list.py | ❌ 要対応 |
| 🔴 高 | 外部コマンド実行のシェルインジェクション | archive_list.py | ❓ 不明 |
| 🟡 中 | ファイルアクセス権限チェック不足 | scanner.py | ⚠️ 改善要 |
| 🟡 中 | ハードコード設定パス | config.yaml | ⚠️ 改善要 |
| 🟡 中 | エラー情報の過度な暴露 | query.py | ⚠️ 改善要 |
| 🟢 低 | 依存パッケージバージョン管理 | requirements.txt | ⚠️ 改善推奨 |
| 🟢 低 | ロギング設定 | 全ファイル | ⚠️ 改善推奨 |

---

## ✅ 既に実装されている良好な対策

1. ✅ **YAML 安全パース**: `yaml.safe_load()` を使用
2. ✅ **JSON の安全な処理**: `json.load/dump` を使用
3. ✅ **メモリ制限**: アーカイブエントリ数とサイズに上限設定
4. ✅ **パストラバーサル検出試行**: archive_list.py で検出試行
5. ✅ **エラーハンドリング**: 例外を適切にキャッチ

---

## 🔧 推奨される対応順序

### Phase 1 (即時対応)
1. `archive_list.py` の `_has_path_traversal()` メソッド実装
2. 外部コマンド実行のシェルインジェクション対策

### Phase 2 (短期)
1. ファイルアクセス権限チェック実装
2. エラーメッセージの適切な抽象化
3. 入力値検証の強化

### Phase 3 (中期)
1. ロギングシステムの改善
2. 環境変数ベースの設定管理
3. セキュリティ監査テストの追加

---

## 📚 参考資料

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CWE-22: Path Traversal](https://cwe.mitre.org/data/definitions/22.html)
- [CWE-78: OS Command Injection](https://cwe.mitre.org/data/definitions/78.html)
- [Python Security Best Practices](https://python.readthedocs.io/en/latest/library/security_warnings.html)

