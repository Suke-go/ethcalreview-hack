"""
LLM Client Abstraction Layer
Supports OpenAI and Gemini providers
"""
import json
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential


class LLMClient(ABC):
    """LLMクライアントの抽象基底クラス"""
    
    @abstractmethod
    async def generate_content_async(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None
    ) -> str:
        """テキスト生成"""
        pass
    
    async def generate_json(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """JSON形式でテキスト生成"""
        full_prompt = f"""{prompt}

You MUST respond in valid JSON format only. Do not use markdown code blocks."""
        
        response = await self.generate_content_async(full_prompt, system_instruction)
        
        # Extract JSON from response
        text = response.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        return json.loads(text.strip())


class OpenAIClient(LLMClient):
    """OpenAI APIクライアント"""
    
    def __init__(self, api_key: str, model: str = "gpt-5-mini"):
        import sys
        from openai import OpenAI
        
        self.model_name = model
        self.client = None
        self._sync_client = None
        
        # Windows環境では同期クライアントのみ使用
        # (非同期クライアントはOSError [Errno 22]を起こすため)
        self._sync_client = OpenAI(api_key=api_key)
    
    async def generate_content_async(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None
    ) -> str:
        """非同期でコンテンツを生成"""
        from openai import AuthenticationError, APIConnectionError, RateLimitError, APIStatusError
        
        # リトライすべき例外の定義
        # AuthenticationError, APIStatusError(400系) はリトライしない
        # RateLimitError, APIConnectionError, APIStatusError(500系) はリトライする
        
        # tenacityのデコレータをメソッド内ではなく、内部関数または直接呼び出す形にすると
        # 動的なインポートに対応しやすいが、ここではデコレータの引数で制御したい。
        # クラスレベルでのインポート依存を避けるため、実行時にリトライロジックを持つラッパー経由で呼び出すのが安全。
        
        return await self._call_with_retry(prompt, system_instruction)

    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=2, max=10),
        # ここで例外フィルタリングを行いたいが、openaiがインポートされていないとNameErrorになる
        # そのため、汎用的な Exception をキャッチし、内部で再送判定を行うか、
        # あるいはここで raise された特定の例外だけリトライするように修正する。
        reraise=True
    )
    async def _call_api_raw(self, messages):
        from openai import AuthenticationError
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
            )
            return response.choices[0].message.content
        except AuthenticationError:
            # 認証エラーはリトライさせないために、そのまま抜ける（retryに引っかからないようにする工夫が必要）
            # しかし tenacity は例外があがるとリトライする。
            # したがって、tenacityの `retry` 引数に条件を渡すのがベスト。
            raise 

    async def _call_with_retry(self, prompt, system_instruction):
        import asyncio
        from openai import AuthenticationError, BadRequestError
        
        messages = []
        if system_instruction:
            messages.append({"role": "developer", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})
        
        print(f"[OPENAI] API call started (prompt: {len(prompt)} chars)", flush=True)

        # 同期クライアントフォールバック
        if self.client is None and hasattr(self, '_sync_client'):
            print("[OPENAI] Using sync client via asyncio.to_thread", flush=True)
            try:
                response = await asyncio.to_thread(
                    self._sync_client.chat.completions.create,
                    model=self.model_name,
                    messages=messages,
                )
                result = response.choices[0].message.content
                print(f"[OPENAI] Response received ({len(result)} chars)", flush=True)
                return result
            except AuthenticationError as e:
                print(f"[OPENAI] Authentication Failed: {e}", flush=True)
                raise ValueError(f"OpenAI Authentication Failed: Invalid API Key.") from e
            except Exception as e:
                print(f"[OPENAI] API call failed: {type(e).__name__}: {e}", flush=True)
                raise

        # 非同期クライアント使用
        from tenacity import AsyncRetrying, retry_if_not_exception_type
        
        no_retry_exceptions = (AuthenticationError, BadRequestError)

        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                retry=retry_if_not_exception_type(no_retry_exceptions),
                reraise=True
            ):
                with attempt:
                    response = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                    )
                    result = response.choices[0].message.content
                    print(f"[OPENAI] Response received ({len(result)} chars)", flush=True)
                    return result
        except AuthenticationError as e:
            print(f"[OPENAI] Authentication Failed: {e}", flush=True)
            raise ValueError(f"OpenAI Authentication Failed: Invalid API Key. Please check your settings.") from e
        except Exception as e:
            print(f"[OPENAI] API call failed: {type(e).__name__}: {e}", flush=True)
            raise


class GeminiClient(LLMClient):
    """Gemini APIクライアント"""
    
    def __init__(self, api_key: str, model: str = "gemini-3-flash"):
        from google import genai
        
        self.api_key = api_key
        self.model_name = model
        print(f"[GEMINI] Initializing: model={model}", flush=True)
        
        try:
            self.client = genai.Client(api_key=api_key)
            print("[GEMINI] Client created successfully", flush=True)
        except Exception as e:
            print(f"[GEMINI] Client creation failed: {type(e).__name__}: {e}", flush=True)
            raise
    
    async def generate_content_async(
        self, 
        prompt: str, 
        system_instruction: Optional[str] = None
    ) -> str:
        """非同期でコンテンツを生成"""
        import asyncio
        from google.genai import types
        from google.genai.errors import ClientError
        from tenacity import AsyncRetrying, retry_if_not_exception_type
        
        print(f"[GEMINI] API call started (prompt: {len(prompt)} chars)", flush=True)
        
        config = None
        if system_instruction:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        
        # 400系エラー（ClientError）はリトライしない
        # 注意: ライブラリのバージョンによって例外階層が異なる場合があるが、
        # google-genai SDKでは ClientError がステータスコードエラーを含む
        
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=2, max=10),
                # ClientError (4xx) はリトライしない
                retry=retry_if_not_exception_type(ClientError),
                reraise=True
            ):
                with attempt:
                    response = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.model_name,
                        contents=prompt,
                        config=config
                    )
                    print(f"[GEMINI] Response received ({len(response.text)} chars)", flush=True)
                    return response.text
        except ClientError as e:
            # 401/403 等のチェック（詳細メッセージに依存する可能性あり）
            print(f"[GEMINI] Client Error (No Retry): {e}", flush=True)
            if "401" in str(e) or "403" in str(e) or "INVALID_ARGUMENT" in str(e):
                 raise ValueError(f"Gemini API Error: {e}") from e
            raise
        except Exception as e:
            print(f"[GEMINI] API call failed: {type(e).__name__}: {e}", flush=True)
            raise


def create_llm_client(
    provider: str, 
    api_key: str, 
    model: Optional[str] = None
) -> LLMClient:
    """
    ファクトリ関数：プロバイダーに応じたクライアントを生成
    
    Args:
        provider: "openai" or "gemini"
        api_key: API key for the provider
        model: Optional model name override
    
    Returns:
        LLMClient instance
    """
    provider = provider.lower()
    
    if provider == "openai":
        return OpenAIClient(api_key=api_key, model=model or "gpt-5-mini")
    elif provider == "gemini":
        return GeminiClient(api_key=api_key, model=model or "gemini-3-flash")
    else:
        raise ValueError(f"Unknown provider: {provider}. Supported: openai, gemini")
