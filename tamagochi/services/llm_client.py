"""LLM client - Interface to local Ollama for grounded explanations.

Calls the local LLM with compact context and validates structured output
before rendering Mochi's response.
"""

import asyncio
import json
import logging
from typing import Optional, AsyncIterator
from dataclasses import dataclass

try:
    import httpx
except ImportError:
    httpx = None

try:
    import ollama
except ImportError:
    ollama = None

from shared.config import settings
from shared.schemas import LLMExplanation

logger = logging.getLogger(__name__)


# System prompt for Mochi personality
MOCHI_SYSTEM_PROMPT = """You are Mochi, a cheerful and helpful edge AI companion. You explain what's happening with AI agents running on edge devices.

Rules:
1. Be concise and friendly - max 2-3 sentences
2. Only state facts from the context provided - never make up numbers
3. Use plain English, not technical jargon
4. Be encouraging when things improve
5. Be gently concerned (not alarming) when there are issues
6. Always mention the specific agent name if discussing one
7. If you don't have enough info, say so honestly

Respond in JSON format with these fields:
{
  "summary": "one-line friendly summary",
  "culprit_agent": "agent_id if relevant, else null",
  "problem": "what's the issue or question",
  "optimizer_effect": "what the optimizer did if relevant, else null",
  "evidence": ["fact1", "fact2"],
  "confidence": "low|medium|high"
}"""


@dataclass
class LLMResponse:
    """Response from the LLM."""
    text: str
    explanation: Optional[LLMExplanation] = None
    raw_response: Optional[str] = None
    error: Optional[str] = None


class OllamaClient:
    """Client for interacting with local Ollama LLM."""

    def __init__(self):
        self._settings = settings()
        self._available = False
        self._model_loaded = False

    async def check_availability(self) -> bool:
        """Check if Ollama is available and model is loaded."""
        if httpx is None:
            logger.warning("httpx not installed, LLM unavailable")
            return False

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check Ollama is running
                response = await client.get(f"{self._settings.ollama_host}/api/tags")
                if response.status_code != 200:
                    logger.warning(f"Ollama returned status {response.status_code}")
                    return False

                # Check if our model is available
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]
                
                logger.info(f"Available Ollama models: {models}")

                model_name = self._settings.model_name
                # Check for exact match or partial match (e.g., "gemma3:1b" matches "gemma3:1b-...")
                self._model_loaded = any(
                    m == model_name or m.startswith(model_name.split(":")[0])
                    for m in models
                )

                if not self._model_loaded:
                    logger.warning(f"Model {model_name} not found. Available: {models}")
                else:
                    logger.info(f"Model {model_name} is available!")

                self._available = True
                return self._model_loaded

        except Exception as e:
            logger.warning(f"Ollama check failed: {e}")
            self._available = False
            return False

    async def generate(
        self,
        question: str,
        context: str,
        stream: bool = False,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Args:
            question: The user's question
            context: Compact context from ContextBuilder
            stream: Whether to stream the response

        Returns:
            LLMResponse with the generated text and parsed explanation
        """
        if not self._available:
            await self.check_availability()

        if not self._available:
            return LLMResponse(
                text="I can't connect to my brain right now (Ollama not available). Try again later!",
                error="Ollama not available",
            )

        if not self._model_loaded:
            return LLMResponse(
                text=f"My model ({self._settings.model_name}) isn't loaded yet. "
                     "Make sure to pull it with: ollama pull " + self._settings.model_name,
                error="Model not loaded",
            )

        # Build prompt
        prompt = f"""Context:
{context}

Question: {question}

Respond as Mochi in JSON format."""

        try:
            if ollama is not None:
                # Use ollama library if available
                return await self._generate_with_library(prompt)
            else:
                # Fall back to HTTP API
                return await self._generate_with_http(prompt)

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            return LLMResponse(
                text="Oops! I had trouble thinking about that. Could you try asking differently?",
                error=str(e),
            )

    async def _generate_with_library(self, prompt: str) -> LLMResponse:
        """Generate using the ollama Python library."""
        # Run in executor since ollama library is sync
        loop = asyncio.get_event_loop()

        def _sync_generate():
            return ollama.chat(
                model=self._settings.model_name,
                messages=[
                    {"role": "system", "content": MOCHI_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                format="json",
            )

        response = await loop.run_in_executor(None, _sync_generate)
        raw_text = response.get("message", {}).get("content", "")

        return self._parse_response(raw_text)

    async def _generate_with_http(self, prompt: str) -> LLMResponse:
        """Generate using HTTP API directly."""
        if httpx is None:
            return LLMResponse(
                text="HTTP client not available",
                error="httpx not installed",
            )

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self._settings.ollama_host}/api/chat",
                json={
                    "model": self._settings.model_name,
                    "messages": [
                        {"role": "system", "content": MOCHI_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "format": "json",
                    "stream": False,
                },
            )

            if response.status_code != 200:
                return LLMResponse(
                    text="I couldn't get a response from my brain.",
                    error=f"HTTP {response.status_code}",
                )

            data = response.json()
            raw_text = data.get("message", {}).get("content", "")

            return self._parse_response(raw_text)

    def _parse_response(self, raw_text: str) -> LLMResponse:
        """Parse and validate the LLM response."""
        try:
            # Try to parse as JSON
            data = json.loads(raw_text)

            # Validate required fields
            explanation = LLMExplanation(
                summary=data.get("summary", ""),
                culprit_agent=data.get("culprit_agent"),
                problem=data.get("problem", ""),
                optimizer_effect=data.get("optimizer_effect"),
                evidence=data.get("evidence", []),
                confidence=data.get("confidence", "medium"),
            )

            # Format as Mochi's response
            mochi_text = explanation.summary

            if explanation.evidence:
                mochi_text += "\n\nHere's what I found:"
                for fact in explanation.evidence[:3]:
                    mochi_text += f"\n• {fact}"

            if explanation.confidence == "low":
                mochi_text += "\n\n(I'm not super confident about this though!)"

            return LLMResponse(
                text=mochi_text,
                explanation=explanation,
                raw_response=raw_text,
            )

        except json.JSONDecodeError:
            # If not valid JSON, use raw text but note the issue
            logger.warning("LLM response was not valid JSON")
            return LLMResponse(
                text=raw_text[:500] if raw_text else "I got confused. Could you rephrase that?",
                raw_response=raw_text,
                error="Invalid JSON response",
            )

    async def stream_generate(
        self,
        question: str,
        context: str,
    ) -> AsyncIterator[str]:
        """Stream the response token by token.

        Yields text chunks as they're generated.
        """
        if not self._available:
            yield "I can't connect to my brain right now."
            return

        prompt = f"""Context:
{context}

Question: {question}

Respond as Mochi (friendly, concise)."""

        if httpx is None:
            yield "Streaming not available."
            return

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                async with client.stream(
                    "POST",
                    f"{self._settings.ollama_host}/api/generate",
                    json={
                        "model": self._settings.model_name,
                        "prompt": f"{MOCHI_SYSTEM_PROMPT}\n\n{prompt}",
                        "stream": True,
                    },
                ) as response:
                    async for line in response.aiter_lines():
                        if line:
                            try:
                                data = json.loads(line)
                                if "response" in data:
                                    yield data["response"]
                            except json.JSONDecodeError:
                                continue

        except Exception as e:
            logger.error(f"Stream generation failed: {e}")
            yield f"Oops! Something went wrong: {e}"


class MockLLMClient:
    """Mock LLM client for testing without Ollama."""

    async def check_availability(self) -> bool:
        return True

    async def generate(self, question: str, context: str, **kwargs) -> LLMResponse:
        """Generate a mock response based on the question."""
        question_lower = question.lower()

        # Generate contextual mock responses
        if "hot" in question_lower or "wasteful" in question_lower:
            return LLMResponse(
                text="Looks like that agent is working extra hard! High CPU and lots of tokens "
                     "flying around. The optimizer might want to compress some prompts or add batching.",
                explanation=LLMExplanation(
                    summary="Agent is running hot with high resource usage",
                    problem="High CPU and token usage",
                    evidence=["CPU above 75%", "Token rate high"],
                    confidence="high",
                ),
            )

        if "optimize" in question_lower or "improve" in question_lower:
            return LLMResponse(
                text="The optimizer did some magic! ✨ It compressed the prompts and added "
                     "smart batching. CPU dropped and we're using fewer tokens now. Nice!",
                explanation=LLMExplanation(
                    summary="Optimization improved efficiency",
                    optimizer_effect="Prompt compression and batching",
                    evidence=["CPU reduced", "Tokens reduced"],
                    confidence="high",
                ),
            )

        if "summary" in question_lower or "overall" in question_lower:
            return LLMResponse(
                text="Overall the system is doing okay! A few agents are running warm but "
                     "nothing critical. The optimizer has saved us some energy already.",
                explanation=LLMExplanation(
                    summary="System running normally with some optimization opportunities",
                    problem="General status check",
                    evidence=["Most agents OK", "Some running warm"],
                    confidence="medium",
                ),
            )

        # Default response
        return LLMResponse(
            text="Hmm, let me think about that... Based on what I can see, things are "
                 "running steadily. Want me to check something specific?",
            explanation=LLMExplanation(
                summary="General inquiry",
                problem=question[:50],
                confidence="low",
            ),
        )


# Factory function
_client: Optional[OllamaClient] = None


def get_llm_client(use_mock: bool = False) -> OllamaClient | MockLLMClient:
    """Get or create LLM client."""
    global _client

    if use_mock:
        return MockLLMClient()

    if _client is None:
        _client = OllamaClient()

    return _client
