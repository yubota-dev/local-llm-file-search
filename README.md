# Local LLM Media & Archive Search

自宅PCの指定ドライブにある **動画・画像・音楽・圧縮ファイルを索引化** し、
「何がどこにあるか」「目的に合う候補はどれか」を検索できるシステム。

**Phase 2実装済み**：文字起こし・画像認識結果も検索対象に追加。
**LLMは検索結果の説明のみ**（推測禁止／根拠必須）

---

## 📋 対象ファイル形式

| カテゴリ | 対応拡張子 |
|---------|----------|
| **動画** | .mp4, .mkv, .mov, .avi, .wmv, .flv, .webm, .m4v |
| **画像** | .jpg, .jpeg, .png, .webp, .gif, .bmp, .tiff, .heic |
| **音楽** | .mp3, .flac, .wav, .m4a, .aac, .ogg, .opus, .wma |
| **圧縮** | .zip, .7z, .rar, .tar, .gz, .tgz |
| **字幕** | .srt, .vtt, .ass |
| **メモ** | .txt, .md（同名ファイル） |
| **メタ** | .nfo, .json, .xml |

---

## 🏗️ プロジェクト構造

```
local-llm-file-search/
├─ backend/
│  ├─ scanner.py           # ドライブ走査＆メディアファイル検出
│  ├─ meta_video_audio.py  # ffprobe による動画・音声メタ抽出
│  ├─ meta_image.py        # Pillow + EXIF で画像メタ抽出
│  ├─ meta_audio.py        # mutagen による音声タグ抽出
│  ├─ archive_list.py      # zip/7z/rar/tar の中身一覧取得
│  ├─ text_sources.py      # 字幕・メモ・メタテキスト抽出
│  ├─ chunker.py           # テキストチャンキング処理
│  ├─ indexer.py           # ベクトルDB へのインデックス化
│  ├─ query.py             # 読み取り専用検索モジュール
│  ├─ transcriber.py       # [Phase 2] Whisper による音声・動画文字起こし
│  ├─ vision.py            # [Phase 2] LLaVA による画像内容説明生成
│  └─ main.py              # [Phase 2] FastAPI Web UI サーバー
├─ frontend/
│  └─ index.html           # [Phase 2] ブラウザ検索UI
├─ config/
│  └─ config.yaml          # 設定ファイル
├─ data/
│  ├─ raw/                 # メタデータJSON（git管理外）
│  └─ index/               # ベクトルDBデータ（git管理外）
├─ .gitignore
├─ requirements.txt
└─ README.md
```

---

## 🚀 セットアップ

### 前提条件

- **OS**: Windows 11
- **Python**: 3.11+（仮想環境推奨）
- **Ollama**: ローカル実行（http://localhost:11434）
- **NVIDIA GPU**: VRAM 8GB以上推奨（Whisper・LLaVA使用時）
- **CUDA 12.4+**: faster-whisper のGPU使用に必要
- **ffprobe**（オプション）: ffmpeg パッケージに含まれる

### インストール手順

```powershell
# 仮想環境の作成
python -m venv venv
venv\Scripts\activate

# 依存パッケージのインストール
pip install -r requirements.txt
```

### Ollamaモデルの準備

```powershell
# 検索・説明用LLM
ollama pull qwen2.5:14b

# ベクトル埋め込み用
ollama pull nomic-embed-text

# 画像認識用（Phase 2）
ollama pull llava:13b
```

### セキュリティ設定（推奨）

```powershell
# Ollamaをlocalhost限定に制限
[System.Environment]::SetEnvironmentVariable("OLLAMA_HOST", "127.0.0.1:11434", "User")

# ファイアウォール設定
netsh advfirewall firewall add rule name="Allow Ollama Localhost" dir=in action=allow protocol=TCP localport=11434 localip=127.0.0.1
netsh advfirewall firewall add rule name="Block Ollama External" dir=in action=block protocol=TCP localport=11434
```

### 設定

`config/config.yaml` を編集：

```yaml
scan:
  root_path: "D:/"        # スラッシュ区切りで指定（バックスラッシュは\tに化ける）

ollama:
  model: "qwen2.5:14b"   # インストール済みモデルに合わせる
```

> ⚠️ `root_path`は必ずスラッシュ(`/`)区切りで指定してください。バックスラッシュ(`\`)を使うと`\t`がタブ文字に変換されるバグがあります。

---

## 📖 使用方法

### Phase 1：CLIで検索

```powershell
# Step 1: スキャン
python backend/scanner.py

# Step 2: インデックス化
python backend/indexer.py

# Step 3: 検索
python backend/query.py "avi"
python backend/query.py "flac"
```

### Phase 2：Web UIで検索

```powershell
# Web UIサーバー起動
python -m backend.main

# ブラウザで開く
# http://127.0.0.1:8000
```

### Phase 2：文字起こし（単体実行）

```powershell
python backend/transcriber.py "D:/music/sample.flac"
```

### Phase 2：画像認識（単体実行）

```powershell
python backend/vision.py "D:/images/photo.jpg"
```

---

## 🔍 各モジュール説明

### `scanner.py`
- 指定フォルダを再帰走査
- 対象拡張子のみ抽出
- パスはWindowsバックスラッシュに正規化して保存

### `indexer.py`
- `metadata.json`を読み込みベクトルDB（ChromaDB）に登録
- `__main__`実行時は`data/raw/metadata.json`を使用

### `query.py`
- ChromaDBから読み取り専用で検索
- 書き込みは一切行わない（indexer.pyのみが書き込み）

### `transcriber.py`（Phase 2）
- faster-whisper（large-v3）で音声・動画を文字起こし
- GPU使用（CUDA）で高速処理
- 日本語デフォルト、自動言語検出対応

### `vision.py`（Phase 2）
- LLaVA:13b（Ollama経由）で画像内容を説明
- 日本語で出力
- 「見えているものだけを説明」する設計（推測しない）

### `main.py`（Phase 2）
- FastAPI Web UIサーバー
- 検索API：`GET /api/search?q=<クエリ>`
- ファイルオープンAPI：`POST /api/open?path=<パス>`

---

## ⚠️ 既知の問題と対処

### `\t`パス問題
`config.yaml`の`root_path`に`\t`や`\n`を含む文字列を書くとタブ・改行に変換される。
**対処**：`root_path: "D:/"` のようにスラッシュ区切りで記述する。

### ChromaDBのtelemetry
起動時に`Anonymized telemetry enabled`と表示される。
**対処**：環境変数 `ANONYMIZED_TELEMETRY=False` を設定。

### Whisper初回起動
初回実行時にlarge-v3モデル（約3GB）をHuggingFaceからダウンロードする。
**対処**：`HF_HOME`環境変数で保存先を変更可能。

---

## 🔧 トラブルシューティング

### `cublas64_12.dll` が見つからない
CUDA 12.4のPATHが通っていない。

```powershell
$env:PATH += ";C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4\bin"
```

### Ollamaに接続できない
タスクトレイのOllamaアイコンを確認。起動していない場合はスタートメニューから起動。

```powershell
curl http://localhost:11434  # "Ollama is running" と返れば正常
```

### インデックスが古い結果を返す
```powershell
Remove-Item -Recurse -Force data\index
Remove-Item -Force data\raw\metadata.json
python backend/scanner.py
python backend/indexer.py
```

---

## 📋 設計原則

### ❌ 禁止事項
- LLM による推測・判断・断定
- 実ファイルのGitコミット
- 根拠なしの回答

### ✅ 必須事項
- すべての回答に`path`と`source_type`を含める
- 見つからない場合は明言する
- 抽出失敗時も落ちない（ログに記録）
- GitHub公開時に個人データを含まない

---

## 📝 ライセンス

MIT License

---

**質問や機能リクエストはIssueで！**
