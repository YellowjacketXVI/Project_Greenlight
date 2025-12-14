"""
Continuity Weaver - Cross-Scene State Tracking Pattern

An agent that maintains "threads" of continuity across all scenes, tracking:
- Character states (position, emotional state, holding props)
- Location states (time of day, lighting, atmosphere)
- Prop states (introduced, used, position)
- Timeline consistency
- Emotional arc progression

Detects breaks in continuity and generates repair patches.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
import asyncio
import json
import re

from greenlight.core.logging_config import get_logger
from .universal_context import UniversalContext

logger = get_logger("patterns.quality.continuity_weaver")


@dataclass
class CharacterState:
    """State of a character at a point in the story."""
    tag: str
    scene: int
    location: str = ""
    position: str = ""  # standing, sitting, etc.
    emotional_state: str = ""
    holding_props: List[str] = field(default_factory=list)
    last_dialogue: str = ""
    transition_shown: bool = True  # Was transition to this state shown?


@dataclass
class PropState:
    """State of a prop at a point in the story."""
    tag: str
    scene: int
    introduced: bool = False
    used: bool = False
    holder: str = ""  # Character tag holding it
    position: str = ""  # Where it is


@dataclass
class TimelineState:
    """Timeline state at a point in the story."""
    scene: int
    time_of_day: str = ""
    time_index: int = 0  # Relative ordering
    relative_to_previous: str = ""  # "same", "later", "next day", etc.


@dataclass
class ContinuityThread:
    """A thread tracking one element across scenes."""
    thread_type: str  # character, location, prop, timeline, emotional
    element_tag: str
    states: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_state_at_scene(self, scene_num: int) -> Optional[Dict]:
        """Get element state at a specific scene."""
        for state in self.states:
            if state.get('scene') == scene_num:
                return state
        return None
    
    def validate_transition(self, from_scene: int, to_scene: int) -> Optional[str]:
        """Validate transition between scenes, return issue if found."""
        from_state = self.get_state_at_scene(from_scene)
        to_state = self.get_state_at_scene(to_scene)
        
        if not from_state or not to_state:
            return None
        
        if self.thread_type == 'character':
            # Character can't teleport without transition
            from_loc = from_state.get('location', '')
            to_loc = to_state.get('location', '')
            if from_loc and to_loc and from_loc != to_loc:
                if not to_state.get('transition_shown', True):
                    return (f"Character [{self.element_tag}] moved from [{from_loc}] "
                            f"to [{to_loc}] without transition shown")
            
            # Check for impossible physical state changes
            from_pos = from_state.get('position', '')
            to_pos = to_state.get('position', '')
            if from_pos == 'unconscious' and to_pos == 'running':
                return (f"Character [{self.element_tag}] went from unconscious "
                        f"to running without recovery shown")
        
        elif self.thread_type == 'timeline':
            # Time can't go backwards
            from_idx = from_state.get('time_index', 0)
            to_idx = to_state.get('time_index', 0)
            if to_idx < from_idx:
                return f"Timeline regression: Scene {to_scene} occurs before Scene {from_scene}"
        
        elif self.thread_type == 'prop':
            # Prop can't be used before introduction
            if to_state.get('used') and not from_state.get('introduced'):
                return (f"Prop [{self.element_tag}] used in Scene {to_scene} "
                        f"but not introduced before")
            
            # Prop can't teleport between characters
            from_holder = from_state.get('holder', '')
            to_holder = to_state.get('holder', '')
            if from_holder and to_holder and from_holder != to_holder:
                if not to_state.get('transfer_shown', True):
                    return (f"Prop [{self.element_tag}] transferred from [{from_holder}] "
                            f"to [{to_holder}] without handoff shown")
        
        return None


@dataclass
class ContinuityIssue:
    """A continuity issue found during validation."""
    thread_type: str
    element_tag: str
    from_scene: int
    to_scene: int
    description: str
    severity: str = "warning"  # critical, warning, suggestion


@dataclass
class RepairPatch:
    """A patch to repair a continuity issue."""
    issue: ContinuityIssue
    patch_type: str  # add_transition, modify_state, add_dialogue
    target_scene: int
    patch_content: str
    insertion_point: str = ""  # Where to insert the patch


@dataclass
class ContinuityReport:
    """Complete continuity analysis report."""
    threads: List[ContinuityThread]
    issues: List[ContinuityIssue]
    patches: List[RepairPatch]
    continuity_score: float  # 0-1


class ContinuityWeaver:
    """
    Weaves and validates continuity threads across the entire script.
    
    Process:
    1. Extract state threads from each scene
    2. Validate all thread transitions
    3. Generate repair patches for issues
    """
    
    def __init__(self, llm_caller: Callable):
        self.llm_caller = llm_caller
        self.threads: Dict[str, ContinuityThread] = {}
    
    async def weave_threads(
        self,
        scenes: List[Dict[str, Any]],
        world_config: Dict[str, Any],
        pitch: str
    ) -> ContinuityReport:
        """
        Extract and validate all continuity threads from the script.
        
        Args:
            scenes: List of scene dictionaries
            world_config: World configuration
            pitch: Story pitch
            
        Returns:
            ContinuityReport with threads, issues, and patches
        """
        logger.info(f"ContinuityWeaver: Weaving threads across {len(scenes)} scenes...")
        
        # Reset threads
        self.threads = {}
        
        # Phase 1: Extract threads from each scene
        for scene in scenes:
            await self._extract_scene_threads(scene, world_config)
        
        # Phase 2: Validate all thread transitions
        issues = self._validate_all_transitions()
        
        # Phase 3: Generate repair patches for issues
        patches = []
        if issues:
            patches = await self._generate_repair_patches(issues, scenes, world_config)
        
        # Calculate continuity score
        score = self._calculate_score(issues)
        
        logger.info(f"ContinuityWeaver: Found {len(issues)} issues, generated {len(patches)} patches")

        return ContinuityReport(
            threads=list(self.threads.values()),
            issues=issues,
            patches=patches,
            continuity_score=score
        )

    async def _extract_scene_threads(
        self,
        scene: Dict[str, Any],
        world_config: Dict[str, Any]
    ) -> None:
        """Extract continuity state from a single scene."""
        scene_number = scene.get('scene_number', 1)
        scene_content = scene.get('content', str(scene))

        prompt = f"""Analyze this scene for continuity tracking.

SCENE {scene_number}:
{scene_content}

WORLD CONFIG CHARACTERS:
{json.dumps([c.get('tag') for c in world_config.get('characters', [])], indent=2)}

WORLD CONFIG PROPS:
{json.dumps([p.get('tag') for p in world_config.get('props', [])], indent=2)}

Extract the following for each element present:

CHARACTERS (for each character in scene):
- tag: Character tag
- location: Where they are in the scene
- position: Physical state (standing, sitting, lying, etc.)
- emotional_state: Current emotional state
- holding_props: List of prop tags they're holding
- transition_shown: Was their arrival/transition shown? (true/false)

PROPS (for each prop in scene):
- tag: Prop tag
- introduced: Is this the first appearance? (true/false)
- used: Is it actively used? (true/false)
- holder: Character tag holding it (or "none")
- transfer_shown: If holder changed, was handoff shown? (true/false)

TIMELINE:
- time_of_day: morning, afternoon, evening, night
- relative_to_previous: same, later, next_day, flashback

Format as JSON with keys: characters, props, timeline
"""

        response = await self.llm_caller(prompt)
        states = self._parse_thread_states(response, scene_number)

        # Update character threads
        for char_state in states.get('characters', []):
            tag = char_state.get('tag')
            if not tag:
                continue
            if tag not in self.threads:
                self.threads[tag] = ContinuityThread(
                    thread_type='character',
                    element_tag=tag,
                    states=[]
                )
            self.threads[tag].states.append({
                'scene': scene_number,
                **char_state
            })

        # Update prop threads
        for prop_state in states.get('props', []):
            tag = prop_state.get('tag')
            if not tag:
                continue
            if tag not in self.threads:
                self.threads[tag] = ContinuityThread(
                    thread_type='prop',
                    element_tag=tag,
                    states=[]
                )
            self.threads[tag].states.append({
                'scene': scene_number,
                **prop_state
            })

        # Update timeline thread
        timeline = states.get('timeline', {})
        if timeline:
            if 'timeline' not in self.threads:
                self.threads['timeline'] = ContinuityThread(
                    thread_type='timeline',
                    element_tag='timeline',
                    states=[]
                )
            # Calculate time index
            prev_states = self.threads['timeline'].states
            time_index = len(prev_states)
            if timeline.get('relative_to_previous') == 'flashback':
                time_index = max(0, time_index - 2)

            self.threads['timeline'].states.append({
                'scene': scene_number,
                'time_of_day': timeline.get('time_of_day', ''),
                'time_index': time_index,
                'relative_to_previous': timeline.get('relative_to_previous', 'later')
            })

    def _parse_thread_states(self, response: str, scene_number: int) -> Dict[str, Any]:
        """Parse thread states from LLM response."""
        # Try to extract JSON
        json_match = re.search(r'\{[\s\S]*\}', response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: return empty structure
        return {'characters': [], 'props': [], 'timeline': {}}

    def _validate_all_transitions(self) -> List[ContinuityIssue]:
        """Validate all thread transitions."""
        issues = []

        for thread in self.threads.values():
            if len(thread.states) < 2:
                continue

            # Sort states by scene number
            sorted_states = sorted(thread.states, key=lambda s: s.get('scene', 0))

            for i in range(len(sorted_states) - 1):
                from_scene = sorted_states[i].get('scene', 0)
                to_scene = sorted_states[i + 1].get('scene', 0)

                issue_desc = thread.validate_transition(from_scene, to_scene)
                if issue_desc:
                    severity = 'critical' if thread.thread_type == 'timeline' else 'warning'
                    issues.append(ContinuityIssue(
                        thread_type=thread.thread_type,
                        element_tag=thread.element_tag,
                        from_scene=from_scene,
                        to_scene=to_scene,
                        description=issue_desc,
                        severity=severity
                    ))

        return issues

    async def _generate_repair_patches(
        self,
        issues: List[ContinuityIssue],
        scenes: List[Dict[str, Any]],
        world_config: Dict[str, Any]
    ) -> List[RepairPatch]:
        """Generate repair patches for continuity issues."""
        patches = []

        for issue in issues:
            prompt = f"""Generate a repair patch for this continuity issue:

ISSUE:
Type: {issue.thread_type}
Element: {issue.element_tag}
From Scene: {issue.from_scene}
To Scene: {issue.to_scene}
Description: {issue.description}

Suggest a minimal fix. Options:
1. ADD_TRANSITION: Add a brief transition line/paragraph
2. MODIFY_STATE: Modify the state description in one scene
3. ADD_DIALOGUE: Add dialogue that explains the change

Format:
PATCH_TYPE: [ADD_TRANSITION/MODIFY_STATE/ADD_DIALOGUE]
TARGET_SCENE: [scene number to modify]
INSERTION_POINT: [beginning/end/after_beat_X]
PATCH_CONTENT: [the actual content to add/modify]
"""

            response = await self.llm_caller(prompt)
            patch = self._parse_patch(response, issue)
            if patch:
                patches.append(patch)

        return patches

    def _parse_patch(self, response: str, issue: ContinuityIssue) -> Optional[RepairPatch]:
        """Parse repair patch from LLM response."""
        patch_type_match = re.search(r'PATCH_TYPE:\s*(\w+)', response, re.IGNORECASE)
        target_match = re.search(r'TARGET_SCENE:\s*(\d+)', response, re.IGNORECASE)
        insertion_match = re.search(r'INSERTION_POINT:\s*(.+)', response, re.IGNORECASE)
        content_match = re.search(r'PATCH_CONTENT:\s*(.+?)(?=\n\n|$)', response, re.DOTALL | re.IGNORECASE)

        if not patch_type_match or not content_match:
            return None

        return RepairPatch(
            issue=issue,
            patch_type=patch_type_match.group(1).upper(),
            target_scene=int(target_match.group(1)) if target_match else issue.to_scene,
            patch_content=content_match.group(1).strip(),
            insertion_point=insertion_match.group(1).strip() if insertion_match else 'beginning'
        )

    def _calculate_score(self, issues: List[ContinuityIssue]) -> float:
        """Calculate continuity score based on issues."""
        if not issues:
            return 1.0

        # Weight by severity
        penalty = 0.0
        for issue in issues:
            if issue.severity == 'critical':
                penalty += 0.2
            elif issue.severity == 'warning':
                penalty += 0.1
            else:
                penalty += 0.05

        return max(0.0, 1.0 - penalty)
