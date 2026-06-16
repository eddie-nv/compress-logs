from fastapi import FastAPI
from pydantic import BaseModel
from compression.compressor import compress

app = FastAPI(title="log-compress", version="0.1.0")


class CompressRequest(BaseModel):
    lines: list[str]


@app.post("/v1/compress")
def compress_logs(req: CompressRequest):
    text, raw_tok, comp_tok = compress(req.lines)
    reduction = round((1 - comp_tok / raw_tok) * 100, 1) if raw_tok else 0
    return {
        "compressed": text,
        "raw_tokens": raw_tok,
        "compressed_tokens": comp_tok,
        "reduction_pct": reduction,
    }


@app.get("/health")
def health():
    return {"status": "ok"}
