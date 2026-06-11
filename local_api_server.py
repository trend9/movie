import base64
import torch
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from diffusers import DiffusionPipeline, LCMScheduler

app = FastAPI()

print("Loading LCM Stable Diffusion model on CPU...")
try:
    pipe = DiffusionPipeline.from_pretrained("SimianLuo/LCM_Dreamshaper_v7", torch_dtype=torch.float32)
    pipe.scheduler = LCMScheduler.from_config(pipe.scheduler.config)
    pipe.to("cpu")
    print("LCM Model loaded successfully.")
except Exception as e:
    print(f"Error loading LCM model: {e}")
    pipe = None

class TextRequest(BaseModel):
    system_prompt: str
    user_prompt: str

class ImageRequest(BaseModel):
    prompt: str
    width: int = 512
    height: int = 512

@app.post("/generate/text")
async def generate_text(req: TextRequest):
    try:
        url = "http://localhost:11434/api/chat"
        payload = {
            "model": "gemma2:2b",
            "messages": [
                {"role": "system", "content": req.system_prompt},
                {"role": "user", "content": req.user_prompt}
            ],
            "stream": False
        }
        res = requests.post(url, json=payload, timeout=180)
        if res.status_code == 200:
            return {"result": res.json().get("message", {}).get("content", "")}
        raise HTTPException(status_code=500, detail="Ollama returned error")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/image")
async def generate_image(req: ImageRequest):
    if not pipe:
        raise HTTPException(status_code=500, detail="LCM model is not loaded.")
    try:
        image = pipe(
            prompt=req.prompt,
            num_inference_steps=4,
            guidance_scale=8.0,
            width=req.width,
            height=req.height
        ).images[0]
        
        import io
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=90)
        return {"image_base64": base64.b64encode(buf.getvalue()).decode("utf-8")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
