"""
Greenlight Unicode Utilities

Text normalization and Unicode handling for consistent text processing.
"""

import re
import unicodedata
from typing import Optional


def normalize_text(text: str, form: str = 'NFC') -> str:
    """
    Normalize Unicode text to a standard form.
    
    Args:
        text: Input text
        form: Unicode normalization form (NFC, NFD, NFKC, NFKD)
        
    Returns:
        Normalized text
    """
    return unicodedata.normalize(form, text)


def clean_unicode(text: str) -> str:
    """
    Clean problematic Unicode characters from text.
    
    Removes:
    - Zero-width characters
    - Control characters (except newlines and tabs)
    - Replacement characters
    
    Args:
        text: Input text
        
    Returns:
        Cleaned text
    """
    # Remove zero-width characters
    text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)
    
    # Remove control characters except newline and tab
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
    
    # Remove replacement character
    text = text.replace('\ufffd', '')
    
    return text


def smart_quotes_to_ascii(text: str) -> str:
    """
    Convert smart quotes and other typographic characters to ASCII equivalents.
    
    Args:
        text: Input text
        
    Returns:
        Text with ASCII quotes
    """
    replacements = {
        '\u2018': "'",  # Left single quote
        '\u2019': "'",  # Right single quote
        '\u201c': '"',  # Left double quote
        '\u201d': '"',  # Right double quote
        '\u2013': '-',  # En dash
        '\u2014': '--', # Em dash
        '\u2026': '...', # Ellipsis
        '\u00a0': ' ',  # Non-breaking space
    }
    
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    
    return text


def remove_diacritics(text: str) -> str:
    """
    Remove diacritical marks from text.
    
    Args:
        text: Input text
        
    Returns:
        Text without diacritics
    """
    # Decompose characters
    nfkd = unicodedata.normalize('NFKD', text)
    # Remove combining characters
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def is_printable(text: str) -> bool:
    """
    Check if all characters in text are printable.
    
    Args:
        text: Input text
        
    Returns:
        True if all characters are printable
    """
    return all(c.isprintable() or c in '\n\t\r' for c in text)


def truncate_text(
    text: str,
    max_length: int,
    suffix: str = "...",
    word_boundary: bool = True
) -> str:
    """
    Truncate text to a maximum length.
    
    Args:
        text: Input text
        max_length: Maximum length including suffix
        suffix: Suffix to add when truncated
        word_boundary: If True, truncate at word boundary
        
    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    
    # Account for suffix length
    target_length = max_length - len(suffix)
    
    if target_length <= 0:
        return suffix[:max_length]
    
    truncated = text[:target_length]
    
    if word_boundary:
        # Find last space
        last_space = truncated.rfind(' ')
        if last_space > target_length // 2:
            truncated = truncated[:last_space]
    
    return truncated.rstrip() + suffix


def count_tokens_estimate(text: str) -> int:
    """
    Estimate token count for text (rough approximation).
    
    Uses ~4 characters per token as a rough estimate.
    For accurate counts, use the actual tokenizer.
    
    Args:
        text: Input text
        
    Returns:
        Estimated token count
    """
    # Rough estimate: ~4 characters per token
    return len(text) // 4


def extract_sentences(text: str) -> list:
    """
    Extract sentences from text.
    
    Args:
        text: Input text
        
    Returns:
        List of sentences
    """
    # Simple sentence splitting
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]

