"""
ユーティリティ関数
エラーハンドリング、ログ設定、JSON解析などの共通機能
"""
import json
import time
import logging
from typing import Any, Dict, Optional, List
import json as _json
from config import Config
from openai import OpenAI
from config import Config


# ==================== ログ設定 ====================
def setup_logger():
    """ログ設定を初期化"""
    # ログディレクトリ作成
    Config.LOG_DIR.mkdir(exist_ok=True)
    
    # ロガー設定
    logger = logging.getLogger(__name__)
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))
    
    # ハンドラーが既に設定されている場合はスキップ
    if logger.handlers:
        return logger
    
    # ファイルハンドラー
    file_handler = logging.FileHandler(
        Config.LOG_DIR / Config.LOG_FILE,
        encoding='utf-8'
    )
    file_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
    
    # コンソールハンドラー
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(Config.LOG_FORMAT))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger


logger = setup_logger()


def save_config_snapshot(version: str = "v2.0") -> None:
    """
    現在の Config 設定をログディレクトリに JSON として保存する。
    """
    try:
        cfg = Config.get_summary()
        # include token-related settings for traceability
        cfg.update({
            'MAX_TOKENS_LAYER2': Config.MAX_TOKENS_LAYER2,
            'MAX_TOKENS_LAYER3': Config.MAX_TOKENS_LAYER3,
            'TECH_DEFAULT_COUNT': Config.TECH_DEFAULT_COUNT,
            'PROMPT_FIELD_MAX_CHARS': getattr(Config, 'PROMPT_FIELD_MAX_CHARS', None)
        })
        path = Config.LOG_DIR / f"config_snapshot_{version}.json"
        with open(path, 'w', encoding='utf-8') as fh:
            fh.write(_json.dumps(cfg, ensure_ascii=False, indent=2))
        logger.info(f"Config snapshot saved: {path}")
    except Exception as e:
        logger.warning(f"Config snapshot の保存に失敗しました: {str(e)}")


# ==================== OpenAI API呼び出し ====================
def call_openai_with_retry(
    prompt: str,
    temperature: float,
    max_completion_tokens: int,
    max_retries: int = None
) -> str:
    """
    OpenAI APIをリトライ機能付きで呼び出し
    
    Args:
        prompt: プロンプト
        temperature: temperature値
        max_completion_tokens: 最大トークン数
        max_retries: 最大リトライ回数
        
    Returns:
        LLMの応答テキスト
        
    Raises:
        Exception: API呼び出しが全て失敗した場合
    """
    if max_retries is None:
        max_retries = Config.MAX_RETRIES
    
    client = OpenAI(api_key=Config.OPENAI_API_KEY)
    
    for attempt in range(max_retries):
        try:
            logger.info(f"OpenAI API呼び出し開始（試行 {attempt + 1}/{max_retries}）")
            
            # 強制的にJSONのみを返すようにシステムメッセージを強化
            system_msg = (
                "あなたは採用コンサルタントです。出力は厳密にJSONのみとし、"
                "説明文・マークダウン・注釈を一切含めないでください。\n"
                "必ず次の形式のJSONだけを返してください。例:\n"
                '{"求人票名":"...","役割":"...","業務プロセス":"...","対象製品":"...","ステークホルダー":"...","使用技術":"..."}'
            )

            response = client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_completion_tokens=max_completion_tokens
            )
            
            # gpt-4o特有のエラーハンドリング（例: モデル非対応のパラメータ）
            if "gpt-4o" in Config.OPENAI_MODEL:
                logger.warning("gpt-4oモデルを使用中: 特定のパラメータに注意してください")
            
            result = response.choices[0].message.content
            # トークン使用量が返ってくる場合はログに出力
            try:
                usage = response.usage if hasattr(response, 'usage') else response.get('usage', None)
            except Exception:
                usage = None

            if usage:
                try:
                    p_t = usage.get('prompt_tokens') if isinstance(usage, dict) else getattr(usage, 'prompt_tokens', None)
                    c_t = usage.get('completion_tokens') if isinstance(usage, dict) else getattr(usage, 'completion_tokens', None)
                    t_t = usage.get('total_tokens') if isinstance(usage, dict) else getattr(usage, 'total_tokens', None)
                except Exception:
                    p_t = c_t = t_t = None
                logger.info(f"OpenAI API呼び出し成功（応答文字数: {len(result)}）。usage: prompt={p_t}, completion={c_t}, total={t_t}")
                # 併せて logs に詳細保存（1行JSON）
                try:
                    d = {
                        'model': Config.OPENAI_MODEL,
                        'prompt_len': len(prompt),
                        'prompt_tokens': p_t,
                        'completion_tokens': c_t,
                        'total_tokens': t_t
                    }
                except Exception:
                    d = None
                try:
                    if d:
                        # Ensure log directory exists, then append to the token usage file
                        Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
                        token_log_path = Config.LOG_DIR / 'token_usage.log'
                        with open(token_log_path, 'a', encoding='utf-8') as fh:
                            fh.write(_json.dumps(d, ensure_ascii=False) + "\n")
                except Exception:
                    logger.debug("トークン使用ログの書き込みに失敗しました")
            else:
                logger.info(f"OpenAI API呼び出し成功（応答文字数: {len(result)}）")

            return result
            
        except Exception as e:
            error_msg = str(e)
            
            # レート制限エラーの処理
            if "rate_limit" in error_msg.lower():
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数バックオフ
                    logger.warning(f"レート制限発生。{wait_time}秒後にリトライします")
                    time.sleep(wait_time)
                    continue
                else:
                    logger.error("レート制限により処理を中断しました")
                    raise Exception("OpenAI APIのレート制限により処理を中断しました")
            
            # その他のAPIエラー
            if attempt < max_retries - 1:
                logger.warning(f"API エラー: {error_msg}。リトライします...")
                time.sleep(Config.RETRY_DELAY)
                continue
            else:
                logger.error(f"OpenAI APIエラー: {error_msg}")
                raise Exception(f"OpenAI APIエラー: {error_msg}")
    
    raise Exception("予期しないエラー: 最大リトライ回数に到達しました")


def call_openai_flex(
    prompt: str,
    temperature: float,
    max_completion_tokens: int,
    system_message: str,
    max_retries: int = None,
) -> str:
    """
    柔軟なシステムメッセージを許可するOpenAI呼び出しラッパー
    """
    if max_retries is None:
        max_retries = Config.MAX_RETRIES

    client = OpenAI(api_key=Config.OPENAI_API_KEY)

    for attempt in range(max_retries):
        try:
            logger.info(f"OpenAI API (flex) 呼び出し開始（試行 {attempt + 1}/{max_retries}）")

            response = client.chat.completions.create(
                model=Config.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_completion_tokens=max_completion_tokens
            )

            result = response.choices[0].message.content
            # usage があればログ
            try:
                usage = response.usage if hasattr(response, 'usage') else response.get('usage', None)
            except Exception:
                usage = None

            if usage:
                try:
                    p_t = usage.get('prompt_tokens') if isinstance(usage, dict) else getattr(usage, 'prompt_tokens', None)
                    c_t = usage.get('completion_tokens') if isinstance(usage, dict) else getattr(usage, 'completion_tokens', None)
                    t_t = usage.get('total_tokens') if isinstance(usage, dict) else getattr(usage, 'total_tokens', None)
                except Exception:
                    p_t = c_t = t_t = None
                logger.info(f"OpenAI API (flex) 呼び出し成功（応答文字数: {len(result)}）。usage: prompt={p_t}, completion={c_t}, total={t_t}")
                try:
                    d = {
                        'model': Config.OPENAI_MODEL,
                        'prompt_len': len(prompt),
                        'prompt_tokens': p_t,
                        'completion_tokens': c_t,
                        'total_tokens': t_t,
                        'flex': True
                    }
                    Config.LOG_DIR.mkdir(parents=True, exist_ok=True)
                    token_log_path = Config.LOG_DIR / 'token_usage.log'
                    with open(token_log_path, 'a', encoding='utf-8') as fh:
                        fh.write(_json.dumps(d, ensure_ascii=False) + "\n")
                except Exception:
                    logger.debug("トークン使用ログの書き込みに失敗しました(flex)")
            else:
                logger.info(f"OpenAI API (flex) 呼び出し成功（応答文字数: {len(result)}）")

            return result

        except Exception as e:
            error_msg = str(e)
            if attempt < max_retries - 1:
                logger.warning(f"API (flex) エラー: {error_msg}。リトライします...")
                time.sleep(Config.RETRY_DELAY)
                continue
            else:
                logger.error(f"OpenAI API (flex) エラー: {error_msg}")
                raise

    raise Exception("予期しないエラー: 最大リトライ回数に到達しました")


def _convert_table_to_table_data(obj):
    """
    LLM出力中のすべての 'table' キーを再帰的に 'table_data' に変換します。
    - 副作用を避けるため、新しいオブジェクトを返します。
    - dict, list を再帰的に巡回します。
    - 同じレベルに既に 'table_data' が存在する場合は変換を行いません（上書き防止）。
    """
    # dict を再帰的に処理
    if isinstance(obj, dict):
        # if this dict already contains 'table_data', prefer to keep it as-is
        has_table_data = "table_data" in obj
        new_obj = {}
        for k, v in obj.items():
            new_key = k
            if k == "table" and not has_table_data:
                new_key = "table_data"
            new_obj[new_key] = _convert_table_to_table_data(v)
        return new_obj

    # list の場合、各要素を変換
    if isinstance(obj, list):
        return [_convert_table_to_table_data(x) for x in obj]

    # それ以外はそのまま返す（数値/文字列/Noneなど）
    return obj

# ==================== JSON解析 ====================
def parse_json_with_retry(response_text: str, max_retries: int = 3) -> Dict[str, Any]:
    """
    JSON解析（失敗時は再試行）
    
    Args:
        response_text: JSON文字列
        max_retries: 最大リトライ回数
        
    Returns:
        パース済みのJSON（辞書型）
        
    Raises:
        Exception: JSON解析に失敗した場合
    """
    original_text = response_text
    
    for attempt in range(max_retries):
        try:
            logger.info(f"JSON解析開始（試行 {attempt + 1}/{max_retries}）")
            result = json.loads(response_text)
            result = _convert_table_to_table_data(result)
            logger.info("JSON解析成功")
            return result
            
        except json.JSONDecodeError as e:
            # ========== 追加箇所（ここから） ==========
            # Extra dataエラーの場合、最初のJSONオブジェクトのみを抽出
            if "Extra data" in str(e):
                try:
                    # JSONデコーダを使用して最初のオブジェクトを抽出
                    decoder = json.JSONDecoder()
                    result, idx = decoder.raw_decode(response_text)
                    result = _convert_table_to_table_data(result)
                    logger.info(f"JSON解析成功（最初のオブジェクトのみ抽出、位置: {idx}）")
                    return result
                except Exception as extract_error:
                    logger.warning(f"最初のJSONオブジェクト抽出に失敗: {str(extract_error)}")
            # ========== 追加箇所（ここまで） ==========
  
            if attempt < max_retries - 1:
                # マークダウンコードブロック除去を試みる
                cleaned = response_text.strip()
                
                # ```json ... ``` 除去
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                elif cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                    
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                
                response_text = cleaned.strip()
                
                logger.warning(f"JSON解析失敗。クリーニング後に再試行します")
                continue
            else:
                logger.error(f"JSON解析に失敗しました: {str(e)}")
                logger.error(f"応答内容: {response_text}")  # 応答内容をログに記録
                # 最後の手段: 応答中の最初の'{'から対応する閉じ括弧までを抽出して再試行
                try:
                    text = original_text
                    starts = [i for i, ch in enumerate(text) if ch == '{']
                    logger.warning("複数候補のJSON抽出を試行します")
                    for start in starts:
                        depth = 0
                        in_string = False
                        escape = False
                        for i in range(start, len(text)):
                            ch = text[i]
                            if ch == '\\' and not escape:
                                escape = True
                                continue
                            if ch == '"' and not escape:
                                in_string = not in_string
                            escape = False
                            if not in_string:
                                if ch == '{':
                                    depth += 1
                                elif ch == '}':
                                    depth -= 1
                                    if depth == 0:
                                        candidate = text[start:i+1]
                                        try:
                                            result = json.loads(candidate)
                                            result = _convert_table_to_table_data(result)
                                            logger.info("JSON解析成功（候補抽出後）")
                                            return result
                                        except Exception:
                                            # この候補で失敗したら次の開始位置を試す
                                            break
                        # 次の開始位置へ
                except Exception as e2:
                    logger.error(f"抽出後のJSON解析も失敗: {str(e2)}")

                raise Exception(
                    f"JSON解析に失敗しました: {str(e)}\n"
                    f"応答: {original_text[:200]}..."
                )
    
    raise Exception("予期しないエラー: JSON解析の最大リトライ回数に到達しました")


# ==================== バリデーション ====================
def validate_structured_data(data: Dict[str, Any]) -> bool:
    """
    レイヤー①の出力データをバリデーション
    
    Args:
        data: レイヤー①の出力データ
        
    Returns:
        バリデーション成功時はTrue
        
    Raises:
        ValueError: バリデーション失敗時
    """
    required_keys = [
        "求人票名", "役割", "業務プロセス", 
        "対象製品", "ステークホルダー", "使用技術"
    ]
    
    for key in required_keys:
        if key not in data or not data[key]:
            raise ValueError(f"必須項目 '{key}' が欠落しています")
    
    # 業務プロセスのフォーマットチェック（簡易版：改行と↓があればOK）
    bp_val = data["業務プロセス"]
    # If it's not a string, try to coerce
    if not isinstance(bp_val, str):
        try:
            # join lists/dicts into a string
            if isinstance(bp_val, list):
                bp_val = "\n↓\n".join([str(x).strip() for x in bp_val if x is not None])
            elif isinstance(bp_val, dict):
                bp_val = "\n↓\n".join([str(v).strip() for v in bp_val.values() if v is not None])
            else:
                bp_val = str(bp_val)
            data["業務プロセス"] = bp_val
            logger.info("業務プロセス: 非文字列を文字列に変換して正規化を試行")
        except Exception:
            pass

    # Now try simple normalization for common alternate separators
    if isinstance(bp_val, str) and ("\n" not in bp_val or "↓" not in bp_val):
        s = bp_val
        s2 = s.replace("->", "↓").replace("→", "↓").replace("=>", "↓")
        s2 = s2.replace("- ", "\n").replace("・", "\n")
        s2 = "\n".join([ln.strip() for ln in s2.splitlines() if ln.strip()])
        lines = [ln for ln in s2.splitlines() if ln]
        if len(lines) > 1:
            data["業務プロセス"] = "\n↓\n".join(lines)
            logger.info("業務プロセス: フォーマットを自動正規化しました（validate_structured_data）")
            bp_val = data["業務プロセス"]

    if "\n" not in bp_val or "↓" not in bp_val:
        raise ValueError(
            "業務プロセスが正しいフォーマットではありません。"
            "ステップを改行と「↓」で区切って記述してください。"
        )
    
    logger.info("構造化データのバリデーション成功")
    return True


def validate_comparison_data(data: Dict[str, Any]) -> bool:
    """
    レイヤー②の出力データをバリデーション
    
    Args:
        data: レイヤー②の出力データ
        
    Returns:
        バリデーション成功時はTrue
        
    Raises:
        ValueError: バリデーション失敗時
    """
    required_fields = [
        "content_b", "gap_analysis", "confidence_score", 
        "uncertain_aspects", "reasoning"
    ]
    
    for field in required_fields:
        if field not in data:
            raise ValueError(f"必須フィールド '{field}' が欠落しています")
    
    # スコア範囲チェック
    score = data["confidence_score"]
    if not isinstance(score, (int, float)) or not 0.0 <= score <= 1.0:
        raise ValueError(
            f"confidence_scoreは0.0-1.0の範囲の数値である必要があります（現在: {score}）"
        )
    
    logger.info(f"比較データのバリデーション成功（自信度: {score:.2f}）")
    return True


def validate_final_output(data: Dict[str, Any]) -> bool:
    """
    レイヤー③の出力データをバリデーション
    
    Args:
        data: レイヤー③の出力データ
        
    Returns:
        バリデーション成功時はTrue
        
    Raises:
        ValueError: バリデーション失敗時
    """
    # table_dataの構造チェック
    if "table_data" not in data:
        raise ValueError("table_dataが欠落しています")
    
    table_data = data["table_data"]
    
    # 7行未満の場合は自動補完（ヘッダー＋6項目）
    if len(table_data) < 7:
        logger.warning(f"table_dataが{len(table_data)}行しかありません。不足分を空行で補完します。")
        header = table_data[0] if table_data else ["", "", "", ""]
        # 空行テンプレート（列数はヘッダーに合わせる）
        empty_row = ["" for _ in range(len(header))]
        while len(table_data) < 7:
            table_data.append(empty_row.copy())
        data["table_data"] = table_data
    elif len(table_data) > 7:
        raise ValueError(
            f"table_dataは7行である必要があります（現在: {len(table_data)}行）"
        )
    
    if len(table_data[0]) != 4:  # 4列
        raise ValueError(
            f"table_dataは4列である必要があります（現在: {len(table_data[0])}列）"
        )
    
    # explanationsの完全性チェック
    if "explanations" not in data:
        raise ValueError("explanationsが欠落しています")
    
    required_items = [
        "求人票名", "役割", "業務プロセス", 
        "対象製品", "ステークホルダー", "使用技術"
    ]
    
    for item in required_items:
        if item not in data["explanations"]:
            raise ValueError(f"解説が欠落: {item}")
    
    logger.info("最終出力のバリデーション成功")
    return True


# ==================== その他ユーティリティ ====================
def format_confidence_score(score: float) -> tuple[str, str]:
    """
    自信度スコアを色分けとメッセージに変換
    
    Args:
        score: 自信度スコア（0.0-1.0）
        
    Returns:
        (色, メッセージ) のタプル
    """
    if score >= 0.8:
        return ("green", "高信頼")
    elif score >= 0.65:
        return ("blue", "標準")
    else:
        return ("orange", "要確認")


def normalize_table_data_structure(final_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    final_output の `table_data` を期待されるフォーマットに正規化します。

    - ヘッダーを固定（["項目名","内容A（求人票の記述）","内容B（実態推察）","ギャップ"]）
    - 行は期待順序の6項目（求人票名、役割、業務プロセス、対象製品、ステークホルダー、使用技術）で並べ替え／補完
    - 各行の列数を4に揃える（超過分は最後の列に結合、欠損は空文字で補完）
    - 可能な限り既存のセル内容は保持する

    受け取ったオブジェクトを変更して返します。
    """
    # CRITICAL: First ensure all 'table' keys are converted to 'table_data'
    final_output = _convert_table_to_table_data(final_output)
    
    expected_items = [
        "求人票名", "役割", "業務プロセス",
        "対象製品", "ステークホルダー", "使用技術"
    ]
    canonical_header = [
        "項目名", "内容A（求人票の記述）", "内容B（実態推察）", "ギャップ"
    ]

    # locate table_data
    table = None
    if isinstance(final_output, dict) and "table_data" in final_output:
        table = final_output.get("table_data")

    # if not found or invalid, try to find first plausible table in nested structure
    def _find_first_table(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "table_data" and isinstance(v, list):
                    return v
                res = _find_first_table(v)
                if res is not None:
                    return res
        elif isinstance(obj, list):
            for item in obj:
                res = _find_first_table(item)
                if res is not None:
                    return res
        return None

    if table is None:
        table = _find_first_table(final_output)

    if not table or not isinstance(table, list):
        # nothing to normalize
        return final_output

    # build a lookup by item name (first column)
    lookup = {}
    for row in table[1:]:
        try:
            key = (row[0] or "").strip()
            if key:
                lookup[key] = row
        except Exception:
            continue

    new_rows = [canonical_header]
    for item in expected_items:
        row = lookup.get(item)
        if row is None:
            # create empty row with item label in first column
            new_row = [item, "", "", ""]
        else:
            # ensure length 4
            if not isinstance(row, list):
                row = [str(row)]
            if len(row) < 4:
                row = row + [""] * (4 - len(row))
            elif len(row) > 4:
                # merge extra columns into last column as strings
                extras = row[3:]
                row = row[:3] + [" ".join([str(x) for x in extras if x is not None])]
            # ensure first col matches canonical item label
            row[0] = item
            new_row = row
        new_rows.append(new_row)

    # apply back to final_output at top-level if present, otherwise try to set the found table location
    if isinstance(final_output, dict) and "table_data" in final_output:
        final_output["table_data"] = new_rows
    else:
        # attempt to replace first found table in nested dict
        def _replace_first_table(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "table_data" and isinstance(v, list):
                        obj[k] = new_rows
                        return True
                    if _replace_first_table(v):
                        return True
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    if isinstance(item, list) and item is table:
                        obj[i] = new_rows
                        return True
                    if _replace_first_table(item):
                        return True
            return False

        _replace_first_table(final_output)

    return final_output


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    テキストを指定長に切り詰め
    
    Args:
        text: 元のテキスト
        max_length: 最大長
        
    Returns:
        切り詰められたテキスト
    """
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


# ==================== QAヘルパー ====================
def _trim_qa_history(history: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """
    会話履歴を上限に合わせてトリムする（アイテム数 & 合計文字数）
    """
    if not history:
        return []

    # 最新から切り取る
    max_items = Config.QA_HISTORY_MAX_ITEMS
    max_chars = Config.QA_HISTORY_MAX_CHARS

    trimmed = history[-max_items:]

    # 文字数が多ければ先頭から削る
    total = sum(len(_json.dumps(item, ensure_ascii=False)) for item in trimmed)
    while total > max_chars and trimmed:
        trimmed.pop(0)
        total = sum(len(_json.dumps(item, ensure_ascii=False)) for item in trimmed)

    return trimmed


def answer_question(structured_data: Dict[str, Any], question: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """
    構造化データを参照して質問に回答する。会話履歴を渡すと文脈を維持する。

    Args:
        structured_data: layer1~3で生成された最終出力（辞書）
        question: ユーザーの質問（日本語）
        history: 既存のQA履歴（{'q':..., 'a':...'} のリスト）

    Returns:
        {'answer': str, 'updated_history': List[...]} を返す
    """
    if history is None:
        history = []

    # 履歴をトリム
    history = _trim_qa_history(history)

    # コンテキスト生成（構造化データをJSONで渡す）
    try:
        context_json = _json.dumps(structured_data, ensure_ascii=False)
    except Exception:
        context_json = str(structured_data)

    # プロンプト作成
    system_msg = (
        "あなたは採用領域に詳しいアシスタントです。以下の提供コンテキストを参照して、"
        "日本語で簡潔に答えてください。必ず根拠（参照した項目名）を一言で示してください。"
    )

    # 履歴を会話文として整形
    history_text = ""
    if history:
        pairs = []
        for turn in history:
            q = turn.get('q', '')
            a = turn.get('a', '')
            pairs.append(f"Q: {q}\nA: {a}")
        history_text = "\n\n".join(pairs)

    user_prompt = (
        f"CONTEXT_JSON:\n{context_json}\n\n"
        f"HISTORY:\n{history_text}\n\n"
        f"QUESTION:\n{question}\n\n"
        "---\n"
        "制約: 回答は日本語で簡潔に。長くても2000文字以内。不要な注釈やコードブロックは付けない。"
    )

    # LLM 呼び出し
    # QAではプレーンテキスト応答を期待するため、柔軟なシステムメッセージを使用
    qa_system = (
        "あなたは採用分野に詳しいアシスタントです。以下のCONTEXT_JSONと履歴を参照し、"
        "日本語で簡潔に根拠を一言添えて回答してください。不要なJSONやコードブロックは出力しないでください。"
    )

    try:
        reply = call_openai_flex(
            prompt=user_prompt,
            temperature=0.0,
            max_completion_tokens=1500,
            system_message=qa_system
        )
        answer = reply.strip()

    except Exception as e:
        logger.error(f"QA 応答取得でエラー: {str(e)}")
        raise

    # 履歴に追加
    new_entry = {'q': question, 'a': answer}
    history.append(new_entry)
    history = _trim_qa_history(history)

    return {'answer': answer, 'updated_history': history}
