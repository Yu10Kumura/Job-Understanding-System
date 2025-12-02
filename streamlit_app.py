"""
採用リクルーター教育支援システム v2.0
Streamlit UI
"""
import streamlit as st
import pandas as pd
from datetime import datetime
import traceback
import re
from html import escape

# 自作モジュールのインポート
from config import Config
from utils import format_confidence_score, logger, answer_question
from layer1 import layer1_extract_structure
from layer2 import layer2_build_comparison_smart
from layer3 import layer3_optimize_for_learning
from modification import handle_modification_request


# ==================== ページ設定 ====================
st.set_page_config(
    page_title="採用リクルーター教育支援システム",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)


# ==================== セッション状態初期化 ====================
def initialize_session_state():
    """セッション状態を初期化"""
    if 'output' not in st.session_state:
        st.session_state.output = None
    
    if 'modification_history' not in st.session_state:
        st.session_state.modification_history = []
    if 'qa_history' not in st.session_state:
        st.session_state.qa_history = []
    
    if 'generation_count' not in st.session_state:
        st.session_state.generation_count = 0


initialize_session_state()


# ==================== ヘッダー ====================
st.title("🎓 採用リクルータージョブ理解支援システム v4.0")
git commit -m "Update Streamlit app for deployment".0")
st.markdown("求人情報を貼り付けるだけで、ジョブ理解とヒアリング仮説を自動生成")
st.markdown("---")


# ==================== 環境設定チェック ====================
try:
    Config.validate()
except ValueError as e:
    st.error(f"⚠️ 環境設定エラー: {e}")
    st.info(
        "**セットアップ手順:**\n\n"
        "1. プロジェクトルートに `config.env` ファイルを作成\n"
        "2. 以下の内容を記載:\n"
        "```\n"
        "OPENAI_API_KEY=sk-...\n"
        "SERPAPI_KEY=...  # オプション\n"
        "```\n"
        "3. または環境変数として設定\n"
    )
    st.stop()


# ==================== メイン処理関数 ====================
def generate_full_output(job_text: str, job_category: str):
    """
    求人票から最終出力を生成
    
    Args:
        job_text: 求人テキスト
        job_category: 職種名
        
    Returns:
        最終出力データ
    """
    start_time = datetime.now()
    
    try:
        # プログレス表示
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # レイヤー① : 求人構造化
        status_text.text("⏳ レイヤー①: 求人情報を構造化しています...")
        progress_bar.progress(10)
        
        structured_data = layer1_extract_structure(job_text)
        progress_bar.progress(30)
        
        # レイヤー②: 業界標準比較
        status_text.text("⏳ レイヤー②: 業界標準と比較しています...")
        
        comparison_data = layer2_build_comparison_smart(structured_data, job_category)
        progress_bar.progress(60)
        
        # レイヤー③: 教育最適化
        status_text.text("⏳ レイヤー③: 教育資料を生成しています...")
        
        final_output = layer3_optimize_for_learning(comparison_data)
        progress_bar.progress(90)
        
        # 完了
        progress_bar.progress(100)
        status_text.text("✅ 生成完了!")
        
        # 処理時間計算
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"総処理時間: {elapsed_time:.2f}秒")
        
        # プログレス表示をクリア
        progress_bar.empty()
        status_text.empty()
        
        return final_output
        
    except Exception as e:
        logger.error(f"生成処理でエラー発生: {str(e)}")
        logger.error(traceback.format_exc())
        raise e


# ==================== 入力エリア ====================
st.subheader("📋 求人情報を入力してください")

col1, col2 = st.columns([3, 1])

with col1:
    job_text = st.text_area(
        "求人テキスト",
        height=200,
        placeholder="求人票の内容をここに貼り付けてください...\n\n例:\n【職種】法人営業\n【業務内容】\n- 新規顧客開拓\n- 提案資料作成\n...",
        help="求人票の全文を貼り付けてください"
    )

with col2:
    job_category = st.text_input(
        "職種名",
        value="法人営業",
        placeholder="例: 法人営業",
        help="職種名を入力してください（例: 法人営業、バックエンドエンジニア）"
    )

# 生成ボタン
generate_button = st.button(
    "🔥 生成",
    type="primary",
    disabled=(not job_text or not job_category),
    use_container_width=True
)

if generate_button:
    with st.spinner("処理中..."):
        try:
            output = generate_full_output(job_text, job_category)
            st.session_state.output = output
            st.session_state.generation_count += 1
            st.session_state.modification_history = []  # 履歴リセット
            st.success("✅ 生成が完了しました!")
            
        except Exception as e:
            st.error(f"❌ エラーが発生しました: {str(e)}")
            st.info("エラーの詳細はログファイルを確認してください")


# ==================== 結果表示エリア ====================
if st.session_state.output:
    st.markdown("---")
    st.subheader("📊 生成結果")
    
    output = st.session_state.output
    
    # 品質スコア表示
    col1, col2 = st.columns(2)
    
    with col1:
        score = output.get("confidence_score", 0.0)
        color, label = format_confidence_score(score)
        
        if color == "green":
            st.success(f"🎯 品質スコア: {score*100:.0f}% ({label})")
        elif color == "blue":
            st.info(f"🎯 品質スコア: {score*100:.0f}% ({label})")
        else:
            st.warning(f"🎯 品質スコア: {score*100:.0f}% ({label})")
    
    with col2:
        web_search = output.get("web_search_performed", False)
        if web_search:
            st.info("ℹ️ Web検索: 実行済み")
        else:
            st.info("ℹ️ Web検索: 未実行")
    
    # 表データ表示
    st.markdown("### 📋 分析表")
    
    table_data = output.get("table_data", [])
    if table_data and len(table_data) > 1:
        df = pd.DataFrame(table_data[1:], columns=table_data[0])
        
        # HTMLテーブルで表示（文字折り返し対応）
        st.markdown("""
        <style>
        .custom-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }
        .custom-table th {
            background-color: #f0f2f6;
            padding: 12px;
            text-align: left;
            border: 1px solid #ddd;
            font-weight: bold;
            position: sticky;
            top: 0;
            z-index: 10;
        }
        .custom-table td {
            padding: 12px;
            border: 1px solid #ddd;
            vertical-align: top;
            white-space: pre-wrap;
            word-wrap: break-word;
            max-width: 300px;
        }
        .custom-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .custom-table tr:hover {
            background-color: #f5f5f5;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # テーブルHTML生成
        html_table = '<table class="custom-table">'

        # ヘッダー
        html_table += '<thead><tr>'
        for col in table_data[0]:
            html_table += f'<th>{escape(str(col))}</th>'
        html_table += '</tr></thead>'

        # データ行
        a_comments = output.get('a_comments', {}) or {}
        headers = table_data[0]
        try:
            a_col_index = headers.index(next(h for h in headers if '内容A' in h))
        except Exception:
            a_col_index = 1

        html_table += '<tbody>'
        for row in table_data[1:]:
            html_table += '<tr>'
            item_name = row[0]
            for ci, cell in enumerate(row):
                cell_html = escape(str(cell)) if cell is not None else ''
                if ci == a_col_index:
                    comment = a_comments.get(item_name, '')
                    if comment:
                        short = (comment[:50] + '...') if len(comment) > 50 else comment
                        comment_html = f"<div class='a-comment'>{escape(short)}</div>"
                    else:
                        comment_html = ''
                    html_table += f'<td>{cell_html}{comment_html}</td>'
                else:
                    html_table += f'<td>{cell_html}</td>'
            html_table += '</tr>'
        html_table += '</tbody>'

        html_table += '</table>'

        # a_comments 用のスタイル
        st.markdown("""
        <style>
        .a-comment {
            color: #6c757d;
            font-size: 12px;
            margin-top: 6px;
        }
        </style>
        """, unsafe_allow_html=True)

        st.markdown(html_table, unsafe_allow_html=True)
    
    # 解説展開エリア
    with st.expander("📖 各項目の解説", expanded=False):
        explanations = output.get("explanations", {})
        
        for item, explanation in explanations.items():
            st.markdown(f"**{item}**")
            st.write(explanation)
            st.markdown("")
    
    # 表の見方展開エリア
    with st.expander("❓ この表の見方", expanded=False):
        how_to_read = output.get("how_to_read", "")
        st.write(how_to_read)
    
    # ダウンロードボタン
    st.markdown("### 💾 ダウンロード")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # CSV出力
        if table_data:
            df = pd.DataFrame(table_data[1:], columns=table_data[0])
            csv_data = df.to_csv(index=False).encode('utf-8-sig')  # BOM付きUTF-8
            
            st.download_button(
                label="📥 CSV形式でダウンロード",
                data=csv_data,
                file_name=f"求人分析_{job_category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
    
    with col2:
        # TSV出力
        if table_data:
            df = pd.DataFrame(table_data[1:], columns=table_data[0])
            tsv_data = df.to_csv(index=False, sep='\t').encode('utf-8-sig')
            
            st.download_button(
                label="📥 TSV形式でダウンロード",
                data=tsv_data,
                file_name=f"求人分析_{job_category}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.tsv",
                mime="text/tab-separated-values",
                use_container_width=True
            )
    
    # ==================== 修正依頼エリア ====================
    st.markdown("---")
    st.subheader("🔧 修正依頼")
    
    st.markdown("修正したい内容を自然な言葉で入力してください")
    
    modification_request = st.text_area(
        "修正内容",
        height=100,
        placeholder="例:\n設計／（設計書）\n↓\n試作／（試作品）\n↓\n評価／（評価レポート）",
        help="業務プロセスは以下の形式で記述してください:\nプロセス／（アウトプット）\n↓\n..."
    )

    # （テンプレートオプションはデフォルト化したため、UI上の選択肢は廃止されています）

    # リアルタイム検証は、ユーザーが「業務プロセス」に言及している場合のみ行う
    if modification_request and "業務プロセス" in modification_request:
        pattern = re.compile(r".+[／/][(（].+[)）]\s*↓\s*.+", flags=re.DOTALL)
        if not pattern.search(modification_request):
            # 警告表示に変更: ユーザーの一般的な日本語リクエストで赤エラーが出ないようにする
            st.warning(
                "（業務プロセス形式のヒント）業務プロセスを編集する場合は、次の形式を推奨します:\nプロセス／（アウトプット）\n↓\n...\n例:\n設計／（設計書）\n↓\n試作／（試作品）\n↓\n評価／（評価レポート)"
            )
    
    modify_button = st.button(
        "✏️ 修正実行",
        disabled=(not modification_request),
        use_container_width=True
    )
    
    if modify_button:
        with st.spinner("修正中..."):
            try:
                # テンプレートはデフォルトで初回出力に適用しているため、ここではフラグは渡しません
                template_flags = None

                modification_response = handle_modification_request(
                    st.session_state.output,
                    modification_request,
                    template_flags=template_flags
                )
                
                # 出力を更新
                st.session_state.output = modification_response["modified_output"]
                
                # 履歴に追加
                st.session_state.modification_history.append({
                    'request': modification_request,
                    'changes': modification_response.get('changes_made', []),
                    'timestamp': modification_response.get('timestamp', '')
                })
                
                st.success("✅ 修正が完了しました!")
                st.rerun()  # ページを再読み込み
                
            except Exception as e:
                st.error(f"❌ 修正処理でエラーが発生しました: {str(e)}")
                st.info("エラーの詳細はログファイルを確認してください")
    
    # 修正履歴展開エリア
    if st.session_state.modification_history:
        with st.expander("📝 修正履歴", expanded=False):
            for i, history in enumerate(reversed(st.session_state.modification_history), 1):
                st.markdown(f"**修正 {len(st.session_state.modification_history) - i + 1}**: {history['request'][:50]}...")
                
                changes = history.get('changes', [])
                for change in changes:
                    st.write(f"  - {change.get('item')}: {change.get('reason')}")
                
                timestamp = history.get('timestamp', '')
                if timestamp:
                    st.caption(f"実行時刻: {timestamp}")
                
                st.markdown("")

    # ==================== QA（質問応答）エリア ====================
    st.markdown("---")
    st.subheader("❓ 出力に基づくQA")
    st.markdown("生成結果を参照して質問してください。会話履歴はセッション内で最大保持されます。")

    qa_question = st.text_input(
        "質問を入力してください",
        placeholder="例: この求人で想定される主なステークホルダーは誰ですか？",
        key="qa_input"
    )

    qa_button = st.button("💬 質問する", disabled=(not qa_question), use_container_width=True)

    if qa_button:
        if not st.session_state.output:
            st.error("まず求人データを生成してください")
        else:
            with st.spinner("回答を取得しています..."):
                try:
                    res = answer_question(st.session_state.output, qa_question, st.session_state.qa_history)
                    answer = res.get('answer', '')
                    st.session_state.qa_history = res.get('updated_history', [])

                    st.markdown("**回答:**")
                    st.write(answer)

                    # 表示用に最近の数ターンを展開
                    if st.session_state.qa_history:
                        with st.expander("💾 QA 履歴（最近）", expanded=False):
                            for turn in reversed(st.session_state.qa_history[-Config.QA_HISTORY_MAX_ITEMS:]):
                                st.markdown(f"**Q:** {turn.get('q','')}\n\n**A:** {turn.get('a','')}")

                except Exception as e:
                    st.error(f"QA処理でエラーが発生しました: {str(e)}")
                    logger.error(traceback.format_exc())


# ==================== サイドバー（システム情報） ====================
with st.sidebar:
    st.header("⚙️ システム情報")
    
    st.markdown("**バージョン**: v2.0")
    st.markdown(f"**モデル**: {Config.OPENAI_MODEL}")
    
    # gpt-4oモデルに関する注意書きを追加
    if Config.OPENAI_MODEL == "gpt-4o":
        st.warning("gpt-4oモデルを使用中: このモデルは一部のAPIパラメータに非対応の可能性があります。")
    
    st.markdown(f"**自信度閾値**: {Config.CONFIDENCE_THRESHOLD}")
    st.markdown(f"**Web検索**: {'有効' if Config.SERPAPI_KEY else '無効'}")
    
    if st.session_state.generation_count > 0:
        st.markdown("---")
        st.metric("生成回数", st.session_state.generation_count)
        st.metric("修正回数", len(st.session_state.modification_history))
    
    st.markdown("---")
    st.markdown("**使い方**")
    st.markdown(
        "1. 求人票を貼り付け\n"
        "2. 職種名を入力\n"
        "3. 生成ボタンをクリック\n"
        "4. 結果を確認・ダウンロード\n"
        "5. 必要に応じて修正依頼"
    )
