"""
Batch Coherency Agent

Analyzes multiple frames together to ensure shot-to-shot consistency:
- Character consistency across frames (same person looks the same)
- Lighting/time of day consistency
- Location consistency
- Clothing consistency
- Prop consistency
- Visual style consistency

Provides batch-level corrections to fix coherency breaks.
"""

import json
import base64
import httpx
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CoherencyIssue:
    """A coherency issue between frames."""
    frames_affected: list[str]  # e.g. ["1.5", "1.11"]
    category: str  # character, lighting, clothing, location, style
    severity: str  # critical, major, minor
    issue: str
    fix_instruction: str


@dataclass
class BatchCoherencyResult:
    """Result of batch coherency analysis."""
    coherency_score: float  # 0-10
    passed: bool
    issues: list[CoherencyIssue] = field(default_factory=list)
    frame_notes: dict[str, str] = field(default_factory=dict)  # per-frame notes
    summary: str = ""


class BatchCoherencyAgent:
    """
    Agent that analyzes multiple frames together for shot-to-shot coherency.
    Uses Gemini to compare frames and identify consistency issues.
    """

    COHERENCY_PROMPT = '''You are a professional film continuity supervisor analyzing storyboard frames for shot-to-shot consistency.

## SCENE CONTEXT
Scene: {scene_id} - {scene_title}
Location: {location}
Time of Day: {time_of_day}
Characters: {characters}

Script Context:
"{script_excerpt}"

## FRAMES TO ANALYZE
{frame_descriptions}

## YOUR TASK
Analyze ALL frames together for COHERENCY and CONSISTENCY:

### 1. CHARACTER CONSISTENCY
- Does the same character look the same across all their frames?
- Same face, same hair style, same age appearance?
- Any frames where a character looks different?

### 2. CLOTHING CONSISTENCY
- Is each character wearing the same outfit across their frames?
- Any costume changes that shouldn't happen?

### 3. LIGHTING CONSISTENCY
- Is the time of day consistent (all sunrise, all night, etc)?
- Is lighting direction consistent?
- Any frames with wrong lighting?

### 4. LOCATION CONSISTENCY
- Do frames in the same location look like the same place?
- Same architectural details, same props in background?

### 5. STYLE CONSISTENCY
- Same visual style across all frames?
- Same level of realism/CGI look?

### 6. CONTINUITY FLOW
- Do the frames flow naturally as a sequence?
- Any jarring transitions?

## OUTPUT FORMAT (JSON only)
```json
{{
    "coherency_score": 7.5,
    "passed": false,
    "summary": "Brief overall assessment",
    "frame_notes": {{
        "1.5": "Good - Mei in pink robe, correct lighting",
        "1.9": "Good - Lin matches reference well",
        "1.11": "Issue - Mei's face looks different from 1.5"
    }},
    "issues": [
        {{
            "frames_affected": ["1.5", "1.11"],
            "category": "character",
            "severity": "major",
            "issue": "Mei's face appears different between frames - different facial structure",
            "fix_instruction": "Regenerate 1.11 to match Mei's appearance from 1.5 - same facial features"
        }},
        {{
            "frames_affected": ["1.5", "1.6", "1.11"],
            "category": "clothing",
            "severity": "critical",
            "issue": "Mei wearing different clothes - pink robe in 1.5, jacket in 1.6",
            "fix_instruction": "Fix 1.6 - change jacket to pink silk sleeping robe to match other Mei frames"
        }}
    ]
}}
```

Categories: character, clothing, lighting, location, style, continuity
Severity: critical (breaks continuity), major (noticeable), minor (subtle)

If coherency_score >= 8 and no critical issues, set passed: true.

ANALYZE THESE FRAMES FOR COHERENCY:'''

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")

    def analyze_batch_coherency(
        self,
        frames: list[tuple[str, Path, str]],  # (frame_id, image_path, description)
        scene_context: dict,
        character_refs: list[Path] = None
    ) -> BatchCoherencyResult:
        """
        Analyze multiple frames together for coherency.

        Args:
            frames: List of (frame_id, image_path, description) tuples
            scene_context: Dict with scene_id, scene_title, location, time_of_day, characters, script_excerpt
            character_refs: Optional character reference sheets to compare against
        """
        # Build frame descriptions
        frame_descriptions = []
        for i, (frame_id, path, desc) in enumerate(frames):
            frame_descriptions.append(f"Frame {frame_id}: {desc}")

        prompt = self.COHERENCY_PROMPT.format(
            scene_id=scene_context.get("scene_id", "1"),
            scene_title=scene_context.get("scene_title", "Unknown"),
            location=scene_context.get("location", "Unknown"),
            time_of_day=scene_context.get("time_of_day", "Unknown"),
            characters=scene_context.get("characters", "Unknown"),
            script_excerpt=scene_context.get("script_excerpt", ""),
            frame_descriptions="\n".join(frame_descriptions)
        )

        # Collect all images
        images = []

        # Add character refs first if provided
        if character_refs:
            for ref in character_refs[:2]:  # Max 2 char refs
                if ref.exists():
                    images.append(ref)

        # Add frame images
        for frame_id, path, desc in frames:
            if path and path.exists():
                images.append(path)

        # Call Gemini
        response = self._call_gemini(prompt, images)

        # Parse response
        return self._parse_response(response)

    def _call_gemini(self, prompt: str, image_paths: list[Path]) -> str:
        """Call Gemini with multiple images."""
        parts = []

        # Add images
        for img_path in image_paths:
            if img_path.exists():
                with open(img_path, "rb") as f:
                    img_data = base64.b64encode(f.read()).decode("utf-8")

                suffix = img_path.suffix.lower()
                mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(suffix, "image/png")

                parts.append({
                    "inline_data": {"mime_type": mime, "data": img_data}
                })

        # Add prompt
        parts.append({"text": prompt})

        # API call
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
        headers = {"Content-Type": "application/json", "x-goog-api-key": self.api_key}
        body = {
            "contents": [{"parts": parts}],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 4096}
        }

        with httpx.Client(timeout=180.0) as client:  # Longer timeout for multiple images
            response = client.post(url, json=body, headers=headers)
            response.raise_for_status()
            result = response.json()

        # Extract text
        text = ""
        for part in result.get("candidates", [{}])[0].get("content", {}).get("parts", []):
            if "text" in part:
                text += part["text"]
        return text

    def _parse_response(self, response: str) -> BatchCoherencyResult:
        """Parse Gemini's JSON response."""
        try:
            # Extract JSON
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]

            data = json.loads(json_str.strip())

            issues = []
            for issue_data in data.get("issues", []):
                issues.append(CoherencyIssue(
                    frames_affected=issue_data.get("frames_affected", []),
                    category=issue_data.get("category", "unknown"),
                    severity=issue_data.get("severity", "minor"),
                    issue=issue_data.get("issue", ""),
                    fix_instruction=issue_data.get("fix_instruction", "")
                ))

            return BatchCoherencyResult(
                coherency_score=data.get("coherency_score", 5.0),
                passed=data.get("passed", False),
                issues=issues,
                frame_notes=data.get("frame_notes", {}),
                summary=data.get("summary", "")
            )

        except Exception as e:
            print(f"  Coherency parse error: {e}")
            return BatchCoherencyResult(
                coherency_score=5.0,
                passed=False,
                summary=f"Parse error: {e}"
            )

    def get_frame_fixes(self, result: BatchCoherencyResult, frame_id: str) -> list[str]:
        """Get fix instructions for a specific frame from coherency issues."""
        fixes = []
        for issue in result.issues:
            if frame_id in issue.frames_affected:
                fixes.append(issue.fix_instruction)
        return fixes


# Convenience function
def check_batch_coherency(
    frames: list[tuple[str, Path, str]],
    scene_context: dict,
    character_refs: list[Path] = None
) -> BatchCoherencyResult:
    """Quick coherency check on a batch of frames."""
    agent = BatchCoherencyAgent()
    return agent.analyze_batch_coherency(frames, scene_context, character_refs)
