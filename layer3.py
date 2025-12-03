"""
レイヤー③: 教育最適化
新人リクルーター向けに表形式データと解説を生成
"""
import json
from typing import Dict, Any
from config import Config
from utils import (
    call_openai_with_retry,
    parse_json_with_retry,
    validate_final_output,
    logger,
    normalize_table_data_structure
)


def _build_layer3_prompt(comparison_final: Dict[str, Any]) -> str:
    """
    レイヤー③のプロンプトを構築
    
    Args:
        comparison_final: レイヤー②の出力
        
    Returns:
        構築されたプロンプト
    """
    prompt = f"""
以下のデータを新人リクルーター向けに最適化してください。
新人は中学生レベルの知識でも理解できるようにしてください。

【データ】
{json.dumps(comparison_final, ensure_ascii=False, indent=2)}

【タスク】

1. **表形式データの生成**
   - 以下の列構成で2次元配列を作成:
     ["項目名", "内容A（求人票の記述）", "内容B（実態推察）", "ギャップ"]
   - 各行は8項目（求人票名、採用背景、役割、業務プロセス、対象製品、ステークホルダー、使用技術、バリューチェーン）
   - セル内の改行は保持（業務プロセスの「↓」「※」など）
   - ギャップセルには【差異】【不足情報】【採用部門へのヒアリング項目】の3要素を含める

2. **項目別解説の生成**
   - 各8項目について、中学生にも分かる一言解説を作成
   - 専門用語は噛み砕く
   - 「なぜこの項目が重要か」を説明
   - 具体例を入れる
   - 各解説は50-100文字程度

3. **表の見方ガイド**
   - この表をどう読むべきか、新人向けに説明
   - 各列の意味を説明:
     * 内容A: 求人票に書かれている文字面
     * 内容B: 実際の業務内容の推察（仮説）
     * ギャップ: AとBの差異、不足情報、確認すべきこと
   - 200-300文字程度

【解説の品質基準】
- 専門用語を使わない（または噛み砕く）
- 具体的な例を入れる
- 「〇〇とは〜です」という定義型より、「〇〇を見ると、〜が分かります」という実用型
- 新人が「なるほど！」と思える内容

【新規項目の説明】

**採用背景**
- 内容A: 「記載なし」と記載
- 内容B: 以下の観点から推察（200-300文字）:
  * 事業拡大・新規プロジェクト立ち上げなどの組織的背景
  * 技術トレンドや市場動向に基づく必要性
  * 既存チームの課題（人員不足、スキルギャップ、世代交代など）
  * 業界一般論に基づく採用動機
- ギャップ: 「推察のみ（求人票に記載なし）」と記載
- 解説: なぜこのポジションが今必要なのか、組織的背景を説明（50-100文字）

**バリューチェーン**
- 内容A: 「記載なし」と記載
- 内容B: 以下の観点から推察（200-300文字）:
  * 全社レベル: 企業全体の価値創造における役割
  * 事業レベル: 担当事業・部門における貢献
  * 業界レベル: 業界全体に対する価値提供
  * コアバリュー: この職種が提供する核心的価値
  * バリューチェーン上の位置: 上流/中流/下流のどこに位置するか
- ギャップ: 「推察のみ（求人票に記載なし）」と記載
- 解説: この仕事が会社や業界にどんな価値を生むかを説明（50-100文字）

【追加のデフォルト適用（テンプレート修正と同等）】
- 以下の改善はユーザーが「修正依頼」を選ばなくても、**初回出力で必ず適用**してください。
- A（内容A: 求人票側）: 各項目で「求人票に欠けている具体性」を短いコメントで補足してください（例: "具体例: 月間10件の新規開拓" のように1行程度）。
- B（内容B: 実態推察）: 使用技術はより専門的で実務に近い候補を増やして列挙してください。一般的すぎるもの（例: Teams, Excel 等）を除外し、優先度の高い上位項目を {Config.TECH_DEFAULT_COUNT} 個まで示してください。可能なら各技術に1短文で利用目的を添えてください。
- B（改行整形）: 内容Bは可読性のために適切に改行して示してください（重要点ごとに改行、箇条書き風）。
- ギャップ（確認質問）: 採用部門にそのまま投げられるような実務的で具体的な確認質問に変換してください（Yes/No で答えられない場合は、確認で得たい具体的な情報を明示する）。

【重要: 職位（役割名）の取り扱い】
- 求人票に記載されている**職位（役割名）**は、語彙を変更しないでください。初期の `comparison_final['content_a']['役割']` に書かれている職位名はそのまま保持し、出力内で職位名を書き換えないでください。
- 内容Bでは職務の『責任範囲』や『裁量』などを具体化・追記して構いませんが、職位名自体は変更せず、必要なら括弧や別ラベル（例: "役割補足"）として追記してください。

⭐⭐⭐ 以下のJSON形式で返してください（8項目に対応）:

{{
  "table": [
    ["項目名", "内容A（求人票の記述）", "内容B（実態推察）", "ギャップ"],
    ["求人票名", "...", "...", "..."],
    ["採用背景", "記載なし", "...", "推察のみ（求人票に記載なし）"],
    ["役割", "...", "...", "..."],
    ["業務プロセス", "...", "...", "..."],
    ["対象製品", "...", "...", "..."],
    ["ステークホルダー", "...", "...", "..."],
    ["使用技術", "...", "...", "..."],
    ["バリューチェーン", "記載なし", "...", "推察のみ（求人票に記載なし）"]
  ],
  "explanations": {{
    "求人票名": "この求人がどんな仕事かを一言で表したもの。例えば「法人営業」なら会社向けの営業、「バックエンドエンジニア」ならサーバー側のプログラマーです。",
    "採用背景": "なぜこのポジションが今必要なのか。事業拡大や新プロジェクト、既存メンバーの不足など、組織的な背景が分かります。",
    "役割": "この人が担う責任の範囲。チームをまとめる立場か、実務担当か、どれくらいの裁量があるかが分かります。",
    "業務プロセス": "仕事の流れを順番に示したもの。どんな作業をして、何を成果物として出すかが分かります。※印は各ステップの意味を補足しています。",
    "対象製品": "どんな商品やサービスを扱うか。製品の特徴が分かると、求められるスキルも見えてきます。",
    "ステークホルダー": "この仕事で関わる人たち。誰に報告して、誰と協力して、誰を巻き込むかが分かります。",
    "使用技術": "仕事で使うツールやソフト。※推察がついているものは、求人票に書いてないけど多分使うだろうというものです。",
    "バリューチェーン": "この仕事が会社や業界にどんな価値を生むか。企画・開発・運用のどの段階を担当し、何が核心的な貢献かが分かります。"
  }},
  "how_to_read": "この表は求人票を深く理解するためのものです。【内容A】は求人票に書かれている文字面。【内容B】は実際の業務内容の推察（仮説）。求人票は抽象的だったり、範囲が狭く見えたりすることが多いので、実態はこうでは？と推察しています。【ギャップ】には3つの情報があります：①AとBの違い、②求人票に書かれていない重要な情報、③採用部門に確認すべき質問。この3つを見ることで、求人票だけでは分からなかった実態や、確認すべきポイントが見えてきます。",
  "confidence_score": {comparison_final.get('confidence_score', 0.0)},
  "web_search_performed": {str(comparison_final.get('web_search_performed', False)).lower()},
  "a_comments": {{
    "求人票名": "",
    "採用背景": "",
    "役割": "",
    "業務プロセス": "",
    "対象製品": "",
    "ステークホルダー": "",
    "使用技術": "",
    "バリューチェーン": ""
  }}
}}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
【出力指示】
必ず上記のJSON形式のみで応答してください。
他の文章、説明、マークダウン記法は一切含めないでください。
JSONオブジェクトをそのまま出力してください。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
    return prompt



def layer3_optimize_for_learning(comparison_final: Dict[str, Any]) -> Dict[str, Any]:
    """
    レイヤー③: 教育最適化
    
    Args:
        comparison_final: レイヤー②の出力
        
    Returns:
        最終出力データ（table_data, explanations, how_to_read等を含む）
        
    Raises:
        Exception: 最適化に失敗した場合
    """
    logger.info("=" * 60)
    logger.info("レイヤー③: 教育最適化 開始")
    
    try:
        # プロンプト構築
        prompt = _build_layer3_prompt(comparison_final)
        
        # LLM呼び出し
        response_text = call_openai_with_retry(
            prompt=prompt,
            temperature=1,
            max_completion_tokens=Config.MAX_TOKENS_LAYER3
        )
        
        # JSON解析
        final_output = parse_json_with_retry(response_text)
        
        # CRITICAL: 正規化を最優先で実行（table→table_data変換含む）
        final_output = normalize_table_data_structure(final_output)
        
        # 出力が要件を満たしているかのサーバ側チェック（Aの具体性補完など）
        try:
            final_output = _ensure_content_a_specificity(final_output, comparison_final)
        except Exception:
            logger.warning("内容Aの自動補完に失敗しましたが、処理は継続します")
        
        # バリデーション
        validate_final_output(final_output)
        
        logger.info("レイヤー③: 教育最適化 完了")
        logger.info(f"表データ: {len(final_output['table_data'])}行 x {len(final_output['table_data'][0])}列")
        logger.info(f"解説数: {len(final_output['explanations'])}項目")
        logger.info("=" * 60)
        
        return final_output
        
    except Exception as e:
        logger.error(f"レイヤー③でエラー発生: {str(e)}")
        raise Exception(f"教育最適化に失敗しました: {str(e)}")


def _ensure_content_a_specificity(final_output: Dict[str, Any], comparison_final: Dict[str, Any]) -> Dict[str, Any]:
    """
    final_output の `table_data` を確認し、`内容A（求人票の記述）` に具体性が欠けている場合は
    LLM に短い具体例（1行）を生成させて追記します。
    """
    try:
        table = final_output.get('table_data')
        if not table or len(table) < 2:
            return final_output

        header = table[0]
        # 想定カラム: ["項目名", "内容A（求人票の記述）", "内容B（実態推察）", "ギャップ"]
        # 内容Aは index 1 を想定
        # 強制モード: 全行に対して1行の具体例を生成して追記する
        a_index = 1
        items = {}
        for row in table[1:]:
            item = row[0]
            items[item] = (row[a_index] or "").strip()

        # --- Consolidation: assume main LLM output already contains `a_comments`.
        # If present, use it; otherwise, initialize empty comments to avoid extra LLM calls.
        comments = {}
        if isinstance(final_output.get('a_comments'), dict):
            for k, v in final_output.get('a_comments', {}).items():
                if isinstance(v, str):
                    comments[k] = v.strip().rstrip('。')
                else:
                    comments[k] = str(v).strip()
        else:
            for row in table[1:]:
                comments[row[0]] = ""

        # 生成結果を final_output の独立フィールド `a_comments` に格納（内容Aは上書きしない）
        final_output['a_comments'] = comments

        # ----- 追加の保護処理: LLMがtable_data内で求人票の重要フィールドを変更してしまうのを防ぐ -----
        try:
            orig_a = comparison_final.get('content_a', {}) if isinstance(comparison_final, dict) else {}
            if orig_a and 'table_data' in final_output and isinstance(final_output['table_data'], list):
                td = final_output['table_data']
                # find rows and replace 内容A for 求人票名/役割 with original if present
                for row in td[1:]:
                    item = row[0]
                    if item in ("求人票名", "役割"):
                        orig_val = orig_a.get(item) or orig_a.get(item.replace('（', '').replace('）', ''))
                        if orig_val:
                            # preserve any parenthetical from generated, but keep original as base
                            try:
                                gen_a = (row[1] or "").strip()
                                import re as _re
                                m = _re.search(r"（.+）$", gen_a)
                                paren = m.group(0) if m else ''
                                new_a = orig_val
                                if paren and paren not in orig_val:
                                    new_a = orig_val + paren
                                row[1] = new_a
                            except Exception:
                                row[1] = orig_val
                final_output['table_data'] = td
        except Exception:
            logger.exception("layer3: 求人票名/役割保護処理でエラー")

        # 続けて使用技術の専門化を行う
        try:
            final_output = _specialize_usage_tech(final_output)
        except Exception:
            logger.warning("使用技術の専門化に失敗しましたが、処理は継続します")

        return final_output
    except Exception:
        logger.exception("_specialize_usage_tech でエラー")
        return final_output


def _specialize_usage_tech(final_output: Dict[str, Any]) -> Dict[str, Any]:
    """
    使用技術（B列）を専門性の高い候補に拡張し、用途を1短文で添えて可読な箇条書きに変換する。
    """
    try:
        table = final_output.get('table_data')
        if not table or len(table) < 2:
            return final_output

        # find usage tech row
        b_index = 2
        target_row = None
        for row in table[1:]:
            if row[0] == '使用技術':
                target_row = row
                break
        if not target_row:
            return final_output

        current_b = (target_row[b_index] or "").strip()

        # If usage tech already looks specialized/structured (contains bullets or '：'), skip extra LLM call.
        if current_b and ("\n-" in current_b or (current_b.count('\n') > 0 and '：' in current_b) or ('：' in current_b and len(current_b) > 40)):
            logger.info("使用技術は既に整形済みと判断、専門化処理をスキップします")
            return final_output

        prompt = f"""
以下は求人の「使用技術」についての元の推察です。これを、一般的・曖昧な表現を除外し、実務で役立つ専門性の高い技術を上位{Config.TECH_DEFAULT_COUNT}件まで列挙してください。
各技術には短く（1文）利用目的を添えてください。出力はJSONで、キーを連番（1,2,...）にして、値に{{"tech": 技術名, "purpose": 利用目的}}の形で返してください。

元の使用技術推察:
{json.dumps(current_b, ensure_ascii=False)}
"""

        resp = call_openai_with_retry(prompt=prompt, temperature=1, max_completion_tokens=800)
        try:
            tech_json = parse_json_with_retry(resp)
        except Exception:
            logger.warning("使用技術専門化: LLM応答のJSON解析に失敗しました")
            return final_output

        # tech_json expected like {"1": {"tech":"Python","purpose":"..."}, ...}
        lines = []
        try:
            keys = sorted(tech_json.keys(), key=lambda x: int(x) if str(x).isdigit() else x)
        except Exception:
            keys = list(tech_json.keys()) if isinstance(tech_json, dict) else []

        for k in keys:
            entry = tech_json.get(k)
            if isinstance(entry, dict):
                t = entry.get('tech')
                p = entry.get('purpose', '')
            else:
                t = entry
                p = ''
            if t:
                if p:
                    lines.append(f"- {t}：{p}")
                else:
                    lines.append(f"- {t}")

        if lines:
            target_row[b_index] = "\n".join(lines)
            final_output['table_data'] = table

        return final_output
    except Exception:
        logger.exception("_specialize_usage_tech でエラー")
        return final_output
