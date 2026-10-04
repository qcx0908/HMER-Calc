"""calculation/router.py —— POST /calculate 路由。

约束（来自 README.md）：
- router 变量必须叫 router
- 路径写全路径，不带 prefix
- 只做参数校验 + 调 Calculator，不写计算逻辑
- 任何异常都要转成 CalculateResponse，绝不 500
"""

from fastapi import APIRouter

from app.common.models import CalculateRequest, CalculateResponse
from app.calculation.calculator import Calculator

router = APIRouter()
_calculator = Calculator()


@router.post("/calculate", response_model=CalculateResponse)
def calculate(request: CalculateRequest) -> CalculateResponse:
    # mode 只允许 deg / rad
    if request.mode not in ("deg", "rad"):
        return CalculateResponse(
            latex=request.latex,
            status="PARSE_ERROR",
            message=f"无效的 mode：{request.mode}（应为 'deg' 或 'rad'）",
        )

    # 交给 Calculator，它自己保证不抛异常
    result = _calculator.calculate(request.latex, request.mode)

    return CalculateResponse(latex=request.latex, **result)