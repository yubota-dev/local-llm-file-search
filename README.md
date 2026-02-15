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

メタデータと付随テキストを文章化し、ベクトルDB に保存します。

### ステップ 3: 検索クエリ実行

```bash
python backend/query.py "artist:Adele genre:Pop"
```

検索条件に一致・近いファイル候補を根拠付きで提示します。

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
**Phase 1: ファイル一覧のみ、展開なし**
- アーカイブ内部のファイル一覧を取得（展開しない）
- ファイル名、サイズ情報をインデックス化
- ディレクトリ構造の把握
- パストラバーサル検出（安全対策）
- **重要**: ファイルの抽出（解凍）はPhase 1では一切行わない
- **重要**: エントリ数・サイズ制限はPhase 1 safeguard（容量管理・爆弾対策）

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

### `query.py` - 読み取り専用検索モジュール

**Architecture: Phase 1 Read-Only Design**
- ✅ Chroma コレクションから読み取り検索のみ
- ❌ データベースへの書き込みはなし（indexer.py のみが書き込み）
- 検索ごとに DB が成長しない設計

実行方式：
- `MediaSearchQuery` クラスで Chroma コレクションに直接接続
- `indexer.py` で事前に索引を作成しておく必要あり
- 検索は `collection.query()` のみ（読み取り）
- 見つからない場合は明確に「Index not found」を報告

---

## ⚠️ Phase 1 の仕様と制限（重要）

### ✅ Phase 1 で対応すること

| 対象情報 | 説明 |
|---------|------|
| **ファイル名** | 検索入力に含まれる語で一致ファイルを検出 |
| **フォルダ名** | 検索入力に含まれる語で一致フォルダを検出 |
| **メタデータ** | FFprobe / Pillow で抽出した duration, resolution, artist, codec など |
| **付随テキスト** | 字幕（.srt/.vtt/.ass）、メモ（.txt/.md）、メタ（.nfo/.json/.xml） |
| **アーカイブ一覧** | 圧縮ファイル内部の「ファイル名・サイズ」のみ（展開しない） |

### ❌ Phase 1 では実装しないもの

| 項目 | 理由 |
|------|------|
| **ファイルの内容解析** | Vision（画像認識）・音声認識・動画内容解析は未対応 |
| **抽象検索** | 「雰囲気」「印象」「スタイル」などのイメージ検索は未対応 |
| **LLMによる推測・判断** | 推測や断定をしない（根拠付き候補提示のみ） |
| **アーカイブファイル抽出** | 圧縮ファイルの展開・内容抽出は Phase 2 以降 |
| **アーカイブ内検索** | 圧縮ファイル内部のファイル検索は Phase 2 以降 |

### 📦 アーカイブ（圧縮ファイル）に関する Phase 1 の制限

**Phase 1では以下のみ実行：**
- ✅ ファイル一覧の取得（ファイル名・サイズ情報）
- ✅ フォルダ構造の把握
- ✅ セキュリティ検査（パストラバーサル検出）
- ✅ 容量監視（エントリ数・合計サイズ制限）

**Phase 1では以下は実行しない：**
- ❌ ファイルの実際の解凍・展開
- ❌ アーカイブ内部ファイルの内容抽出
- ❌ 圧縮ファイル内部の検索機能
- ❌ マルウェア検査などの深い内容検査

**理由：** 安全性とPhase分離の厳守。展開時のリスク（爆弾ファイル、パストトラバーサル）は Phase 2+ で慎重に検討。

### 🎯 Phase 1 の LLM の役割

- ✅ **検索結果の根拠を説明** → 「ファイル名に『xxx』が含まれる」
- ✅ **複数候補をすべて提示** → 推測せず、一致・近いものすべて
- ✅ **見つからない場合は明言** → 「該当ファイルが見つかりません」
- ❌ **推測や判断をしない** → 「この画像は〇〇っぽい」と言わない
- ❌ **内容を想像しない** → ファイル名以外から意味を推測しない

### 💡 将来の拡張性

Phase 1 の設計は以下を意識しています：

- メタデータの **文章化・ベクトル化** が可能 → 将来、意味的検索対応
- 各情報に **source_type を明記** → 根拠の出所が明確
- **LLMが候補提示のみ** → 将来、推論機能を追加可能

---

## 📊 検索入力の例（Phase 1）

### ✅ Phase 1 で対応できる入力

```
artist:Adele
resolution:1920x1080
duration:>60min
subtitle
"filename:sample"
```

### ❌ Phase 1 では対応できない入力

```
悲しい雰囲気の音楽を探して  （😢 感情推測）
4K画質の風景写真を探して     （🏞️  内容認識）
落ち着いた配色の画像を探して （🎨 ビジュアル解析）
```

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

## ✅ Phase 1 完了宣言

このプロジェクトの **Phase 1** は **設計・実装・文書化** が完了しました。

### Phase 1 の成果物

- ✅ メディアファイル走査エンジン（中身解析なし）
- ✅ メタデータ抽出（FFprobe, Pillow, mutagen）
- ✅ 付随テキスト索引化（字幕・メモ・メタ）
- ✅ アーカイブ一覧取得（展開なし）
- ✅ ベクトルDB インデックス化
- ✅ 根拠付きLLM統合検索（推測禁止）

### Phase 1 の責務

| 責務 | 実装状況 |
|------|---------|
| ファイル中身解析をしない | ✅ 完全に実装 |
| ファイル名・フォルダ名・メタ・テキストのみ搜索対象 | ✅ 完全に実装 |
| LLM は推測・判断・断定をしない | ✅ 完全に実装 |
| 根拠を明示して候補を返す | ✅ 完全に実装 |
| コードに Phase 1 制約コメントを明記 | ✅ 完全に実装 |

### Phase 2 への扉を開いたまま

Phase 1 は以下を意識して設計、後続フェーズで容易に拡張可能：

- メタデータの文章化・ベクトル化構造
- source_type による出所管理
- LLM が「候補提示のみ」の前提フレームワーク

**Phase 2 で可能になること（実装予定なし）：**
- Vision API による画像認識
- Speech-to-Text による文字起こし
- 抽象検索（雰囲気・イメージ検索）
- アーカイブ展開・内部検索

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
