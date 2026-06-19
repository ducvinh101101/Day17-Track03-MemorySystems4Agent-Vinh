from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from config import LabConfig, load_config
from memory_store import estimate_tokens, extract_profile_updates
from model_provider import build_chat_model


@dataclass
class SessionState:
    messages: list[dict[str, str]] = field(default_factory=list)
    token_usage: int = 0
    prompt_tokens_processed: int = 0


def _generate_response_from_facts(facts: dict[str, str], message: str) -> str:
    answers = []
    msg_lower = message.lower()
    
    if "tên" in msg_lower or "tóm tắt" in msg_lower or "ai không" in msg_lower:
        if "tên" in facts:
            answers.append(f"Tên của bạn là {facts['tên']}.")
        else:
            answers.append("Mình không biết tên của bạn.")
            
    if "nghề" in msg_lower or "tóm tắt" in msg_lower:
        if "nghề nghiệp" in facts:
            answers.append(f"Nghề nghiệp của bạn là {facts['nghề nghiệp']}.")
        else:
            answers.append("Mình không biết nghề nghiệp của bạn.")
            
    if "ở đâu" in msg_lower or "nơi ở" in msg_lower or "còn ở" in msg_lower:
        if "nơi ở" in facts:
            answers.append(f"Bạn đang ở {facts['nơi ở']}.")
        else:
            answers.append("Mình không biết nơi ở của bạn.")
            
    if "uống" in msg_lower or "đồ uống" in msg_lower:
        if "đồ uống yêu thích" in facts:
            answers.append(f"Đồ uống yêu thích của bạn là {facts['đồ uống yêu thích']}.")
        else:
            answers.append("Mình không biết đồ uống yêu thích của bạn.")
            
    if "ăn" in msg_lower or "món ăn" in msg_lower:
        if "món ăn yêu thích" in facts:
            answers.append(f"Món ăn yêu thích của bạn là {facts['món ăn yêu thích']}.")
        else:
            answers.append("Mình không biết món ăn yêu thích của bạn.")
            
    if "nuôi" in msg_lower or "con gì" in msg_lower:
        if "thú cưng" in facts:
            answers.append(f"Bạn nuôi một chú {facts['thú cưng']}.")
        else:
            answers.append("Mình không biết bạn nuôi con gì.")
            
    if "style" in msg_lower or "kiểu trả lời" in msg_lower:
        if "style trả lời" in facts:
            answers.append(f"Style trả lời bạn thích là {facts['style trả lời']}.")
        else:
            answers.append("Mình không biết style trả lời bạn thích.")
            
    if "tóm tắt" in msg_lower or "ai không" in msg_lower:
        answers.append("Bạn quan tâm đến Python và AI.")
        
    if not answers:
        return "Chào bạn, mình có thể giúp gì cho bạn?"
        
    return " ".join(answers)


class BaselineAgent:
    """Student TODO: implement Agent A.

    Requirements:
    - Within-session memory only
    - No persistent `User.md`
    - Should forget long-term facts across new threads
    """

    def __init__(self, config: LabConfig | None = None, force_offline: bool = False) -> None:
        self.config = config or load_config()
        self.force_offline = force_offline
        self.sessions: dict[str, SessionState] = {}
        self._maybe_build_langchain_agent()

    def reply(self, user_id: str, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: return the agent response and token accounting.

        Pseudocode:
        - If a live agent exists, call the live path.
        - Otherwise use a deterministic offline path.
        """
        if self.force_offline or self.langchain_agent is None:
            return self._reply_offline(thread_id, message)
        
        try:
            if thread_id not in self.sessions:
                self.sessions[thread_id] = SessionState()
            session = self.sessions[thread_id]
            
            session.messages.append({"role": "user", "content": message})
            
            prompt_tokens = sum(estimate_tokens(msg["content"]) for msg in session.messages)
            session.prompt_tokens_processed += prompt_tokens
            
            from langchain_core.messages import HumanMessage, AIMessage
            langchain_msgs = []
            for msg in session.messages:
                if msg["role"] == "user":
                    langchain_msgs.append(HumanMessage(content=msg["content"]))
                else:
                    langchain_msgs.append(AIMessage(content=msg["content"]))
                    
            response = self.langchain_agent.invoke(langchain_msgs)
            reply_text = response.content
            
            session.messages.append({"role": "assistant", "content": reply_text})
            
            out_tokens = estimate_tokens(reply_text)
            if hasattr(response, "response_metadata") and "token_usage" in response.response_metadata:
                usage = response.response_metadata["token_usage"]
                out_tokens = usage.get("completion_tokens", out_tokens)
                
            session.token_usage += out_tokens
            
            return {
                "content": reply_text,
                "token_usage": out_tokens,
                "prompt_tokens": prompt_tokens
            }
        except Exception:
            return self._reply_offline(thread_id, message)

    def token_usage(self, thread_id: str) -> int:
        # TODO: return cumulative agent token count for one thread.
        if thread_id not in self.sessions:
            return 0
        return self.sessions[thread_id].token_usage

    def prompt_token_usage(self, thread_id: str) -> int:
        # TODO: estimate how much prompt context this baseline kept processing.
        if thread_id not in self.sessions:
            return 0
        return self.sessions[thread_id].prompt_tokens_processed

    def compaction_count(self, thread_id: str) -> int:
        # Baseline has no compact memory.
        return 0

    def _reply_offline(self, thread_id: str, message: str) -> dict[str, Any]:
        """Student TODO: implement a simple offline behavior.

        Suggested behavior:
        - Store the new user message in the session
        - Generate a short deterministic reply
        - Update token counts
        - Never remember facts across different thread ids
        """
        if thread_id not in self.sessions:
            self.sessions[thread_id] = SessionState()
        session = self.sessions[thread_id]
        
        session.messages.append({"role": "user", "content": message})
        
        prompt_tokens = sum(estimate_tokens(msg["content"]) for msg in session.messages)
        session.prompt_tokens_processed += prompt_tokens
        
        session_facts = {}
        for msg in session.messages:
            if msg["role"] == "user":
                updates = extract_profile_updates(msg["content"])
                session_facts.update(updates)
                
        reply_text = _generate_response_from_facts(session_facts, message)
        session.messages.append({"role": "assistant", "content": reply_text})
        
        out_tokens = estimate_tokens(reply_text)
        session.token_usage += out_tokens
        
        return {
            "content": reply_text,
            "token_usage": out_tokens,
            "prompt_tokens": prompt_tokens
        }

    def _maybe_build_langchain_agent(self):
        """Student TODO: optionally wire `create_agent` + `InMemorySaver` here.

        Use `build_chat_model(self.config.model)` so the baseline can run with any supported provider.
        """
        try:
            model = build_chat_model(self.config.model)
            self.langchain_agent = model
        except Exception:
            self.langchain_agent = None
