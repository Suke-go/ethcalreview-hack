"""
Gemini APIクライアント
"""
import logging
from google import genai
from google.genai import types
from typing import Optional, Dict, Any
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential, before_sleep_log

logger = logging.getLogger(__name__)


class GeminiClient:
    """Gemini API非同期クライアント（新SDK使用）"""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model_name = model
        print(f"[GEMINI] Initializing: model={model}", flush=True)
        try:
            self.client = genai.Client(api_key=api_key)
            print("[GEMINI] Client created successfully", flush=True)
        except Exception as e:
            print(f"[GEMINI] Client creation failed: {type(e).__name__}: {e}", flush=True)
            raise
    
    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=2, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING)
    )
    async def generate_content_async(
        self, 
        prompt: str,
        system_instruction: Optional[str] = None
    ) -> str:
        """非同期でコンテンツを生成"""
        print(f"[GEMINI] API call started (prompt: {len(prompt)} chars)", flush=True)
        
        config = None
        if system_instruction:
            config = types.GenerateContentConfig(
                system_instruction=system_instruction
            )
        
        try:
            # 非同期で生成
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents=prompt,
                config=config
            )
            print(f"[GEMINI] Response received ({len(response.text)} chars)", flush=True)
            return response.text
        except Exception as e:
            print(f"[GEMINI] API call failed: {type(e).__name__}: {e}", flush=True)
            raise
    
    async def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None
    ) -> Dict[str, Any]:
        """JSON形式でコンテンツを生成"""
        import json
        
        full_prompt = f"""{prompt}

必ずJSON形式で回答してください。マークダウンのコードブロックは使わないでください。"""
        
        response = await self.generate_content_async(full_prompt, system_instruction)
        
        # JSON部分を抽出
        text = response.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        return json.loads(text.strip())

