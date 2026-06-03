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


# 提示詞模板 (階段三實作時使用)
_PROMPT_TEMPLATE = """\
你是資深股票分析師。根據以下公司資訊,給出合理的三情境 (Bear/Base/Bull) Forward P/E 倍數。

公司: {name} ({ticker})
產業 (sector): {sector}
細分 (industry): {industry}
目前 Forward P/E: {forward_pe}
目前 Trailing P/E: {trailing_pe}
分析師目標均價: {analyst_target}

請考慮:
1. 該產業當下的估值水位與市場情緒
2. 該公司相對同業的成長性與護城河
3. 近期可能的催化劑或風險

只回傳 JSON,格式如下,不要任何其他文字:
{{"bear_pe": <數字>, "base_pe": <數字>, "bull_pe": <數字>, "rationale": "<一句話理由>"}}
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
            print("  ⚠️  未設定 ANTHROPIC_API_KEY,LLM 假設不可用")
            if self.fallback:
                print("     → fallback 回產業分類表")
                result = self._fallback_engine.generate(company)
                result.source += " (LLM fallback)"
                return result
            raise RuntimeError("需要 ANTHROPIC_API_KEY 才能使用 LLM 假設")

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

        print("  ⚠️  LLM 假設引擎尚未實作 (階段三功能)")
        if self.fallback:
            print("     → 目前 fallback 回產業分類表")
            result = self._fallback_engine.generate(company)
            result.source += " (LLM not-yet-implemented)"
            return result
        raise NotImplementedError("LLMBasedAssumptions 為階段三功能,尚未實作")
