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
        :param n_ctx: Context window size (default 4096)
        :param n_threads: Number of CPU threads (None = auto-detect)
        :param max_tokens: Max tokens to generate
        :param temperature: Sampling temperature (lower = more deterministic)
        """
        self.nlp = nlp
        self.lt_client = LTClient(lang, lt_server_url)
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
        hints_str = "\n".join(f"- {h}" for h in lt_hints[:5]) if lt_hints else "Aucune."
        
        return f"""[INST] Corrige UNIQUEMENT les fautes d'orthographe et de grammaire. Ne change PAS le sens du texte.

INTERDICTIONS STRICTES:
- Ne JAMAIS changer le sens des verbes (aller reste aller, pas "veux aller")
- Ne JAMAIS remplacer les mots par des synonymes
- Ne JAMAIS ajouter de mots qui n'existent pas dans l'original
- Ne JAMAIS modifier les marqueurs ENT_X_Y

CORRECTIONS AUTORISÉES:
- Orthographe
- Conjugaison
- Accords: genre, nombre, articles
- Ponctuation: apostrophes, virgules

Erreurs détectées:
{hints_str}

Texte original:
{text}

Texte corrigé (MÊME sens, MÊMES mots): [/INST]"""
    
    def _extract_lt_hints(self, matches) -> list[str]:
        """Extract error messages from LanguageTool matches with context."""
        hints = []
        for m in matches[:5]:  # Limit to top 5 errors
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
            
            if error_text and suggestions:
                suggestion_str = " / ".join(f'"{s}"' for s in suggestions)
                hints.append(f'"{error_text}" → {suggestion_str}: {msg}')
            elif error_text:
                hints.append(f'"{error_text}": {msg}')
            elif msg:
                hints.append(msg)
                
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
        
        # TODO : SPACY stopt woriking when runner LLM pipline
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
                    for i, (placeholder, original) in enumerate(masked, 1):
                        print(f"  {i}. {placeholder} → {original}")
                print(f"\nTexto enmascarado:\n{text_to_check}\n")
        
        # Step 2: Pre-pass with LT
        lt_matches_before = self.lt_client.check(text_to_check)
        error_count_before = len(lt_matches_before)
        lt_hints = self._extract_lt_hints(lt_matches_before)
        
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
                max_tokens=min(self.max_tokens, len(text_to_check.split()) * 2),  # Dynamic limit
                temperature=0.1,  # Very low temperature for conservative corrections
                top_p=0.85,  # Focused sampling
                repeat_penalty=1.1,  # Avoid repetitions
                stop=["</s>", "[INST]", "\n\n", "Texte"],  # Stop early
                echo=False,
            )
            llm_output = response['choices'][0]['text'].strip()
            
            if debug:
                print(f"Respuesta LLM:\n{llm_output}\n")
        except Exception as e:
            print(f"[LLM_ERROR] {e}")
            # Fallback: return original text
            return reinject_entities(text_to_check, masked) if masked else text
        
        # Step 4: Post-validation
        error_count_after = self._count_lt_errors(llm_output)
        
        if debug:
            print(f"{'='*70}")
            print("STEP 4: Post-validación")
            print(f"{'='*70}")
            print(f"Errores antes:  {error_count_before}")
            print(f"Errores después: {error_count_after}")
        
        if error_count_after > error_count_before:
            if debug:
                print(f"⚠️  REVERTIDO (empeoró la calidad)")
            else:
                print(f"[LLM_DEGRADED] Errors increased ({error_count_before} → {error_count_after}), reverting to input")
            final_text = text_to_check
        else:
            if debug:
                print(f"✓ ACEPTADO (mejoró o mantuvo calidad)")
            final_text = llm_output
        
        if debug:
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
        self.lt_client.close()
        # llama-cpp-python handles cleanup automatically
