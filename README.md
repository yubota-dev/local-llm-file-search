# Local LLM Media & Archive Search

自宅PCの指定ドライブにある **動画・画像・音楽・圧縮ファイルを索引化** し、  
「何がどこにあるか」「目的に合う候補はどれか」を検索できるシステム

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
local-llm-media-search/
├─ backend/
│  ├─ scanner.py           # ドライブ走査＆メディアファイル検出
│  ├─ meta_video_audio.py  # ffprobe による動画・音声メタ抽出
│  ├─ meta_image.py        # Pillow + EXIF で画像メタ抽出
│  ├─ meta_audio.py        # mutagen による音声タグ抽出
│  ├─ archive_list.py      # zip/7z/rar/tar の中身一覧取得
│  ├─ text_sources.py      # 字幕・メモ・メタテキスト抽出
│  ├─ chunker.py           # テキストチャンキング処理
│  ├─ indexer.py           # ベクトルDB へのインデックス化
│  └─ query.py             # LLM 統合検索クエリ処理
├─ config/
│  └─ config.yaml          # 設定ファイル
├─ data/
│  ├─ raw/                 # 実ファイル置き場（git管理外）
│  └─ index/               # ベクトルDBデータ
├─ .gitignore             # Git 除外設定
├─ requirements.txt       # Python依存関係
└─ README.md             # このファイル
```

---

## 🚀 セットアップ

### 前提条件

- **OS**: Windows 11
- **Python**: 3.9+ （仮想環境推奨）
- **Ollama**: ローカル実行（http://localhost:11434）
- **ffprobe** （オプション）: ffmpeg パッケージに含まれる
- **exiftool** （オプション）: EXIF 抽出用

### インストール手順

```bash
# 仮想環境の作成
python -m venv venv
venv\Scripts\activate

# 依存パッケージのインストール
pip install -r requirements.txt

# （オプション）ffmpeg のインストール（Windows）
# https://ffmpeg.org/download.html からダウンロード、PATH に追加

# （オプション）exiftool のインストール（Windows）
# https://exiftool.org からダウンロード、PATH に追加
```

### 設定

1. **config/config.yaml** を編集
   - `root_path` をスキャン対象ドライブに設定（例: `D:\\`）
   - Ollama モデル設定（デフォルト: `mistral`）

2. **Ollama の起動**
   ```bash
   ollama serve
   ```

3. **初回走査**
   ```bash
   python backend/scanner.py
   ```

---

## 📖 使用方法

### ステップ 1: メディア走査＆メタデータ抽出

```bash
python backend/scanner.py
```

指定ドライブから対象ファイルをスキャンし、メタデータを抽出します。

**出力**: `data/raw/metadata.json`

### ステップ 2: テキストチャンキング＆インデックス化

```bash
python backend/indexer.py
```

メタデータと付随テキストをベクトル化し、ベクトルDBに保存します。

### ステップ 3: 検索クエリ実行

```bash
python backend/query.py "4K resolution の 映画 を探して"
```

LLM がベクトル検索結果を基に、根拠付きで候補ファイルを提示します。

---

## 🔍 各モジュール説明

### `scanner.py`
- 指定フォルダを再帰走査
- 対象拡張子のみ抽出
- 共通メタ：`path`, `name`, `ext`, `size`, `mtime`
- 同名の字幕・メモ・メタファイルも自動紐づけ

### `meta_video_audio.py`
ffprobe で以下を取得：
- `duration`, `codec`, `bitrate`, `sample_rate`, `channels`
- `width`, `height`, `fps` （動画）
- `tags` （artist, title など）

### `meta_image.py`
Pillow で画像情報、EXIF で：
- 撮影日時、機種、向き、GPS（取得可能な範囲）

### `archive_list.py`
**展開しない** で中身を一覧化（Phase 1）：
- ファイル名、サイズ
- ディレクトリ構造
- パストラバーサル検出

### `text_sources.py`
テキスト抽出：
- 字幕 `.srt/.vtt/.ass` （全文）
- メタ `.nfo/.txt/.md/.json/.xml` （サイズ上限あり）
- 文字コード失敗時も続行

### `indexer.py`
インデックス化：
- メディアメタを文章化
- チャンキング処理
- ベクトルDB へ保存

### `query.py`
検索実行：
- LLM に質問を送信
- ベクトル検索で根拠を取得
- Path と source_type を必ず含める

---

## 📋 主要な制約＆ルール

### ❌ 禁止事項

- ❌ LLM による推測・判断
- ❌ 実ファイルの Git コミット
- ❌ Phase 1 での圧縮ファイル展開
- ❌ 根拠なしの回答

### ✅ 必須事項

- ✅ 抽出失敗時も落ちない（ログに記録）
- ✅ すべての回答に `path` と `source_type` を含める
- ✅ 見つからない場合は「見つかりません」と明言
- ✅ GitHub 公開時も個人データなし

---

## 📚 Phase 1 の対応範囲

### ✅ Phase 1 で実装

| タスク | 内容 |
|--------|------|
| メタデータ抽出 | ffprobe, Pillow, mutagen 使用 |
| テキスト抽出 | 字幕、メモ、メタファイル |
| アーカイブ一覧化 | 中身をリスト（展開しない） |
| ベクトル索引化 | Chroma/FAISS で埋め込み |
| 根拠付き検索 | LLM が文献を必ず引用 |

### ⏳ Phase 2 以降

| タスク | 内容 |
|--------|------|
| 文字起こし | 動画・音声の自動文字化 |
| 物体認識 | 画像の中身解析 |
| アーカイブ展開 | 圧縮ファイル内部の検索 |
| マルチモーダル | 画像 + テキスト複合検索 |

---

## 🔧 トラブルシューティング

### ffprobe が見つからない

```bash
# Windows: ffmpeg をダウンロード & PATH に追加
# または config.yaml で use_ffprobe: false に設定

# フォールバック処理で続行します
```

### Ollama に接続できない

```bash
# Ollama の起動確認
ollama serve

# モデルのダウンロード
ollama pull mistral
```

### 大量ファイルでメモリ不足

- `meta_audio.py`, `text_sources.py` でバッチ処理を追加
- `archive_list.py` でエントリ数上限 (`archive_max_entries`) を厳しくする
- チャンク化処理の最適化（Phase 2）

---

## 📝 ライセンス

MIT License

---

## 📌 注記

このプロジェクトは **個人のメディア管理** を目的としています。  
GitHub 公開時は、必ず個人ファイルが含まれていないことを確認してください。

**.gitignore** で以下が除外されます：

- `data/raw/**/*` （実ファイル）
- `data/index/` （ベクトルDB データ）
- `.env` ファイル

---

**質問や機能リクエストは Issue で！**
