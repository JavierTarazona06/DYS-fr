from __future__ import annotations
import ollama
from spacy.language import Language
from src.guardrails.entities import mask_entities, reinject_entities
from .base import TextImprover
from .lt_client import LTClient

class OllamaImprover(TextImprover):
    """
    Hybrid improver using Ollama (Gemma 3) + LanguageTool.
    """
    
    def __init__(
        self,
        model_name: str,
        lang: str,
        lt_server_url: str,
        nlp: Language | None = None,
        temperature: float = 0.1,
    ):
        self.model_name = model_name
        self.nlp = nlp
        self.lt_client = LTClient(lang, lt_server_url)
        self.temperature = temperature

    def _build_system_prompt(self) -> str:
        return (
            "Tu es un expert en accessibilité cognitive (DYS). "
            "Ta tâche est de corriger l'orthographe et la grammaire du texte fourni. "
            "RÈGLES STRICTES : "
            "1. Ne change JAMAIS le sens du texte. "
            "2. Ne change JAMAIS les noms propres ou les codes 'ENT_X_Y'. "
            "3. Ne fais pas de paraphrase inutile, garde le style de l'auteur. "
            "4. Réponds UNIQUEMENT avec le texte corrigé, sans introduction ni guillemets."
        )

    def _build_user_prompt(self, text: str, lt_hints: list[str]) -> str:
        hints_str = "\n".join(f"- {h}" for h in lt_hints[:5]) if lt_hints else "Aucune."
        return (
            f"Voici des indices sur les erreurs détectées par un correcteur grammatical :\n{hints_str}\n\n"
            f"Texte à corriger :\n{text}"
        )

    def _extract_lt_hints(self, matches) -> list[str]:
        # (Same logic as LLMImprover - condensed for brevity)
        hints = []
        for m in matches[:5]:
            msg = getattr(m, 'message', '')
            context = getattr(m, 'context', '')
            if context and msg:
                hints.append(msg)
        return hints

    def _count_lt_errors(self, text: str) -> int:
        return len(self.lt_client.check(text))

    def improve(self, text: str, debug: bool = False) -> str:
        # 1. Mask Entities
        masked = []
        text_to_check = text
        if self.nlp:
            doc = self.nlp(text)
            text_to_check, masked = mask_entities(doc)

        # 2. LT Pre-pass (Get Hints)
        matches = self.lt_client.check(text_to_check)
        hints = self._extract_lt_hints(matches)
        errors_before = len(matches)

        # 3. Call Ollama
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {'role': 'system', 'content': self._build_system_prompt()},
                    {'role': 'user', 'content': self._build_user_prompt(text_to_check, hints)},
                ],
                options={'temperature': self.temperature}
            )
            corrected_text = response['message']['content'].strip()
            
            # Clean up if model adds quotes or generic intros
            if corrected_text.startswith('"') and corrected_text.endswith('"'):
                corrected_text = corrected_text[1:-1]
            
        except Exception as e:
            if debug: print(f"Ollama Error: {e}")
            return text  # Fallback on error

        # 4. Post-Validation
        errors_after = self._count_lt_errors(corrected_text)
        
        # If model hallucinated and made it worse, revert
        if errors_after > errors_before:
            final_text = text_to_check 
        else:
            final_text = corrected_text

        # 5. Reinject Entities
        if masked:
            final_text = reinject_entities(final_text, masked)

        return final_text