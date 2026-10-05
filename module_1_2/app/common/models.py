from pydantic import BaseModel
from typing import List, Optional

class RecognizeRequest(BaseModel):
    image: str

class Token(BaseModel):
    text: str
    confidence: float
    range_start: int
    range_end: int
    alternatives: List[str] = []

class RecognitionResponse(BaseModel):
    latex: str
    confidence: float
    tokens: List[Token] = []
    status: str = "SUCCESS"            # "SUCCESS" | "ERROR"（识别失败）
    message: Optional[str] = None

class CalculateRequest(BaseModel):
    latex: str
    mode: str = "deg"              # "deg" | "rad" | "auto"（组长订正：新增 auto，默认值保持 deg 不变）

class CalculateResponse(BaseModel):
    latex: str
    value: Optional[float] = None
    value_latex: Optional[str] = None
    status: str                    # SUCCESS | PARSE_ERROR | COMPUTE_ERROR
    message: Optional[str] = None
