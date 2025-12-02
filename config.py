"""
設定ファイル
環境変数、パラメータ設定、定数などを定義
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Streamlit Cloud対応: st.secretsが利用可能ならそちらを優先
try:
    import streamlit as st
    _USE_STREAMLIT_SECRETS = hasattr(st, 'secrets') and len(st.secrets) > 0
except (ImportError, RuntimeError):
    _USE_STREAMLIT_SECRETS = False

# config.envファイルを読み込み（`config.env` を優先し、なければ example を使用）
if not _USE_STREAMLIT_SECRETS:
    env_path = Path(__file__).parent / 'config.env'
    if not env_path.exists():
        env_path = Path(__file__).parent / 'config.env.example'
    
    if env_path.exists():
        load_dotenv(env_path)


class Config:
    """システム全体の設定を管理するクラス"""
    
    # ==================== LLM設定 ====================
    OPENAI_MODEL = "gpt-5-mini"
    
    # Streamlit Cloud対応: st.secretsから読み込み、なければ環境変数
    if _USE_STREAMLIT_SECRETS:
        try:
            import streamlit as st
            OPENAI_API_KEY = st.secrets.get("OPENAI_API_KEY", "")
        except Exception:
            OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    else:
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    
    # ==================== SerpAPI設定 ====================
    if _USE_STREAMLIT_SECRETS:
        try:
            import streamlit as st
            SERPAPI_KEY = st.secrets.get("SERPAPI_API_KEY", "")
        except Exception:
            SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
    else:
        SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
    
    # ==================== 処理パラメータ ====================
    # Web検索発動の閾値（この値未満の自信度でWeb検索を実行）
    CONFIDENCE_THRESHOLD = 0.65
    
    # SerpAPIで取得する検索結果数
    MAX_SEARCH_RESULTS = 5
    
    # 検索結果から抽出する最大文字数
    WEB_CONTEXT_MAX_CHARS = 3000
    # プロンプトに含める各フィールドの最大文字数（超過分は切り詰める）
    PROMPT_FIELD_MAX_CHARS = 3000
    
    # ==================== Temperature設定 ====================
    # 安定性のため、出力の揺らぎを抑える（temperature=0）
    TEMP_LAYER1 = 0.0  # レイヤー①: 構造化
    TEMP_LAYER2 = 0.0  # レイヤー②: 比較
    TEMP_LAYER3 = 0.0  # レイヤー③: 教育最適化
    
    # ==================== トークン制限 ====================
    MAX_TOKENS_LAYER1 = 2000
    MAX_TOKENS_LAYER2 = 2500  # Layer②: プロンプトが長いため出力を抑制（8192制限対策）
    MAX_TOKENS_LAYER3 = 3500  # Layer③: 表データ生成
    MAX_TOKENS_MODIFICATION = 3500

    # ==================== QAメモリ設定 ====================
    QA_HISTORY_MAX_ITEMS = 10       # セッションに保持するQAターン数
    QA_HISTORY_MAX_CHARS = 4000     # 会話履歴をこの文字数でトリムする

    # ==================== 技術フィルタ/テンプレート設定 ====================
    TECH_BLACKLIST = ["Teams", "PowerPoint", "Excel", "Word", "Slack"]
    TECH_DEFAULT_COUNT = 6  # Bの使用技術を何個程度に増やすか（デフォルト）
    TECH_FOCUS_DEFAULT = "auto"  # auto|infrastructure|backend|data|ml
    
    # ==================== リトライ設定 ====================
    MAX_RETRIES = 3
    RETRY_DELAY = 2  # 秒
    
    # ==================== ログ設定 ====================
    LOG_LEVEL = "INFO"
    LOG_FILE = "recruiter_system.log"
    LOG_FORMAT = '%(asctime)s [%(levelname)s] %(message)s'
    
    # ==================== ファイルパス ====================
    BASE_DIR = Path(__file__).parent
    LOG_DIR = BASE_DIR / "logs"
    
    @classmethod
    def validate(cls):
        """設定の妥当性をチェック"""
        errors = []
        
        if not cls.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEYが設定されていません")
        
        if not 0.0 <= cls.CONFIDENCE_THRESHOLD <= 1.0:
            errors.append(f"CONFIDENCE_THRESHOLDは0.0-1.0の範囲である必要があります（現在: {cls.CONFIDENCE_THRESHOLD}）")
        
        if cls.MAX_SEARCH_RESULTS < 1:
            errors.append(f"MAX_SEARCH_RESULTSは1以上である必要があります（現在: {cls.MAX_SEARCH_RESULTS}）")
        
        if errors:
            raise ValueError("\n".join(errors))
        
        return True
    
    @classmethod
    def get_summary(cls):
        """設定の概要を返す"""
        return {
            "モデル": cls.OPENAI_MODEL,
            "自信度閾値": cls.CONFIDENCE_THRESHOLD,
            "Web検索結果数": cls.MAX_SEARCH_RESULTS,
            "SerpAPI設定": "有効" if cls.SERPAPI_KEY else "無効",
        }
