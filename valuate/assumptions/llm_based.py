"""
assumptions/llm_based.py
========================
階段三假設引擎: 呼叫 Claude API 動態生成三情境 P/E。

★★★ 此為「階段三」功能,目前是空殼 + TODO,尚未啟用 ★★★

設計概念:
  把公司的 sector / industry / 近期催化劑 餵給 Claude,
  讓它根據當下產業狀況給出比靜態對照表更精準的三情境 P/E + 理由。

使用前提 (BYOK - Bring Your Own Key):
  使用者必須自備 Anthropic API key:
    export ANTHROPIC_API_KEY="sk-ant-xxxxx"

成本: 每次估值約 $0.01-0.05 (使用者自付給 Anthropic,作者不經手)

未啟用時的行為:
  若使用者加 --use-llm 但未實作/未設 key,
  應 fallback 回 SectorBasedAssumptions 並印出提示。
"""

from __future__ import annotations
import os
from .base import AssumptionEngine, ScenarioAssumption
from .sector_based import SectorBasedAssumptions


# Prompt template (used when stage 3 is implemented)
_PROMPT_TEMPLATE = """\
You are a senior equity analyst. Given the company info below, provide reasonable three-scenario (Bear/Base/Bull) forward P/E multiples.

Company: {name} ({ticker})
Sector: {sector}
Industry: {industry}
Current forward P/E: {forward_pe}
Current trailing P/E: {trailing_pe}
Analyst mean target: {analyst_target}

Consider:
1. The sector's current valuation level and market sentiment
2. The company's growth and moat relative to peers
3. Likely near-term catalysts or risks

Return JSON only, in this exact format, with no other text:
{{"bear_pe": <number>, "base_pe": <number>, "bull_pe": <number>, "rationale": "<one-sentence reason>"}}
"""


class LLMBasedAssumptions(AssumptionEngine):
    """
    用 Claude API 產生假設 (階段三)。

    目前為空殼: __init__ 會檢查 API key,generate 會 fallback。
    階段三實作時,把 generate 內的 TODO 換成真正的 API 呼叫。
    """

    def __init__(self, model: str = "claude-sonnet-4-6", fallback=True):
        self.model = model
        self.fallback = fallback
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        self._fallback_engine = SectorBasedAssumptions()

    def generate(self, company) -> ScenarioAssumption:
        # 檢查前提
        if not self.api_key:
            print("  !  ANTHROPIC_API_KEY not set; LLM assumptions unavailable")
            if self.fallback:
                print("     -> falling back to the sector table")
                result = self._fallback_engine.generate(company)
                result.source += " (LLM fallback)"
                return result
            raise RuntimeError("ANTHROPIC_API_KEY is required to use LLM assumptions")

        # ===================================================
        # TODO (階段三實作):
        #   1. pip install anthropic
        #   2. from anthropic import Anthropic
        #   3. client = Anthropic(api_key=self.api_key)
        #   4. prompt = _PROMPT_TEMPLATE.format(...)
        #   5. resp = client.messages.create(
        #          model=self.model,
        #          max_tokens=300,
        #          messages=[{"role": "user", "content": prompt}],
        #      )
        #   6. 解析 resp 的 JSON → ScenarioAssumption
        #   7. 加 try/except: API 失敗時 fallback 回 sector_based
        # ===================================================

        print("  !  LLM assumption engine not yet implemented (stage 3 feature)")
        if self.fallback:
            print("     -> falling back to the sector table for now")
            result = self._fallback_engine.generate(company)
            result.source += " (LLM not-yet-implemented)"
            return result
        raise NotImplementedError("LLMBasedAssumptions is a stage-3 feature, not yet implemented")
