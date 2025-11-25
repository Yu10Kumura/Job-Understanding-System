"""
修正依頼処理
自然言語による修正指示を解釈し、該当項目を差分修正
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional
from config import Config
from utils import (
    call_openai_with_retry,
    parse_json_with_retry,
    logger
)
import re


def _build_modification_prompt(
    current_output: Dict[str, Any],
    user_request: str
) -> str:
    """
    修正依頼のプロンプトを構築
    
    Args:
        current_output: 現在の最終出力
        user_request: ユーザーからの修正依頼
        
    Returns:
        構築されたプロンプト
    """
    prompt = f"""
【現在の出力】
{json.dumps(current_output, ensure_ascii=False, indent=2)}

【修正依頼】
{user_request}

【タスク】
修正依頼に従い、該当箇所のみを修正してください。

【指示】
- 修正箇所を特定し、必要な変更を実施
- 他の項目はそのまま保持
- 修正理由を簡潔に記録

【出力形式】
以下のJSON形式で返してください。

{{
  "modified_output": {{...}},
  "changes_made": [{{"item": "", "reason": ""}}]
}}
"""
    return prompt


def _build_template_modification_prompt(
    current_output: Dict[str, Any],
    template_flags: Dict[str, Any]
) -> str:
    """
    テンプレートベースの修正プロンプトを構築する。

    template_flags は以下のキーを想定:
      - add_comments_for_a: bool
      - specialize_b_tech: bool
      - tech_count: int
      - tech_focus: str
      - reformat_b_newlines: bool
      - improve_gap_questions: bool
    """
    parts = []
    parts.append("以下は自動テンプレート修正です。現在の出力JSONを参照し、指定された変換のみを行ってください。")

    if template_flags.get("add_comments_for_a"):
        parts.append("1) A（求人票の原文）について: 各項目（求人票名, 役割, 業務プロセス, 対象製品, ステークホルダー, 使用技術）に対して、\n   - どの具体性が欠けているか（要点を1行ずつ、最大3箇条）を追加してください。現状のAの記載を変えずに、コメントフィールドとして追加してください。")

    if template_flags.get("specialize_b_tech"):
        tech_count = template_flags.get("tech_count") or Config.TECH_DEFAULT_COUNT
        tech_focus = template_flags.get("tech_focus") or Config.TECH_FOCUS_DEFAULT
        parts.append(
            f"2) B（推察された実態）の `使用技術` を改善してください:\n   - 現在の低専門度ツール（例: {', '.join(Config.TECH_BLACKLIST)}) は除外すること。\n   - {tech_focus} を考慮して、より専門性の高い技術/ツールを上位{tech_count}個列挙し、可能なら各技術に短い使用例(1行)を添えてください。\n   - 他のBの項目は保持しつつ、使用技術欄のみ差し替えてください."
        )

    if template_flags.get("reformat_b_newlines"):
        parts.append("3) Bの各フィールド（特に長文の説明）は、可読性向上のため適切に改行（段落化）してください。各段落は最大120文字程度で折り返してください。")

    if template_flags.get("improve_gap_questions"):
        parts.append("4) ギャップ項目内の『採用部門へのヒアリング項目』を、ギャップを埋めるために実際に役立つ具体的な質問に書き換えてください。各ギャップにつき3つの実務的な質問を示してください（誰に、何を、どのように確認すれば良いかが明確なもの）。")

    # 最終指示: JSON出力を期待
    parts.append(
        "出力フォーマット: JSONで返してください。フィールドは変更後の `modified_output` と `changes_made` を含め、`changes_made` は変更された項目ごとに{item, reason}の配列としてください。"
    )

    prompt = f"【現在の出力】\n{json.dumps(current_output, ensure_ascii=False, indent=2)}\n\n【要求】\n" + "\n\n".join(parts)
    return prompt


def handle_modification_request(
    current_output: Dict[str, Any],
    user_request: str,
    template_flags: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    修正依頼を処理
    
    Args:
        current_output: 現在の最終出力
        user_request: ユーザーからの修正依頼
        
    Returns:
        修正応答（modified_output, changes_made, timestampを含む）
        
    Raises:
        Exception: 修正処理に失敗した場合
    """
    logger.info("=" * 60)
    logger.info("修正依頼処理 開始")
    logger.info(f"修正依頼: {user_request[:100]}...")

    try:
        # フォーマット検証
        # 注意: ここではユーザーが入力した実際の改行文字を扱うため、
        # 正規表現は実際の改行や空白を許容するようにします。
        if "業務プロセス" in user_request:
            # 全角／半角の括弧とスラッシュに対応する
            pattern = re.compile(r".+[／/][(（].+[)）]\s*↓\s*.+", flags=re.DOTALL)
            if not pattern.search(user_request):
                raise ValueError(
                    "業務プロセスのフォーマットが正しくありません。期待される形式: 'プロセス／（アウトプット）\n↓\n...'"
                )

        # プロンプト構築
        if template_flags:
            prompt = _build_template_modification_prompt(current_output, template_flags)
        else:
            prompt = _build_modification_prompt(current_output, user_request)

        # LLM呼び出し
        response_text = call_openai_with_retry(
            prompt=prompt,
            temperature=0.2,  # 変換指示は低めで安定化
            max_tokens=Config.MAX_TOKENS_MODIFICATION
        )
        
        # JSON解析
        modification_response = parse_json_with_retry(response_text)

        # サーバ側で安全マージ: modified_output が元の `current_output` の `内容A` を
        # まるごと置き換えてしまうケースを防ぐ。ルール:
        # - 各行の項目名でマッチして、modified の 内容A が元の内容A を包含していなければ
        #   元の内容A を保持する（上書きしない）。
        try:
            orig = current_output
            mod = modification_response.get("modified_output", {})
            if orig and mod and isinstance(orig, dict) and isinstance(mod, dict):
                # table_data のマージを行う
                orig_table = orig.get('table_data')
                mod_table = mod.get('table_data')
                if orig_table and mod_table and isinstance(orig_table, list) and isinstance(mod_table, list):
                    # build map from item name to row for orig
                    orig_map = {row[0]: row for row in orig_table[1:]} if len(orig_table) > 1 else {}
                    mod_map = {row[0]: row for row in mod_table[1:]} if len(mod_table) > 1 else {}

                    # iterate through items present in orig_map
                    for item, orig_row in orig_map.items():
                        mod_row = mod_map.get(item)
                        if not mod_row:
                            continue
                        # 内容A index assumed 1
                        try:
                            orig_a = (orig_row[1] or "").strip()
                            mod_a = (mod_row[1] or "").strip()
                        except Exception:
                            continue

                        # Protect key fields from destructive replacement.
                        # Always preserve original '求人票名' and '役割' unless the user explicitly requested renaming.
                        if item in ("求人票名", "役割"):
                            if orig_a:
                                logger.info(f"保護: '{item}' は上書きされないよう元の値を保持します")
                                mod_row[1] = orig_a
                                continue

                        # If modified A does not include original A as substring and original A is non-empty,
                        # assume replacement is incorrect and restore original A (but keep any explicit parenthetical additions).
                        if orig_a and orig_a not in mod_a:
                            # attempt to preserve appended parenthetical from mod_a if present
                            # e.g., mod_a == "役職名（具体例: ...）" but orig_a == "求人票名" -> don't replace
                            # We'll prefer orig_a and if mod_a contains a parenthetical not present in orig_a, append it.
                            import re as _re
                            paren = ""
                            m = _re.search(r"（.+）$", mod_a)
                            if m:
                                paren = m.group(0)
                                if paren and paren not in orig_a:
                                    new_a = orig_a + paren
                                else:
                                    new_a = orig_a
                            else:
                                new_a = orig_a

                            # set back into mod_row so modified_output will contain corrected value
                            mod_row[1] = new_a

                    # reconstruct mod_table with header preserved
                    new_table = [mod_table[0]]
                    for row in mod_table[1:]:
                        new_table.append(row)
                    modification_response['modified_output']['table_data'] = new_table
        except Exception as e:
            logger.warning(f"修正応答マージ中に問題が発生しました: {str(e)}")

        # タイムスタンプ追加
        modification_response["timestamp"] = datetime.now().isoformat()
        
        # 変更内容をログ出力
        changes = modification_response.get("changes_made", [])
        logger.info(f"修正項目数: {len(changes)}")
        for change in changes:
            logger.info(f"  - {change.get('item')}: {change.get('reason')}")
        
        logger.info("修正依頼処理 完了")
        logger.info("=" * 60)
        
        return modification_response
        
    except Exception as e:
        logger.error(f"修正依頼処理でエラー発生: {str(e)}")
        raise Exception(f"修正依頼の処理に失敗しました: {str(e)}")
