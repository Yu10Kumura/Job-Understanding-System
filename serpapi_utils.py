"""
SerpAPI連携機能
Google検索を実行し、結果を取得・整形する
"""
import requests
from typing import List, Dict
from config import Config
from utils import logger


def serpapi_search(query: str, num_results: int = None) -> List[Dict[str, str]]:
    """
    SerpAPIを使ってGoogle検索を実行
    
    Args:
        query: 検索クエリ
        num_results: 取得する結果数（Noneの場合はConfig.MAX_SEARCH_RESULTSを使用）
        
    Returns:
        検索結果のリスト（各要素は {title, link, snippet} の辞書）
        
    Raises:
        Exception: SerpAPI呼び出しに失敗した場合
    """
    if num_results is None:
        num_results = Config.MAX_SEARCH_RESULTS
    
    if not Config.SERPAPI_KEY:
        raise Exception("SERPAPI_KEYが設定されていません")
    
    logger.info(f"SerpAPI検索開始: query='{query}', num={num_results}")
    
    params = {
        "q": query,
        "api_key": Config.SERPAPI_KEY,
        "num": num_results,
        "hl": "ja",  # 日本語
        "gl": "jp",  # 日本
        "engine": "google"
    }
    
    try:
        response = requests.get(
            "https://serpapi.com/search",
            params=params,
            timeout=30
        )
        
        if response.status_code != 200:
            raise Exception(
                f"SerpAPI HTTPエラー: {response.status_code}"
            )
        
        data = response.json()
        
        # エラーレスポンスのチェック
        if "error" in data:
            raise Exception(f"SerpAPIエラー: {data['error']}")
        
        # 検索結果の抽出
        results = []
        for item in data.get("organic_results", []):
            results.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "snippet": item.get("snippet", "")
            })
        
        logger.info(f"SerpAPI検索成功: {len(results)}件の結果を取得")
        return results
        
    except requests.exceptions.RequestException as e:
        logger.error(f"SerpAPI接続エラー: {str(e)}")
        raise Exception(f"SerpAPI接続エラー: {str(e)}")
    
    except KeyError as e:
        logger.error(f"SerpAPIレスポンス解析エラー: {str(e)}")
        raise Exception(f"SerpAPIレスポンス解析エラー: {str(e)}")
    
    except Exception as e:
        logger.error(f"SerpAPI予期しないエラー: {str(e)}")
        raise Exception(f"SerpAPI予期しないエラー: {str(e)}")


def serpapi_search_with_fallback(query: str, num_results: int = None) -> List[Dict[str, str]]:
    """
    SerpAPI検索（失敗時は空リストを返す）
    
    Args:
        query: 検索クエリ
        num_results: 取得する結果数
        
    Returns:
        検索結果のリスト（失敗時は空リスト）
    """
    try:
        return serpapi_search(query, num_results)
    
    except Exception as e:
        logger.warning(f"SerpAPI検索失敗: {str(e)}")
        logger.info("LLMの知識のみで継続します")
        return []


def format_search_results(
    results1: List[Dict[str, str]], 
    results2: List[Dict[str, str]], 
    max_chars: int = None
) -> str:
    """
    検索結果をLLMに渡す形式に整形
    
    Args:
        results1: 検索クエリ1の結果
        results2: 検索クエリ2の結果
        max_chars: 各検索結果から抽出する最大文字数
        
    Returns:
        整形済みテキスト
    """
    if max_chars is None:
        max_chars = Config.WEB_CONTEXT_MAX_CHARS
    
    logger.info(f"検索結果を整形中: results1={len(results1)}件, results2={len(results2)}件")
    
    context = "【検索1: 業務フロー】\n"
    
    if not results1:
        context += "（検索結果なし）\n\n"
    else:
        for i, item in enumerate(results1, 1):
            snippet = item["snippet"][:max_chars]
            title = item["title"][:100]  # タイトルも制限
            context += f"{i}. {title}\n{snippet}\n\n"
    
    context += "\n【検索2: 使用技術】\n"
    
    if not results2:
        context += "（検索結果なし）\n\n"
    else:
        for i, item in enumerate(results2, 1):
            snippet = item["snippet"][:max_chars]
            title = item["title"][:100]
            context += f"{i}. {title}\n{snippet}\n\n"
    
    logger.info(f"検索結果整形完了: 総文字数={len(context)}")
    
    return context


def execute_dual_search(job_category: str) -> str:
    """
    2つの検索クエリを実行し、整形済みコンテキストを返す
    
    Args:
        job_category: 職種名
        
    Returns:
        整形済みの検索結果テキスト
    """
    logger.info(f"デュアル検索開始: job_category='{job_category}'")
    
    # 検索クエリ1: 業務フロー
    query1 = f"{job_category} 業務フロー 標準的な流れ"
    results1 = serpapi_search_with_fallback(query1)
    
    # 検索クエリ2: 使用技術
    query2 = f"{job_category} 使用技術 ツール 最新"
    results2 = serpapi_search_with_fallback(query2)
    
    # 結果を整形
    web_context = format_search_results(results1, results2)
    
    logger.info("デュアル検索完了")
    
    return web_context
