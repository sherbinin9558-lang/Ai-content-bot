"""Google Gemini image/video provider adapters."""
from __future__ import annotations
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
import aiohttp
from bot.services.ai_router import AIJob, Feature, ProviderResult

class GoogleGenerativeProvider:
    provider_name = "google"
    def __init__(self, api_key: str, model_name: str, telegram_bot_token: str | None = None):
        self.model_name=model_name; self._api_key=api_key; self._telegram_bot_token=telegram_bot_token
    def supports(self, operation: str) -> bool:
        return (operation=="image" and self.model_name in {"gemini-3.1-flash-image","gemini-3-pro-image"}) or (operation=="video" and self.model_name in {"veo-3.1-generate-preview","veo-3.1-fast-generate-preview"})
    async def _photo_bytes(self,file_id:str):
        if not self._telegram_bot_token: raise RuntimeError("Telegram bot token is required for image input")
        timeout=aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(f"https://api.telegram.org/bot{self._telegram_bot_token}/getFile",params={"file_id":file_id}) as response:
                data=await response.json(content_type=None)
                if response.status>=400 or not data.get("ok"): raise RuntimeError("Не удалось получить файл Telegram")
                path=(data.get("result") or {}).get("file_path")
                if not path: raise RuntimeError("Telegram не вернул путь к файлу")
            async with session.get(f"https://api.telegram.org/file/bot{self._telegram_bot_token}/{path}") as response:
                if response.status>=400: raise RuntimeError("Не удалось скачать фотографию Telegram")
                return await response.read(),"image/jpeg"
    async def run(self,job:AIJob)->ProviderResult:
        from google import genai
        from google.genai import types
        client=genai.Client(api_key=self._api_key)
        if job.feature is Feature.PHOTO:
            file_id=job.params.get("file_id")
            if not file_id: raise RuntimeError("Для улучшения фото требуется изображение")
            image_bytes,mime_type=await self._photo_bytes(str(file_id))
            part=types.Part.from_bytes(data=image_bytes,mime_type=mime_type)
            response=await asyncio.to_thread(client.models.generate_content,model=self.model_name,contents=[job.prompt,part],config=types.GenerateContentConfig(response_modalities=["TEXT","IMAGE"]))
            for item in response.parts:
                if item.inline_data is not None:
                    return ProviderResult(media=item.inline_data.data,mime_type=item.inline_data.mime_type or "image/png",filename="ai_result.png")
            raise RuntimeError("Модель не вернула изображение")
        if job.feature is Feature.VIDEO:
            operation=await asyncio.to_thread(client.models.generate_videos,model=self.model_name,prompt=job.prompt,config=types.GenerateVideosConfig(aspect_ratio="9:16" if "вертик" in job.prompt.lower() else "16:9",duration_seconds="8",resolution="720p"))
            while not operation.done:
                await asyncio.sleep(8)
                operation=await asyncio.to_thread(client.operations.get,operation)
            if not operation.response or not operation.response.generated_videos: raise RuntimeError("Veo не вернул видео")
            video=operation.response.generated_videos[0].video
            with TemporaryDirectory() as tmp:
                target=str(Path(tmp)/"result.mp4")
                await asyncio.to_thread(client.files.download,file=video,download_path=target)
                data=Path(target).read_bytes()
            return ProviderResult(media=data,mime_type="video/mp4",filename="ai_video.mp4")
        raise RuntimeError("Неподдерживаемая функция для Google provider")
