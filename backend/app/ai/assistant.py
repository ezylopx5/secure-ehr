"""LangGraph clinical assistant workflow with PII scrubbing and offline fallback.

Pipeline stages:
1. ``scrub_input``      - redact direct PII patterns from the prompt
2. ``build_context``    - summarize de-identified clinical/prediction context
3. ``generate_reply``   - query local Ollama if reachable, else synthesize a
                          deterministic evidence-backed clinical response
"""
from __future__ import annotations

from typing import Any, TypedDict

import httpx

try:
    from langgraph.graph import END, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover
    END = "__end__"
    StateGraph = None  # type: ignore[assignment]
    LANGGRAPH_AVAILABLE = False

from app.core.config import IS_VERCEL, get_settings
from app.middleware.stack import PiiScrubber


class AssistantState(TypedDict, total=False):
    raw_prompt: str
    scrubbed_prompt: str
    clinical_context: dict[str, Any]
    reply: str
    trace: list[dict[str, Any]]


def _scrub_node(state: AssistantState) -> AssistantState:
    raw = state.get("raw_prompt", "")
    scrubbed = PiiScrubber.scrub(raw.strip())
    trace = list(state.get("trace") or [])
    trace.append(
        {
            "step": "scrub_input",
            "redacted": scrubbed != raw.strip(),
        }
    )
    return {**state, "scrubbed_prompt": scrubbed, "trace": trace}


def _context_node(state: AssistantState) -> AssistantState:
    ctx = state.get("clinical_context") or {}
    trace = list(state.get("trace") or [])
    trace.append(
        {
            "step": "build_context",
            "record_count": len(ctx.get("records", [])),
            "prediction_count": len(ctx.get("predictions", [])),
        }
    )
    return {**state, "trace": trace}


def _fallback_synthesis(prompt: str, ctx: dict[str, Any]) -> str:
    records = ctx.get("records") or []
    predictions = ctx.get("predictions") or []
    parts = [f"Clinical Synthesis for: \"{prompt}\""]

    if predictions:
        pred_summaries = []
        for pred in predictions[:3]:
            top_feats = ", ".join(
                f"{f['feature']} ({f['contribution']:+.2f})"
                for f in (pred.get("top_features") or [])[:3]
            )
            pred_summaries.append(
                f"{pred['disease']} [{pred['risk_band']} risk, p={pred['probability']:.1%}"
                + (f", top SHAP drivers: {top_feats}]" if top_feats else "]")
            )
        parts.append("• Encrypted AI Risk Assessments: " + "; ".join(pred_summaries) + ".")
    else:
        parts.append(
            "• Encrypted AI Risk Assessments: None recorded yet (run a Homomorphic AI Risk model in the tab to include TreeSHAP drivers)."
        )

    if records:
        rec_items = []
        for r in records[:4]:
            payload = r.get("payload") or {}
            kv = ", ".join(
                f"{k}={v}" for k, v in list(payload.items())[:5]
            )
            rec_items.append(
                f"{r.get('title', 'Record')} ({r.get('category', 'general')}/{r.get('record_type', 'note')})"
                + (f": [{kv}]" if kv else "")
            )
        parts.append(
            f"• Consented Clinical Records ({len(records)} reviewed): "
            + " | ".join(rec_items)
            + "."
        )
    else:
        parts.append("• Consented Clinical Records: No consented records available for this role.")

    parts.append(
        "• Recommendation: Correlate elevated biomarkers or SHAP risk drivers with longitudinal vitals and confirm active patient consent before ordering interventions."
    )
    return "\n".join(parts)


def _generate_node(state: AssistantState) -> AssistantState:
    settings = get_settings()
    prompt = state.get("scrubbed_prompt") or ""
    ctx = state.get("clinical_context") or {}
    trace = list(state.get("trace") or [])

    reply: str | None = None
    engine_used = "langgraph-clinical-synthesizer"
    should_try_ollama = not (
        IS_VERCEL and "localhost" in settings.OLLAMA_BASE_URL
    )
    if should_try_ollama:
        try:
            response = httpx.post(
                f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": (
                        "You are a clinical decision-support assistant operating on "
                        "de-identified EHR context. Be concise and safety-focused.\n\n"
                        f"Context: {ctx}\nQuestion: {prompt}"
                    ),
                    "stream": False,
                },
                timeout=1.5,
            )
            if response.status_code == 200:
                candidate = (response.json().get("response") or "").strip()
                if candidate:
                    reply = PiiScrubber.scrub(candidate)
                    engine_used = f"ollama:{settings.OLLAMA_MODEL}"
        except Exception:  # noqa: BLE001
            reply = None

    if not reply:
        reply = _fallback_synthesis(prompt, ctx)

    trace.append({"step": "generate_reply", "engine": engine_used})
    return {**state, "reply": reply, "trace": trace}


def _build_graph():
    if not LANGGRAPH_AVAILABLE:
        return None
    graph = StateGraph(AssistantState)
    graph.add_node("scrub_input", _scrub_node)
    graph.add_node("build_context", _context_node)
    graph.add_node("generate_reply", _generate_node)
    graph.set_entry_point("scrub_input")
    graph.add_edge("scrub_input", "build_context")
    graph.add_edge("build_context", "generate_reply")
    graph.add_edge("generate_reply", END)
    return graph.compile()


_COMPILED_GRAPH = _build_graph()


def run_clinical_assistant(prompt: str, clinical_context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute the LangGraph clinical assistant workflow."""
    initial: AssistantState = {
        "raw_prompt": prompt,
        "clinical_context": clinical_context or {},
        "trace": [],
    }
    if _COMPILED_GRAPH is not None:
        final_state = _COMPILED_GRAPH.invoke(initial)
    else:
        final_state = _generate_node(_context_node(_scrub_node(initial)))
    return {
        "scrubbed_prompt": final_state["scrubbed_prompt"],
        "reply": final_state["reply"],
        "trace": final_state["trace"],
    }
