# tools/web_tools.py
from duckduckgo_search import DDGS

def buscar_en_web(query: str, max_results: int = 5) -> list:
    """
    Busca información en la web usando DuckDuckGo de forma limpia y sin API keys.
    """
    resultados = []
    try:
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                resultados.append({
                    "titulo": r.get("title"),
                    "enlace": r.get("href"),
                    "cuerpo": r.get("body")
                })
    except Exception as e:
        resultados.append({"error": str(e)})
    return resultados

def buscar_en_youtube(query: str, max_results: int = 5) -> list:
    """
    Busca videos en YouTube utilizando DuckDuckGo para extraer títulos, enlaces y descripciones.
    """
    resultados = []
    try:
        query_yt = f"site:youtube.com {query}"
        with DDGS() as ddgs:
            for r in ddgs.text(query_yt, max_results=max_results):
                resultados.append({
                    "titulo": r.get("title"),
                    "enlace": r.get("href"),
                    "descripcion": r.get("body")
                })
    except Exception as e:
        resultados.append({"error": str(e)})
    return resultados
