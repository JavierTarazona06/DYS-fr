from __future__ import annotations
import os
from typing import Optional

from llama_cpp import Llama
from spacy.language import Language

from src.guardrails.entities import mask_entities, reinject_entities
from .base import TextImprover
from .lt_client import LTClient


class LLMImprover(TextImprover):
    """
    Hybrid improver: uses LanguageTool for pre-pass, then LLM for rewriting,
    followed by post-validation.
    """
    
    def __init__(
        self,
        model_path: str,
        lang: str,
        lt_server_url: str,
        nlp: Language | None = None,
        lt_client: LTClient | None = None,
        lt_config: dict | None = None,
        validate_with_lt_after: bool = False,
        n_ctx: int = 4096,
        n_threads: int | None = None,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ):
        """
        :param model_path: Path to the GGUF model file
        :param lang: Language code for LanguageTool ("fr")
        :param lt_server_url: LanguageTool server URL
        :param nlp: spaCy model for NER
        :param lt_client: Optional pre-existing LTClient to reuse (avoids creating new connections)
        :param lt_config: Optional LT client settings (timeouts, retries, cache)
        :param validate_with_lt_after: If True, compare LT errors before/after
        :param n_ctx: Context window size (default 4096)
        :param n_threads: Number of CPU threads (None = auto-detect)
        :param max_tokens: Max tokens to generate
        :param temperature: Sampling temperature (lower = more deterministic)
        """
        self.nlp = nlp
        # Reuse existing client if provided, otherwise create new one
        if lt_client is not None:
            self.lt_client = lt_client
            self._owns_lt_client = False  # Don't close shared client
        else:
            self.lt_client = LTClient(lang, lt_server_url, config=lt_config)
            self._owns_lt_client = True
        self.validate_with_lt_after = validate_with_lt_after
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Load LLM with CPU-optimized settings
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads or os.cpu_count(),
            n_gpu_layers=0,  # CPU only
            use_mlock=True,  # Keep model in RAM
            use_mmap=True,  # Memory-map model file (faster load on SSD)
            verbose=False,
        )
    
    def _build_prompt(self, text: str, lt_hints: list[str]) -> str:
        """Build instruction prompt for Mistral."""
        hints_str = "\n".join(f"- {h}" for h in lt_hints) if lt_hints else "Aucune."
        
        # Prompt ultra-simplificado para textos muy cortos (evita cortes prematuros)
        if len(text.split()) <= 10:
            return f"""[INST]Corrige strictement le texte ci-dessous en français :
{text}

Erreurs détectées à corriger (liste non exhaustive) :
{hints_str}

- N'ajout plus d'information. Retourne suelement le texte corrigé.
- Tout mot qui commence par "ENT_" (ENT_X_PER-Personne, ENT_X_LOC-Location, ENT_X_ORG-Organisation, ENT_X_MISC-Autre, ENT_X_DATE-Date) est un marqueur spécial.
- Ne JAMAIS les modifier, supprimer ni déplacer. Tu dois les recopier à l'identique.

Texte corrigé :
[/INST]"""
        
        # Prompt normal para textos más largos # TODO : Puede ,ejorar con el prompt de stramlit
        return f"""[[INST]
Tu es un correcteur orthographique minimal pour le français. Tu corriges des textes écrits par des personnes DYS. Tu dois seulement les rendre lisibles et grammaticalement corrects, sans les réécrire ni changer le sens.

Texte original :
{text}

Suggestions :
{hints_str}

RÈGLES STRICTES :

1) Marqueurs ENT_X_Y
- Tout mot qui commence par "ENT_" (ENT_X_PER-Personne, ENT_X_LOC-Location, ENT_X_ORG-Organisation, ENT_X_MISC-Autre, ENT_X_DATE-Date) est un marqueur spécial.
- Ne JAMAIS les modifier, supprimer ni déplacer. Tu dois les recopier à l'identique.

2) Verbes et temps
- Ne JAMAIS remplacer un verbe par un synonyme.
- Ne JAMAIS changer le temps verbal (ne pas passer au passé simple, futur, etc.).
- Garder les auxiliaires existants ("a", "est", "avait", etc.).
- Corriger "a" + verbe incorrect vers "a" + participe passé correct
  (ex : "a acheter" → "a acheté", INTERDIT : "acheta").

3) Corrections autorisées
- Orthographe, accords, conjugaison (même temps), ponctuation.
- Ne pas ajouter de nouveaux mots porteurs de sens (noms, verbes, adjectifs, adverbes).
- Fusionner ou séparer des mots seulement pour corriger une faute évidente
  (ex : "l ecol" → "l'école").

4) Structure et style
- Ne pas changer l'ordre des mots ni le registre de langue.
- Ne pas résumer, développer ou expliquer : même contenu, simplement corrigé.

Texte corrigé (UNIQUEMENT le texte corrigé) :
[/INST]"""
    
    def _extract_lt_hints(self, matches) -> list[str]:
        """Extract error messages from LanguageTool matches with context."""
        hints = []
        # Patterns to skip (entity placeholders)
        skip_patterns = ["ENT_", "_PER", "_LOC", "_ORG", "_MISC", "_DATE"]
        
        #for m in matches:
        until = len(matches) * 0.1
        until = until if until > 5 else 5
        for m in matches[:int(until)]:  # Limit to top 5 errors
            # Get the original word/phrase that has the error
            context = getattr(m, 'context', '')
            offset = getattr(m, 'offset', 0)
            length = getattr(m, 'errorLength', 0)
            
            # Extract the problematic text
            if context and offset >= 0 and length > 0:
                error_text = context[offset:offset + length]
            else:
                error_text = ""
            
            # Get suggested replacements
            replacements = getattr(m, 'replacements', [])
            suggestions = [r for r in replacements[:3]] if replacements else []
            
            # Build hint with context
            msg = getattr(m, 'message', '')
            
            # Create hint string
            hint = None
            if error_text and suggestions:
                suggestion_str = " / ".join(f'"{s}"' for s in suggestions)
                hint = f'"{error_text}" → {suggestion_str}: {msg}'
            elif error_text:
                hint = f'"{error_text}": {msg}'
            elif msg:
                hint = msg
            
            # Skip hint if it contains entity placeholder patterns
            if hint and not any(pattern in hint for pattern in skip_patterns):
                hints.append(hint)
                
        return hints
    
    def _count_lt_errors(self, text: str) -> int:
        """Count errors detected by LanguageTool."""
        matches = self.lt_client.check(text)
        return len(matches)
    
    def improve(self, text: str, debug: bool = False) -> str:
        """
        Hybrid pipeline:
        1. Mask entities (spaCy)
        2. Pre-pass with LT (get hints + initial correction)
        3. LLM rewrite with constraints
        4. Post-validation (degrade if LT errors increase)
        5. Reinject entities
        """
        if debug:
            print(f"\n{'='*70}")
            print("🔍 DEBUG MODE - LLM Improver Pipeline")
            print(f"{'='*70}")
            print(f"\n📝 ENTRADA ORIGINAL:\n{text}\n")
        
        masked = []
        text_to_check = text
        
        # Step 1: Mask entities
        if self.nlp is not None:
            doc = self.nlp(text)
            text_to_check, masked = mask_entities(doc)
            if debug:
                print(f"{'='*70}")
                print("STEP 1: Mask Entities (spaCy)")
                print(f"{'='*70}")
                print(f"Entidades detectadas: {len(masked)}")
                if masked:
                    for i, entity in enumerate(masked, 1):
                        print(f"  {i}. {entity.placeholder} → {entity.text}")
                print(f"\nTexto enmascarado:\n{text_to_check}\n")
        
        # Step 2: Pre-pass with LT
        lt_matches_before = self.lt_client.check(text_to_check)
        #error_count_before = len(lt_matches_before)
        lt_hints = self._extract_lt_hints(lt_matches_before)
        error_count_before = len(lt_hints)
        
        if debug:
            print(f"{'='*70}")
            print("STEP 2: Pre-pass con LanguageTool")
            print(f"{'='*70}")
            print(f"Errores detectados: {error_count_before}")
            if lt_hints:
                for i, hint in enumerate(lt_hints, 1):
                    print(f"  {i}. {hint}")
            else:
                print("  (ningún error detectado)")
            print()
        
        # Step 3: LLM rewrite
        prompt = self._build_prompt(text_to_check, lt_hints)
        
        if debug:
            print(f"{'='*70}")
            print("STEP 3: Generación LLM")
            print(f"{'='*70}")
            print(f"Prompt enviado:\n{prompt}\n")
        
        try:
            response = self.llm(
                prompt,
                max_tokens=min(self.max_tokens, max(50, len(text_to_check.split()) * 4)),  # Mínimo 50 tokens, margen x4
                temperature=0.1,  # Very low temperature for conservative corrections
                top_p=0.85,  # Focused sampling
                repeat_penalty=1.1,  # Avoid repetitions
                stop=["</s>", "[INST]"],  # Solo stops seguros (sin "\n\n" ni "Texte" que causan cortes)
                echo=False,
            )
            llm_output = response['choices'][0]['text'].strip()
            
            # Verificar que la respuesta no esté cortada
            finish_reason = response['choices'][0].get('finish_reason', '')
            if finish_reason == 'length' and debug:
                print(f"⚠️  Respuesta cortada por límite de tokens\n")
            
            if debug:
                print(f"Respuesta LLM:\n{llm_output}\n")
        except Exception as e:
            print(f"[LLM_ERROR] {e}")
            # Fallback: return original text
            return reinject_entities(text_to_check, masked) if masked else text
        
        # Step 4: Post-validation (optional for lower latency)
        if self.validate_with_lt_after:
            if debug:
                print(f"{'='*70}")
                print("STEP 4: Post-validation")
                print(f"{'='*70}")
                print("Checking errors with LanguageTool...")

            lt_matches_after = self.lt_client.check(llm_output)
            lt_hints_after = self._extract_lt_hints(lt_matches_after)
            error_count_after = len(lt_hints_after)

            if debug:
                print(f"Errors before: {error_count_before}")
                print(f"Errors after:  {error_count_after}")
                if lt_hints_after:
                    print("\nRemaining errors:")
                    for i, hint in enumerate(lt_hints_after, 1):
                        print(f"  {i}. {hint}")

            if error_count_after > error_count_before:
                if debug:
                    print("REVERTED (quality degraded)")
                else:
                    print(
                        f"[LLM_DEGRADED] Errors increased ({error_count_before} -> "
                        f"{error_count_after}), reverting to input"
                    )
                final_text = text_to_check
            else:
                if debug:
                    print("ACCEPTED (quality preserved or improved)")
                final_text = llm_output

            if debug:
                print()
        else:
            final_text = llm_output
            if debug:
                print(f"{'='*70}")
                print("STEP 4: Post-validation skipped (fast mode)")
                print(f"{'='*70}")
                print()
        
        # Step 5: Reinject entities
        if masked:
            final_text = reinject_entities(final_text, masked)
            if debug:
                print(f"{'='*70}")
                print("STEP 5: Reinserción de entidades")
                print(f"{'='*70}")
                print(f"Texto con entidades restauradas:\n{final_text}\n")
        
        if debug:
            print(f"{'='*70}")
            print("✅ RESULTADO FINAL")
            print(f"{'='*70}")
            print(final_text)
            print(f"{'='*70}\n")
        
        return final_text
    
    def close(self):
        """Release resources."""
        # Only close LT client if we own it
        if self._owns_lt_client:
            self.lt_client.close()
        # llama-cpp-python handles cleanup automatically
