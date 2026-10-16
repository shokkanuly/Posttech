import re
import time
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import UserRole
from app.models.user import User
from app.models.knowledge import KnowledgeDocument, KnowledgeChunk
from app.schemas.ai import AIChatRequest, AIChatResponse, SourceCitation
from app.services.audit_service import audit_service


class AIService:
    # Terms indicating inquiry about private employee records or unauthorized employment actions
    PRIVACY_RESTRICTED_TERMS = [
        "salary of", "зарплата", "айлық", "жалақы",
        "who got fired", "кого уволили", "кім жұмыстан шықты",
        "personal phone", "личный телефон", "жеке телефон",
        "confidential", "паспортные данные", "жеке куәлік",
        "terminate employee", "уволить сотрудника", "жұмыстан босату"
    ]

    STOP_WORDS = {
        "what", "the", "for", "with", "from", "how", "does", "can", "are", "and", "this", "that",
        "policy", "rules", "about", "guide", "sample",
        "что", "как", "для", "или", "это", "где", "правила", "инструкция",
        "қалай", "қандай", "қайда", "туралы", "ереже"
    }

    @classmethod
    def _check_privacy_and_guardrails(cls, question: str) -> Optional[str]:
        q_lower = question.lower()
        for term in cls.PRIVACY_RESTRICTED_TERMS:
            if term in q_lower:
                return (
                    "AI Jana respects strict employee privacy and data protection boundaries. "
                    "Individual salaries, disciplinary records, and personal confidential details "
                    "are not accessible via public knowledge queries. For personal HR queries, "
                    "please check your own 'My Profile' page or consult with HR Operations."
                )
        return None

    @classmethod
    def _tokenize(cls, text: str) -> List[str]:
        tokens = re.findall(r"\w+", text.lower())
        # Filter short words and stop words
        return [t for t in tokens if len(t) > 2 and t not in cls.STOP_WORDS]

    @classmethod
    def retrieve_relevant_chunks(
        cls, db: Session, question: str, user_role: UserRole
    ) -> List[Tuple[KnowledgeChunk, float]]:
        """
        Retrieves matching chunks ranked by term overlap, tag matching, and section relevance.
        Applies role access control so chunks marked for specific roles aren't leaked.
        """
        query_tokens = cls._tokenize(question)
        if not query_tokens:
            return []

        chunks = (
            db.query(KnowledgeChunk)
            .join(KnowledgeDocument)
            .filter(KnowledgeDocument.is_active == True)
            .all()
        )

        ranked: List[Tuple[KnowledgeChunk, float]] = []

        for chunk in chunks:
            # Role check
            if chunk.access_level != "all" and chunk.access_level != user_role.value:
                if user_role != UserRole.HR_ADMIN:
                    continue

            score = 0.0
            doc_title = (chunk.document.title or "").lower()
            section_title = (chunk.section_title or "").lower()
            content = (chunk.content or "").lower()
            tags = (chunk.tags or "").lower()

            # Weightings:
            for token in query_tokens:
                if token in tags:
                    score += 0.40
                if token in section_title:
                    score += 0.35
                if token in doc_title:
                    score += 0.20
                if token in content:
                    score += 0.15

            # Bonus for exact multi-word phrase match
            clean_q = question.strip().lower()
            if len(clean_q) > 4 and clean_q in content:
                score += 0.50

            if score > 0:
                ranked.append((chunk, score))

        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    @classmethod
    def process_chat_query(
        cls,
        db: Session,
        user: User,
        payload: AIChatRequest,
        ip_address: Optional[str] = None,
    ) -> AIChatResponse:
        start_time = time.time()
        question = payload.question.strip()

        # 1. Guardrail & Privacy Check
        privacy_violation = cls._check_privacy_and_guardrails(question)
        if privacy_violation:
            audit_service.log_event(
                db=db,
                action="AI_QUERY_PRIVACY_BLOCKED",
                actor_id=user.id,
                target_type="ai_chat",
                details={"question": question, "reason": "privacy_guardrail"},
                ip_address=ip_address,
            )
            elapsed = round((time.time() - start_time) * 1000, 2)
            return AIChatResponse(
                question=question,
                answer=privacy_violation,
                answer_status="unauthorized",
                sources=[],
                escalation_guidance=f"Contact HR Operations at {settings.HR_SUPPORT_EMAIL} for confidential matters.",
                processing_time_ms=elapsed,
            )

        # 2. Retrieval from Knowledge Base
        ranked_chunks = cls.retrieve_relevant_chunks(db, question, user.role)

        # 3. Confidence Threshold Check
        best_score = ranked_chunks[0][1] if ranked_chunks else 0.0
        if not ranked_chunks or best_score < settings.AI_CONFIDENCE_THRESHOLD:
            # Safe fallback: Do NOT invent or hallucinate answers!
            fallback_answer = (
                "I couldn't find a reliable answer in the approved HR knowledge base, "
                "so I don't want to make an unverified guess. "
                "Please check the official policy documentation or contact your HR People Partner for confirmation."
            )
            audit_service.log_event(
                db=db,
                action="AI_QUERY_FALLBACK",
                actor_id=user.id,
                target_type="ai_chat",
                details={"question": question, "best_score": best_score},
                ip_address=ip_address,
            )
            elapsed = round((time.time() - start_time) * 1000, 2)
            return AIChatResponse(
                question=question,
                answer=fallback_answer,
                answer_status="fallback",
                sources=[],
                escalation_guidance=f"Escalate to Jana Post HR Support: {settings.HR_SUPPORT_EMAIL} or submit an inquiry ticket.",
                processing_time_ms=elapsed,
            )

        # 4. Grounded Synthesis
        # Take the top 1-2 chunks
        top_chunks = [c for c, s in ranked_chunks[:2]]
        citations: List[SourceCitation] = []
        answer_parts = []

        for chunk in top_chunks:
            citations.append(
                SourceCitation(
                    document_title=chunk.document.title,
                    section_title=chunk.section_title,
                    snippet=chunk.content[:220] + ("..." if len(chunk.content) > 220 else ""),
                    version=f"v{chunk.document.version} (Approved)",
                )
            )
            answer_parts.append(chunk.content)

        # Synthesize clear, grounded answer
        synthesized_answer = (
            f"Based on the approved **{top_chunks[0].document.title}** ({top_chunks[0].section_title}):\n\n"
            f"{top_chunks[0].content}"
        )
        if len(top_chunks) > 1 and top_chunks[1].document.id != top_chunks[0].document.id:
            synthesized_answer += (
                f"\n\nAdditionally, according to **{top_chunks[1].document.title}**:\n"
                f"{top_chunks[1].content}"
            )

        synthesized_answer += (
            "\n\n*Note: This answer is strictly grounded in the approved JanaMen HR knowledge base.*"
        )

        audit_service.log_event(
            db=db,
            action="AI_QUERY_GROUNDED_ANSWER",
            actor_id=user.id,
            target_type="ai_chat",
            details={
                "question": question,
                "score": best_score,
                "sources": [c.section_title for c in top_chunks],
            },
            ip_address=ip_address,
        )

        elapsed = round((time.time() - start_time) * 1000, 2)
        return AIChatResponse(
            question=question,
            answer=synthesized_answer,
            answer_status="grounded",
            sources=citations,
            escalation_guidance="If you have specialized circumstances, you can also contact hr-support@janapost.kz.",
            processing_time_ms=elapsed,
        )


ai_service = AIService()
