"""
レイヤー①: 求人構造化
求人テキストから6項目を抽出し、構造化データを生成
"""
from typing import Dict, Any
from config import Config
from utils import (
    call_openai_with_retry,
    parse_json_with_retry,
    validate_structured_data,
    logger
)


def _build_layer1_prompt(job_text: str) -> str:
    """
    レイヤー①のプロンプトを構築
    
    Args:
        job_text: 求人テキスト
        
    Returns:
        構築されたプロンプト
    """
    prompt = f"""
以下の求人票から、6項目を【簡潔・要点のみ】で抽出してください。

【制約】
- 各項目は最大200文字・3文以内
- 求人票の文章をそのままコピペしない
- キーワード・箇条書きで簡潔に
- 冗長な説明や繰り返しは禁止
- 軽い補足説明はカッコ書きで可
- 技術項目以外は推測禁止

【求人票】
{job_text}

【抽出項目】
1. 求人票名：タイトルを簡潔に
2. 役割：役割・ポジションを要点のみ
3. 業務プロセス：業務内容を短いステップで（改行と「↓」で区切る）
4. 対象製品：製品・サービス名のみ
5. ステークホルダー：関係者を列挙（C=協力、R=報告、I=巻き込み）
6. 使用技術：明記技術・ツールをカテゴリ分け（※推察は明記）

【出力形式】
次のJSON形式のみで返答してください（他の文章・装飾・説明は禁止）。
{{
  "求人票名": "...",
  "役割": "...",
  "業務プロセス": "...",
  "対象製品": "...",
  "ステークホルダー": "...",
  "使用技術": "..."
}}
"""
    return prompt


def layer1_extract_structure(job_text: str) -> Dict[str, Any]:
    """
    レイヤー①: 求人テキストから構造化データを抽出
    
    Args:
        job_text: 求人テキスト
        
    Returns:
        構造化データ（6項目を含む辞書）
        
    Raises:
        Exception: 抽出に失敗した場合
    """
    logger.info("=" * 60)
    logger.info("レイヤー①: 求人構造化 開始")
    logger.info(f"入力テキスト長: {len(job_text)}文字")
    
    try:
        # プロンプト構築
        prompt = _build_layer1_prompt(job_text)
        
        # LLM呼び出し
        response_text = call_openai_with_retry(
            prompt=prompt,
            temperature=Config.TEMP_LAYER1,
            max_tokens=Config.MAX_TOKENS_LAYER1
        )
        
        # JSON解析
        structured_data = parse_json_with_retry(response_text)

        # 業務プロセスの正規化: モデルが配列や別区切りで返す場合に期待形式へ変換
        try:
            # デバッグ用: パース後のキー一覧と業務プロセスの存在確認
            logger.info(f"Parsed structured_data keys: {list(structured_data.keys())}")
            bp = structured_data.get("業務プロセス")
            logger.info(f"Raw 業務プロセス (type={type(bp)}). repr head: {repr(bp)[:300]}")

            # 配列で返ってきた場合は結合
            if isinstance(bp, list):
                structured_data["業務プロセス"] = "\n↓\n".join([str(x).strip() for x in bp if x is not None])
                logger.info("業務プロセス: list -> joined string with '\\n↓\\n'")

            # 辞書で返ってきた場合は値を順に結合
            elif isinstance(bp, dict):
                vals = [str(v).strip() for v in bp.values() if v is not None]
                structured_data["業務プロセス"] = "\n↓\n".join(vals)
                logger.info("業務プロセス: dict -> joined values into string")

            # 文字列だが↓が無い場合は類似の区切り文字を置換してみる
            elif isinstance(bp, str):
                s = bp.strip()
                if "↓" not in s:
                    # 改行があり、別の矢印文字やハイフンで区切られているケースを正規化
                    s = s.replace("->", "↓").replace("→", "↓").replace("=>", "↓")
                    # ハイフンや箇条書きを改行区切りに変換
                    s = s.replace("- ", "\n").replace("・", "\n")
                    # 連続改行を単一化
                    s = "\n".join([ln.strip() for ln in s.splitlines() if ln.strip()])
                    # 最後に各行を↓でつなげる
                    lines = [ln for ln in s.splitlines() if ln]
                    if len(lines) > 1:
                        structured_data["業務プロセス"] = "\n↓\n".join(lines)
                        logger.info("業務プロセス: string normalized into lines joined by '\\n↓\\n'")

            # 最終整形: すべての '↓' の前後が改行で囲まれるようにする
            try:
                bp2 = structured_data.get("業務プロセス")
                if isinstance(bp2, str):
                    s = bp2
                    # '←' といった別文字は触らない。まず '↓' の前後に確実に改行を入れる
                    s = s.replace('\r', '')
                    s = s.replace('\n\s*↓\s*\n', '\n↓\n')
                    # 保守的な置換: '文字↓' -> '文字\n↓' ; '↓文字' -> '↓\n文字'
                    s = s.replace('↓', '\n↓\n')
                    # 連続した改行を単一化
                    s = '\n'.join([ln for ln in s.splitlines() if ln.strip()])
                    # 複数連結による重複 '↓' の扱いを調整（↓が連続している場合は1つに）
                    s = s.replace('\n↓\n\n↓\n', '\n↓\n')
                    structured_data["業務プロセス"] = s
                    logger.info("業務プロセス: 最終正規化を適用しました")
            except Exception:
                logger.warning("業務プロセス: 最終正規化で例外発生しましたが継続します")

        except Exception as e:
            logger.warning(f"業務プロセス正規化中に例外発生: {str(e)}")

        # バリデーション
        validate_structured_data(structured_data)
        
        logger.info("レイヤー①: 求人構造化 完了")
        logger.info(f"抽出項目: {', '.join(structured_data.keys())}")
        logger.info("=" * 60)
        
        return structured_data
        
    except Exception as e:
        logger.error(f"レイヤー①でエラー発生: {str(e)}")
        if "業務プロセスが正しいフォーマットではありません" in str(e):
            raise Exception(
                "求人構造化に失敗しました: 業務プロセスのフォーマットが正しくありません。\n"
                "期待される形式: 'プロセス／（アウトプット）\\n↓\\n...'\n"
                "例:\n"
                "設計／（設計書）\\n↓\\n試作／（試作品）\\n↓\\n評価／（評価レポート）"
            )
        else:
            raise Exception(f"求人構造化に失敗しました: {str(e)}")
