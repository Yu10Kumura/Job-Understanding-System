# 採用リクルーター教育支援システム v2.0

新人採用リクルーターが求人票を深く理解するための教育資料を自動生成するシステムです。

## 🎯 主な機能

- ✅ 求人票の自動構造化（6項目抽出）
- ✅ 業界標準との自動比較（LLM知識 + 条件付きWeb検索）
- ✅ 新人向け解説文の自動生成
- ✅ CSV/TSV形式での出力
- ✅ 自然言語による修正依頼対応

## 📋 必要要件

- Python 3.9以上
- OpenAI APIキー（必須）
- SerpAPIキー（オプション：Web検索機能を使用する場合）

## 🚀 セットアップ手順

### 1. リポジトリのクローン

```bash
cd /Users/yutokumura/Desktop/Python/求人内容理解システム
```

### 2. 依存ライブラリのインストール

```bash
pip install -r requirements.txt
```

### 3. 環境変数の設定

プロジェクトルートに `config.env` ファイルを作成し、以下の内容を記載:

```env
# OpenAI API設定（必須）
OPENAI_API_KEY=sk-...

# SerpAPI設定（オプション）
SERPAPI_KEY=...
```

または、環境変数として直接設定:

```bash
export OPENAI_API_KEY="sk-..."
export SERPAPI_KEY="..."  # オプション
```

### 4. アプリケーションの起動

```bash
streamlit run streamlit_app.py
```

ブラウザが自動的に開き、`http://localhost:8501` でアプリケーションにアクセスできます。

## 📖 使い方

### 基本的な使い方

1. **求人情報を入力**
   - 左側のテキストエリアに求人票の内容を貼り付け
   - 右側に職種名を入力（例: 法人営業、バックエンドエンジニア）

2. **生成ボタンをクリック**
   - システムが自動的に3つのレイヤーで処理を実行
   - レイヤー①: 求人構造化
   - レイヤー②: 業界標準比較（条件付きWeb検索）
   - レイヤー③: 教育最適化

3. **結果の確認**
   - 品質スコア（自信度）を確認
   - 分析表を確認
   - 各項目の解説を展開して詳細を確認
   - 「この表の見方」を確認

4. **ダウンロード**
   - CSV形式またはTSV形式でダウンロード可能
   - ファイル名には職種名と日時が自動付与

5. **修正依頼（オプション）**
   - 結果に満足しない場合、自然言語で修正依頼
   - 例: "業務プロセスにテストフェーズを追加して"
   - 修正履歴は展開エリアで確認可能

### 入力例

```
【職種】法人営業
【業務内容】
- 新規顧客開拓
- 提案資料作成
- 商談・契約締結
- 既存顧客フォロー
【必須スキル】
- 営業経験3年以上
- Excel・PowerPoint使用経験
【歓迎スキル】
- SaaS製品の営業経験
- データ分析スキル
```

## ⚙️ システム設定

### パラメータ調整

`config.py` で以下のパラメータを調整できます:

```python
# Web検索発動の閾値（この値未満でWeb検索を実行）
CONFIDENCE_THRESHOLD = 0.65

# SerpAPIで取得する検索結果数
MAX_SEARCH_RESULTS = 5

# 検索結果から抽出する最大文字数
WEB_CONTEXT_MAX_CHARS = 800

# Temperature設定
TEMP_LAYER1 = 0.3  # レイヤー①
TEMP_LAYER2 = 0.4  # レイヤー②
TEMP_LAYER3 = 0.3  # レイヤー③

# トークン制限
MAX_TOKENS_LAYER1 = 2000
MAX_TOKENS_LAYER2 = 3000
MAX_TOKENS_LAYER3 = 3000
```

### ログ確認

ログは `logs/recruiter_system.log` に出力されます。

エラーが発生した場合は、このログファイルで詳細を確認してください。

## 📊 出力形式

### 表データの構成

| 項目名 | 内容A（求人要約） | 内容B（AI提起） | ギャップ（A vs B） |
|--------|------------------|----------------|-------------------|
| 求人票名 | ... | ... | ... |
| 役割 | ... | ... | ... |
| 業務プロセス | ... | ... | ... |
| 対象製品 | ... | ... | ... |
| ステークホルダー | ... | ... | ... |
| 使用技術 | ... | ... | ... |

### 各項目の説明

- **求人票名**: 職種名を簡潔に表現
- **役割**: この人が担う責任範囲
- **業務プロセス**: 「プロセス名／（アウトプット）」形式で列挙
- **対象製品**: 扱う商材・サービス
- **ステークホルダー**: 関わる部署・役職（RACI分類付き）
- **使用技術**: 明記されている技術 + 推察される技術

## 🔍 Web検索機能について

### 発動条件

自信度スコアが閾値（デフォルト: 0.65）未満の場合、自動的にWeb検索を実行します。

### 検索クエリ

1. `{職種名} 業務フロー 標準的な流れ`
2. `{職種名} 使用技術 ツール 最新`

### 効果

- 業界標準パターンの精度向上
- 最新の技術トレンド反映
- 自信度スコアの向上（通常 +0.15程度）

### SerpAPIが未設定の場合

- Web検索はスキップされますが、LLMの知識のみで処理を継続
- 機能は制限されますが、基本的な動作は可能

## 🐛 トラブルシューティング

### よくあるエラー

#### `OPENAI_API_KEYが設定されていません`

**原因**: OpenAI APIキーが環境変数に設定されていない

**解決方法**:
1. `config.env` ファイルを作成
2. `OPENAI_API_KEY=sk-...` を記載
3. または環境変数として `export OPENAI_API_KEY="sk-..."` を実行

#### `JSON解析に失敗しました`

**原因**: LLMの応答がJSON形式でない、またはフォーマットが不正

**解決方法**:
1. 自動的に3回までリトライされます
2. それでも失敗する場合は、ログファイルで応答内容を確認
3. 必要に応じてプロンプトを調整（`layer1.py`, `layer2.py`, `layer3.py`）

#### `SerpAPI接続エラー`

**原因**: SerpAPIキーが無効、またはネットワークエラー

**解決方法**:
1. SerpAPIキーが正しいか確認
2. ネットワーク接続を確認
3. SerpAPIを使用しない場合は、`SERPAPI_KEY` を未設定にしてもOK

### ログ確認方法

```bash
tail -f logs/recruiter_system.log
```

## 📂 ファイル構成

```
求人内容理解システム/
├── streamlit_app.py          # メインアプリケーション
├── config.py                 # 設定ファイル
├── utils.py                  # ユーティリティ関数
├── serpapi_utils.py          # SerpAPI連携
├── layer1.py                 # レイヤー①: 求人構造化
├── layer2.py                 # レイヤー②: 業界標準比較
├── layer3.py                 # レイヤー③: 教育最適化
├── modification.py           # 修正依頼処理
├── requirements.txt          # 依存ライブラリ
├── config.env.example        # 環境変数テンプレート
├── README.md                 # このファイル
├── .gitignore
├── .streamlit/
│   └── secrets.toml         # Streamlit Cloud用シークレット（ローカルでは不要）
├── logs/
│   └── recruiter_system.log # ログファイル
└── tests/
    └── (テストファイル)
```

## 🚢 デプロイ（Streamlit Cloud）

### 前提条件

✅ GitHubアカウント  
✅ OpenAI APIキー  
✅ SerpAPIキー（オプション）

### ステップ1: GitHubリポジトリ作成

```bash
# プロジェクトディレクトリに移動
cd /Users/yutokumura/Desktop/Python/求人内容理解システム

# Gitリポジトリ初期化
git init

# .gitignoreの確認（config.env, logs/ が除外されているか）
cat .gitignore

# 全ファイルをステージング
git add .

# コミット
git commit -m "Initial commit: 求人内容理解システム v3.0"

# GitHubで新規リポジトリ作成後、リモート追加
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# プッシュ
git branch -M main
git push -u origin main
```

### ステップ2: Streamlit Cloudでデプロイ

1. **Streamlit Cloudにサインイン**
   - https://share.streamlit.io/ にアクセス
   - GitHubアカウントでサインイン

2. **新しいアプリを作成**
   - 「New app」をクリック
   - 以下を選択：
     - **Repository**: `YOUR_USERNAME/YOUR_REPO_NAME`
     - **Branch**: `main`
     - **Main file path**: `streamlit_app.py`

3. **Secretsを設定**
   - 「Advanced settings」をクリック
   - 「Secrets」タブで以下を入力：

```toml
OPENAI_API_KEY = "sk-proj-..."
SERPAPI_API_KEY = "your-serpapi-key"
```

4. **デプロイ**
   - 「Deploy!」をクリック
   - 数分で公開URL（例: `https://your-app-name.streamlit.app`）が発行されます

### ステップ3: 動作確認

✅ アプリが起動する  
✅ 求人情報入力→生成が動作する  
✅ テーブル表示が正しい  
✅ CSVダウンロードが動作する

### 更新方法

```bash
# コードを修正後
git add .
git commit -m "Update: 機能改善"
git push origin main

# Streamlit Cloudが自動的に再デプロイします
```

### トラブルシューティング（デプロイ）

**エラー: `ModuleNotFoundError`**
- `requirements.txt` に必要なパッケージが記載されているか確認
- Streamlit Cloudでログを確認

**エラー: `OPENAI_API_KEY not found`**
- Secretsが正しく設定されているか確認
- キーの名前が `OPENAI_API_KEY` で完全一致しているか確認

**ログの確認**
- Streamlit Cloudのダッシュボード → アプリ選択 → 「Manage app」 → 「Logs」

## 📊 パフォーマンス指標

| 処理 | 目標時間 | 許容時間 |
|------|---------|---------|
| レイヤー① | 5秒 | 10秒 |
| レイヤー②（Web検索なし） | 8秒 | 15秒 |
| レイヤー②（Web検索あり） | 20秒 | 40秒 |
| レイヤー③ | 7秒 | 15秒 |
| **合計（検索なし）** | **20秒** | **40秒** |
| **合計（検索あり）** | **32秒** | **65秒** |

## 💰 コスト目安

| 項目 | 目標 | 備考 |
|------|------|------|
| OpenAI API（検索なし） | $0.10/件 | GPT-4使用時 |
| OpenAI API（検索あり） | $0.15/件 | GPT-4使用時 |
| SerpAPI | $0.005/件 | 2回検索時 |
| **合計（検索あり）** | **$0.155/件** | |

## 🤝 サポート

問題が発生した場合:

1. ログファイル（`logs/recruiter_system.log`）を確認
2. エラーメッセージを記録
3. 再現手順を整理

## 📝 ライセンス

このプロジェクトは内部使用を目的としています。

## 🔄 バージョン履歴

### v2.0 (2025-01-24)
- 初回リリース
- 条件付きWeb検索機能
- 自然言語修正依頼対応
- CSV/TSV出力
