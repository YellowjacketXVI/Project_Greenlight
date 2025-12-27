"""
Greenlight OmniMind Tool Executor

Provides tool execution capabilities for the OmniMind assistant.
Adapted from Prometheus Assistant with Greenlight-specific integrations.
"""

from __future__ import annotations

import json
import fnmatch
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

from greenlight.core.logging_config import get_logger

logger = get_logger("omni_mind.tools")


class ToolCategory(Enum):
    """Categories of tools."""
    FILE_MANAGEMENT = "file_management"
    PROJECT_INFO = "project_info"
    TAG_REFERENCE = "tag_reference"
    PIPELINE = "pipeline"
    IMAGE = "image"
    TASK = "task"
    CONTENT_MODIFICATION = "content_modification"
    UI_AUTOMATION = "ui_automation"


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    result: Any = None
    error: Optional[str] = None
    tool_name: str = ""
    duration_ms: Optional[float] = None


@dataclass
class ToolDeclaration:
    """Declaration of a tool for LLM function calling."""
    name: str
    description: str
    parameters: Dict[str, Any]
    category: ToolCategory = ToolCategory.FILE_MANAGEMENT


class ToolExecutor:
    """
    Executes tools for the OmniMind assistant.

    Provides sandboxed file operations, project info, tag management,
    pipeline execution, and task management.
    """

    def __init__(self, project_path: Path = None):
        """
        Initialize the tool executor.

        Args:
            project_path: Root path of the current project (sandbox boundary)
        """
        self.project_path = Path(project_path) if project_path else None
        self._tools: Dict[str, Callable] = {}
        self._declarations: List[ToolDeclaration] = []
        self._task_plan: Dict[str, Any] = {}

        # Optional integrations
        self._tag_registry = None
        self._reference_manager = None
        self._story_pipeline = None
        self._shot_pipeline = None

        # New v2 pipeline integrations
        self._story_pipeline_v2 = None
        self._world_bible_pipeline = None
        self._directing_pipeline = None
        self._procedural_generator = None
        self._tag_reference_system = None
        self._context_engine = None

        self._register_tools()

    def set_project(self, project_path: Path) -> None:
        """Set the current project path."""
        self.project_path = Path(project_path) if project_path else None
        logger.info(f"Tool executor project set to: {self.project_path}")

    def set_integrations(
        self,
        tag_registry=None,
        reference_manager=None,
        story_pipeline=None,
        shot_pipeline=None,
        story_pipeline_v2=None,
        world_bible_pipeline=None,
        directing_pipeline=None,
        procedural_generator=None,
        tag_reference_system=None,
        context_engine=None
    ) -> None:
        """Set optional integrations."""
        self._tag_registry = tag_registry
        self._reference_manager = reference_manager
        self._story_pipeline = story_pipeline
        self._shot_pipeline = shot_pipeline
        # New v2 pipelines
        self._story_pipeline_v2 = story_pipeline_v2
        self._world_bible_pipeline = world_bible_pipeline
        self._directing_pipeline = directing_pipeline
        self._procedural_generator = procedural_generator
        self._tag_reference_system = tag_reference_system
        self._context_engine = context_engine

    def _register_tools(self) -> None:
        """Register all available tools."""
        # File management tools
        self._register_tool("list_directory", self._list_directory,
            "List files and subdirectories in a directory within the project.",
            {"path": {"type": "string", "description": "Relative path from project root. Use '.' for root."}},
            ["path"], ToolCategory.FILE_MANAGEMENT)

        self._register_tool("read_file", self._read_file,
            "Read the contents of a text file within the project.",
            {"path": {"type": "string", "description": "Relative path to the file from project root."}},
            ["path"], ToolCategory.FILE_MANAGEMENT)

        self._register_tool("write_file", self._write_file,
            "Write or overwrite content to a file. Creates parent directories if needed.",
            {"path": {"type": "string", "description": "Relative path to the file."},
             "content": {"type": "string", "description": "Content to write."}},
            ["path", "content"], ToolCategory.FILE_MANAGEMENT)

        self._register_tool("append_file", self._append_file,
            "Append content to the end of an existing file.",
            {"path": {"type": "string", "description": "Relative path to the file."},
             "content": {"type": "string", "description": "Content to append."}},
            ["path", "content"], ToolCategory.FILE_MANAGEMENT)

        self._register_tool("delete_file", self._delete_file,
            "Delete a file within the project.",
            {"path": {"type": "string", "description": "Relative path to delete."}},
            ["path"], ToolCategory.FILE_MANAGEMENT)

        self._register_tool("create_directory", self._create_directory,
            "Create a new directory within the project.",
            {"path": {"type": "string", "description": "Relative path for new directory."}},
            ["path"], ToolCategory.FILE_MANAGEMENT)

        self._register_tool("search_files", self._search_files,
            "Search for files by name pattern. Supports wildcards: *.txt, *config*",
            {"pattern": {"type": "string", "description": "Filename pattern to search."},
             "directory": {"type": "string", "description": "Optional: limit to directory."}},
            ["pattern"], ToolCategory.FILE_MANAGEMENT)

        # Project info tools
        self._register_tool("get_project_info", self._get_project_info,
            "Get project structure info: characters, locations, props, key files.",
            {}, [], ToolCategory.PROJECT_INFO)

        self._register_tool("get_project_summary", self._get_project_summary,
            "Get a summary of the project including tag counts and file statistics.",
            {}, [], ToolCategory.PROJECT_INFO)

        # Tag/Reference tools
        self._register_tool("omni_find_related", self._omni_find_related,
            "Find all resources, related tags, and mentions related to a specific tag.",
            {"tag": {"type": "string", "description": "The tag to search for (e.g., 'MARCUS', 'LOC_OFFICE')"}},
            ["tag"], ToolCategory.TAG_REFERENCE)

        self._register_tool("omni_search_tags", self._omni_search_tags,
            "Search for tags by partial name or type.",
            {"query": {"type": "string", "description": "Partial tag name to search for."},
             "tag_type": {"type": "string", "description": "Optional: filter by tag type (character, location, prop)"}},
            [], ToolCategory.TAG_REFERENCE)

        self._register_tool("omni_get_summary", self._omni_get_summary,
            "Get a summary of all tracked tags and resources.",
            {}, [], ToolCategory.TAG_REFERENCE)

        self._register_tool("get_missing_references", self._get_missing_references,
            "Find registered tags that don't have reference images.",
            {}, [], ToolCategory.TAG_REFERENCE)

        # Pipeline tools
        self._register_tool("run_writer", self._run_writer,
            "Run the Writer pipeline to create story documents from a pitch.",
            {"llm": {"type": "string", "description": "LLM to use: 'claude-haiku', 'claude-sonnet', 'gemini-flash'. Default: claude-haiku"},
             "media_type": {"type": "string", "description": "Media type: 'brief', 'short', 'standard', 'extended', 'feature'. Default: brief"},
             "dry_run": {"type": "boolean", "description": "Preview without making changes. Default: false"}},
            [], ToolCategory.PIPELINE)

        self._register_tool("run_director", self._run_director,
            "Run the Director pipeline to create storyboard prompts from story documents. Frame count is determined autonomously.",
            {"llm": {"type": "string", "description": "LLM to use: 'gemini-flash', 'claude-haiku'. Default: gemini-flash"},
             "dry_run": {"type": "boolean", "description": "Preview without making changes. Default: false"}},
            [], ToolCategory.PIPELINE)

        self._register_tool("generate_storyboard", self._generate_storyboard,
            "Generate storyboard images from prompts using AI image models.",
            {"model": {"type": "string", "description": "Image model: 'seedream', 'nano_banana_pro', 'flux_kontext_pro'. Default: seedream"},
             "start_shot": {"type": "string", "description": "Starting shot ID (e.g., '1.1')"},
             "end_shot": {"type": "string", "description": "Ending shot ID (e.g., '2.5')"}},
            [], ToolCategory.PIPELINE)

        self._register_tool("run_full_pipeline_auto", self._run_full_pipeline_auto,
            "Run the complete Writer → Director → Storyboard pipeline with optimal settings for testing. Frame count is determined autonomously.",
            {"llm": {"type": "string", "description": "LLM for Writer/Director: 'claude-haiku', 'gemini-flash'. Default: claude-haiku"},
             "image_model": {"type": "string", "description": "Image model: 'seedream', 'nano_banana_pro'. Default: seedream"},
             "dry_run": {"type": "boolean", "description": "Preview without making changes. Default: false"}},
            [], ToolCategory.PIPELINE)

        # New v2 Pipeline tools
        self._register_tool("run_story_v2", self._run_story_v2,
            "Run the Assembly-based Story Pipeline v2 with 7-agent parallel proposals and 5-judge consensus.",
            {"pipeline_mode": {"type": "string", "description": "Mode: 'assembly' (7+7 agents) or 'classic' (4-layer). Default: assembly"},
             "dry_run": {"type": "boolean", "description": "Preview without making changes. Default: false"}},
            [], ToolCategory.PIPELINE)

        self._register_tool("run_world_bible", self._run_world_bible,
            "Run the World Bible Research Pipeline to generate chunked-per-tag world configuration.",
            {"tag_types": {"type": "array", "description": "Tag types to process: ['character', 'location', 'prop']. Default: all"},
             "dry_run": {"type": "boolean", "description": "Preview without making changes. Default: false"}},
            [], ToolCategory.PIPELINE)

        self._register_tool("run_directing", self._run_directing,
            "Run the Directing Pipeline to transform Script into Visual_Script with frame notations.",
            {"generation_protocol": {"type": "string", "description": "Protocol: 'scene_chunked', 'beat_chunked', or 'expansion'. Default: scene_chunked"},
             "media_type": {"type": "string", "description": "Media type for word caps: 'short', 'brief', 'standard', 'extended', 'feature'. Default: standard"},
             "dry_run": {"type": "boolean", "description": "Preview without making changes. Default: false"}},
            [], ToolCategory.PIPELINE)

        self._register_tool("run_procedural", self._run_procedural,
            "Run the Procedural Generation system for micro-chunked prose generation with state tracking.",
            {"protocol": {"type": "string", "description": "Protocol: 'scene_chunked', 'beat_chunked', or 'expansion'. Default: scene_chunked"},
             "chunk_size": {"type": "integer", "description": "Words per chunk (200-400 optimal). Default: 300"},
             "scene_id": {"type": "string", "description": "Optional: process only this scene ID"},
             "dry_run": {"type": "boolean", "description": "Preview without making changes. Default: false"}},
            [], ToolCategory.PIPELINE)

        self._register_tool("extract_tags", self._extract_tags,
            "Extract and validate tags from content using 10-agent consensus (100% agreement required).",
            {"content": {"type": "string", "description": "Content to extract tags from. If empty, uses current script."},
             "tag_types": {"type": "array", "description": "Tag types to extract: ['character', 'location', 'prop']. Default: all"}},
            [], ToolCategory.TAG_REFERENCE)

        self._register_tool("generate_reference_prompts", self._generate_reference_prompts,
            "Generate reference image prompts for validated tags.",
            {"tags": {"type": "array", "description": "List of tags to generate prompts for. If empty, uses all validated tags."},
             "style_notes": {"type": "string", "description": "Optional style notes to include in prompts."}},
            [], ToolCategory.TAG_REFERENCE)

        self._register_tool("get_pipeline_status", self._get_pipeline_status,
            "Get the status and availability of all pipelines.",
            {}, [], ToolCategory.PIPELINE)

        # Task management tools
        self._register_tool("create_task_plan", self._create_task_plan,
            "Create a structured task plan for a complex goal.",
            {"goal": {"type": "string", "description": "The overall goal to accomplish"},
             "tasks": {"type": "array", "description": "List of tasks with optional subtasks"}},
            ["goal", "tasks"], ToolCategory.TASK)

        self._register_tool("update_task_status", self._update_task_status,
            "Update the status of a task in the current plan.",
            {"task_id": {"type": "string", "description": "The task ID to update"},
             "status": {"type": "string", "description": "New status: not_started, in_progress, complete, failed"}},
            ["task_id", "status"], ToolCategory.TASK)

        self._register_tool("get_task_plan", self._get_task_plan,
            "Get the current task plan and status.",
            {}, [], ToolCategory.TASK)

        # Image analysis tools
        self._register_tool("analyze_image", self._analyze_image,
            "Analyze an image for content, style, characters, and tags.",
            {"path": {"type": "string", "description": "Relative path to the image file."},
             "analysis_type": {"type": "string", "description": "Type: 'full', 'character', 'scene', 'style'. Default: full"}},
            ["path"], ToolCategory.IMAGE)

        self._register_tool("story_analysis_protocol", self._story_analysis_protocol,
            "Perform comprehensive story analysis on a batch of storyboard images (up to 6).",
            {"image_paths": {"type": "array", "items": {"type": "string"}, "description": "List of 1-6 image paths to analyze."},
             "analysis_focus": {"type": "string", "description": "Focus: 'full', 'narrative', 'character_consistency', 'prompt_accuracy', 'visual_style'"},
             "include_prompts": {"type": "boolean", "description": "Cross-reference with prompts. Default: true"},
             "include_story_context": {"type": "boolean", "description": "Load WORLD_BIBLE.json context. Default: true"}},
            ["image_paths"], ToolCategory.IMAGE)

        # Autonomous agent tools (Gemini 2.5 powered)
        self._register_tool("analyze_image_gemini", self._analyze_image_gemini,
            "Analyze an image using Gemini 2.5 for detailed structured analysis with symbolic notation.",
            {"path": {"type": "string", "description": "Relative path to the image file."},
             "analysis_type": {"type": "string", "description": "Type: 'full', 'character', 'scene', 'validation'. Default: full"},
             "expected": {"type": "object", "description": "For validation: expected attributes to check against"}},
            ["path"], ToolCategory.IMAGE)

        self._register_tool("edit_image", self._edit_image,
            "Edit an image using Nano Banana Pro with template prefixes (edit/reangle/recreate).",
            {"source_path": {"type": "string", "description": "Path to the source image to edit."},
             "edit_instruction": {"type": "string", "description": "Natural language edit instruction."},
             "prefix_type": {"type": "string", "description": "Prefix type: 'edit', 'reangle', 'recreate'. Default: edit"},
             "output_path": {"type": "string", "description": "Optional output path. Default: overwrites source."}},
            ["source_path", "edit_instruction"], ToolCategory.IMAGE)

        self._register_tool("autonomous_character_modification", self._autonomous_character_modification,
            "Execute a complete autonomous character modification workflow using Gemini 2.5 for planning.",
            {"character_tag": {"type": "string", "description": "Character tag (e.g., 'CHAR_MEI' or 'MEI')"},
             "modification_description": {"type": "string", "description": "Natural language description of changes (e.g., 'change to African American female with white hair')"},
             "auto_execute": {"type": "boolean", "description": "Automatically execute planned tasks. Default: true"}},
            ["character_tag", "modification_description"], ToolCategory.CONTENT_MODIFICATION)

        self._register_tool("find_frames_by_character", self._find_frames_by_character,
            "Find all storyboard frames containing a specific character.",
            {"character_tag": {"type": "string", "description": "Character tag (e.g., 'CHAR_MEI' or 'MEI')"}},
            ["character_tag"], ToolCategory.PROJECT_INFO)

        self._register_tool("validate_image_changes", self._validate_image_changes,
            "Validate that an image matches expected modifications using Gemini 2.5 analysis.",
            {"image_path": {"type": "string", "description": "Path to the image to validate."},
             "expected_attributes": {"type": "object", "description": "Expected attributes (e.g., {'ethnicity': 'African American', 'hair_color': 'white'})"}},
            ["image_path", "expected_attributes"], ToolCategory.IMAGE)

        # Self-healing tools
        self._register_tool("diagnose_project", self._diagnose_project,
            "Diagnose issues in the project structure, tags, or pipelines.",
            {"target": {"type": "string", "description": "What to diagnose: 'project', 'tags', 'continuity', 'pipelines', 'all'. Default: all"}},
            [], ToolCategory.PROJECT_INFO)

        self._register_tool("auto_fix_issue", self._auto_fix_issue,
            "Automatically fix a diagnosed issue by its ID.",
            {"issue_id": {"type": "string", "description": "The issue ID from diagnose_project"}},
            ["issue_id"], ToolCategory.PROJECT_INFO)

        self._register_tool("run_self_healing", self._run_self_healing,
            "Run the self-healing process to detect and auto-fix issues.",
            {"issue_type": {"type": "string", "description": "Type of issues: 'all', 'structure', 'tags', 'continuity'. Default: all"}},
            [], ToolCategory.PROJECT_INFO)

        self._register_tool("validate_notation", self._validate_notation,
            "Validate scene.frame.camera notation in visual scripts. Format: {scene}.{frame}.c{letter} (e.g., 1.2.cA)",
            {"file_path": {"type": "string", "description": "Path to file to validate. Default: storyboards/visual_script.md"},
             "auto_fix": {"type": "boolean", "description": "Auto-fix old notation format. Default: false"}},
            [], ToolCategory.PROJECT_INFO)

        self._register_tool("parse_notation", self._parse_notation,
            "Parse a scene.frame.camera notation string into components.",
            {"notation": {"type": "string", "description": "Notation to parse (e.g., '1.2.cA', '1.2', or '1')"}},
            ["notation"], ToolCategory.PROJECT_INFO)

        self._register_tool("translate_prompt", self._translate_prompt,
            "Translate a natural language prompt into tool operations.",
            {"prompt": {"type": "string", "description": "Natural language prompt to translate"},
             "auto_execute": {"type": "boolean", "description": "Whether to auto-execute the plan. Default: false"}},
            ["prompt"], ToolCategory.TASK)

        self._register_tool("retrieve_context", self._retrieve_context,
            "Retrieve relevant context using the Agent Retrieval Tool.",
            {"query": {"type": "string", "description": "Natural language query"},
             "scope": {"type": "string", "description": "Scope: 'project', 'world_bible', 'story', 'storyboard', 'tags', 'all'. Default: all"},
             "tags": {"type": "array", "description": "Optional tags to filter by"}},
            ["query"], ToolCategory.TAG_REFERENCE)

        # Test runner tools
        self._register_tool("run_tests", self._run_tests,
            "Run pytest tests. Can run all tests or specific test paths.",
            {"test_path": {"type": "string", "description": "Path to test file or directory. Default: 'tests'"},
             "verbose": {"type": "boolean", "description": "Show verbose output. Default: true"},
             "pattern": {"type": "string", "description": "Test name pattern to match. Default: None"},
             "markers": {"type": "string", "description": "Pytest markers to filter. Default: None"}},
            [], ToolCategory.TASK)

        self._register_tool("list_tests", self._list_tests,
            "List available tests without running them.",
            {"test_path": {"type": "string", "description": "Path to test file or directory. Default: 'tests'"}},
            [], ToolCategory.TASK)

        # Process library tools
        self._register_tool("list_processes", self._list_processes,
            "List all available processes that can be triggered by natural language.",
            {}, [], ToolCategory.TASK)

        self._register_tool("execute_process", self._execute_process,
            "Execute a process by ID or natural language description.",
            {"process_id": {"type": "string", "description": "Process ID or natural language description"},
             "parameters": {"type": "object", "description": "Optional parameters to pass to the process"}},
            ["process_id"], ToolCategory.TASK)

        self._register_tool("run_full_pipeline", self._run_full_pipeline,
            "Run the complete pipeline: Writer followed by Director.",
            {"dry_run": {"type": "boolean", "description": "Preview without making changes. Default: false"}},
            [], ToolCategory.PIPELINE)

        # RAG-based content modification tools
        self._register_tool("modify_content", self._modify_content,
            "Find and modify content across the entire project using RAG search. Updates world bible, scripts, and all documents.",
            {"entity_type": {"type": "string", "description": "Type: 'character', 'location', 'prop', 'tag', 'text'"},
             "entity_name": {"type": "string", "description": "Name of the entity to modify (e.g., 'Mei', 'TEAHOUSE')"},
             "modification_type": {"type": "string", "description": "Type: 'update_description', 'add_trait', 'rename', 'replace_text'"},
             "new_value": {"type": "string", "description": "The new value to apply"},
             "dry_run": {"type": "boolean", "description": "Preview changes without applying. Default: true"}},
            ["entity_type", "entity_name", "modification_type", "new_value"], ToolCategory.TAG_REFERENCE)

        self._register_tool("find_all_occurrences", self._find_all_occurrences,
            "Find all occurrences of an entity across the project using RAG search.",
            {"entity_name": {"type": "string", "description": "Name or tag to search for"},
             "include_context": {"type": "boolean", "description": "Include surrounding context. Default: true"}},
            ["entity_name"], ToolCategory.TAG_REFERENCE)

        self._register_tool("batch_replace", self._batch_replace,
            "Replace text across multiple files in the project.",
            {"search_text": {"type": "string", "description": "Text to search for"},
             "replace_text": {"type": "string", "description": "Text to replace with"},
             "file_pattern": {"type": "string", "description": "File pattern to search in (e.g., '*.md', '*.json'). Default: all"},
             "dry_run": {"type": "boolean", "description": "Preview changes without applying. Default: true"}},
            ["search_text", "replace_text"], ToolCategory.FILE_MANAGEMENT)

        # UI Pointer tools for guiding users
        self._register_tool("point_to_ui", self._point_to_ui,
            "Highlight a UI element with neon green to guide the user. Use this to show users where to click.",
            {"element_id": {"type": "string", "description": "ID of the UI element to highlight (e.g., 'world_bible_step', 'writer_step', 'director_step')"},
             "message": {"type": "string", "description": "Guidance message to show the user"},
             "duration": {"type": "number", "description": "How long to highlight in seconds. Default: 5.0"}},
            ["element_id", "message"], ToolCategory.TASK)

        self._register_tool("list_ui_elements", self._list_ui_elements,
            "List all UI elements that can be highlighted for user guidance.",
            {},
            [], ToolCategory.TASK)

        self._register_tool("unhighlight_all", self._unhighlight_all_ui,
            "Remove all UI highlights.",
            {},
            [], ToolCategory.TASK)

        # UI Automation tools - for OmniMind to operate the UI
        self._register_tool("click_ui_element", self._click_ui_element,
            "Click a UI element (button, menu item). Use list_ui_elements to see available elements.",
            {"element_id": {"type": "string", "description": "ID of the UI element to click"}},
            ["element_id"], ToolCategory.TASK)

        self._register_tool("invoke_ui_action", self._invoke_ui_action,
            "Invoke an action on a UI element (set_value, select, focus).",
            {"element_id": {"type": "string", "description": "ID of the UI element"},
             "action": {"type": "string", "description": "Action: 'click', 'set_value', 'select', 'focus'"},
             "value": {"type": "string", "description": "Value for set_value or select actions"}},
            ["element_id", "action"], ToolCategory.TASK)

        self._register_tool("get_ui_element_state", self._get_ui_element_state,
            "Get the current state of a UI element (text, value, visibility).",
            {"element_id": {"type": "string", "description": "ID of the UI element"}},
            ["element_id"], ToolCategory.TASK)

        self._register_tool("run_ui_test", self._run_ui_test,
            "Run a UI test sequence: launch app, perform actions, capture errors.",
            {"actions": {"type": "array", "items": {"type": "object"}, "description": "List of actions: [{action: 'click', element_id: 'x'}, ...]"},
             "capture_errors": {"type": "boolean", "description": "Capture and return any errors. Default: true"}},
            [], ToolCategory.TASK)

        self._register_tool("capture_terminal_errors", self._capture_terminal_errors,
            "Capture errors from the terminal output of the running app.",
            {"terminal_id": {"type": "integer", "description": "Terminal/process ID to read from"},
             "parse_tracebacks": {"type": "boolean", "description": "Parse Python tracebacks. Default: true"}},
            [], ToolCategory.PROJECT_INFO)

        # Document change tracking tools
        self._register_tool("get_pending_changes", self._get_pending_changes,
            "Get list of documents with unsaved changes. Use this to check what the user has modified.",
            {},
            [], ToolCategory.FILE_MANAGEMENT)

        self._register_tool("save_document_changes", self._save_document_changes,
            "Save changes to modified documents. Call this when user confirms they want to save.",
            {"file_paths": {"type": "array", "items": {"type": "string"}, "description": "Specific files to save. If empty, saves all pending changes."}},
            [], ToolCategory.FILE_MANAGEMENT)

        self._register_tool("revert_document_changes", self._revert_document_changes,
            "Revert documents to their original content. Call this when user wants to undo changes.",
            {"file_paths": {"type": "array", "items": {"type": "string"}, "description": "Specific files to revert. If empty, reverts all pending changes."}},
            [], ToolCategory.FILE_MANAGEMENT)

        # Error reporting and self-healing tools for Augment integration
        self._register_tool("report_error", self._report_error,
            "Report an error with full context for Augment to fix. Generates structured transcript.",
            {"error_message": {"type": "string", "description": "The error message"},
             "error_type": {"type": "string", "description": "Error type (e.g., 'ImportError', 'TypeError')"},
             "source": {"type": "string", "description": "Source of the error (e.g., 'pipeline.writer')"},
             "level": {"type": "string", "description": "Detail level: 'minimal', 'standard', 'full'. Default: standard"},
             "try_self_heal": {"type": "boolean", "description": "Attempt self-healing first. Default: true"}},
            ["error_message"], ToolCategory.PROJECT_INFO)

        self._register_tool("get_error_reports", self._get_error_reports,
            "Get recent error reports for review or Augment handoff.",
            {"limit": {"type": "integer", "description": "Number of reports to return. Default: 10"},
             "export_for_augment": {"type": "boolean", "description": "Format for Augment consumption. Default: true"}},
            [], ToolCategory.PROJECT_INFO)

        self._register_tool("run_self_heal", self._run_self_heal_tool,
            "Run self-healing on a specific error or all pending errors.",
            {"error_id": {"type": "string", "description": "Specific error ID to heal. If empty, heals all pending."}},
            [], ToolCategory.PROJECT_INFO)

        self._register_tool("get_healing_stats", self._get_healing_stats,
            "Get self-healing statistics and success rates.",
            {},
            [], ToolCategory.PROJECT_INFO)

        self._register_tool("export_error_for_augment", self._export_error_for_augment,
            "Export a specific error report in Augment-optimized format for efficient fixing.",
            {"error_id": {"type": "string", "description": "Error ID to export"},
             "level": {"type": "string", "description": "Detail level: 'minimal', 'standard', 'full'. Default: standard"}},
            ["error_id"], ToolCategory.PROJECT_INFO)

        # Image generation tools
        self._register_tool("generate_image", self._generate_image,
            "Generate an image using AI models. Use symbolic notation like @IMG_NANO_BANANA_PRO or nicknames like 'nano banana pro'.",
            {"prompt": {"type": "string", "description": "Description of the image to generate"},
             "model": {"type": "string", "description": "Model to use: nano_banana, nano_banana_pro, seedream, flux_kontext_pro, flux_kontext_max. Default: nano_banana_pro"},
             "output_name": {"type": "string", "description": "Optional filename for output (without extension)"},
             "aspect_ratio": {"type": "string", "description": "Aspect ratio: 1:1, 16:9, 9:16, 4:3, 3:4. Default: 1:1"}},
            ["prompt"], ToolCategory.PROJECT_INFO)

        # Style Core tools
        self._register_tool("get_style_core", self._get_style_core,
            "Get the current Style Core settings (visual style, style notes, lighting, vibe).",
            {}, [], ToolCategory.PROJECT_INFO)

        self._register_tool("set_visual_style", self._set_visual_style,
            "Set the project's visual style type.",
            {"style": {"type": "string", "description": "Visual style: 'live_action', 'anime', 'animation_2d', 'animation_3d', 'mixed_reality'"}},
            ["style"], ToolCategory.CONTENT_MODIFICATION)

        self._register_tool("update_style_notes", self._update_style_notes,
            "Update the project's style notes with custom visual direction.",
            {"notes": {"type": "string", "description": "Style notes describing the visual aesthetic, mood, and look"}},
            ["notes"], ToolCategory.CONTENT_MODIFICATION)

        self._register_tool("suggest_style_notes", self._suggest_style_notes,
            "Generate suggested style notes based on the project's genre, pitch, and visual style.",
            {"include_lighting": {"type": "boolean", "description": "Include lighting suggestions. Default: true"},
             "include_vibe": {"type": "boolean", "description": "Include mood/vibe suggestions. Default: true"}},
            [], ToolCategory.PROJECT_INFO)

        # Shell execution tools for testing and automation
        self._register_tool("execute_shell", self._execute_shell,
            "Execute a shell command. Use for running scripts, tests, or system commands.",
            {"command": {"type": "string", "description": "Shell command to execute"},
             "cwd": {"type": "string", "description": "Working directory. Default: project root"},
             "timeout": {"type": "integer", "description": "Timeout in seconds. Default: 60"}},
            ["command"], ToolCategory.TASK)

        self._register_tool("launch_app", self._launch_app,
            "Launch the Greenlight application for testing. Returns immediately while app runs.",
            {"wait_seconds": {"type": "integer", "description": "Seconds to wait for startup. Default: 5"}},
            [], ToolCategory.TASK)

        self._register_tool("check_imports", self._check_imports,
            "Check if a module can be imported without errors. Useful for validating code changes.",
            {"module_path": {"type": "string", "description": "Module path to check (e.g., 'greenlight.pipelines.directing_pipeline')"}},
            ["module_path"], ToolCategory.PROJECT_INFO)

        self._register_tool("validate_syntax", self._validate_syntax,
            "Validate Python syntax of a file without executing it.",
            {"file_path": {"type": "string", "description": "Path to Python file to validate"}},
            ["file_path"], ToolCategory.PROJECT_INFO)

        # Backdoor UI Automation tools - for OmniMind to control the running app
        self._register_tool("backdoor_ping", self._backdoor_ping,
            "Ping the running Greenlight app to check if it's responsive.",
            {}, [], ToolCategory.UI_AUTOMATION)

        self._register_tool("backdoor_open_project", self._backdoor_open_project,
            "Open a project in the running Greenlight app.",
            {"project_path": {"type": "string", "description": "Path to the project folder (e.g., 'projects/Go for Orchid')"}},
            ["project_path"], ToolCategory.UI_AUTOMATION)

        self._register_tool("backdoor_navigate", self._backdoor_navigate,
            "Navigate to a view in the running Greenlight app.",
            {"view": {"type": "string", "description": "View to navigate to: 'world_bible', 'script', 'storyboard', 'editor'"}},
            ["view"], ToolCategory.UI_AUTOMATION)

        self._register_tool("backdoor_click", self._backdoor_click,
            "Click a UI element in the running Greenlight app.",
            {"element_id": {"type": "string", "description": "ID of the UI element to click (use backdoor_list_ui_elements to see available)"}},
            ["element_id"], ToolCategory.UI_AUTOMATION)

        self._register_tool("backdoor_list_ui_elements", self._backdoor_list_ui_elements,
            "List all registered UI elements in the running Greenlight app.",
            {}, [], ToolCategory.UI_AUTOMATION)

        self._register_tool("backdoor_run_director", self._backdoor_run_director,
            "Open the Director dialog in the running Greenlight app.",
            {"scene_filter": {"type": "string", "description": "Optional: filter to specific scene"}},
            [], ToolCategory.UI_AUTOMATION)

        self._register_tool("backdoor_set_zoom", self._backdoor_set_zoom,
            "Set the storyboard zoom level in the running Greenlight app.",
            {"zoom": {"type": "integer", "description": "Zoom level 0-100 (0=row view, 100=grid view)"}},
            ["zoom"], ToolCategory.UI_AUTOMATION)

        self._register_tool("backdoor_get_errors", self._backdoor_get_errors,
            "Get any cached errors from the running Greenlight app.",
            {}, [], ToolCategory.UI_AUTOMATION)

        self._register_tool("backdoor_run_test_sequence", self._backdoor_run_test_sequence,
            "Run a sequence of UI actions in the running Greenlight app and capture errors.",
            {"actions": {"type": "array", "items": {"type": "object"},
                        "description": "List of actions: [{command: 'open_project', params: {path: '...'}}, {command: 'navigate', params: {view: 'storyboard'}}, ...]"}},
            ["actions"], ToolCategory.UI_AUTOMATION)

        # Character modification tools
        self._register_tool("modify_character", self._modify_character,
            "Modify a character's profile in the world bible. Updates world_config.json and optionally archives/regenerates affected frames.",
            {"character_tag": {"type": "string", "description": "Character tag (e.g., 'CHAR_MEI' or 'MEI')"},
             "field": {"type": "string", "description": "Field to modify: 'name', 'role', 'age', 'ethnicity', 'backstory', 'visual_appearance', 'costume', 'psychology', 'personality', 'speech_style', 'physicality'"},
             "new_value": {"type": "string", "description": "New value for the field"},
             "regenerate_frames": {"type": "boolean", "description": "Regenerate storyboard frames featuring this character. Default: false"},
             "archive_old_frames": {"type": "boolean", "description": "Archive old frames before regenerating. Default: true"}},
            ["character_tag", "field", "new_value"], ToolCategory.CONTENT_MODIFICATION)

        self._register_tool("archive_character_frames", self._archive_character_frames,
            "Archive all storyboard frames featuring a specific character.",
            {"character_tag": {"type": "string", "description": "Character tag (e.g., 'CHAR_MEI' or 'MEI')"},
             "archive_reason": {"type": "string", "description": "Reason for archiving (e.g., 'character redesign')"}},
            ["character_tag"], ToolCategory.CONTENT_MODIFICATION)

        self._register_tool("regenerate_character_frames", self._regenerate_character_frames,
            "Regenerate all storyboard frames featuring a specific character using updated profile.",
            {"character_tag": {"type": "string", "description": "Character tag (e.g., 'CHAR_MEI' or 'MEI')"},
             "use_reference": {"type": "boolean", "description": "Use character reference images. Default: true"}},
            ["character_tag"], ToolCategory.CONTENT_MODIFICATION)

        # Generic content modification tools (for autonomous agent)
        self._register_tool("modify_content", self._modify_content,
            "Modify content in project files. Supports characters, locations, props.",
            {"entity_type": {"type": "string", "description": "Type: 'character', 'location', 'prop'"},
             "entity_name": {"type": "string", "description": "Name or tag of the entity"},
             "modification_type": {"type": "string", "description": "Type: 'update', 'add', 'remove'"},
             "new_value": {"type": "object", "description": "New values as key-value pairs"}},
            ["entity_type", "entity_name", "new_value"], ToolCategory.CONTENT_MODIFICATION)

        self._register_tool("find_all_occurrences", self._find_all_occurrences,
            "Find all occurrences of an entity across project files.",
            {"entity_type": {"type": "string", "description": "Type: 'character', 'location', 'prop', 'tag'"},
             "entity_name": {"type": "string", "description": "Name or tag to search for"}},
            ["entity_type", "entity_name"], ToolCategory.PROJECT_INFO)

        self._register_tool("generate_character_reference", self._generate_character_reference,
            "Generate a new reference image for a character using their updated profile.",
            {"character_tag": {"type": "string", "description": "Character tag (e.g., 'CHAR_MEI')"},
             "prompt_override": {"type": "string", "description": "Optional custom prompt. Default: auto-generate from profile"},
             "model": {"type": "string", "description": "Image model. Default: nano_banana_pro"}},
            ["character_tag"], ToolCategory.IMAGE)

        # Storyboard frame selection tools (backdoor)
        self._register_tool("select_storyboard_frames", self._select_storyboard_frames,
            "Select specific storyboard frames by ID for batch operations.",
            {"frame_ids": {"type": "array", "items": {"type": "string"}, "description": "List of frame IDs to select (e.g., ['1.1', '1.2', '2.3'])"},
             "clear_existing": {"type": "boolean", "description": "Clear existing selection first. Default: true"}},
            ["frame_ids"], ToolCategory.UI_AUTOMATION)

        self._register_tool("regenerate_selected_frames", self._regenerate_selected_frames,
            "Regenerate all currently selected storyboard frames.",
            {"use_references": {"type": "boolean", "description": "Use reference images. Default: true"},
             "model": {"type": "string", "description": "Image model to use. Default: project default"}},
            [], ToolCategory.UI_AUTOMATION)

        self._register_tool("get_selected_frames", self._get_selected_frames,
            "Get the list of currently selected storyboard frames.",
            {}, [], ToolCategory.UI_AUTOMATION)

        self._register_tool("regenerate_frames_by_character", self._regenerate_frames_by_character,
            "Regenerate all storyboard frames containing a specific character using their key reference image.",
            {"character_tag": {"type": "string", "description": "Character tag (e.g., 'CHAR_MEI')"},
             "model": {"type": "string", "description": "Image model. Default: seedream"}},
            ["character_tag"], ToolCategory.IMAGE)

        self._register_tool("regenerate_single_frame", self._regenerate_single_frame,
            "Regenerate a single storyboard frame by its frame_id.",
            {"frame_id": {"type": "string", "description": "Frame ID (e.g., '1.3')"},
             "model": {"type": "string", "description": "Image model. Default: seedream"}},
            ["frame_id"], ToolCategory.IMAGE)

        self._register_tool("continuity_check", self._continuity_check,
            "Analyze storyboard frames for continuity issues using Gemini 2.5 multi-image analysis.",
            {"user_request": {"type": "string", "description": "Natural language request (e.g., 'frame 1.3 seems weird')"},
             "auto_fix": {"type": "boolean", "description": "Automatically fix issues and regenerate. Default: true"}},
            ["user_request"], ToolCategory.PROJECT_INFO)

        # =========================================================================
        # PROJECT LIFECYCLE MANAGEMENT TOOLS
        # =========================================================================

        self._register_tool("log_error_pattern", self._log_error_pattern,
            "Log an error pattern and its solution to the .health directory for learning.",
            {"error_type": {"type": "string", "description": "Type of error (e.g., 'ImportError', 'AttributeError', 'TclError')"},
             "error_message": {"type": "string", "description": "The error message or pattern"},
             "solution": {"type": "string", "description": "The solution that fixed the error"},
             "context": {"type": "string", "description": "Additional context about when this error occurs"}},
            ["error_type", "error_message", "solution"], ToolCategory.PROJECT_INFO)

        self._register_tool("get_error_patterns", self._get_error_patterns,
            "Get logged error patterns and their solutions for self-healing reference.",
            {"error_type": {"type": "string", "description": "Filter by error type. Default: all"}},
            [], ToolCategory.PROJECT_INFO)

        self._register_tool("run_project_lifecycle", self._run_project_lifecycle,
            "Run the complete project lifecycle: Writer → Director → Image Generation.",
            {"stages": {"type": "array", "items": {"type": "string"}, "description": "Stages to run: ['writer', 'director', 'images']. Default: all"},
             "dry_run": {"type": "boolean", "description": "Preview without executing. Default: false"},
             "auto_heal": {"type": "boolean", "description": "Automatically attempt to fix errors. Default: true"}},
            [], ToolCategory.PIPELINE)

        self._register_tool("get_project_status", self._get_project_status,
            "Get comprehensive project status including pipeline progress, errors, and health.",
            {}, [], ToolCategory.PROJECT_INFO)

        self._register_tool("self_heal_project", self._self_heal_project,
            "Run self-healing diagnostics and auto-fix common issues.",
            {"target": {"type": "string", "description": "What to heal: 'structure', 'tags', 'continuity', 'all'. Default: all"},
             "auto_fix": {"type": "boolean", "description": "Automatically apply fixes. Default: true"}},
            [], ToolCategory.PROJECT_INFO)

        self._register_tool("create_task", self._create_task,
            "Create a task for OmniMind to track and execute.",
            {"title": {"type": "string", "description": "Task title"},
             "description": {"type": "string", "description": "Task description"},
             "priority": {"type": "string", "description": "Priority: 'critical', 'high', 'medium', 'low'. Default: medium"},
             "category": {"type": "string", "description": "Category: 'pipeline', 'fix', 'generate', 'review'. Default: pipeline"}},
            ["title", "description"], ToolCategory.TASK)

        self._register_tool("list_tasks", self._list_tasks,
            "List all pending tasks for the current project.",
            {"status": {"type": "string", "description": "Filter by status: 'pending', 'in_progress', 'completed', 'failed', 'all'. Default: pending"}},
            [], ToolCategory.TASK)

        self._register_tool("execute_task", self._execute_task,
            "Execute a specific task by ID.",
            {"task_id": {"type": "string", "description": "The task ID to execute"}},
            ["task_id"], ToolCategory.TASK)

        self._register_tool("generate_health_report", self._generate_health_report,
            "Generate and save a comprehensive health report for the project.",
            {}, [], ToolCategory.PROJECT_INFO)

        # =========================================================================
        # END-TO-END PIPELINE TOOLS (OmniMind Autonomous Execution)
        # =========================================================================

        self._register_tool("run_e2e_pipeline", self._run_e2e_pipeline,
            "Run complete end-to-end pipeline: Writer → Director → Reference Images → Storyboard. Uses Claude Haiku 4.5 for text and Seedream 4.5 for images. Frame count is determined autonomously.",
            {"llm": {"type": "string", "description": "LLM: 'claude-haiku-4.5', 'claude-opus-4.5', 'gemini-flash'. Default: claude-haiku-4.5"},
             "image_model": {"type": "string", "description": "Image model: 'seedream', 'nano_banana_pro'. Default: seedream"},
             "generate_references": {"type": "boolean", "description": "Generate reference images for tags. Default: true"},
             "dry_run": {"type": "boolean", "description": "Preview without executing. Default: false"}},
            [], ToolCategory.PIPELINE)

        self._register_tool("generate_all_reference_images", self._generate_all_reference_images,
            "Generate reference images for all extracted tags (characters, locations, props).",
            {"tag_types": {"type": "array", "description": "Tag types: ['character', 'location', 'prop']. Default: all"},
             "model": {"type": "string", "description": "Image model: 'seedream', 'nano_banana_pro'. Default: nano_banana_pro"},
             "overwrite": {"type": "boolean", "description": "Overwrite existing references. Default: false"}},
            [], ToolCategory.IMAGE)

        self._register_tool("wait_for_pipeline", self._wait_for_pipeline,
            "Wait for a running pipeline to complete. Polls status until done or timeout.",
            {"pipeline_name": {"type": "string", "description": "Pipeline: 'writer', 'director', 'storyboard', 'any'"},
             "timeout_seconds": {"type": "integer", "description": "Max wait time in seconds. Default: 300"}},
            ["pipeline_name"], ToolCategory.PIPELINE)

        self._register_tool("get_e2e_pipeline_status", self._get_e2e_pipeline_status,
            "Get detailed status of the end-to-end pipeline execution.",
            {}, [], ToolCategory.PIPELINE)

        # =========================================================================
        # SELF-CORRECTION TOOLS (Autonomous Error Detection and Fixing)
        # =========================================================================

        self._register_tool("detect_missing_characters", self._detect_missing_characters,
            "Detect consensus-approved character tags that are missing from world_config.json.",
            {}, [], ToolCategory.PIPELINE)

        self._register_tool("fix_missing_characters", self._fix_missing_characters,
            "Automatically generate and insert missing character profiles into world_config.json based on story context.",
            {"missing_tags": {"type": "array", "description": "List of missing character tags to fix. If empty, auto-detects."},
             "dry_run": {"type": "boolean", "description": "Preview without making changes. Default: false"},
             "llm_provider": {"type": "string", "description": "LLM provider: 'gemini' (default), 'anthropic', or 'grok'"},
             "llm_model": {"type": "string", "description": "Specific model ID. Uses provider default if not specified."}},
            [], ToolCategory.PIPELINE)

        self._register_tool("validate_world_config", self._validate_world_config,
            "Validate that all consensus-approved tags have corresponding entries in world_config.json.",
            {}, [], ToolCategory.PIPELINE)

    def _register_tool(
        self,
        name: str,
        handler: Callable,
        description: str,
        properties: Dict[str, Any],
        required: List[str],
        category: ToolCategory
    ) -> None:
        """Register a tool with its handler and declaration."""
        self._tools[name] = handler
        self._declarations.append(ToolDeclaration(
            name=name,
            description=description,
            parameters={
                "type": "object",
                "properties": properties,
                "required": required
            },
            category=category
        ))

    def get_declarations(self) -> List[Dict[str, Any]]:
        """Get tool declarations for LLM function calling."""
        return [
            {
                "name": d.name,
                "description": d.description,
                "parameters": d.parameters
            }
            for d in self._declarations
        ]

    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a tool by name with given arguments."""
        import time
        start = time.time()

        if tool_name not in self._tools:
            return ToolResult(
                success=False,
                error=f"Unknown tool: {tool_name}",
                tool_name=tool_name
            )

        try:
            result = self._tools[tool_name](**kwargs)
            duration = (time.time() - start) * 1000
            return ToolResult(
                success=True,
                result=result,
                tool_name=tool_name,
                duration_ms=duration
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error(f"Tool {tool_name} failed: {e}")
            return ToolResult(
                success=False,
                error=str(e),
                tool_name=tool_name,
                duration_ms=duration
            )

    def _validate_path(self, path: str) -> Path:
        """Validate and resolve a path within the project sandbox."""
        if not self.project_path:
            raise ValueError("No project loaded")

        resolved = (self.project_path / path).resolve()

        # Security check - ensure path is within project
        try:
            resolved.relative_to(self.project_path.resolve())
        except ValueError:
            raise ValueError(f"Path '{path}' is outside project boundary")

        return resolved

    # =========================================================================
    #  FILE MANAGEMENT TOOLS
    # =========================================================================

    def _list_directory(self, path: str = ".") -> Dict[str, Any]:
        """List files and subdirectories in a directory."""
        resolved = self._validate_path(path)

        if not resolved.exists():
            return {"error": f"Directory not found: {path}"}

        if not resolved.is_dir():
            return {"error": f"Not a directory: {path}"}

        files = []
        dirs = []

        for item in sorted(resolved.iterdir()):
            if item.name.startswith('.'):
                continue
            if item.is_dir():
                dirs.append(item.name + "/")
            else:
                files.append({
                    "name": item.name,
                    "size": item.stat().st_size
                })

        return {
            "path": path,
            "directories": dirs,
            "files": files,
            "total_items": len(dirs) + len(files)
        }

    def _read_file(self, path: str) -> Dict[str, Any]:
        """Read the contents of a text file."""
        resolved = self._validate_path(path)

        if not resolved.exists():
            return {"error": f"File not found: {path}"}

        if not resolved.is_file():
            return {"error": f"Not a file: {path}"}

        try:
            content = resolved.read_text(encoding='utf-8')
            return {
                "path": path,
                "content": content,
                "size": len(content),
                "lines": content.count('\n') + 1
            }
        except UnicodeDecodeError:
            return {"error": f"Cannot read binary file: {path}"}

    def _write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write content to a file."""
        resolved = self._validate_path(path)

        # Create parent directories if needed
        resolved.parent.mkdir(parents=True, exist_ok=True)

        resolved.write_text(content, encoding='utf-8')

        return {
            "path": path,
            "success": True,
            "size": len(content),
            "message": f"Wrote {len(content)} bytes to {path}"
        }

    def _append_file(self, path: str, content: str) -> Dict[str, Any]:
        """Append content to a file."""
        resolved = self._validate_path(path)

        if not resolved.exists():
            return {"error": f"File not found: {path}"}

        with open(resolved, 'a', encoding='utf-8') as f:
            f.write(content)

        return {
            "path": path,
            "success": True,
            "appended": len(content),
            "message": f"Appended {len(content)} bytes to {path}"
        }

    def _delete_file(self, path: str) -> Dict[str, Any]:
        """Delete a file."""
        resolved = self._validate_path(path)

        if not resolved.exists():
            return {"error": f"File not found: {path}"}

        if not resolved.is_file():
            return {"error": f"Not a file (use delete_directory for directories): {path}"}

        resolved.unlink()

        return {
            "path": path,
            "success": True,
            "message": f"Deleted {path}"
        }

    def _create_directory(self, path: str) -> Dict[str, Any]:
        """Create a directory."""
        resolved = self._validate_path(path)

        if resolved.exists():
            return {"error": f"Path already exists: {path}"}

        resolved.mkdir(parents=True, exist_ok=True)

        return {
            "path": path,
            "success": True,
            "message": f"Created directory {path}"
        }

    def _search_files(self, pattern: str, directory: str = ".") -> Dict[str, Any]:
        """Search for files by pattern."""
        resolved = self._validate_path(directory)

        if not resolved.exists():
            return {"error": f"Directory not found: {directory}"}

        matches = []
        for item in resolved.rglob("*"):
            if item.is_file() and fnmatch.fnmatch(item.name, pattern):
                rel_path = item.relative_to(self.project_path)
                matches.append(str(rel_path))

        return {
            "pattern": pattern,
            "directory": directory,
            "matches": matches,
            "count": len(matches)
        }

    # =========================================================================
    #  PROJECT INFO TOOLS
    # =========================================================================

    def _get_project_info(self) -> Dict[str, Any]:
        """Get project structure information."""
        if not self.project_path:
            return {"error": "No project loaded"}

        info = {
            "name": self.project_path.name,
            "path": str(self.project_path),
            "structure": {}
        }

        # Check for key directories
        key_dirs = ["world_bible", "story_documents", "storyboard_prompts",
                    "storyboard_images", "references"]

        for dir_name in key_dirs:
            dir_path = self.project_path / dir_name
            if dir_path.exists():
                file_count = sum(1 for f in dir_path.rglob("*") if f.is_file())
                info["structure"][dir_name] = {"exists": True, "file_count": file_count}
            else:
                info["structure"][dir_name] = {"exists": False}

        # Check for key files
        key_files = ["WORLD_BIBLE.json", "pitch.md", "style_guide.md"]
        info["key_files"] = {}

        for file_name in key_files:
            # Check in root and world_bible
            for check_path in [self.project_path / file_name,
                               self.project_path / "world_bible" / file_name]:
                if check_path.exists():
                    info["key_files"][file_name] = str(check_path.relative_to(self.project_path))
                    break

        return info

    def _get_project_summary(self) -> Dict[str, Any]:
        """Get a summary of the project."""
        if not self.project_path:
            return {"error": "No project loaded"}

        summary = {
            "name": self.project_path.name,
            "tags": {"total": 0, "by_category": {}},
            "files": {"total": 0, "by_type": {}},
            "references": {"total": 0, "missing": []}
        }

        # Count tags from registry
        if self._tag_registry:
            all_tags = self._tag_registry.get_all_tags()
            summary["tags"]["total"] = len(all_tags)

            by_category = {}
            for tag in all_tags:
                cat = tag.category.value if hasattr(tag, 'category') else 'unknown'
                by_category[cat] = by_category.get(cat, 0) + 1
            summary["tags"]["by_category"] = by_category

        # Count files by type
        by_type = {}
        total_files = 0
        for item in self.project_path.rglob("*"):
            if item.is_file() and not item.name.startswith('.'):
                ext = item.suffix.lower() or 'no_extension'
                by_type[ext] = by_type.get(ext, 0) + 1
                total_files += 1

        summary["files"]["total"] = total_files
        summary["files"]["by_type"] = by_type

        # Check for missing references
        if self._reference_manager:
            missing = self._reference_manager.get_missing_references()
            summary["references"]["missing"] = missing
            summary["references"]["total"] = summary["tags"]["total"] - len(missing)

        return summary

    # =========================================================================
    #  TAG/REFERENCE TOOLS
    # =========================================================================

    def _omni_find_related(self, tag: str) -> Dict[str, Any]:
        """Find all resources related to a tag."""
        if not self.project_path:
            return {"error": "No project loaded"}

        result = {
            "tag": tag,
            "files_mentioning": [],
            "related_tags": [],
            "references": []
        }

        # Search for tag mentions in text files
        tag_pattern = f"[{tag}]"
        for item in self.project_path.rglob("*"):
            if item.is_file() and item.suffix in ['.txt', '.md', '.json']:
                try:
                    content = item.read_text(encoding='utf-8')
                    if tag_pattern in content or tag in content:
                        result["files_mentioning"].append(
                            str(item.relative_to(self.project_path))
                        )
                except:
                    pass

        # Get related tags from registry
        if self._tag_registry:
            tag_info = self._tag_registry.get_tag(tag)
            if tag_info and hasattr(tag_info, 'related_tags'):
                result["related_tags"] = list(tag_info.related_tags)

        # Get reference images
        if self._reference_manager:
            refs = self._reference_manager.scan_references(tag)
            result["references"] = [str(r.path) for r in refs]

        return result

    def _omni_search_tags(self, query: str = "", tag_type: str = None) -> Dict[str, Any]:
        """Search for tags by partial name or type."""
        if not self._tag_registry:
            return {"error": "Tag registry not available"}

        all_tags = self._tag_registry.get_all_tags()
        matches = []

        for tag in all_tags:
            # Filter by type if specified
            if tag_type:
                cat = tag.category.value if hasattr(tag, 'category') else ''
                if tag_type.lower() not in cat.lower():
                    continue

            # Filter by query if specified
            if query:
                if query.lower() not in tag.name.lower():
                    continue

            matches.append({
                "name": tag.name,
                "category": tag.category.value if hasattr(tag, 'category') else 'unknown',
                "aliases": list(tag.aliases) if hasattr(tag, 'aliases') else []
            })

        return {
            "query": query,
            "tag_type": tag_type,
            "matches": matches,
            "count": len(matches)
        }

    def _omni_get_summary(self) -> Dict[str, Any]:
        """Get a summary of all tracked tags and resources."""
        return self._get_project_summary()

    def _get_missing_references(self) -> Dict[str, Any]:
        """Find tags without reference images."""
        if not self._reference_manager:
            return {"error": "Reference manager not available"}

        missing = self._reference_manager.get_missing_references()

        return {
            "missing_references": missing,
            "count": len(missing),
            "message": f"Found {len(missing)} tags without reference images"
        }
    # =========================================================================
    #  PIPELINE TOOLS
    # =========================================================================

    def _run_writer(self, llm: str = "claude-haiku", media_type: str = "brief", dry_run: bool = False) -> Dict[str, Any]:
        """Run the Writer pipeline via backdoor (Assembly mode with 7 agents + 5 judges).

        Args:
            llm: LLM to use - 'claude-haiku', 'claude-sonnet', 'gemini-flash'. Default: claude-haiku
            media_type: Media type - 'brief', 'short', 'standard', 'extended', 'feature'. Default: brief
            dry_run: Preview without making changes
        """
        if not self.project_path:
            return {"error": "No project loaded"}

        # Check for pitch file
        pitch_path = self.project_path / "world_bible" / "pitch.md"
        if not pitch_path.exists():
            pitch_path = self.project_path / "pitch.md"

        if not pitch_path.exists():
            return {"error": "No pitch.md file found. Create a pitch first."}

        if dry_run:
            return {
                "dry_run": True,
                "pitch_file": str(pitch_path.relative_to(self.project_path)),
                "llm": llm,
                "media_type": media_type,
                "message": f"Would run Writer pipeline with LLM={llm}, media_type={media_type}"
            }

        try:
            # Use backdoor to run via UI
            from greenlight.omni_mind.backdoor import BackdoorClient
            client = BackdoorClient()

            result = client.send_command("run_writer", {
                "auto_run": True,
                "llm": llm,
                "media_type": media_type,
                "visual_style": "live_action"
            })

            if result.get("success"):
                return {
                    "success": True,
                    "message": f"Writer pipeline started via backdoor (llm={llm}, media_type={media_type})",
                    "note": "Pipeline running in background. Check pipeline panel for progress."
                }
            else:
                return {"error": result.get("error", "Unknown error")}

        except Exception as e:
            logger.error(f"Writer pipeline failed: {e}")
            return {"error": f"Writer pipeline failed: {e}"}

    def _run_director(self, llm: str = "gemini-flash", dry_run: bool = False) -> Dict[str, Any]:
        """Run the Director pipeline via backdoor.

        Args:
            llm: LLM to use - 'gemini-flash', 'claude-haiku'. Default: gemini-flash
            dry_run: Preview without making changes

        Note: Frame count is determined autonomously by the pipeline.
        """
        if not self.project_path:
            return {"error": "No project loaded"}

        # Check for script
        script_path = self.project_path / "scripts" / "script.md"
        if not script_path.exists():
            return {"error": "No script.md found. Run Writer first."}

        if dry_run:
            return {
                "dry_run": True,
                "script_file": str(script_path.relative_to(self.project_path)),
                "llm": llm,
                "message": f"Would run Director pipeline with LLM={llm} (frame count determined autonomously)"
            }

        try:
            # Use backdoor to run via UI
            from greenlight.omni_mind.backdoor import BackdoorClient
            client = BackdoorClient()

            result = client.send_command("run_director", {
                "auto_run": True,
                "llm": llm
            })

            if result.get("success"):
                return {
                    "success": True,
                    "message": f"Director pipeline started via backdoor (llm={llm}, frame count autonomous)",
                    "note": "Pipeline running in background. Check pipeline panel for progress."
                }
            else:
                return {"error": result.get("error", "Unknown error")}

        except Exception as e:
            return {"error": f"Director pipeline failed: {e}"}

    def _generate_storyboard(
        self,
        model: str = "seedream",
        start_shot: str = None,
        end_shot: str = None
    ) -> Dict[str, Any]:
        """Generate storyboard images via backdoor.

        Args:
            model: Image model - 'seedream', 'nano_banana_pro', 'flux_kontext_pro'. Default: seedream
            start_shot: Starting shot ID (e.g., '1.1')
            end_shot: Ending shot ID (e.g., '2.5')
        """
        if not self.project_path:
            return {"error": "No project loaded"}

        # Check for prompts
        prompts_path = self.project_path / "storyboard_output" / "prompts" / "shot_prompts.json"
        if not prompts_path.exists():
            prompts_path = self.project_path / "storyboards" / "storyboard_prompts.json"

        if not prompts_path.exists():
            return {"error": "No storyboard prompts found. Run Director first."}

        try:
            # Use backdoor to run via UI
            from greenlight.omni_mind.backdoor import BackdoorClient
            client = BackdoorClient()

            result = client.send_command("run_storyboard", {
                "model": model,
                "start_shot": start_shot,
                "end_shot": end_shot
            })

            if result.get("success"):
                return {
                    "success": True,
                    "message": f"Storyboard generation started via backdoor (model={model})",
                    "note": "Generation running in background. Check storyboard view for progress."
                }
            else:
                return {"error": result.get("error", "Unknown error")}

        except Exception as e:
            return {"error": f"Storyboard generation failed: {e}"}

    def _run_full_pipeline_auto(
        self,
        llm: str = "claude-haiku",
        image_model: str = "seedream",
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Run the complete Writer → Director → Storyboard pipeline with optimal settings.

        Args:
            llm: LLM for Writer/Director - 'claude-haiku', 'gemini-flash'. Default: claude-haiku
            image_model: Image model - 'seedream', 'nano_banana_pro'. Default: seedream
            dry_run: Preview without making changes

        Note: Frame count is determined autonomously by the Director pipeline.
        """
        if not self.project_path:
            return {"error": "No project loaded"}

        # Check for pitch file
        pitch_path = self.project_path / "world_bible" / "pitch.md"
        if not pitch_path.exists():
            pitch_path = self.project_path / "pitch.md"

        if not pitch_path.exists():
            return {"error": "No pitch.md file found. Create a pitch first."}

        if dry_run:
            return {
                "dry_run": True,
                "pitch_file": str(pitch_path.relative_to(self.project_path)),
                "llm": llm,
                "image_model": image_model,
                "stages": ["Writer", "Director", "Storyboard"],
                "message": f"Would run full pipeline: Writer({llm}, brief) → Director({llm}, autonomous frames) → Storyboard({image_model})"
            }

        try:
            from greenlight.omni_mind.backdoor import BackdoorClient
            client = BackdoorClient()

            # Start Writer pipeline
            logger.info(f"Starting full pipeline: Writer → Director → Storyboard")
            logger.info(f"  LLM: {llm}, Image Model: {image_model}")

            writer_result = client.send_command("run_writer", {
                "auto_run": True,
                "llm": llm,
                "media_type": "brief",
                "visual_style": "live_action"
            })

            if not writer_result.get("success"):
                return {"error": f"Writer failed: {writer_result.get('error')}"}

            return {
                "success": True,
                "message": "Full pipeline initiated",
                "stages": {
                    "writer": {"status": "started", "llm": llm, "media_type": "brief"},
                    "director": {"status": "pending", "llm": llm, "frame_count": "autonomous"},
                    "storyboard": {"status": "pending", "model": image_model}
                },
                "note": "Writer started. Director and Storyboard will need to be triggered after Writer completes. Use run_director and generate_storyboard tools."
            }

        except Exception as e:
            logger.error(f"Full pipeline failed: {e}")
            return {"error": f"Full pipeline failed: {e}"}

    # =========================================================================
    #  V2 PIPELINE TOOLS
    # =========================================================================

    def _run_story_v2(
        self,
        pipeline_mode: str = "assembly",
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Run the Assembly-based Story Pipeline v2."""
        if not self.project_path:
            return {"error": "No project loaded"}

        if not self._story_pipeline_v2:
            return {"error": "Story Pipeline v2 not available. Ensure it's initialized."}

        # Check for pitch file
        pitch_path = self.project_path / "world_bible" / "pitch.md"
        if not pitch_path.exists():
            pitch_path = self.project_path / "pitch.md"

        if not pitch_path.exists():
            return {"error": "No pitch.md file found. Create a pitch first."}

        if dry_run:
            return {
                "dry_run": True,
                "pipeline_mode": pipeline_mode,
                "pitch_file": str(pitch_path.relative_to(self.project_path)),
                "message": f"Would run Story Pipeline v2 in {pipeline_mode} mode"
            }

        try:
            pitch_content = pitch_path.read_text(encoding='utf-8')
            # Run the v2 pipeline
            import asyncio
            result = asyncio.run(self._story_pipeline_v2.run(
                pitch_content,
                context={"pipeline_mode": pipeline_mode}
            ))

            return {
                "success": result.status.value == "completed" if hasattr(result, 'status') else True,
                "pipeline_mode": pipeline_mode,
                "message": "Story Pipeline v2 completed",
                "output_file": "scripts/script.md"
            }
        except Exception as e:
            return {"error": f"Story Pipeline v2 failed: {e}"}

    def _run_world_bible(
        self,
        tag_types: List[str] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Run the World Bible Research Pipeline."""
        if not self.project_path:
            return {"error": "No project loaded"}

        if not self._world_bible_pipeline:
            return {"error": "World Bible Pipeline not available. Ensure it's initialized."}

        tag_types = tag_types or ["character", "location", "prop"]

        # Check for pitch file
        pitch_path = self.project_path / "world_bible" / "pitch.md"
        if not pitch_path.exists():
            pitch_path = self.project_path / "pitch.md"

        if not pitch_path.exists():
            return {"error": "No pitch.md file found. Create a pitch first."}

        if dry_run:
            return {
                "dry_run": True,
                "tag_types": tag_types,
                "pitch_file": str(pitch_path.relative_to(self.project_path)),
                "message": f"Would run World Bible Pipeline for tag types: {tag_types}"
            }

        try:
            pitch_content = pitch_path.read_text(encoding='utf-8')
            import asyncio
            result = asyncio.run(self._world_bible_pipeline.run(
                pitch_content,
                context={"tag_types": tag_types}
            ))

            return {
                "success": result.status.value == "completed" if hasattr(result, 'status') else True,
                "tag_types": tag_types,
                "message": "World Bible Pipeline completed",
                "output_file": "world_bible/world_config.json"
            }
        except Exception as e:
            return {"error": f"World Bible Pipeline failed: {e}"}

    def _run_directing(
        self,
        generation_protocol: str = "scene_chunked",
        media_type: str = "standard",
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Run the Directing Pipeline."""
        if not self.project_path:
            return {"error": "No project loaded"}

        # Check for script - only use scripts/script.md
        script_path = self.project_path / "scripts" / "script.md"
        if not script_path.exists():
            return {"error": "No script found. Run Writer Pipeline first to create scripts/script.md"}

        if dry_run:
            return {
                "dry_run": True,
                "generation_protocol": generation_protocol,
                "media_type": media_type,
                "script_file": str(script_path.relative_to(self.project_path)),
                "message": f"Would run Directing Pipeline with {generation_protocol} protocol"
            }

        try:
            import asyncio
            from greenlight.core.config import get_config
            from greenlight.llm import LLMManager
            from greenlight.pipelines.directing_pipeline import DirectingPipeline, DirectingInput

            logger.info("Creating Directing pipeline on-demand...")

            # Load script content
            script_content = script_path.read_text(encoding='utf-8')

            # Load project config
            config_path = self.project_path / "project.json"
            project_config = {}
            if config_path.exists():
                project_config = json.loads(config_path.read_text(encoding='utf-8'))

            # Create pipeline components
            config = get_config()
            llm_manager = LLMManager(config)

            # Create directing pipeline
            directing_pipeline = DirectingPipeline(llm_caller=llm_manager)

            # Parse scenes from script
            scenes = self._parse_scenes_for_directing(script_content)

            # Create directing input
            directing_input = DirectingInput(
                scenes=scenes,
                project_path=self.project_path,
                generation_protocol=generation_protocol,
                media_type=media_type,
                style_notes=project_config.get("style_notes", "")
            )

            # Run async pipeline
            async def run_async():
                return await directing_pipeline.run(directing_input)

            # Get or create event loop
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            logger.info("Running Directing pipeline...")
            pipeline_result = loop.run_until_complete(run_async())

            if not pipeline_result.success:
                return {"error": f"Pipeline failed: {pipeline_result.error}"}

            result = pipeline_result.output

            # Save outputs
            storyboard_dir = self.project_path / "storyboard"
            storyboard_dir.mkdir(exist_ok=True)

            # Save visual script
            if hasattr(result, 'to_markdown'):
                vs_path = storyboard_dir / "visual_script.md"
                vs_path.write_text(result.to_markdown(), encoding='utf-8')
                logger.info(f"Saved visual script to {vs_path}")

            if hasattr(result, 'to_dict'):
                json_path = storyboard_dir / "visual_script.json"
                json_path.write_text(json.dumps(result.to_dict(), indent=2), encoding='utf-8')
                logger.info(f"Saved visual script JSON to {json_path}")

            return {
                "success": True,
                "generation_protocol": generation_protocol,
                "media_type": media_type,
                "message": "Directing Pipeline completed",
                "scenes": len(result.scenes) if hasattr(result, 'scenes') else 0,
                "frames": result.total_frames if hasattr(result, 'total_frames') else 0,
                "output_dir": str(storyboard_dir.relative_to(self.project_path))
            }
        except Exception as e:
            logger.error(f"Directing pipeline failed: {e}")
            return {"error": f"Directing Pipeline failed: {e}"}

    def _parse_scenes_for_directing(self, script_content: str) -> List[Dict[str, Any]]:
        """Parse scenes from script content for directing pipeline."""
        import re
        scenes = []

        # Try beat-centric format first: ## Beat: scene.X.YY
        beat_pattern = r'## Beat: scene\.(\d+)\.(\d+)'
        beat_matches = list(re.finditer(beat_pattern, script_content))

        if beat_matches:
            # Group beats by scene
            scene_beats: Dict[int, List[Dict]] = {}
            lines = script_content.split('\n')

            for i, match in enumerate(beat_matches):
                scene_num = int(match.group(1))
                beat_num = int(match.group(2))
                start_pos = match.end()

                # Find end position (next beat or end of file)
                if i + 1 < len(beat_matches):
                    end_pos = beat_matches[i + 1].start()
                else:
                    end_pos = len(script_content)

                beat_content = script_content[start_pos:end_pos].strip()

                if scene_num not in scene_beats:
                    scene_beats[scene_num] = []

                scene_beats[scene_num].append({
                    "beat_id": f"scene.{scene_num}.{beat_num:02d}",
                    "content": beat_content
                })

            # Create scene data from grouped beats
            for scene_num in sorted(scene_beats.keys()):
                beats = scene_beats[scene_num]
                full_content = "\n\n".join(b["content"] for b in beats)

                scenes.append({
                    "scene_id": f"scene.{scene_num}",
                    "scene_number": scene_num,
                    "beats": beats,
                    "content": full_content,
                    "description": beats[0]["content"][:200] if beats else ""
                })
        else:
            # Try scene-centric format: ## Scene N
            scene_pattern = r'## Scene (\d+)[:\s]*([^\n]*)'
            scene_matches = list(re.finditer(scene_pattern, script_content))

            for i, match in enumerate(scene_matches):
                scene_num = int(match.group(1))
                scene_title = match.group(2).strip()
                start_pos = match.end()

                if i + 1 < len(scene_matches):
                    end_pos = scene_matches[i + 1].start()
                else:
                    end_pos = len(script_content)

                scene_content = script_content[start_pos:end_pos].strip()

                scenes.append({
                    "scene_id": f"scene.{scene_num}",
                    "scene_number": scene_num,
                    "title": scene_title,
                    "content": scene_content,
                    "description": scene_content[:200]
                })

        return scenes

    def _run_procedural(
        self,
        protocol: str = "scene_chunked",
        chunk_size: int = 300,
        scene_id: str = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Run the Procedural Generation system."""
        if not self.project_path:
            return {"error": "No project loaded"}

        if not self._procedural_generator:
            return {"error": "Procedural Generator not available. Ensure it's initialized."}

        # Check for visual_script or script
        visual_script_path = self.project_path / "storyboard" / "visual_script.md"
        script_path = self.project_path / "scripts" / "script.md"

        if visual_script_path.exists():
            source_path = visual_script_path
        elif script_path.exists():
            source_path = script_path
        else:
            return {"error": "No script found. Run Writer or Directing Pipeline first."}

        if dry_run:
            return {
                "dry_run": True,
                "protocol": protocol,
                "chunk_size": chunk_size,
                "scene_id": scene_id,
                "source_file": str(source_path.relative_to(self.project_path)),
                "message": f"Would run Procedural Generation with {protocol} protocol"
            }

        try:
            script_content = source_path.read_text(encoding='utf-8')
            import asyncio
            result = asyncio.run(self._procedural_generator.generate(
                script_content,
                protocol=protocol,
                chunk_size=chunk_size,
                scene_id=scene_id
            ))

            return {
                "success": True,
                "protocol": protocol,
                "chunk_size": chunk_size,
                "chunks_generated": result.get("chunks_generated", 0) if isinstance(result, dict) else 0,
                "message": "Procedural Generation completed"
            }
        except Exception as e:
            return {"error": f"Procedural Generation failed: {e}"}

    def _extract_tags(
        self,
        content: str = None,
        tag_types: List[str] = None
    ) -> Dict[str, Any]:
        """Extract and validate tags using 10-agent consensus."""
        if not self.project_path:
            return {"error": "No project loaded"}

        if not self._tag_reference_system:
            return {"error": "Tag Reference System not available. Ensure it's initialized."}

        tag_types = tag_types or ["character", "location", "prop"]

        # If no content provided, read from current script
        if not content:
            script_path = self.project_path / "storyboard" / "visual_script.md"
            if not script_path.exists():
                script_path = self.project_path / "scripts" / "script.md"
            if not script_path.exists():
                return {"error": "No script found and no content provided."}
            content = script_path.read_text(encoding='utf-8')

        try:
            import asyncio
            result = asyncio.run(self._tag_reference_system.extract_and_validate(
                content,
                tag_types=tag_types
            ))

            return {
                "success": True,
                "tags_extracted": result.get("validated_tags", []) if isinstance(result, dict) else [],
                "consensus_achieved": result.get("consensus_achieved", False) if isinstance(result, dict) else False,
                "tag_types": tag_types,
                "message": "Tag extraction completed with 10-agent consensus"
            }
        except Exception as e:
            return {"error": f"Tag extraction failed: {e}"}

    def _generate_reference_prompts(
        self,
        tags: List[str] = None,
        style_notes: str = None
    ) -> Dict[str, Any]:
        """Generate reference image prompts for validated tags."""
        if not self.project_path:
            return {"error": "No project loaded"}

        if not self._tag_reference_system:
            return {"error": "Tag Reference System not available. Ensure it's initialized."}

        try:
            import asyncio
            result = asyncio.run(self._tag_reference_system.generate_reference_prompts(
                tags=tags,
                style_notes=style_notes
            ))

            return {
                "success": True,
                "prompts_generated": result.get("prompts", []) if isinstance(result, dict) else [],
                "count": len(result.get("prompts", [])) if isinstance(result, dict) else 0,
                "message": "Reference prompts generated"
            }
        except Exception as e:
            return {"error": f"Reference prompt generation failed: {e}"}

    def _get_pipeline_status(self) -> Dict[str, Any]:
        """Get the status and availability of all pipelines."""
        return {
            "pipelines": {
                "story_pipeline": {
                    "available": self._story_pipeline is not None,
                    "type": "classic_4_layer"
                },
                "story_pipeline_v2": {
                    "available": self._story_pipeline_v2 is not None,
                    "type": "assembly_7_7"
                },
                "world_bible_pipeline": {
                    "available": self._world_bible_pipeline is not None,
                    "type": "chunked_per_tag"
                },
                "directing_pipeline": {
                    "available": self._directing_pipeline is not None,
                    "type": "frame_notation"
                },
                "procedural_generator": {
                    "available": self._procedural_generator is not None,
                    "type": "micro_chunked"
                },
                "shot_pipeline": {
                    "available": self._shot_pipeline is not None,
                    "type": "legacy_director"
                }
            },
            "tag_reference_system": {
                "available": self._tag_reference_system is not None,
                "type": "10_agent_consensus"
            },
            "project_loaded": self.project_path is not None,
            "project_path": str(self.project_path) if self.project_path else None
        }

    # =========================================================================
    #  TASK MANAGEMENT TOOLS
    # =========================================================================

    def _create_task_plan(self, goal: str, tasks: List[Dict]) -> Dict[str, Any]:
        """Create a structured task plan."""
        import uuid

        plan = {
            "id": str(uuid.uuid4())[:8],
            "goal": goal,
            "status": "in_progress",
            "tasks": []
        }

        for i, task in enumerate(tasks):
            task_id = f"task_{i+1}"
            task_entry = {
                "id": task_id,
                "name": task.get("name", f"Task {i+1}"),
                "description": task.get("description", ""),
                "status": "not_started",
                "subtasks": []
            }

            # Add subtasks if present
            for j, subtask in enumerate(task.get("subtasks", [])):
                subtask_entry = {
                    "id": f"{task_id}.{j+1}",
                    "name": subtask.get("name", f"Subtask {j+1}"),
                    "description": subtask.get("description", ""),
                    "status": "not_started"
                }
                task_entry["subtasks"].append(subtask_entry)

            plan["tasks"].append(task_entry)

        self._task_plan = plan

        return {
            "success": True,
            "plan_id": plan["id"],
            "goal": goal,
            "task_count": len(plan["tasks"]),
            "message": f"Created task plan with {len(plan['tasks'])} tasks"
        }

    def _update_task_status(
        self,
        task_id: str,
        status: str,
        message: str = None
    ) -> Dict[str, Any]:
        """Update the status of a task."""
        if not self._task_plan:
            return {"error": "No task plan exists. Create one first."}

        valid_statuses = ["not_started", "in_progress", "complete", "failed", "cancelled"]
        if status not in valid_statuses:
            return {"error": f"Invalid status. Must be one of: {valid_statuses}"}

        # Find and update the task
        for task in self._task_plan.get("tasks", []):
            if task["id"] == task_id:
                task["status"] = status
                if message:
                    task["message"] = message
                return {
                    "success": True,
                    "task_id": task_id,
                    "new_status": status,
                    "message": f"Updated task {task_id} to {status}"
                }

            # Check subtasks
            for subtask in task.get("subtasks", []):
                if subtask["id"] == task_id:
                    subtask["status"] = status
                    if message:
                        subtask["message"] = message
                    return {
                        "success": True,
                        "task_id": task_id,
                        "new_status": status,
                        "message": f"Updated subtask {task_id} to {status}"
                    }

        return {"error": f"Task not found: {task_id}"}

    def _get_task_plan(self) -> Dict[str, Any]:
        """Get the current task plan."""
        if not self._task_plan:
            return {"message": "No task plan exists"}

        # Calculate progress
        total = 0
        complete = 0

        for task in self._task_plan.get("tasks", []):
            total += 1
            if task["status"] == "complete":
                complete += 1

            for subtask in task.get("subtasks", []):
                total += 1
                if subtask["status"] == "complete":
                    complete += 1

        progress = (complete / total * 100) if total > 0 else 0

        return {
            "plan": self._task_plan,
            "progress": f"{progress:.1f}%",
            "complete": complete,
            "total": total
        }

    # =========================================================================
    #  IMAGE ANALYSIS TOOLS
    # =========================================================================

    def _analyze_image(
        self,
        path: str = None,
        analysis_type: str = "full",
        image_id: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Analyze an image for content, style, and characters.

        Args:
            path: Direct path to image file
            image_id: Tag-based reference (e.g., 'CHAR_MEI_REF') - will resolve to reference image
            analysis_type: Type of analysis - 'full', 'character', 'scene'
        """
        # Handle image_id (tag-based reference)
        if image_id and not path:
            # Try to resolve image_id to a path
            tag = image_id.replace("_REF", "").upper()
            if not tag.startswith("CHAR_") and not tag.startswith("LOC_") and not tag.startswith("PROP_"):
                tag = f"CHAR_{tag}"

            # Look for reference image
            if self.project_path:
                ref_dir = self.project_path / "references" / tag
                if ref_dir.exists():
                    # Find key reference or first image
                    key_files = list(ref_dir.glob("*.key"))
                    if key_files:
                        # Get the image file (key file is marker, actual image has same name without .key)
                        key_path = key_files[0]
                        img_path = key_path.with_suffix("")
                        if img_path.exists():
                            path = str(img_path)
                    else:
                        # Use first image in directory
                        for ext in ['.png', '.jpg', '.jpeg', '.webp']:
                            imgs = list(ref_dir.glob(f"*{ext}"))
                            if imgs:
                                path = str(imgs[0])
                                break

            if not path:
                return {"error": f"Could not resolve image_id: {image_id}"}

        if not path:
            return {"error": "No path or image_id provided"}

        resolved = self._validate_path(path)

        if not resolved.exists():
            return {"error": f"Image not found: {path}"}

        if resolved.suffix.lower() not in ['.png', '.jpg', '.jpeg', '.webp', '.gif']:
            return {"error": f"Not an image file: {path}"}

        # Basic image info
        import os
        stat = os.stat(resolved)

        result = {
            "path": path,
            "size_bytes": stat.st_size,
            "analysis_type": analysis_type,
            "analysis": {}
        }

        # Try to get image dimensions
        try:
            from PIL import Image
            with Image.open(resolved) as img:
                result["width"] = img.width
                result["height"] = img.height
                result["format"] = img.format
                result["mode"] = img.mode
        except ImportError:
            result["note"] = "PIL not available for detailed image analysis"
        except Exception as e:
            result["note"] = f"Could not read image details: {e}"

        # Extract tags from filename if present
        filename = resolved.stem
        import re
        tags = re.findall(r'\[([A-Z_]+)\]', filename)
        if tags:
            result["detected_tags"] = tags

        # Check for corresponding prompt file
        prompt_path = resolved.parent / f"{filename}.txt"
        if prompt_path.exists():
            try:
                result["prompt"] = prompt_path.read_text(encoding='utf-8')[:500]
            except:
                pass

        return result

    def _story_analysis_protocol(
        self,
        image_paths: List[str],
        analysis_focus: str = "full",
        include_prompts: bool = True,
        include_story_context: bool = True
    ) -> Dict[str, Any]:
        """Perform comprehensive story analysis on a batch of storyboard images."""
        if not self.project_path:
            return {"error": "No project loaded"}

        if not image_paths:
            return {"error": "No image paths provided"}

        if len(image_paths) > 6:
            return {"error": "Maximum 6 images per analysis batch"}

        result = {
            "analysis_focus": analysis_focus,
            "images": [],
            "story_context": None,
            "overall_assessment": {}
        }

        # Analyze each image
        for path in image_paths:
            img_result = self._analyze_image(path, analysis_focus)
            result["images"].append(img_result)

        # Load story context if requested
        if include_story_context:
            world_bible_path = self.project_path / "world_bible" / "WORLD_BIBLE.json"
            if not world_bible_path.exists():
                world_bible_path = self.project_path / "WORLD_BIBLE.json"

            if world_bible_path.exists():
                try:
                    import json
                    with open(world_bible_path, 'r', encoding='utf-8') as f:
                        world_bible = json.load(f)
                    result["story_context"] = {
                        "title": world_bible.get("title", "Unknown"),
                        "characters": list(world_bible.get("characters", {}).keys()),
                        "locations": list(world_bible.get("locations", {}).keys())
                    }
                except:
                    pass

        # Collect all detected tags across images
        all_tags = set()
        for img in result["images"]:
            if "detected_tags" in img:
                all_tags.update(img["detected_tags"])

        result["overall_assessment"] = {
            "image_count": len(image_paths),
            "unique_tags": list(all_tags),
            "analysis_complete": True
        }

        return result

    # =========================================================================
    #  AUTONOMOUS AGENT TOOLS (Gemini 2.5 Powered)
    # =========================================================================

    def _analyze_image_gemini(
        self,
        path: str,
        analysis_type: str = "full",
        expected: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze an image using Gemini 2.5 for detailed structured analysis."""
        import asyncio
        from greenlight.omni_mind.autonomous_agent import AutonomousTaskManager

        resolved = self._validate_path(path)
        if not resolved.exists():
            return {"success": False, "error": f"Image not found: {path}"}

        # Create task manager and run analysis
        manager = AutonomousTaskManager(
            project_path=self.project_path,
            tool_executor=self
        )

        context = {"expected": expected} if expected else None

        # Run async analysis
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            manager.analyze_image(resolved, analysis_type, context)
        )

        return result.to_dict()

    def _edit_image(
        self,
        source_path: str,
        edit_instruction: str,
        prefix_type: str = "edit",
        output_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Edit an image using Nano Banana Pro with template prefixes."""
        from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel

        resolved = self._validate_path(source_path)
        if not resolved.exists():
            return {"success": False, "error": f"Source image not found: {source_path}"}

        # Determine output path
        if output_path:
            out_resolved = self._validate_path(output_path)
        else:
            out_resolved = resolved  # Overwrite source

        # Build prefix based on type
        prefix_map = {
            "edit": "Edit this image: ",
            "reangle": "Recreate this image from a different angle: ",
            "recreate": "Recreate this image with the following changes: "
        }
        prefix = prefix_map.get(prefix_type, "Edit this image: ")

        # Get image dimensions
        try:
            from PIL import Image
            with Image.open(resolved) as img:
                width, height = img.size
        except Exception:
            width, height = 1920, 1080  # Default

        # Create image request
        request = ImageRequest(
            prompt=f"{prefix}{edit_instruction}",
            model=ImageModel.NANO_BANANA_PRO,
            size=(width, height),
            reference_images=[str(resolved)],
            output_path=str(out_resolved),
            prefix_type="none"  # We already added prefix
        )

        # Generate using ImageHandler with ContextEngine for world context
        try:
            handler = ImageHandler(project_path=self.project_path, context_engine=self._context_engine)
            result = handler.generate(request)

            return {
                "success": result.success,
                "output_path": str(out_resolved),
                "edit_instruction": edit_instruction,
                "prefix_type": prefix_type,
                "error": result.error if not result.success else None
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _autonomous_character_modification(
        self,
        character_tag: str,
        modification_description: str,
        auto_execute: bool = True
    ) -> Dict[str, Any]:
        """Execute a complete autonomous character modification workflow."""
        import asyncio
        from greenlight.omni_mind.autonomous_agent import AutonomousTaskManager

        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        # Create task manager
        manager = AutonomousTaskManager(
            project_path=self.project_path,
            tool_executor=self
        )

        # Run async modification
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            manager.execute_character_modification(
                character_tag,
                modification_description,
                auto_execute
            )
        )

        return result

    def _find_frames_by_character(self, character_tag: str) -> Dict[str, Any]:
        """Find all storyboard frames containing a specific character."""
        from greenlight.omni_mind.autonomous_agent import AutonomousTaskManager

        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        manager = AutonomousTaskManager(project_path=self.project_path)
        frames = manager.find_frames_with_character(character_tag)

        return {
            "success": True,
            "character_tag": character_tag,
            "frame_count": len(frames),
            "frames": [
                {
                    "frame_id": f["frame_id"],
                    "scene_id": f["scene_id"],
                    "has_image": f["image_path"].exists() if f.get("image_path") else False
                }
                for f in frames
            ]
        }

    def _validate_image_changes(
        self,
        image_path: str,
        expected_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate that an image matches expected modifications."""
        import asyncio
        from greenlight.omni_mind.autonomous_agent import AutonomousTaskManager

        resolved = self._validate_path(image_path)
        if not resolved.exists():
            return {"success": False, "error": f"Image not found: {image_path}"}

        manager = AutonomousTaskManager(
            project_path=self.project_path,
            tool_executor=self
        )

        # Run validation analysis
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        result = loop.run_until_complete(
            manager.analyze_image(
                resolved,
                analysis_type="validation",
                context={"expected": expected_attributes}
            )
        )

        # Parse validation result
        validation_result = {
            "success": result.success,
            "image_path": image_path,
            "expected": expected_attributes,
            "analysis": result.to_dict()
        }

        # Check if raw response contains match info
        if result.raw_response:
            try:
                import json
                json_start = result.raw_response.find("{")
                json_end = result.raw_response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    data = json.loads(result.raw_response[json_start:json_end])
                    validation_result["matches"] = data.get("matches", False)
                    validation_result["match_score"] = data.get("match_score", 0.0)
                    validation_result["matched_attributes"] = data.get("matched_attributes", [])
                    validation_result["mismatched_attributes"] = data.get("mismatched_attributes", [])
            except:
                pass

        return validation_result

    # =========================================================================
    #  SELF-HEALING TOOLS
    # =========================================================================

    def _diagnose_project(self, target: str = "all") -> Dict[str, Any]:
        """Diagnose issues in the project."""
        if not self.project_path:
            return {"error": "No project loaded"}

        issues = []
        recommendations = []

        # Check project structure
        if target in ["project", "structure", "all"]:
            required_dirs = ["world_bible", "story_documents", "storyboard_prompts"]
            for dir_name in required_dirs:
                dir_path = self.project_path / dir_name
                if not dir_path.exists():
                    issues.append({
                        "id": f"missing_dir_{dir_name}",
                        "type": "structure",
                        "severity": "warning",
                        "message": f"Missing directory: {dir_name}",
                        "auto_fixable": True
                    })
                    recommendations.append(f"Create {dir_name} directory")

            # Check for key files
            key_files = [
                ("world_bible/pitch.md", "pitch.md"),
                ("world_bible/WORLD_BIBLE.json", "WORLD_BIBLE.json"),
            ]
            for primary, fallback in key_files:
                primary_path = self.project_path / primary
                fallback_path = self.project_path / fallback
                if not primary_path.exists() and not fallback_path.exists():
                    issues.append({
                        "id": f"missing_file_{primary.replace('/', '_')}",
                        "type": "structure",
                        "severity": "info",
                        "message": f"Missing file: {primary}",
                        "auto_fixable": False
                    })

        # Check tags
        if target in ["tags", "all"]:
            script_path = self.project_path / "scripts" / "script.md"
            if script_path.exists():
                import re
                content = script_path.read_text(encoding='utf-8')
                found_tags = set(re.findall(r'\[([A-Z_]+)\]', content))

                if self._tag_registry:
                    registered = {t.name for t in self._tag_registry.get_all_tags()}
                    unregistered = found_tags - registered

                    for tag in list(unregistered)[:10]:  # Limit to 10
                        issues.append({
                            "id": f"unregistered_tag_{tag}",
                            "type": "tag",
                            "severity": "info",
                            "message": f"Unregistered tag: [{tag}]",
                            "auto_fixable": True
                        })

        # Check pipelines
        if target in ["pipelines", "all"]:
            pipelines = {
                "story_pipeline": self._story_pipeline,
                "story_pipeline_v2": self._story_pipeline_v2,
                "world_bible_pipeline": self._world_bible_pipeline,
                "directing_pipeline": self._directing_pipeline,
                "procedural_generator": self._procedural_generator,
            }
            for name, pipeline in pipelines.items():
                if pipeline is None:
                    issues.append({
                        "id": f"unavailable_pipeline_{name}",
                        "type": "pipeline",
                        "severity": "info",
                        "message": f"Pipeline not initialized: {name}",
                        "auto_fixable": False
                    })

        return {
            "target": target,
            "issues": issues,
            "issue_count": len(issues),
            "recommendations": recommendations,
            "auto_fixable_count": sum(1 for i in issues if i.get("auto_fixable"))
        }

    def _auto_fix_issue(self, issue_id: str) -> Dict[str, Any]:
        """Automatically fix an issue by ID."""
        if not self.project_path:
            return {"error": "No project loaded"}

        # Handle missing directory
        if issue_id.startswith("missing_dir_"):
            dir_name = issue_id.replace("missing_dir_", "")
            dir_path = self.project_path / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)
            return {
                "success": True,
                "issue_id": issue_id,
                "action": "create_directory",
                "message": f"Created directory: {dir_name}"
            }

        # Handle unregistered tag (suggest registration)
        if issue_id.startswith("unregistered_tag_"):
            tag = issue_id.replace("unregistered_tag_", "")
            return {
                "success": True,
                "issue_id": issue_id,
                "action": "suggest_registration",
                "message": f"Tag [{tag}] should be added to world bible",
                "requires_user_action": True
            }

        return {
            "success": False,
            "issue_id": issue_id,
            "message": f"Cannot auto-fix issue: {issue_id}"
        }

    def _run_self_healing(self, issue_type: str = "all") -> Dict[str, Any]:
        """Run the self-healing process."""
        if not self.project_path:
            return {"error": "No project loaded"}

        # Step 1: Diagnose
        diagnosis = self._diagnose_project(issue_type)

        # Step 2: Auto-fix what we can
        fixed = []
        failed = []

        for issue in diagnosis.get("issues", []):
            if issue.get("auto_fixable"):
                try:
                    result = self._auto_fix_issue(issue["id"])
                    if result.get("success"):
                        fixed.append(issue["id"])
                    else:
                        failed.append({"id": issue["id"], "reason": result.get("message")})
                except Exception as e:
                    failed.append({"id": issue["id"], "reason": str(e)})

        return {
            "issues_found": len(diagnosis.get("issues", [])),
            "auto_fixed": len(fixed),
            "fixed_issues": fixed,
            "failed_fixes": failed,
            "remaining_issues": [
                i for i in diagnosis.get("issues", [])
                if i["id"] not in fixed
            ],
            "recommendations": diagnosis.get("recommendations", [])
        }

    def _validate_notation(
        self,
        file_path: str = "storyboards/visual_script.md",
        auto_fix: bool = False
    ) -> Dict[str, Any]:
        """Validate scene.frame.camera notation in visual scripts.

        Notation format: {scene}.{frame}.c{letter}
        Examples: 1.1.cA, 1.2.cB, 2.3.cC
        """
        import re

        if not self.project_path:
            return {"error": "No project loaded"}

        full_path = self.project_path / file_path
        if not full_path.exists():
            return {"error": f"File not found: {file_path}"}

        try:
            content = full_path.read_text(encoding="utf-8")
        except Exception as e:
            return {"error": f"Failed to read file: {e}"}

        # Import patterns from canonical source
        from greenlight.config.notation_patterns import SCENE_FRAME_CAMERA_PATTERNS, REGEX_PATTERNS
        patterns = {
            "full_id": SCENE_FRAME_CAMERA_PATTERNS["camera_block"],  # [1.2.cA] (camera block header)
            "old_frame": r"\{frame_(\d+)\.(\d+)\}",     # {frame_1.2} - legacy format
            "scene_marker": REGEX_PATTERNS["scene_header"],    # ## Scene 1:
        }

        # Find all notations
        valid_notations = []
        old_notations = []
        issues = []

        # Check for new format
        for match in re.finditer(patterns["full_id"], content):
            scene, frame, camera = match.groups()
            valid_notations.append({
                "notation": f"{scene}.{frame}.c{camera}",
                "scene": int(scene),
                "frame": int(frame),
                "camera": camera,
                "position": match.start()
            })

        # Check for old format
        for match in re.finditer(patterns["old_frame"], content):
            scene, frame = match.groups()
            old_notations.append({
                "old_notation": f"{{frame_{scene}.{frame}}}",
                "new_notation": f"[{scene}.{frame}.cA]",
                "scene": int(scene),
                "frame": int(frame),
                "position": match.start()
            })
            issues.append(f"Old notation found: {{frame_{scene}.{frame}}} → should be [{scene}.{frame}.cA]")

        # Auto-fix if requested
        fixed_content = None
        if auto_fix and old_notations:
            fixed_content = content
            for old in old_notations:
                fixed_content = fixed_content.replace(
                    old["old_notation"],
                    old["new_notation"]
                )
            # Write back
            try:
                full_path.write_text(fixed_content, encoding="utf-8")
            except Exception as e:
                return {"error": f"Failed to write fixed file: {e}"}

        return {
            "valid": len(issues) == 0,
            "file": file_path,
            "valid_notations": len(valid_notations),
            "old_notations": len(old_notations),
            "issues": issues,
            "auto_fixed": auto_fix and len(old_notations) > 0,
            "notation_format": "scene.frame.camera (e.g., 1.2.cA)",
            "examples": valid_notations[:5] if valid_notations else []
        }

    def _parse_notation(self, notation: str) -> Dict[str, Any]:
        """Parse a scene.frame.camera notation string into components.

        Supports:
        - Full: 1.2.cA → scene=1, frame=2, camera=A
        - Frame: 1.2 → scene=1, frame=2
        - Scene: 1 → scene=1
        """
        import re

        # Try full notation: 1.2.cA
        full_match = re.match(r"^(\d+)\.(\d+)\.c([A-Z])$", notation)
        if full_match:
            return {
                "valid": True,
                "type": "camera",
                "scene": int(full_match.group(1)),
                "frame": int(full_match.group(2)),
                "camera": full_match.group(3),
                "full_id": notation,
                "description": f"Scene {full_match.group(1)}, Frame {full_match.group(2)}, Camera {full_match.group(3)}"
            }

        # Try scene.frame: 1.2
        sf_match = re.match(r"^(\d+)\.(\d+)$", notation)
        if sf_match:
            return {
                "valid": True,
                "type": "frame",
                "scene": int(sf_match.group(1)),
                "frame": int(sf_match.group(2)),
                "camera": None,
                "full_id": notation,
                "description": f"Scene {sf_match.group(1)}, Frame {sf_match.group(2)}"
            }

        # Try just scene number
        if notation.isdigit():
            return {
                "valid": True,
                "type": "scene",
                "scene": int(notation),
                "frame": None,
                "camera": None,
                "full_id": notation,
                "description": f"Scene {notation}"
            }

        return {
            "valid": False,
            "error": f"Invalid notation: {notation}",
            "expected_formats": [
                "scene.frame.camera (e.g., 1.2.cA)",
                "scene.frame (e.g., 1.2)",
                "scene (e.g., 1)"
            ]
        }

    def _translate_prompt(
        self,
        prompt: str,
        auto_execute: bool = False
    ) -> Dict[str, Any]:
        """Translate a natural language prompt into tool operations."""
        # This is a simplified synchronous version
        # The full async version is in OmniMind

        # Simple pattern matching for common requests
        prompt_lower = prompt.lower()

        if "run" in prompt_lower and "story" in prompt_lower:
            return {
                "translated": True,
                "tool": "run_story_v2",
                "parameters": {"pipeline_mode": "assembly"},
                "description": "Run Story Pipeline v2",
                "auto_execute": auto_execute
            }
        elif "run" in prompt_lower and "world" in prompt_lower:
            return {
                "translated": True,
                "tool": "run_world_bible",
                "parameters": {},
                "description": "Run World Bible Pipeline",
                "auto_execute": auto_execute
            }
        elif "run" in prompt_lower and "direct" in prompt_lower:
            return {
                "translated": True,
                "tool": "run_directing",
                "parameters": {},
                "description": "Run Directing Pipeline",
                "auto_execute": auto_execute
            }
        elif "diagnose" in prompt_lower or "check" in prompt_lower:
            return {
                "translated": True,
                "tool": "diagnose_project",
                "parameters": {"target": "all"},
                "description": "Diagnose project issues",
                "auto_execute": auto_execute
            }
        elif "fix" in prompt_lower or "heal" in prompt_lower:
            return {
                "translated": True,
                "tool": "run_self_healing",
                "parameters": {"issue_type": "all"},
                "description": "Run self-healing",
                "auto_execute": auto_execute
            }
        else:
            return {
                "translated": False,
                "message": "Could not translate prompt. Use specific tool names.",
                "available_tools": [d.name for d in self._declarations[:10]]
            }

    def _retrieve_context(
        self,
        query: str,
        scope: str = "all",
        tags: List[str] = None
    ) -> Dict[str, Any]:
        """Retrieve relevant context."""
        if not self.project_path:
            return {"error": "No project loaded"}

        # Search for relevant content
        results = []

        # Search in story documents
        if scope in ["story", "all"]:
            story_dir = self.project_path / "story_documents"
            if story_dir.exists():
                for file in story_dir.glob("*.md"):
                    try:
                        content = file.read_text(encoding='utf-8')
                        if query.lower() in content.lower():
                            results.append({
                                "source": str(file.relative_to(self.project_path)),
                                "type": "story",
                                "snippet": content[:500]
                            })
                    except:
                        pass

        # Search in world bible
        if scope in ["world_bible", "all"]:
            wb_path = self.project_path / "world_bible" / "WORLD_BIBLE.json"
            if wb_path.exists():
                try:
                    content = wb_path.read_text(encoding='utf-8')
                    if query.lower() in content.lower():
                        results.append({
                            "source": "world_bible/WORLD_BIBLE.json",
                            "type": "world_bible",
                            "snippet": content[:500]
                        })
                except:
                    pass

        # Filter by tags if provided
        if tags:
            filtered = []
            for r in results:
                for tag in tags:
                    if f"[{tag}]" in r.get("snippet", ""):
                        filtered.append(r)
                        break
            results = filtered

        return {
            "query": query,
            "scope": scope,
            "tags_filter": tags,
            "results": results,
            "count": len(results)
        }

    def _run_tests(
        self,
        test_path: str = "tests",
        verbose: bool = True,
        pattern: str = None,
        markers: str = None
    ) -> Dict[str, Any]:
        """Run pytest tests."""
        import subprocess
        import sys

        # Build pytest command
        cmd = [sys.executable, "-m", "pytest", test_path]

        if verbose:
            cmd.append("-v")

        if pattern:
            cmd.extend(["-k", pattern])

        if markers:
            cmd.extend(["-m", markers])

        # Add output formatting
        cmd.append("--tb=short")

        try:
            # Run pytest
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                cwd=str(Path(__file__).parent.parent.parent)  # greenlight root
            )

            # Parse output
            output = result.stdout + result.stderr

            # Extract test counts from output
            passed = 0
            failed = 0
            skipped = 0
            errors = 0

            # Look for summary line like "5 passed, 2 failed, 1 skipped"
            import re
            summary_match = re.search(r'(\d+) passed', output)
            if summary_match:
                passed = int(summary_match.group(1))

            failed_match = re.search(r'(\d+) failed', output)
            if failed_match:
                failed = int(failed_match.group(1))

            skipped_match = re.search(r'(\d+) skipped', output)
            if skipped_match:
                skipped = int(skipped_match.group(1))

            error_match = re.search(r'(\d+) error', output)
            if error_match:
                errors = int(error_match.group(1))

            return {
                "success": result.returncode == 0,
                "test_path": test_path,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "errors": errors,
                "total": passed + failed + skipped + errors,
                "return_code": result.returncode,
                "output": output[-2000:] if len(output) > 2000 else output,  # Truncate
                "command": " ".join(cmd)
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Test execution timed out after 5 minutes",
                "test_path": test_path
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "test_path": test_path
            }

    def _list_tests(self, test_path: str = "tests") -> Dict[str, Any]:
        """List available tests without running them."""
        import subprocess
        import sys

        cmd = [sys.executable, "-m", "pytest", test_path, "--collect-only", "-q"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=str(Path(__file__).parent.parent.parent)
            )

            # Parse collected tests
            tests = []
            for line in result.stdout.split('\n'):
                line = line.strip()
                if line and '::' in line and not line.startswith('='):
                    tests.append(line)

            return {
                "success": True,
                "test_path": test_path,
                "tests": tests,
                "count": len(tests)
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "test_path": test_path
            }

    def _execute_shell(
        self,
        command: str,
        cwd: str = None,
        timeout: int = 60
    ) -> Dict[str, Any]:
        """Execute a shell command."""
        import subprocess
        import sys

        # Determine working directory
        if cwd:
            work_dir = Path(cwd)
            if not work_dir.is_absolute() and self.project_path:
                work_dir = self.project_path / cwd
        elif self.project_path:
            work_dir = self.project_path
        else:
            work_dir = Path(__file__).parent.parent.parent  # greenlight root

        try:
            # Use shell=True for complex commands on Windows
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(work_dir)
            )

            output = result.stdout + result.stderr

            return {
                "success": result.returncode == 0,
                "command": command,
                "return_code": result.returncode,
                "stdout": result.stdout[-3000:] if len(result.stdout) > 3000 else result.stdout,
                "stderr": result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr,
                "cwd": str(work_dir)
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Command timed out after {timeout} seconds",
                "command": command
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "command": command
            }

    def _launch_app(self, wait_seconds: int = 5) -> Dict[str, Any]:
        """Launch the Greenlight application for testing."""
        import subprocess
        import sys
        import time

        greenlight_root = Path(__file__).parent.parent.parent

        try:
            # Launch the app in a new process
            process = subprocess.Popen(
                [sys.executable, "-m", "greenlight"],
                cwd=str(greenlight_root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait for startup
            time.sleep(wait_seconds)

            # Check if still running
            if process.poll() is None:
                return {
                    "success": True,
                    "message": f"Greenlight app launched successfully (PID: {process.pid})",
                    "pid": process.pid,
                    "status": "running"
                }
            else:
                # Process exited - get output
                stdout, stderr = process.communicate(timeout=1)
                return {
                    "success": False,
                    "message": "App exited during startup",
                    "return_code": process.returncode,
                    "stdout": stdout[-1000:] if stdout else "",
                    "stderr": stderr[-1000:] if stderr else ""
                }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _check_imports(self, module_path: str) -> Dict[str, Any]:
        """Check if a module can be imported without errors."""
        import subprocess
        import sys

        # Build a simple import check script
        check_script = f"""
import sys
try:
    import {module_path}
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {{type(e).__name__}}: {{e}}")
    sys.exit(1)
"""

        try:
            result = subprocess.run(
                [sys.executable, "-c", check_script],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(Path(__file__).parent.parent.parent)
            )

            if result.returncode == 0:
                return {
                    "success": True,
                    "module": module_path,
                    "message": f"Module '{module_path}' imports successfully"
                }
            else:
                error_output = result.stdout + result.stderr
                return {
                    "success": False,
                    "module": module_path,
                    "error": error_output.strip()
                }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "module": module_path,
                "error": "Import check timed out"
            }
        except Exception as e:
            return {
                "success": False,
                "module": module_path,
                "error": str(e)
            }

    def _validate_syntax(self, file_path: str) -> Dict[str, Any]:
        """Validate Python syntax of a file without executing it."""
        import ast

        # Resolve path
        if self.project_path:
            full_path = self.project_path / file_path
        else:
            full_path = Path(file_path)

        if not full_path.exists():
            # Try relative to greenlight root
            full_path = Path(__file__).parent.parent.parent / file_path

        if not full_path.exists():
            return {
                "success": False,
                "file": file_path,
                "error": f"File not found: {file_path}"
            }

        try:
            content = full_path.read_text(encoding='utf-8')
            ast.parse(content)

            return {
                "success": True,
                "file": file_path,
                "message": "Syntax is valid",
                "lines": len(content.split('\n'))
            }

        except SyntaxError as e:
            return {
                "success": False,
                "file": file_path,
                "error": f"Syntax error at line {e.lineno}: {e.msg}",
                "line": e.lineno,
                "offset": e.offset,
                "text": e.text
            }
        except Exception as e:
            return {
                "success": False,
                "file": file_path,
                "error": str(e)
            }

    def _list_processes(self) -> Dict[str, Any]:
        """List all available processes from the process library."""
        from greenlight.omni_mind.process_library import ProcessLibrary, ProcessCategory

        library = ProcessLibrary()
        processes = library.list_all()

        by_category = {}
        for process in processes:
            cat = process.category.value
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append({
                "id": process.id,
                "name": process.name,
                "description": process.description,
                "triggers": process.triggers[:3],
                "estimated_duration": process.estimated_duration
            })

        return {
            "success": True,
            "total_processes": len(processes),
            "by_category": by_category,
            "formatted": library.format_process_list()
        }

    def _execute_process(
        self,
        process_id: str,
        parameters: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Execute a process by ID or natural language."""
        from greenlight.omni_mind.process_library import ProcessLibrary
        import asyncio

        library = ProcessLibrary()
        library.set_tool_executor(self)

        if self.project_path:
            library.set_project(self.project_path)

        # Try to get by ID first
        process = library.get(process_id)

        # If not found, try natural language match
        if not process:
            process = library.match(process_id)

        if not process:
            return {
                "success": False,
                "error": f"No process found matching: {process_id}",
                "available": [p.id for p in library.list_all()]
            }

        # Execute the process
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        execution = loop.run_until_complete(
            library.execute(process, parameters)
        )

        return {
            "success": execution.status.value == "completed",
            "process_id": process.id,
            "process_name": process.name,
            "status": execution.status.value,
            "result": execution.result,
            "error": execution.error,
            "logs": execution.logs,
            "duration_ms": (
                (execution.completed_at - execution.started_at).total_seconds() * 1000
                if execution.completed_at else None
            )
        }

    def _run_full_pipeline(self, dry_run: bool = False) -> Dict[str, Any]:
        """Run the complete Writer + Director pipeline."""
        if not self.project_path:
            return {"error": "No project loaded"}

        if dry_run:
            return {
                "dry_run": True,
                "steps": [
                    {"step": 1, "name": "Writer Pipeline", "description": "Generate story from pitch"},
                    {"step": 2, "name": "Director Pipeline", "description": "Create storyboard prompts"}
                ],
                "estimated_duration": "10-20 minutes"
            }

        results = []

        # Run Writer
        writer_result = self._run_writer()
        results.append({"pipeline": "writer", "result": writer_result})

        if writer_result.get("error"):
            return {
                "success": False,
                "error": f"Writer pipeline failed: {writer_result.get('error')}",
                "results": results
            }

        # Run Director
        director_result = self._run_director()
        results.append({"pipeline": "director", "result": director_result})

        return {
            "success": not director_result.get("error"),
            "results": results,
            "message": "Full pipeline completed" if not director_result.get("error") else "Director failed"
        }

    # =========================================================================
    # RAG-BASED CONTENT MODIFICATION TOOLS
    # =========================================================================

    def _find_all_occurrences(
        self,
        entity_name: str,
        include_context: bool = True
    ) -> Dict[str, Any]:
        """Find all occurrences of an entity across the project."""
        if not self.project_path:
            return {"error": "No project loaded"}

        import re
        occurrences = []
        search_dirs = ["world_bible", "story_documents", "storyboard_output"]
        file_patterns = ["*.md", "*.json", "*.txt"]

        # Build search pattern
        pattern = re.compile(
            rf'\b{re.escape(entity_name)}\b|\[{re.escape(entity_name.upper())}\]',
            re.IGNORECASE
        )

        for search_dir in search_dirs:
            dir_path = self.project_path / search_dir
            if not dir_path.exists():
                continue

            for file_pattern in file_patterns:
                for file_path in dir_path.rglob(file_pattern):
                    try:
                        content = file_path.read_text(encoding='utf-8')
                        matches = list(pattern.finditer(content))

                        if matches:
                            for match in matches:
                                # Get context around match
                                start = max(0, match.start() - 100)
                                end = min(len(content), match.end() + 100)
                                context = content[start:end] if include_context else None

                                # Get line number
                                line_num = content[:match.start()].count('\n') + 1

                                occurrences.append({
                                    "file": str(file_path.relative_to(self.project_path)),
                                    "line": line_num,
                                    "match": match.group(),
                                    "context": f"...{context}..." if context else None
                                })
                    except Exception as e:
                        logger.warning(f"Error reading {file_path}: {e}")

        return {
            "entity": entity_name,
            "total_occurrences": len(occurrences),
            "occurrences": occurrences,
            "files_searched": sum(1 for d in search_dirs if (self.project_path / d).exists())
        }

    def _modify_content(
        self,
        entity_type: str,
        entity_name: str,
        modification_type: str,
        new_value: str,
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Modify content across the project using RAG search."""
        if not self.project_path:
            return {"error": "No project loaded"}

        import json
        import re

        changes = []

        # First, find all occurrences
        occurrences = self._find_all_occurrences(entity_name, include_context=False)

        if modification_type == "update_description":
            # Update in world bible JSON
            world_config_path = self.project_path / "world_bible" / "world_config.json"
            if world_config_path.exists():
                try:
                    config = json.loads(world_config_path.read_text(encoding='utf-8'))

                    # Find and update entity
                    entity_key = f"{entity_type}s"  # characters, locations, props
                    if entity_key in config:
                        for item in config[entity_key]:
                            if item.get("name", "").lower() == entity_name.lower() or \
                               item.get("tag", "").lower() == entity_name.lower():
                                old_desc = item.get("description", "")
                                item["description"] = new_value
                                changes.append({
                                    "file": "world_bible/world_config.json",
                                    "field": f"{entity_key}[{item.get('name')}].description",
                                    "old_value": old_desc[:100] + "..." if len(old_desc) > 100 else old_desc,
                                    "new_value": new_value[:100] + "..." if len(new_value) > 100 else new_value
                                })

                    if not dry_run and changes:
                        world_config_path.write_text(
                            json.dumps(config, indent=2, ensure_ascii=False),
                            encoding='utf-8'
                        )
                except Exception as e:
                    return {"error": f"Failed to update world config: {e}"}

        elif modification_type == "rename":
            # Rename entity across all files
            old_name = entity_name
            new_name = new_value

            for occ in occurrences.get("occurrences", []):
                file_path = self.project_path / occ["file"]
                try:
                    content = file_path.read_text(encoding='utf-8')

                    # Replace occurrences
                    new_content = re.sub(
                        rf'\b{re.escape(old_name)}\b',
                        new_name,
                        content,
                        flags=re.IGNORECASE
                    )

                    # Also replace tag format
                    new_content = re.sub(
                        rf'\[{re.escape(old_name.upper())}\]',
                        f'[{new_name.upper()}]',
                        new_content
                    )

                    if content != new_content:
                        changes.append({
                            "file": occ["file"],
                            "type": "rename",
                            "old_value": old_name,
                            "new_value": new_name
                        })

                        if not dry_run:
                            file_path.write_text(new_content, encoding='utf-8')
                except Exception as e:
                    logger.warning(f"Error modifying {file_path}: {e}")

        elif modification_type == "add_trait":
            # Add trait to character in world bible
            world_config_path = self.project_path / "world_bible" / "world_config.json"
            if world_config_path.exists():
                try:
                    config = json.loads(world_config_path.read_text(encoding='utf-8'))

                    if "characters" in config:
                        for char in config["characters"]:
                            if char.get("name", "").lower() == entity_name.lower():
                                if "traits" not in char:
                                    char["traits"] = []
                                char["traits"].append(new_value)
                                changes.append({
                                    "file": "world_bible/world_config.json",
                                    "field": f"characters[{char.get('name')}].traits",
                                    "action": "added",
                                    "new_value": new_value
                                })

                    if not dry_run and changes:
                        world_config_path.write_text(
                            json.dumps(config, indent=2, ensure_ascii=False),
                            encoding='utf-8'
                        )
                except Exception as e:
                    return {"error": f"Failed to update world config: {e}"}

        elif modification_type == "replace_text":
            # Generic text replacement
            return self._batch_replace(entity_name, new_value, "*.*", dry_run)

        return {
            "entity_type": entity_type,
            "entity_name": entity_name,
            "modification_type": modification_type,
            "dry_run": dry_run,
            "changes": changes,
            "total_changes": len(changes),
            "occurrences_found": occurrences.get("total_occurrences", 0),
            "message": "Preview only - no changes applied" if dry_run else f"Applied {len(changes)} changes"
        }

    def _batch_replace(
        self,
        search_text: str,
        replace_text: str,
        file_pattern: str = "*.*",
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """Replace text across multiple files."""
        if not self.project_path:
            return {"error": "No project loaded"}

        import fnmatch

        changes = []
        search_dirs = ["world_bible", "story_documents", "storyboard_output"]

        for search_dir in search_dirs:
            dir_path = self.project_path / search_dir
            if not dir_path.exists():
                continue

            for file_path in dir_path.rglob("*"):
                if not file_path.is_file():
                    continue

                if not fnmatch.fnmatch(file_path.name, file_pattern):
                    continue

                try:
                    content = file_path.read_text(encoding='utf-8')

                    if search_text in content:
                        count = content.count(search_text)
                        new_content = content.replace(search_text, replace_text)

                        changes.append({
                            "file": str(file_path.relative_to(self.project_path)),
                            "occurrences": count,
                            "search": search_text,
                            "replace": replace_text
                        })

                        if not dry_run:
                            file_path.write_text(new_content, encoding='utf-8')
                except Exception as e:
                    logger.warning(f"Error processing {file_path}: {e}")

        return {
            "search_text": search_text,
            "replace_text": replace_text,
            "file_pattern": file_pattern,
            "dry_run": dry_run,
            "changes": changes,
            "total_files": len(changes),
            "total_replacements": sum(c["occurrences"] for c in changes),
            "message": "Preview only - no changes applied" if dry_run else f"Applied changes to {len(changes)} files"
        }

    # =========================================================================
    # UI POINTER TOOLS (OmniMind Guidance)
    # =========================================================================

    def _point_to_ui(
        self,
        element_id: str,
        message: str,
        duration: float = 5.0
    ) -> Dict[str, Any]:
        """Highlight a UI element to guide the user."""
        try:
            from greenlight.ui.components.ui_pointer import get_ui_registry

            registry = get_ui_registry()
            success = registry.point_to(element_id, message, duration)

            if success:
                return {
                    "success": True,
                    "element_id": element_id,
                    "message": message,
                    "duration": duration,
                    "status": f"Highlighting '{element_id}' for {duration} seconds"
                }
            else:
                # List available elements
                available = registry.list_elements()
                return {
                    "success": False,
                    "error": f"Element '{element_id}' not found",
                    "available_elements": available
                }
        except ImportError:
            return {
                "success": False,
                "error": "UI pointer system not available"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _list_ui_elements(self) -> Dict[str, Any]:
        """List all UI elements that can be highlighted."""
        try:
            from greenlight.ui.components.ui_pointer import get_ui_registry

            registry = get_ui_registry()
            elements = registry.get_element_info()

            return {
                "success": True,
                "elements": elements,
                "total": len(elements),
                "categories": list(set(e["category"] for e in elements.values()))
            }
        except ImportError:
            return {
                "success": False,
                "error": "UI pointer system not available",
                "elements": {}
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "elements": {}
            }

    def _unhighlight_all_ui(self) -> Dict[str, Any]:
        """Remove all UI highlights."""
        try:
            from greenlight.ui.components.ui_pointer import get_ui_registry

            registry = get_ui_registry()
            registry.unhighlight_all()

            return {
                "success": True,
                "message": "All UI highlights removed"
            }
        except ImportError:
            return {
                "success": False,
                "error": "UI pointer system not available"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _click_ui_element(self, element_id: str) -> Dict[str, Any]:
        """Click a UI element."""
        try:
            from greenlight.ui.components.ui_pointer import click_element, get_ui_registry

            registry = get_ui_registry()
            elements = registry.list_elements()

            if element_id not in elements:
                return {
                    "success": False,
                    "error": f"Element '{element_id}' not found",
                    "available_elements": elements
                }

            success = click_element(element_id)
            return {
                "success": success,
                "element_id": element_id,
                "message": f"Clicked '{element_id}'" if success else f"Failed to click '{element_id}'"
            }
        except ImportError:
            return {"success": False, "error": "UI pointer system not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _invoke_ui_action(
        self,
        element_id: str,
        action: str,
        value: str = None
    ) -> Dict[str, Any]:
        """Invoke an action on a UI element."""
        try:
            from greenlight.ui.components.ui_pointer import invoke_action

            kwargs = {}
            if value is not None:
                kwargs['value'] = value

            result = invoke_action(element_id, action, **kwargs)
            return {
                "success": bool(result),
                "element_id": element_id,
                "action": action,
                "value": value,
                "message": f"Action '{action}' on '{element_id}' {'succeeded' if result else 'failed'}"
            }
        except ImportError:
            return {"success": False, "error": "UI pointer system not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_ui_element_state(self, element_id: str) -> Dict[str, Any]:
        """Get the current state of a UI element."""
        try:
            from greenlight.ui.components.ui_pointer import get_element_state

            state = get_element_state(element_id)
            if "error" in state and state.get("error", "").startswith("Element not found"):
                return {"success": False, **state}
            return {"success": True, **state}
        except ImportError:
            return {"success": False, "error": "UI pointer system not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _run_ui_test(
        self,
        actions: List[Dict[str, Any]] = None,
        capture_errors: bool = True
    ) -> Dict[str, Any]:
        """Run a UI test sequence."""
        results = []
        errors = []

        if not actions:
            return {
                "success": True,
                "message": "No actions specified",
                "results": [],
                "errors": []
            }

        try:
            from greenlight.ui.components.ui_pointer import (
                click_element, invoke_action, get_element_state
            )

            for i, action_spec in enumerate(actions):
                action_type = action_spec.get('action', 'click')
                element_id = action_spec.get('element_id', '')

                try:
                    if action_type == 'click':
                        success = click_element(element_id)
                        results.append({
                            "step": i + 1,
                            "action": "click",
                            "element_id": element_id,
                            "success": success
                        })
                    elif action_type in ('set_value', 'select', 'focus'):
                        value = action_spec.get('value', '')
                        success = invoke_action(element_id, action_type, value=value)
                        results.append({
                            "step": i + 1,
                            "action": action_type,
                            "element_id": element_id,
                            "value": value,
                            "success": bool(success)
                        })
                    elif action_type == 'wait':
                        import time
                        wait_time = action_spec.get('seconds', 1)
                        time.sleep(wait_time)
                        results.append({
                            "step": i + 1,
                            "action": "wait",
                            "seconds": wait_time,
                            "success": True
                        })
                    elif action_type == 'check_state':
                        state = get_element_state(element_id)
                        results.append({
                            "step": i + 1,
                            "action": "check_state",
                            "element_id": element_id,
                            "state": state,
                            "success": "error" not in state
                        })
                except Exception as e:
                    error_info = {
                        "step": i + 1,
                        "action": action_type,
                        "element_id": element_id,
                        "error": str(e)
                    }
                    errors.append(error_info)
                    results.append({**error_info, "success": False})

            return {
                "success": len(errors) == 0,
                "total_steps": len(actions),
                "completed": len(results),
                "failed": len(errors),
                "results": results,
                "errors": errors if capture_errors else []
            }

        except ImportError:
            return {"success": False, "error": "UI pointer system not available"}
        except Exception as e:
            return {"success": False, "error": str(e), "results": results, "errors": errors}

    def _capture_terminal_errors(
        self,
        terminal_id: int = None,
        parse_tracebacks: bool = True
    ) -> Dict[str, Any]:
        """Capture errors from terminal output."""
        import re

        # This would integrate with the terminal/process management
        # For now, we'll provide a structure for parsing error output
        errors = []
        tracebacks = []

        # Pattern for Python tracebacks
        traceback_pattern = re.compile(
            r'Traceback \(most recent call last\):.*?(?=\n\n|\Z)',
            re.DOTALL
        )
        error_pattern = re.compile(
            r'((?:Error|Exception|AttributeError|TypeError|ImportError|KeyError|ValueError|NameError)[^\n]*)',
            re.IGNORECASE
        )

        return {
            "success": True,
            "terminal_id": terminal_id,
            "message": "Use execute_shell or launch_app to capture output, then parse with this tool",
            "patterns": {
                "traceback": "Traceback (most recent call last):",
                "error_types": ["AttributeError", "TypeError", "ImportError", "KeyError", "ValueError", "NameError"]
            },
            "errors": errors,
            "tracebacks": tracebacks
        }

    # =========================================================================
    # DOCUMENT CHANGE TRACKING TOOLS
    # =========================================================================

    def _get_pending_changes(self) -> Dict[str, Any]:
        """Get list of documents with unsaved changes."""
        try:
            from greenlight.omni_mind.document_tracker import get_document_tracker

            tracker = get_document_tracker()
            summary = tracker.get_changes_summary()

            if summary["total_changes"] == 0:
                return {
                    "success": True,
                    "has_changes": False,
                    "message": "No pending changes detected.",
                    "changes": []
                }

            return {
                "success": True,
                "has_changes": True,
                "total_changes": summary["total_changes"],
                "files": summary["file_names"],
                "details": summary["files"],
                "message": f"Found {summary['total_changes']} document(s) with unsaved changes."
            }
        except ImportError:
            return {
                "success": False,
                "error": "Document tracker not available",
                "has_changes": False
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "has_changes": False
            }

    def _save_document_changes(self, file_paths: List[str] = None) -> Dict[str, Any]:
        """Save changes to modified documents."""
        try:
            from greenlight.omni_mind.document_tracker import get_document_tracker

            tracker = get_document_tracker()
            result = tracker.save_changes(file_paths)

            if result["saved_count"] > 0:
                return {
                    "success": True,
                    "saved_files": result["saved"],
                    "saved_count": result["saved_count"],
                    "remaining_changes": result["remaining_changes"],
                    "message": f"✅ Saved {result['saved_count']} document(s)."
                }
            else:
                return {
                    "success": True,
                    "saved_count": 0,
                    "message": "No documents to save."
                }
        except ImportError:
            return {
                "success": False,
                "error": "Document tracker not available"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _revert_document_changes(self, file_paths: List[str] = None) -> Dict[str, Any]:
        """Revert documents to their original content."""
        try:
            from greenlight.omni_mind.document_tracker import get_document_tracker

            tracker = get_document_tracker()
            result = tracker.revert_changes(file_paths)

            if result["reverted_count"] > 0:
                return {
                    "success": True,
                    "reverted_files": result["reverted"],
                    "reverted_count": result["reverted_count"],
                    "remaining_changes": result["remaining_changes"],
                    "message": f"↩️ Reverted {result['reverted_count']} document(s) to original."
                }
            else:
                return {
                    "success": True,
                    "reverted_count": 0,
                    "message": "No documents to revert."
                }
        except ImportError:
            return {
                "success": False,
                "error": "Document tracker not available"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # ==================== ERROR REPORTING & SELF-HEALING TOOLS ====================

    def _get_error_reporter(self):
        """Get or create the error reporter instance."""
        if not hasattr(self, '_error_reporter') or self._error_reporter is None:
            from greenlight.omni_mind.error_reporter import ErrorReporter
            self._error_reporter = ErrorReporter(
                project_path=self.project_path,
                health_logger=getattr(self, '_health_logger', None)
            )
        return self._error_reporter

    def _get_self_healer(self):
        """Get or create the self-healer instance."""
        if not hasattr(self, '_self_healer') or self._self_healer is None:
            from greenlight.omni_mind.self_healer import SelfHealer
            self._self_healer = SelfHealer(
                project_path=self.project_path,
                health_logger=getattr(self, '_health_logger', None)
            )
        return self._self_healer

    def _report_error(
        self,
        error_message: str,
        error_type: str = "Exception",
        source: str = "unknown",
        level: str = "standard",
        try_self_heal: bool = True
    ) -> Dict[str, Any]:
        """
        Report an error with full context for Augment to fix.

        This generates a structured transcript optimized for Augment
        to quickly understand and fix the error.
        """
        from greenlight.omni_mind.error_reporter import TranscriptLevel, SelfHealStatus

        reporter = self._get_error_reporter()
        healer = self._get_self_healer()

        # Create exception from message
        error = Exception(error_message)
        error.__class__.__name__ = error_type

        # Map level string to enum
        level_map = {
            "minimal": TranscriptLevel.MINIMAL,
            "standard": TranscriptLevel.STANDARD,
            "full": TranscriptLevel.FULL
        }
        transcript_level = level_map.get(level.lower(), TranscriptLevel.STANDARD)

        # Try self-healing first if requested
        heal_result = None
        if try_self_heal:
            from greenlight.omni_mind.self_healer import HealResult
            heal_result, actions = healer.heal(error, {"source": source})

            if heal_result == HealResult.SUCCESS:
                return {
                    "success": True,
                    "self_healed": True,
                    "actions": [a.to_dict() for a in actions],
                    "message": f"✅ Error self-healed: {actions[0].action_taken if actions else 'Fixed'}"
                }

        # Generate transcript for Augment
        transcript = reporter.report(
            error=error,
            source=source,
            level=transcript_level,
            context={"error_type": error_type},
            try_self_heal=False  # Already tried above
        )

        # Save report to file for Augment access
        report_path = None
        if self.project_path:
            try:
                report_path = reporter.save_report(transcript.id)
            except Exception as e:
                logger.warning(f"Could not save error report: {e}")

        return {
            "success": True,
            "self_healed": False,
            "transcript_id": transcript.id,
            "category": transcript.category.value,
            "severity": transcript.severity,
            "suggested_fixes": transcript.suggested_fixes,
            "report_path": str(report_path) if report_path else None,
            "augment_transcript": transcript.to_markdown(transcript_level),
            "message": f"📋 Error reported: {transcript.id}. Ready for Augment handoff."
        }

    def _get_error_reports(
        self,
        limit: int = 10,
        export_for_augment: bool = True
    ) -> Dict[str, Any]:
        """Get recent error reports for review or Augment handoff."""
        reporter = self._get_error_reporter()

        transcripts = reporter.get_recent(limit)

        if not transcripts:
            return {
                "success": True,
                "count": 0,
                "reports": [],
                "message": "No error reports found."
            }

        reports = []
        for t in transcripts:
            report = {
                "id": t.id,
                "timestamp": t.timestamp.isoformat(),
                "category": t.category.value,
                "error_type": t.error_type,
                "error_message": t.error_message[:100] + "..." if len(t.error_message) > 100 else t.error_message,
                "file": f"{t.primary_file}:{t.primary_line}",
                "severity": t.severity,
                "self_heal_status": "healed" if any(
                    a.status.value == "success" for a in t.self_heal_attempts
                ) else "pending"
            }

            if export_for_augment:
                report["augment_transcript"] = t.to_minimal()

            reports.append(report)

        return {
            "success": True,
            "count": len(reports),
            "reports": reports,
            "message": f"Found {len(reports)} error report(s)."
        }

    def _run_self_heal_tool(self, error_id: str = None) -> Dict[str, Any]:
        """Run self-healing on a specific error or all pending errors."""
        reporter = self._get_error_reporter()
        healer = self._get_self_healer()

        if error_id:
            # Heal specific error
            transcript = reporter.get_transcript(error_id)
            if not transcript:
                return {
                    "success": False,
                    "error": f"Error report {error_id} not found"
                }

            error = Exception(transcript.error_message)
            result, actions = healer.heal(error, {
                "source": transcript.primary_file,
                "category": transcript.category.value
            })

            return {
                "success": True,
                "error_id": error_id,
                "result": result.value,
                "actions": [a.to_dict() for a in actions],
                "message": f"Self-heal result: {result.value}"
            }
        else:
            # Heal all pending
            transcripts = reporter.get_recent(20)
            results = []

            for t in transcripts:
                if not any(a.status.value == "success" for a in t.self_heal_attempts):
                    error = Exception(t.error_message)
                    result, actions = healer.heal(error, {"source": t.primary_file})
                    results.append({
                        "error_id": t.id,
                        "result": result.value,
                        "actions_count": len(actions)
                    })

            return {
                "success": True,
                "processed": len(results),
                "results": results,
                "message": f"Processed {len(results)} pending error(s)."
            }

    def _get_healing_stats(self) -> Dict[str, Any]:
        """Get self-healing statistics and success rates."""
        healer = self._get_self_healer()
        stats = healer.get_stats()

        return {
            "success": True,
            "stats": stats,
            "recent_history": [a.to_dict() for a in healer.get_history(10)],
            "message": f"Self-healing success rate: {stats['success_rate']:.1f}%"
        }

    def _export_error_for_augment(
        self,
        error_id: str,
        level: str = "standard"
    ) -> Dict[str, Any]:
        """Export a specific error report in Augment-optimized format."""
        from greenlight.omni_mind.error_reporter import TranscriptLevel

        reporter = self._get_error_reporter()

        level_map = {
            "minimal": TranscriptLevel.MINIMAL,
            "standard": TranscriptLevel.STANDARD,
            "full": TranscriptLevel.FULL
        }
        transcript_level = level_map.get(level.lower(), TranscriptLevel.STANDARD)

        content = reporter.export_for_augment(error_id, transcript_level)

        if "not found" in content.lower():
            return {
                "success": False,
                "error": content
            }

        # Also save to file
        report_path = None
        if self.project_path:
            try:
                report_path = reporter.save_report(error_id)
            except Exception as e:
                logger.warning(f"Could not save report: {e}")

        return {
            "success": True,
            "error_id": error_id,
            "level": level,
            "report_path": str(report_path) if report_path else None,
            "augment_transcript": content,
            "message": f"📋 Error {error_id} exported for Augment. Level: {level}"
        }


    # ==================== IMAGE GENERATION TOOLS ====================

    def _generate_image(
        self,
        prompt: str,
        model: str = "nano_banana_pro",
        output_name: str = None,
        aspect_ratio: str = "1:1"
    ) -> Dict[str, Any]:
        """
        Generate an image using AI models.

        Automatically applies the project's Style Core suffix for visual consistency.

        Args:
            prompt: Description of the image to generate
            model: Model to use (nano_banana, nano_banana_pro, seedream, flux_kontext, etc.)
            output_name: Optional filename for the output (without extension)
            aspect_ratio: Aspect ratio (1:1, 16:9, 9:16, 4:3, 3:4)
        """
        from greenlight.config.api_dictionary import lookup_model, lookup_by_symbol
        import os

        # Get style suffix from project's Style Core using canonical utility
        style_suffix = ""
        if self.project_path:
            from greenlight.core.style_utils import get_style_suffix as _get_style_suffix
            style_suffix = _get_style_suffix(project_path=self.project_path)

        # Append style suffix to prompt
        if style_suffix:
            prompt = f"{prompt}. Style: {style_suffix}"

        # Resolve model
        model_entry = None
        if model.startswith("@"):
            model_entry = lookup_by_symbol(model)
        else:
            model_entry = lookup_model(model)

        if not model_entry:
            return {
                "error": f"Unknown model: {model}",
                "available_models": [
                    "nano_banana", "nano_banana_pro", "seedream",
                    "flux_kontext_pro", "flux_kontext_max", "sdxl"
                ]
            }

        # Check for API key (support alternative key names)
        api_key = os.getenv(model_entry.env_key)
        if not api_key and model_entry.env_key == "GOOGLE_API_KEY":
            # Try alternative key names for Google
            api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            return {
                "error": f"Missing API key: {model_entry.env_key}",
                "message": f"Set {model_entry.env_key} environment variable to use {model_entry.display_name}"
            }

        # Determine output path
        if self.project_path:
            output_dir = self.project_path / "generated_images"
            output_dir.mkdir(parents=True, exist_ok=True)
        else:
            output_dir = Path(".")

        if not output_name:
            from datetime import datetime
            output_name = f"generated_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        output_path = output_dir / f"{output_name}.png"

        # Generate based on provider
        try:
            if model_entry.provider.value == "google":
                return self._generate_with_google(prompt, model_entry, output_path, aspect_ratio)
            elif model_entry.provider.value == "replicate":
                return self._generate_with_replicate(prompt, model_entry, output_path, aspect_ratio)
            else:
                return {"error": f"Provider {model_entry.provider.value} not yet implemented for image generation"}
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            return {"error": str(e), "model": model_entry.display_name}

    def _generate_with_google(
        self, prompt: str, model_entry, output_path: Path, aspect_ratio: str
    ) -> Dict[str, Any]:
        """Generate image using Google Gemini/Imagen API."""
        import os
        import json
        from urllib import request, error
        import base64

        api_key = os.getenv(model_entry.env_key) or os.getenv("GEMINI_API_KEY")

        # Build request for Gemini image generation
        # Use gemini-2.0-flash-exp for image generation (supports responseModalities)
        model_id = "gemini-2.0-flash-exp"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_id}:generateContent?key={api_key}"

        body = {
            "contents": [{
                "parts": [{"text": f"Generate an image: {prompt}"}]
            }],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"]
            }
        }

        req = request.Request(
            url,
            data=json.dumps(body).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method="POST"
        )

        try:
            with request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            # Extract image from response
            candidates = result.get("candidates", [])
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                for part in parts:
                    if "inlineData" in part:
                        image_data = base64.b64decode(part["inlineData"]["data"])
                        with open(output_path, 'wb') as f:
                            f.write(image_data)

                        return {
                            "success": True,
                            "model": model_entry.display_name,
                            "output_path": str(output_path),
                            "prompt": prompt,
                            "message": f"✅ Image generated with {model_entry.display_name}"
                        }

            return {"error": "No image in response", "raw": result}

        except error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            return {"error": f"Google API error: {e.code}", "details": error_body}

    def _generate_with_replicate(
        self, prompt: str, model_entry, output_path: Path, aspect_ratio: str
    ) -> Dict[str, Any]:
        """Generate image using Replicate API."""
        import os
        import json
        import time
        from urllib import request, error

        api_key = os.getenv(model_entry.env_key)

        # Create prediction
        url = f"https://api.replicate.com/v1/models/{model_entry.model_id}/predictions"

        body = {
            "input": {
                "prompt": prompt,
                "aspect_ratio": aspect_ratio
            }
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Prefer": "wait"
        }

        req = request.Request(
            url,
            data=json.dumps(body).encode('utf-8'),
            headers=headers,
            method="POST"
        )

        try:
            with request.urlopen(req, timeout=300) as resp:
                result = json.loads(resp.read().decode('utf-8'))

            # Poll if needed
            status = result.get("status", "")
            if status in ("starting", "processing"):
                poll_url = result.get("urls", {}).get("get", f"https://api.replicate.com/v1/predictions/{result['id']}")
                for _ in range(60):  # Max 5 minutes
                    time.sleep(5)
                    poll_req = request.Request(poll_url, headers={"Authorization": f"Bearer {api_key}"})
                    with request.urlopen(poll_req, timeout=30) as resp:
                        result = json.loads(resp.read().decode('utf-8'))
                    if result.get("status") == "succeeded":
                        break
                    elif result.get("status") in ("failed", "canceled"):
                        return {"error": f"Generation {result.get('status')}: {result.get('error', 'Unknown')}"}

            # Download output image
            output = result.get("output", [])
            if output:
                img_url = output[0] if isinstance(output, list) else output
                img_req = request.Request(img_url)
                with request.urlopen(img_req, timeout=60) as resp:
                    image_data = resp.read()

                with open(output_path, 'wb') as f:
                    f.write(image_data)

                return {
                    "success": True,
                    "model": model_entry.display_name,
                    "output_path": str(output_path),
                    "prompt": prompt,
                    "message": f"✅ Image generated with {model_entry.display_name}"
                }

            return {"error": "No output in response", "raw": result}

        except error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            return {"error": f"Replicate API error: {e.code}", "details": error_body}



    # =========================================================================
    # STYLE CORE TOOLS
    # =========================================================================

    def _get_style_core(self) -> Dict[str, Any]:
        """Get the current Style Core settings from world_config.json.

        Uses the canonical style_utils module for consistent style handling.
        Single source of truth: world_config.json
        """
        if not self.project_path:
            return {"error": "No project loaded"}

        from greenlight.core.style_utils import load_world_config

        world_config = load_world_config(self.project_path)

        if not world_config:
            return {
                "visual_style": "live_action",
                "style_notes": "",
                "lighting": "",
                "vibe": ""
            }

        return {
            "visual_style": world_config.get("visual_style", "live_action"),
            "style_notes": world_config.get("style_notes", ""),
            "lighting": world_config.get("lighting", ""),
            "vibe": world_config.get("vibe", "")
        }

    def _set_visual_style(self, style: str) -> Dict[str, Any]:
        """Set the project's visual style type in world_config.json."""
        if not self.project_path:
            return {"error": "No project loaded"}

        from greenlight.core.style_utils import validate_visual_style, load_world_config
        import json

        if not validate_visual_style(style):
            valid_styles = ['live_action', 'anime', 'animation_2d', 'animation_3d', 'mixed_reality']
            return {"error": f"Invalid style. Must be one of: {valid_styles}"}

        # Load and update world_config.json
        world_config_path = self.project_path / "world_bible" / "world_config.json"
        world_config = load_world_config(self.project_path)

        world_config["visual_style"] = style

        # Ensure directory exists
        world_config_path.parent.mkdir(parents=True, exist_ok=True)
        world_config_path.write_text(json.dumps(world_config, indent=2), encoding='utf-8')

        return {
            "success": True,
            "visual_style": style,
            "message": f"Visual style set to: {style}"
        }

    def _update_style_notes(self, notes: str) -> Dict[str, Any]:
        """Update the project's style notes in world_config.json."""
        if not self.project_path:
            return {"error": "No project loaded"}

        from greenlight.core.style_utils import load_world_config
        import json

        # Load and update world_config.json
        world_config_path = self.project_path / "world_bible" / "world_config.json"
        world_config = load_world_config(self.project_path)

        world_config["style_notes"] = notes

        # Ensure directory exists
        world_config_path.parent.mkdir(parents=True, exist_ok=True)
        world_config_path.write_text(json.dumps(world_config, indent=2), encoding='utf-8')

        return {
            "success": True,
            "style_notes": notes,
            "message": "Style notes updated successfully"
        }

    def _suggest_style_notes(
        self,
        include_lighting: bool = True,
        include_vibe: bool = True
    ) -> Dict[str, Any]:
        """Generate suggested style notes based on project context."""
        if not self.project_path:
            return {"error": "No project loaded"}

        # Get current style settings
        current = self._get_style_core()
        visual_style = current.get('visual_style', 'live_action')

        # Read pitch for context
        pitch_path = self.project_path / "world_bible" / "pitch.md"
        pitch_content = ""
        if pitch_path.exists():
            try:
                pitch_content = pitch_path.read_text(encoding='utf-8')
            except:
                pass

        # Style-specific suggestions
        style_suggestions = {
            "live_action": {
                "base": "Photorealistic cinematography with natural lighting and practical effects",
                "lighting": "Natural key lighting with motivated sources, soft fill, cinematic contrast",
                "vibe": "Grounded, immersive, authentic"
            },
            "anime": {
                "base": "Dynamic anime style with expressive characters and bold visual storytelling",
                "lighting": "Dramatic rim lighting, vibrant color palettes, stylized shadows",
                "vibe": "Energetic, emotional, visually striking"
            },
            "animation_2d": {
                "base": "Hand-drawn aesthetic with fluid motion and artistic expression",
                "lighting": "Painted lighting effects, warm color harmonies, soft gradients",
                "vibe": "Artistic, nostalgic, expressive"
            },
            "animation_3d": {
                "base": "Modern 3D rendering with depth, texture, and dimensional lighting",
                "lighting": "Global illumination, subsurface scattering, volumetric effects",
                "vibe": "Polished, immersive, cinematic"
            },
            "mixed_reality": {
                "base": "Seamless blend of live action and CGI elements",
                "lighting": "Matched lighting between practical and digital, HDR integration",
                "vibe": "Fantastical yet grounded, visually innovative"
            }
        }

        suggestion = style_suggestions.get(visual_style, style_suggestions["live_action"])

        result = {
            "visual_style": visual_style,
            "suggested_notes": suggestion["base"]
        }

        if include_lighting:
            result["suggested_lighting"] = suggestion["lighting"]

        if include_vibe:
            result["suggested_vibe"] = suggestion["vibe"]

        # Combine into full suggestion
        full_suggestion = suggestion["base"]
        if include_lighting:
            full_suggestion += f"\n\nLighting: {suggestion['lighting']}"
        if include_vibe:
            full_suggestion += f"\n\nVibe: {suggestion['vibe']}"

        result["full_suggestion"] = full_suggestion
        result["message"] = f"Style suggestions generated for {visual_style} style"

        return result

    # ========== Backdoor UI Automation Tools ==========

    def _get_backdoor_client(self):
        """Get or create a backdoor client."""
        from greenlight.omni_mind.backdoor import BackdoorClient
        return BackdoorClient()

    def _backdoor_ping(self) -> Dict[str, Any]:
        """Ping the running Greenlight app."""
        try:
            client = self._get_backdoor_client()
            is_alive = client.ping()
            return {
                "success": True,
                "alive": is_alive,
                "message": "App is responsive" if is_alive else "App not responding"
            }
        except Exception as e:
            return {"success": False, "alive": False, "error": str(e)}

    def _backdoor_open_project(self, project_path: str) -> Dict[str, Any]:
        """Open a project in the running app."""
        try:
            client = self._get_backdoor_client()
            result = client.send_command("open_project", {"path": project_path})
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _backdoor_navigate(self, view: str) -> Dict[str, Any]:
        """Navigate to a view in the running app."""
        try:
            client = self._get_backdoor_client()
            result = client.send_command("navigate", {"view": view})
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _backdoor_click(self, element_id: str) -> Dict[str, Any]:
        """Click a UI element in the running app."""
        try:
            client = self._get_backdoor_client()
            result = client.send_command("click", {"element_id": element_id})
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _backdoor_list_ui_elements(self) -> Dict[str, Any]:
        """List all registered UI elements."""
        try:
            client = self._get_backdoor_client()
            result = client.send_command("list_ui_elements", {})
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _backdoor_run_director(self, scene_filter: str = None) -> Dict[str, Any]:
        """Open the Director dialog."""
        try:
            client = self._get_backdoor_client()
            params = {}
            if scene_filter:
                params["scene_filter"] = scene_filter
            result = client.send_command("run_director", params)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _backdoor_set_zoom(self, zoom: int) -> Dict[str, Any]:
        """Set the storyboard zoom level."""
        try:
            client = self._get_backdoor_client()
            result = client.send_command("set_zoom", {"zoom": zoom})
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _backdoor_get_errors(self) -> Dict[str, Any]:
        """Get cached errors from the running app."""
        try:
            client = self._get_backdoor_client()
            result = client.send_command("get_errors", {})
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _backdoor_run_test_sequence(self, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Run a sequence of UI actions and capture errors."""
        try:
            client = self._get_backdoor_client()
            results = []
            errors = []

            for i, action in enumerate(actions):
                command = action.get("command", "")
                params = action.get("params", {})

                try:
                    result = client.send_command(command, params)
                    results.append({
                        "step": i + 1,
                        "command": command,
                        "result": result
                    })

                    if not result.get("success", False):
                        errors.append({
                            "step": i + 1,
                            "command": command,
                            "error": result.get("error", "Unknown error")
                        })
                except Exception as e:
                    errors.append({
                        "step": i + 1,
                        "command": command,
                        "error": str(e)
                    })

                # Small delay between actions
                import time
                time.sleep(0.5)

            # Get any errors from the app
            app_errors = client.send_command("get_errors", {})

            return {
                "success": len(errors) == 0,
                "steps_completed": len(results),
                "total_steps": len(actions),
                "results": results,
                "errors": errors,
                "app_errors": app_errors.get("errors", [])
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # CHARACTER MODIFICATION TOOLS
    # =========================================================================

    def _modify_character(
        self,
        character_tag: str,
        field: str,
        new_value: str,
        regenerate_frames: bool = False,
        archive_old_frames: bool = True
    ) -> Dict[str, Any]:
        """Modify a character's profile in the world bible."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        # Normalize tag
        tag = character_tag.upper()
        if not tag.startswith("CHAR_"):
            tag = f"CHAR_{tag}"

        # Load world_config.json (check both locations)
        config_path = self.project_path / "world_bible" / "world_config.json"
        if not config_path.exists():
            config_path = self.project_path / "world_config.json"
        if not config_path.exists():
            return {"success": False, "error": "world_config.json not found"}

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # Find the character
            characters = config.get("characters", [])
            char_found = None
            char_index = -1

            for i, char in enumerate(characters):
                if char.get("tag", "").upper() == tag:
                    char_found = char
                    char_index = i
                    break

            if char_found is None:
                return {"success": False, "error": f"Character {tag} not found in world_config.json"}

            # Valid fields
            valid_fields = [
                "name", "role", "age", "ethnicity", "backstory", "visual_appearance",
                "costume", "psychology", "personality", "speech_style", "physicality",
                "speech_patterns", "decision_heuristics", "literacy_level", "world_attributes"
            ]

            if field not in valid_fields:
                return {"success": False, "error": f"Invalid field '{field}'. Valid: {valid_fields}"}

            # Store old value for logging
            old_value = char_found.get(field, "")

            # Update the field
            char_found[field] = new_value
            characters[char_index] = char_found
            config["characters"] = characters

            # Save updated config
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            result = {
                "success": True,
                "character": tag,
                "field": field,
                "old_value": old_value[:100] + "..." if len(old_value) > 100 else old_value,
                "new_value": new_value[:100] + "..." if len(new_value) > 100 else new_value,
                "frames_archived": 0,
                "frames_regenerated": 0
            }

            # Archive old frames if requested
            if regenerate_frames and archive_old_frames:
                archive_result = self._archive_character_frames(tag, f"Character modification: {field}")
                result["frames_archived"] = archive_result.get("frames_archived", 0)

            # Regenerate frames if requested
            if regenerate_frames:
                regen_result = self._regenerate_character_frames(tag)
                result["frames_regenerated"] = regen_result.get("frames_regenerated", 0)

            return result

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _archive_character_frames(
        self,
        character_tag: str,
        archive_reason: str = "character update"
    ) -> Dict[str, Any]:
        """Archive all storyboard frames featuring a specific character."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        # Normalize tag
        tag = character_tag.upper()
        if not tag.startswith("CHAR_"):
            tag = f"CHAR_{tag}"

        try:
            # Find frames directory
            frames_dir = self.project_path / "storyboard_output"
            if not frames_dir.exists():
                return {"success": False, "error": "No storyboard_output directory found"}

            # Create archive directory
            archive_dir = self.project_path / ".archive" / "frames" / tag.lower()
            archive_dir.mkdir(parents=True, exist_ok=True)

            # Load visual_script.json to find frames with this character
            visual_script_path = self.project_path / "visual_script.json"
            frames_to_archive = []

            if visual_script_path.exists():
                with open(visual_script_path, "r", encoding="utf-8") as f:
                    visual_script = json.load(f)

                # Find frames with this character tag
                for scene in visual_script.get("scenes", []):
                    for frame in scene.get("frames", []):
                        frame_tags = frame.get("tags", [])
                        if tag in frame_tags or tag.replace("CHAR_", "") in frame_tags:
                            frame_id = frame.get("frame_id", "")
                            if frame_id:
                                frames_to_archive.append(frame_id)

            # Archive the frame images
            archived_count = 0
            import shutil
            from datetime import datetime

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for frame_id in frames_to_archive:
                # Look for frame image files
                for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                    frame_file = frames_dir / f"frame_{frame_id.replace('.', '_')}{ext}"
                    if frame_file.exists():
                        archive_name = f"{frame_id.replace('.', '_')}_{timestamp}{ext}"
                        shutil.move(str(frame_file), str(archive_dir / archive_name))
                        archived_count += 1
                        break

            # Log the archive action
            log_file = archive_dir / "archive_log.txt"
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"\n[{timestamp}] Archived {archived_count} frames\n")
                f.write(f"Reason: {archive_reason}\n")
                f.write(f"Frames: {', '.join(frames_to_archive)}\n")

            return {
                "success": True,
                "character": tag,
                "frames_archived": archived_count,
                "archive_path": str(archive_dir),
                "frame_ids": frames_to_archive
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _regenerate_character_frames(
        self,
        character_tag: str,
        use_reference: bool = True
    ) -> Dict[str, Any]:
        """Regenerate all storyboard frames featuring a specific character."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        # Normalize tag
        tag = character_tag.upper()
        if not tag.startswith("CHAR_"):
            tag = f"CHAR_{tag}"

        try:
            # Load visual_script.json to find frames with this character
            visual_script_path = self.project_path / "visual_script.json"
            if not visual_script_path.exists():
                return {"success": False, "error": "visual_script.json not found"}

            with open(visual_script_path, "r", encoding="utf-8") as f:
                visual_script = json.load(f)

            # Find frames with this character tag
            frames_to_regenerate = []
            for scene in visual_script.get("scenes", []):
                for frame in scene.get("frames", []):
                    frame_tags = frame.get("tags", [])
                    if tag in frame_tags or tag.replace("CHAR_", "") in frame_tags:
                        frame_id = frame.get("frame_id", "")
                        if frame_id:
                            frames_to_regenerate.append(frame_id)

            if not frames_to_regenerate:
                return {
                    "success": True,
                    "character": tag,
                    "frames_regenerated": 0,
                    "message": f"No frames found featuring {tag}"
                }

            # Use backdoor to trigger regeneration if app is running
            try:
                client = self._get_backdoor_client()
                result = client.send_command("regenerate_frames", {
                    "frame_ids": frames_to_regenerate,
                    "use_references": use_reference
                })
                return {
                    "success": result.get("success", False),
                    "character": tag,
                    "frames_regenerated": len(frames_to_regenerate),
                    "frame_ids": frames_to_regenerate
                }
            except Exception:
                # App not running - return info for manual regeneration
                return {
                    "success": True,
                    "character": tag,
                    "frames_to_regenerate": len(frames_to_regenerate),
                    "frame_ids": frames_to_regenerate,
                    "message": "App not running. Use these frame IDs to regenerate manually."
                }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _modify_content(
        self,
        entity_type: str,
        entity_name: str,
        new_value: Any = None,
        modification_type: str = "update",
        field: str = None,
        **kwargs
    ) -> Dict[str, Any]:
        """Modify content in project files. Generic wrapper for autonomous agent.

        Supports two formats:
        1. new_value as dict: {"ethnicity": "African American", "appearance": "..."}
        2. field + new_value: field="ethnicity", new_value="African American"
        """
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        entity_type = entity_type.lower()

        if entity_type == "character":
            # Map to modify_character for each field
            results = []
            tag = entity_name.upper()
            if not tag.startswith("CHAR_"):
                tag = f"CHAR_{tag}"

            # Handle both formats
            if field and new_value is not None:
                # Format 2: field + new_value as separate params
                fields_to_update = {field: new_value}
            elif isinstance(new_value, dict):
                # Format 1: new_value as dict
                fields_to_update = new_value
            elif new_value is not None:
                # Single value without field - try to infer
                return {"success": False, "error": "Must specify 'field' when new_value is not a dict"}
            else:
                return {"success": False, "error": "No new_value provided"}

            for fld, value in fields_to_update.items():
                if fld in ["ethnicity", "appearance", "visual_appearance", "costume", "name", "role", "age", "backstory"]:
                    # Map appearance to visual_appearance
                    actual_field = "visual_appearance" if fld == "appearance" else fld
                    result = self._modify_character(tag, actual_field, str(value))
                    results.append({"field": actual_field, "result": result})

            return {
                "success": all(r["result"].get("success", False) for r in results) if results else False,
                "entity_type": entity_type,
                "entity_name": entity_name,
                "modifications": results
            }

        elif entity_type == "location":
            # TODO: Implement location modification
            return {"success": False, "error": "Location modification not yet implemented"}

        elif entity_type == "prop":
            # TODO: Implement prop modification
            return {"success": False, "error": "Prop modification not yet implemented"}

        else:
            return {"success": False, "error": f"Unknown entity type: {entity_type}"}

    def _find_all_occurrences(
        self,
        entity_type: str,
        entity_name: str
    ) -> Dict[str, Any]:
        """Find all occurrences of an entity across project files."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        entity_type = entity_type.lower()
        occurrences = {
            "storyboard_frames": [],
            "script_mentions": [],
            "world_bible_refs": []
        }

        # Normalize tag
        tag = entity_name.upper()
        if entity_type == "character" and not tag.startswith("CHAR_"):
            tag = f"CHAR_{tag}"
        elif entity_type == "location" and not tag.startswith("LOC_"):
            tag = f"LOC_{tag}"
        elif entity_type == "prop" and not tag.startswith("PROP_"):
            tag = f"PROP_{tag}"

        try:
            # Search visual_script.json for storyboard frames
            visual_script_path = self.project_path / "storyboard" / "visual_script.json"
            if not visual_script_path.exists():
                visual_script_path = self.project_path / "visual_script.json"

            if visual_script_path.exists():
                with open(visual_script_path, "r", encoding="utf-8") as f:
                    visual_script = json.load(f)

                for scene in visual_script.get("scenes", []):
                    for frame in scene.get("frames", []):
                        frame_tags = frame.get("tags", [])
                        prompt = frame.get("prompt", "")
                        if tag in frame_tags or entity_name.upper() in prompt.upper():
                            occurrences["storyboard_frames"].append({
                                "frame_id": frame.get("frame_id", ""),
                                "scene": scene.get("scene_number", ""),
                                "prompt_preview": prompt[:100] + "..." if len(prompt) > 100 else prompt
                            })

            # Search script for mentions
            scripts_dir = self.project_path / "scripts"
            if scripts_dir.exists():
                for script_file in scripts_dir.glob("*.md"):
                    content = script_file.read_text(encoding="utf-8")
                    if entity_name.upper() in content.upper() or tag in content:
                        # Count mentions
                        count = content.upper().count(entity_name.upper())
                        occurrences["script_mentions"].append({
                            "file": script_file.name,
                            "mention_count": count
                        })

            return {
                "success": True,
                "entity_type": entity_type,
                "entity_name": entity_name,
                "tag": tag,
                "occurrences": occurrences,
                "total_frames": len(occurrences["storyboard_frames"]),
                "total_script_mentions": sum(m["mention_count"] for m in occurrences["script_mentions"])
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _generate_character_reference(
        self,
        character_tag: str,
        prompt_override: str = None,
        model: str = "nano_banana_pro"
    ) -> Dict[str, Any]:
        """Generate a new reference image for a character."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        # Normalize tag
        tag = character_tag.upper()
        if not tag.startswith("CHAR_"):
            tag = f"CHAR_{tag}"

        try:
            # Load character data from world_config
            config_path = self.project_path / "world_bible" / "world_config.json"
            if not config_path.exists():
                config_path = self.project_path / "world_config.json"

            if not config_path.exists():
                return {"success": False, "error": "world_config.json not found"}

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # Find character
            char_data = None
            for char in config.get("characters", []):
                if char.get("tag", "").upper() == tag:
                    char_data = char
                    break

            if not char_data:
                return {"success": False, "error": f"Character {tag} not found"}

            # Build prompt from character data
            if prompt_override:
                prompt = prompt_override
            else:
                name = char_data.get("name", "Character")
                appearance = char_data.get("visual_appearance", char_data.get("appearance", ""))
                costume = char_data.get("costume", "")
                ethnicity = char_data.get("ethnicity", "")
                age = char_data.get("age", "")

                prompt = f"Character portrait of {name}"
                if age:
                    prompt += f", {age}"
                if ethnicity:
                    prompt += f", {ethnicity}"
                if appearance:
                    prompt += f". {appearance}"
                if costume:
                    prompt += f" Wearing: {costume}"

            # Get style suffix from Context Engine (single source of truth)
            style_suffix = ""
            if self._context_engine:
                style_suffix = self._context_engine.get_world_style()

            # Generate image using ImageHandler with ContextEngine for world context
            from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel

            handler = ImageHandler(self.project_path, context_engine=self._context_engine)

            # Map model name
            model_map = {
                "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
                "nano_banana": ImageModel.NANO_BANANA,
                "seedream": ImageModel.SEEDREAM,
                "flux_kontext_pro": ImageModel.FLUX_KONTEXT_PRO
            }
            img_model = model_map.get(model.lower(), ImageModel.NANO_BANANA_PRO)

            # Create output path
            ref_dir = self.project_path / "references" / tag
            ref_dir.mkdir(parents=True, exist_ok=True)

            # Archive existing key reference if any
            existing_key = list(ref_dir.glob("*.key"))
            if existing_key:
                for key_file in existing_key:
                    key_file.rename(key_file.with_suffix(".key.old"))

            # Generate image
            import asyncio
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = ref_dir / f"{tag}_reference_{timestamp}.png"

            request = ImageRequest(
                prompt=prompt,  # Use prompt without inline style (style_suffix handles it)
                output_path=output_path,
                model=img_model,
                prefix_type="recreate",  # Use recreate template for character references
                style_suffix=style_suffix if style_suffix else None,
                add_clean_suffix=True
            )

            # Handle both sync and async contexts
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context - use nest_asyncio or run in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        lambda: asyncio.run(handler.generate(request))
                    )
                    result = future.result(timeout=120)
            except RuntimeError:
                # No running loop - create one
                result = asyncio.run(handler.generate(request))

            if result.success:
                # Mark as key reference
                img_path = result.image_path or output_path
                key_marker = img_path.with_suffix(img_path.suffix + ".key")
                key_marker.touch()

                return {
                    "success": True,
                    "character": tag,
                    "image_path": str(img_path),
                    "prompt_used": full_prompt[:200] + "..." if len(full_prompt) > 200 else full_prompt
                }
            else:
                return {"success": False, "error": result.error or "Image generation failed"}

        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # STORYBOARD FRAME SELECTION TOOLS
    # =========================================================================

    def _select_storyboard_frames(
        self,
        frame_ids: List[str],
        clear_existing: bool = True
    ) -> Dict[str, Any]:
        """Select specific storyboard frames by ID."""
        try:
            client = self._get_backdoor_client()
            result = client.send_command("select_frames", {
                "frame_ids": frame_ids,
                "clear_existing": clear_existing
            })
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _regenerate_selected_frames(
        self,
        use_references: bool = True,
        model: str = None
    ) -> Dict[str, Any]:
        """Regenerate all currently selected storyboard frames."""
        try:
            client = self._get_backdoor_client()
            params = {"use_references": use_references}
            if model:
                params["model"] = model
            result = client.send_command("regenerate_selected", params)
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_selected_frames(self) -> Dict[str, Any]:
        """Get the list of currently selected storyboard frames."""
        try:
            client = self._get_backdoor_client()
            result = client.send_command("get_selected_frames", {})
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _regenerate_frames_by_character(
        self,
        character_tag: str,
        model: str = None
    ) -> Dict[str, Any]:
        """Regenerate all storyboard frames containing a specific character.

        This finds all frames with the character, uses their updated reference image,
        and regenerates each frame.
        """
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        # Normalize tag
        tag = character_tag.upper()
        if not tag.startswith("CHAR_"):
            tag = f"CHAR_{tag}"

        try:
            # Step 1: Find all frames with this character
            frames_result = self._find_frames_by_character(tag)
            if not frames_result.get("success", False):
                return frames_result

            # Extract frame_ids from frames list
            frames_list = frames_result.get("frames", [])
            frame_ids = [f.get("frame_id") for f in frames_list if f.get("frame_id")]
            if not frame_ids:
                return {"success": True, "message": f"No frames found with {tag}", "regenerated": 0}

            # Step 2: Get the key reference image for this character
            ref_dir = self.project_path / "references" / tag
            key_ref_path = None
            if ref_dir.exists():
                key_files = list(ref_dir.glob("*.key"))
                if key_files:
                    # Key file is a marker, actual image has same name without .key
                    key_marker = key_files[0]
                    img_path = key_marker.with_suffix("")
                    if img_path.exists():
                        key_ref_path = img_path

            if not key_ref_path:
                return {"success": False, "error": f"No key reference image found for {tag}"}

            # Step 3: Load visual script
            visual_script_path = self.project_path / "storyboard" / "visual_script.json"
            if not visual_script_path.exists():
                return {"success": False, "error": "visual_script.json not found"}

            with open(visual_script_path, "r", encoding="utf-8") as f:
                visual_script = json.load(f)

            # Step 4: Regenerate each frame
            from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel
            import asyncio

            handler = ImageHandler(self.project_path, context_engine=self._context_engine)

            # Map model name
            img_model = ImageModel.SEEDREAM  # Default for storyboard
            if model:
                model_map = {
                    "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
                    "nano_banana": ImageModel.NANO_BANANA,
                    "seedream": ImageModel.SEEDREAM,
                    "flux_kontext_pro": ImageModel.FLUX_KONTEXT_PRO
                }
                img_model = model_map.get(model.lower(), ImageModel.SEEDREAM)

            # Get style suffix using canonical style_utils
            style_suffix = ""
            if self.project_path:
                from greenlight.core.style_utils import get_style_suffix as _get_style_suffix
                style_suffix = _get_style_suffix(project_path=self.project_path)

            regenerated = []
            failed = []

            # Helper to generate a single frame
            async def generate_frame(frame_id: str) -> Dict[str, Any]:
                # Parse frame_id (e.g., "1.2")
                parts = frame_id.split(".")
                if len(parts) < 2:
                    return {"frame_id": frame_id, "success": False, "error": "Invalid frame_id format"}
                scene_num, frame_num = int(parts[0]), int(parts[1])

                # Find frame in visual script
                frame_data = None
                for scene in visual_script.get("scenes", []):
                    if scene.get("scene_number") == scene_num:
                        for frame in scene.get("frames", []):
                            if frame.get("frame_number") == frame_num:
                                frame_data = frame
                                break
                        break

                if not frame_data:
                    return {"frame_id": frame_id, "success": False, "error": "Frame not found in visual script"}

                # Build prompt
                prompt = frame_data.get("prompt", "")
                if style_suffix:
                    prompt = f"{prompt}. Style: {style_suffix}"

                # Output path
                output_dir = self.project_path / "storyboard" / "frames"
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / f"frame_{scene_num}_{frame_num}.png"

                # Archive existing
                if output_path.exists():
                    archive_dir = self.project_path / "storyboard" / ".archive"
                    archive_dir.mkdir(parents=True, exist_ok=True)
                    from datetime import datetime
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    archive_path = archive_dir / f"frame_{scene_num}_{frame_num}_{timestamp}.png"
                    output_path.rename(archive_path)

                # Create request with reference image
                request = ImageRequest(
                    prompt=prompt,
                    output_path=output_path,
                    model=img_model,
                    reference_images=[key_ref_path],
                    prefix_type="edit",
                    style_suffix=style_suffix
                )

                result = await handler.generate(request)
                return {"frame_id": frame_id, "success": result.success, "error": result.error}

            # Process all frames
            async def process_all_frames():
                results = []
                for frame_id in frame_ids:
                    result = await generate_frame(frame_id)
                    results.append(result)
                return results

            # Handle both sync and async contexts
            import concurrent.futures
            try:
                asyncio.get_running_loop()
                # We're in an async context - run in thread
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(process_all_frames()))
                    results = future.result(timeout=600)  # 10 min timeout for multiple frames
            except RuntimeError:
                # No running loop - create one
                results = asyncio.run(process_all_frames())

            for r in results:
                if r.get("success"):
                    regenerated.append(r["frame_id"])
                else:
                    failed.append({"frame_id": r["frame_id"], "error": r.get("error")})

            return {
                "success": len(failed) == 0,
                "character": tag,
                "reference_used": str(key_ref_path),
                "regenerated": regenerated,
                "failed": failed,
                "total_frames": len(frame_ids)
            }

        except Exception as e:
            logger.error(f"Failed to regenerate frames: {e}")
            return {"success": False, "error": str(e)}

    def _regenerate_single_frame(
        self,
        frame_id: str,
        model: str = None
    ) -> Dict[str, Any]:
        """Regenerate a single storyboard frame by its frame_id."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel
        import asyncio

        try:
            # Parse frame_id
            parts = frame_id.split(".")
            if len(parts) < 2:
                return {"success": False, "error": f"Invalid frame_id format: {frame_id}"}
            scene_num, frame_num = int(parts[0]), int(parts[1])

            # Load visual script
            script_path = self.project_path / "storyboard" / "visual_script.json"
            if not script_path.exists():
                return {"success": False, "error": "Visual script not found"}

            import json
            with open(script_path, "r", encoding="utf-8") as f:
                visual_script = json.load(f)

            # Find frame data
            frame_data = None
            for scene in visual_script.get("scenes", []):
                if scene.get("scene_number") == scene_num:
                    for frame in scene.get("frames", []):
                        if frame.get("frame_number") == frame_num:
                            frame_data = frame
                            break
                    break

            if not frame_data:
                return {"success": False, "error": f"Frame {frame_id} not found in visual script"}

            # Get prompt
            prompt = frame_data.get("prompt", "")
            if not prompt:
                return {"success": False, "error": f"No prompt found for frame {frame_id}"}

            # Get style context using canonical style_utils
            style_suffix = ""
            if self.project_path:
                from greenlight.core.style_utils import get_style_suffix as _get_style_suffix
                style_suffix = _get_style_suffix(project_path=self.project_path)
                if style_suffix:
                    prompt = f"{prompt}. Style: {style_suffix}"

            # Determine model
            img_model = ImageModel.SEEDREAM
            if model:
                model_lower = model.lower()
                if "nano" in model_lower or "gemini" in model_lower:
                    img_model = ImageModel.NANO_BANANA
                elif "flux" in model_lower:
                    img_model = ImageModel.FLUX_KONTEXT

            # Output path
            output_dir = self.project_path / "storyboard" / "frames"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"frame_{scene_num}_{frame_num}.png"

            # Archive existing
            if output_path.exists():
                archive_dir = self.project_path / "storyboard" / ".archive"
                archive_dir.mkdir(parents=True, exist_ok=True)
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_path = archive_dir / f"frame_{scene_num}_{frame_num}_{timestamp}.png"
                output_path.rename(archive_path)

            # Find character references in prompt (tags MUST be in brackets per notation standard)
            reference_images = []
            import re
            char_tags = re.findall(r'\[(CHAR_[A-Z0-9_]+)\]', prompt)
            for tag in set(char_tags):
                ref_dir = self.project_path / "references" / tag
                if ref_dir.exists():
                    # Find key reference
                    for f in ref_dir.iterdir():
                        if f.suffix == ".key":
                            key_img = ref_dir / f.stem
                            if key_img.exists():
                                reference_images.append(key_img)
                                break

            # Create handler and request with ContextEngine for world context
            handler = ImageHandler(project_path=self.project_path, context_engine=self._context_engine)
            request = ImageRequest(
                prompt=prompt,
                output_path=output_path,
                model=img_model,
                reference_images=reference_images if reference_images else None,
                prefix_type="generate",
                style_suffix=style_suffix
            )

            # Generate
            async def do_generate():
                return await handler.generate(request)

            import concurrent.futures
            try:
                asyncio.get_running_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(do_generate()))
                    result = future.result(timeout=120)
            except RuntimeError:
                result = asyncio.run(do_generate())

            return {
                "success": result.success,
                "frame_id": frame_id,
                "output_path": str(result.image_path or output_path),
                "model_used": result.model_used,
                "error": result.error
            }

        except Exception as e:
            logger.error(f"Failed to regenerate frame {frame_id}: {e}")
            return {"success": False, "error": str(e)}

    def _continuity_check(
        self,
        user_request: str,
        auto_fix: bool = True
    ) -> Dict[str, Any]:
        """Analyze storyboard frames for continuity issues using Gemini 2.5."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        from greenlight.omni_mind.autonomous_agent import AutonomousTaskManager
        import asyncio

        try:
            manager = AutonomousTaskManager(
                project_path=self.project_path,
                tool_executor=self
            )

            async def run_check():
                return await manager.execute_continuity_check(user_request, auto_fix=auto_fix)

            import concurrent.futures
            try:
                asyncio.get_running_loop()
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(run_check()))
                    result = future.result(timeout=300)  # 5 min timeout
            except RuntimeError:
                result = asyncio.run(run_check())

            return result

        except Exception as e:
            logger.error(f"Continuity check failed: {e}")
            return {"success": False, "error": str(e)}

    # =========================================================================
    # PROJECT LIFECYCLE MANAGEMENT IMPLEMENTATIONS
    # =========================================================================

    def _log_error_pattern(
        self,
        error_type: str,
        error_message: str,
        solution: str,
        context: str = ""
    ) -> Dict[str, Any]:
        """Log an error pattern and solution for learning."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        try:
            import json
            from datetime import datetime

            health_dir = self.project_path / ".health"
            health_dir.mkdir(exist_ok=True)

            patterns_file = health_dir / "error_patterns.json"

            # Load existing patterns
            patterns = []
            if patterns_file.exists():
                patterns = json.loads(patterns_file.read_text(encoding='utf-8'))

            # Add new pattern
            pattern = {
                "id": f"err_{len(patterns):04d}",
                "error_type": error_type,
                "error_message": error_message,
                "solution": solution,
                "context": context,
                "logged_at": datetime.now().isoformat(),
                "times_matched": 0
            }
            patterns.append(pattern)

            # Save
            patterns_file.write_text(json.dumps(patterns, indent=2), encoding='utf-8')

            return {
                "success": True,
                "pattern_id": pattern["id"],
                "message": f"Logged error pattern: {error_type}",
                "total_patterns": len(patterns)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _get_error_patterns(self, error_type: str = None) -> Dict[str, Any]:
        """Get logged error patterns for self-healing reference."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        try:
            import json

            patterns_file = self.project_path / ".health" / "error_patterns.json"

            if not patterns_file.exists():
                return {"success": True, "patterns": [], "count": 0}

            patterns = json.loads(patterns_file.read_text(encoding='utf-8'))

            # Filter by type if specified
            if error_type:
                patterns = [p for p in patterns if p["error_type"].lower() == error_type.lower()]

            return {
                "success": True,
                "patterns": patterns,
                "count": len(patterns)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _run_project_lifecycle(
        self,
        stages: List[str] = None,
        dry_run: bool = False,
        auto_heal: bool = True
    ) -> Dict[str, Any]:
        """Run the complete project lifecycle."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        stages = stages or ["writer", "director", "images"]
        results = []
        errors = []

        if dry_run:
            return {
                "dry_run": True,
                "stages": stages,
                "message": f"Would run stages: {', '.join(stages)}",
                "estimated_duration": "15-30 minutes"
            }

        for stage in stages:
            try:
                if stage == "writer":
                    result = self._run_writer()
                elif stage == "director":
                    result = self._run_director()
                elif stage == "images":
                    result = self._generate_storyboard()
                else:
                    result = {"error": f"Unknown stage: {stage}"}

                results.append({"stage": stage, "result": result})

                if result.get("error"):
                    errors.append({"stage": stage, "error": result["error"]})
                    if auto_heal:
                        heal_result = self._self_heal_project(target="all", auto_fix=True)
                        results.append({"stage": f"{stage}_heal", "result": heal_result})

            except Exception as e:
                errors.append({"stage": stage, "error": str(e)})

        return {
            "success": len(errors) == 0,
            "stages_completed": [r["stage"] for r in results if not r["result"].get("error")],
            "results": results,
            "errors": errors
        }

    def _get_project_status(self) -> Dict[str, Any]:
        """Get comprehensive project status."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        try:
            import json

            status = {
                "project_path": str(self.project_path),
                "project_name": self.project_path.name,
                "structure": {},
                "pipelines": {},
                "health": {},
                "errors": []
            }

            # Check structure
            dirs_to_check = [
                ("world_bible", "World Bible"),
                ("scripts", "Scripts"),
                ("storyboards", "Storyboards"),
                ("storyboard_output", "Generated Images"),
                ("references", "References"),
                (".health", "Health Logs")
            ]

            for dir_name, label in dirs_to_check:
                dir_path = self.project_path / dir_name
                if dir_path.exists():
                    file_count = sum(1 for f in dir_path.rglob("*") if f.is_file())
                    status["structure"][dir_name] = {"exists": True, "files": file_count}
                else:
                    status["structure"][dir_name] = {"exists": False}

            # Check pipeline outputs
            pitch_path = self.project_path / "world_bible" / "pitch.md"
            script_path = self.project_path / "scripts" / "script.md"
            storyboard_path = self.project_path / "storyboards" / "storyboard_prompts.json"

            status["pipelines"]["writer"] = "complete" if script_path.exists() else "pending"
            status["pipelines"]["director"] = "complete" if storyboard_path.exists() else "pending"

            # Count generated images
            images_dir = self.project_path / "storyboard_output" / "generated"
            if images_dir.exists():
                image_count = len(list(images_dir.glob("*.png"))) + len(list(images_dir.glob("*.jpg")))
                status["pipelines"]["images"] = f"{image_count} generated"
            else:
                status["pipelines"]["images"] = "pending"

            # Load health info
            health_file = self.project_path / ".health" / "health_report.md"
            if health_file.exists():
                status["health"]["last_report"] = health_file.stat().st_mtime

            # Load error patterns
            patterns_file = self.project_path / ".health" / "error_patterns.json"
            if patterns_file.exists():
                patterns = json.loads(patterns_file.read_text(encoding='utf-8'))
                status["health"]["error_patterns"] = len(patterns)

            return {"success": True, "status": status}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _self_heal_project(
        self,
        target: str = "all",
        auto_fix: bool = True
    ) -> Dict[str, Any]:
        """Run self-healing diagnostics and auto-fix."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        issues = []
        fixed = []

        try:
            # Check and fix structure
            if target in ["structure", "all"]:
                required_dirs = [
                    "world_bible", "scripts", "storyboards",
                    "storyboard_output", "references", ".health"
                ]
                for dir_name in required_dirs:
                    dir_path = self.project_path / dir_name
                    if not dir_path.exists():
                        issues.append({"type": "missing_dir", "path": dir_name})
                        if auto_fix:
                            dir_path.mkdir(parents=True, exist_ok=True)
                            fixed.append(f"Created directory: {dir_name}")

            # Check for required files
            if target in ["structure", "all"]:
                pitch_path = self.project_path / "world_bible" / "pitch.md"
                if not pitch_path.exists():
                    issues.append({"type": "missing_file", "path": "world_bible/pitch.md"})

            # Check tags consistency
            if target in ["tags", "all"]:
                world_config = self.project_path / "world_bible" / "world_config.json"
                if world_config.exists():
                    import json
                    config = json.loads(world_config.read_text(encoding='utf-8'))
                    # Check for characters without references
                    for char in config.get("characters", []):
                        tag = char.get("tag", "")
                        ref_dir = self.project_path / "references" / tag
                        if not ref_dir.exists():
                            issues.append({"type": "missing_reference", "tag": tag})

            return {
                "success": True,
                "issues_found": len(issues),
                "issues": issues,
                "auto_fixed": len(fixed),
                "fixed": fixed
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _create_task(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        category: str = "pipeline"
    ) -> Dict[str, Any]:
        """Create a task for OmniMind to track."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        try:
            import json
            from datetime import datetime
            import uuid

            health_dir = self.project_path / ".health"
            health_dir.mkdir(exist_ok=True)

            tasks_file = health_dir / "tasks.json"

            # Load existing tasks
            tasks = []
            if tasks_file.exists():
                tasks = json.loads(tasks_file.read_text(encoding='utf-8'))

            # Create new task
            task = {
                "id": str(uuid.uuid4())[:8],
                "title": title,
                "description": description,
                "priority": priority,
                "category": category,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            tasks.append(task)

            # Save
            tasks_file.write_text(json.dumps(tasks, indent=2), encoding='utf-8')

            return {
                "success": True,
                "task_id": task["id"],
                "message": f"Created task: {title}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _list_tasks(self, status: str = "pending") -> Dict[str, Any]:
        """List tasks for the current project."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        try:
            import json

            tasks_file = self.project_path / ".health" / "tasks.json"

            if not tasks_file.exists():
                return {"success": True, "tasks": [], "count": 0}

            tasks = json.loads(tasks_file.read_text(encoding='utf-8'))

            # Filter by status
            if status != "all":
                tasks = [t for t in tasks if t["status"] == status]

            return {
                "success": True,
                "tasks": tasks,
                "count": len(tasks)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _execute_task(self, task_id: str) -> Dict[str, Any]:
        """Execute a specific task by ID."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        try:
            import json
            from datetime import datetime

            tasks_file = self.project_path / ".health" / "tasks.json"

            if not tasks_file.exists():
                return {"success": False, "error": "No tasks file found"}

            tasks = json.loads(tasks_file.read_text(encoding='utf-8'))

            # Find task
            task = next((t for t in tasks if t["id"] == task_id), None)
            if not task:
                return {"success": False, "error": f"Task not found: {task_id}"}

            # Update status
            task["status"] = "in_progress"
            task["updated_at"] = datetime.now().isoformat()

            # Execute based on category
            result = None
            if task["category"] == "pipeline":
                if "writer" in task["title"].lower():
                    result = self._run_writer()
                elif "director" in task["title"].lower():
                    result = self._run_director()
                else:
                    result = {"message": "Manual execution required"}
            elif task["category"] == "fix":
                result = self._self_heal_project()
            else:
                result = {"message": "Task type requires manual execution"}

            # Update task status
            task["status"] = "completed" if result and not result.get("error") else "failed"
            task["result"] = result
            task["updated_at"] = datetime.now().isoformat()

            # Save
            tasks_file.write_text(json.dumps(tasks, indent=2), encoding='utf-8')

            return {
                "success": True,
                "task_id": task_id,
                "status": task["status"],
                "result": result
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _generate_health_report(self) -> Dict[str, Any]:
        """Generate and save a comprehensive health report."""
        if not self.project_path:
            return {"success": False, "error": "No project loaded"}

        try:
            from datetime import datetime

            health_dir = self.project_path / ".health"
            health_dir.mkdir(exist_ok=True)

            # Get project status
            status_result = self._get_project_status()
            status = status_result.get("status", {})

            # Get error patterns
            patterns_result = self._get_error_patterns()
            patterns = patterns_result.get("patterns", [])

            # Get tasks
            tasks_result = self._list_tasks(status="all")
            tasks = tasks_result.get("tasks", [])

            # Generate report
            lines = [
                "# Project Health Report",
                f"**Generated:** {datetime.now().isoformat()}",
                f"**Project:** {self.project_path.name}",
                "",
                "## Structure Status",
                ""
            ]

            for dir_name, info in status.get("structure", {}).items():
                icon = "✅" if info.get("exists") else "❌"
                files = f" ({info.get('files', 0)} files)" if info.get("exists") else ""
                lines.append(f"- {icon} {dir_name}{files}")

            lines.extend([
                "",
                "## Pipeline Status",
                ""
            ])

            for pipeline, state in status.get("pipelines", {}).items():
                icon = "✅" if state == "complete" or "generated" in str(state) else "⏳"
                lines.append(f"- {icon} {pipeline}: {state}")

            if patterns:
                lines.extend([
                    "",
                    "## Error Patterns Logged",
                    ""
                ])
                for p in patterns[-5:]:
                    lines.append(f"- **{p['error_type']}**: {p['error_message'][:50]}...")

            if tasks:
                lines.extend([
                    "",
                    "## Tasks",
                    ""
                ])
                for t in tasks[-5:]:
                    icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅", "failed": "❌"}.get(t["status"], "❓")
                    lines.append(f"- {icon} [{t['priority']}] {t['title']}")

            lines.extend([
                "",
                "---",
                "*Generated by OmniMind Project Health Logger*"
            ])

            report = "\n".join(lines)
            report_path = health_dir / "health_report.md"
            report_path.write_text(report, encoding='utf-8')

            return {
                "success": True,
                "report_path": str(report_path),
                "message": "Health report generated"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # END-TO-END PIPELINE METHODS (OmniMind Autonomous Execution)
    # =========================================================================

    # Pipeline state tracking
    _e2e_pipeline_state: Dict[str, Any] = {}

    def _run_e2e_pipeline(
        self,
        llm: str = "claude-haiku-4.5",
        image_model: str = "seedream",
        generate_references: bool = True,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """Run complete end-to-end pipeline: Writer → Director → References → Storyboard.

        Uses Claude Haiku 4.5 as primary LLM and Seedream 4.5 for storyboard images.
        Frame count is determined autonomously by the Director pipeline.
        """
        if not self.project_path:
            return {"error": "No project loaded"}

        # Map LLM names to actual model identifiers
        llm_map = {
            "claude-haiku-4.5": "claude-haiku",
            "claude-haiku": "claude-haiku",
            "claude-opus-4.5": "claude-opus",
            "claude-opus": "claude-opus",
            "gemini-flash": "gemini-flash",
            "grok-4": "grok-4"
        }
        llm_id = llm_map.get(llm, "claude-haiku")

        # Initialize pipeline state
        self._e2e_pipeline_state = {
            "status": "initializing",
            "started_at": None,
            "stages": {
                "writer": {"status": "pending", "result": None},
                "director": {"status": "pending", "result": None},
                "references": {"status": "pending", "result": None},
                "storyboard": {"status": "pending", "result": None}
            },
            "config": {
                "llm": llm,
                "image_model": image_model,
                "frame_count": "autonomous",
                "generate_references": generate_references
            },
            "errors": []
        }

        if dry_run:
            return {
                "dry_run": True,
                "pipeline": "Writer → Director → References → Storyboard",
                "config": self._e2e_pipeline_state["config"],
                "message": f"Would run: Writer({llm}) → Director({llm}, autonomous frames) → References → Storyboard({image_model})"
            }

        try:
            from datetime import datetime
            from greenlight.omni_mind.backdoor import BackdoorClient

            self._e2e_pipeline_state["started_at"] = datetime.now().isoformat()
            self._e2e_pipeline_state["status"] = "running"

            client = BackdoorClient()

            # Stage 1: Writer Pipeline
            logger.info(f"E2E Pipeline: Starting Writer ({llm})")
            self._e2e_pipeline_state["stages"]["writer"]["status"] = "running"

            writer_result = client.send_command("run_writer", {
                "auto_run": True,
                "llm": llm_id,
                "media_type": "brief",
                "visual_style": "live_action"
            }, timeout=300)

            if not writer_result.get("success"):
                self._e2e_pipeline_state["stages"]["writer"]["status"] = "failed"
                self._e2e_pipeline_state["stages"]["writer"]["result"] = writer_result
                self._e2e_pipeline_state["status"] = "failed"
                self._e2e_pipeline_state["errors"].append(f"Writer failed: {writer_result.get('error')}")
                return {"error": f"Writer pipeline failed: {writer_result.get('error')}"}

            self._e2e_pipeline_state["stages"]["writer"]["status"] = "complete"
            self._e2e_pipeline_state["stages"]["writer"]["result"] = writer_result

            # Stage 2: Director Pipeline (frame count determined autonomously)
            logger.info(f"E2E Pipeline: Starting Director ({llm}, autonomous frame count)")
            self._e2e_pipeline_state["stages"]["director"]["status"] = "running"

            director_result = client.send_command("run_director", {
                "auto_run": True,
                "llm": llm_id
            }, timeout=300)

            if not director_result.get("success"):
                self._e2e_pipeline_state["stages"]["director"]["status"] = "failed"
                self._e2e_pipeline_state["stages"]["director"]["result"] = director_result
                self._e2e_pipeline_state["status"] = "failed"
                self._e2e_pipeline_state["errors"].append(f"Director failed: {director_result.get('error')}")
                return {"error": f"Director pipeline failed: {director_result.get('error')}"}

            self._e2e_pipeline_state["stages"]["director"]["status"] = "complete"
            self._e2e_pipeline_state["stages"]["director"]["result"] = director_result

            # Stage 3: Reference Image Generation (if enabled)
            if generate_references:
                logger.info("E2E Pipeline: Generating reference images")
                self._e2e_pipeline_state["stages"]["references"]["status"] = "running"

                ref_result = self._generate_all_reference_images(
                    tag_types=["character", "location", "prop"],
                    model="nano_banana_pro",
                    overwrite=False
                )

                if ref_result.get("error"):
                    self._e2e_pipeline_state["stages"]["references"]["status"] = "failed"
                    self._e2e_pipeline_state["stages"]["references"]["result"] = ref_result
                    # Don't fail entire pipeline for reference errors
                    self._e2e_pipeline_state["errors"].append(f"References warning: {ref_result.get('error')}")
                else:
                    self._e2e_pipeline_state["stages"]["references"]["status"] = "complete"
                    self._e2e_pipeline_state["stages"]["references"]["result"] = ref_result
            else:
                self._e2e_pipeline_state["stages"]["references"]["status"] = "skipped"

            # Stage 4: Storyboard Generation
            logger.info(f"E2E Pipeline: Starting Storyboard ({image_model})")
            self._e2e_pipeline_state["stages"]["storyboard"]["status"] = "running"

            storyboard_result = client.send_command("run_storyboard", {
                "model": image_model
            }, timeout=600)

            if not storyboard_result.get("success"):
                self._e2e_pipeline_state["stages"]["storyboard"]["status"] = "failed"
                self._e2e_pipeline_state["stages"]["storyboard"]["result"] = storyboard_result
                self._e2e_pipeline_state["status"] = "failed"
                self._e2e_pipeline_state["errors"].append(f"Storyboard failed: {storyboard_result.get('error')}")
                return {"error": f"Storyboard generation failed: {storyboard_result.get('error')}"}

            self._e2e_pipeline_state["stages"]["storyboard"]["status"] = "complete"
            self._e2e_pipeline_state["stages"]["storyboard"]["result"] = storyboard_result
            self._e2e_pipeline_state["status"] = "complete"

            return {
                "success": True,
                "message": "End-to-end pipeline completed successfully",
                "stages": self._e2e_pipeline_state["stages"],
                "config": self._e2e_pipeline_state["config"]
            }

        except Exception as e:
            self._e2e_pipeline_state["status"] = "failed"
            self._e2e_pipeline_state["errors"].append(str(e))
            return {"error": f"E2E pipeline failed: {e}"}

    def _generate_all_reference_images(
        self,
        tag_types: List[str] = None,
        model: str = "nano_banana_pro",
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """Generate reference images for all extracted tags."""
        if not self.project_path:
            return {"error": "No project loaded"}

        tag_types = tag_types or ["character", "location", "prop"]

        try:
            import asyncio
            import json
            from datetime import datetime
            from greenlight.core.image_handler import ImageHandler, ImageRequest, ImageModel

            # Load world config for tag descriptions
            world_config_path = self.project_path / "world_bible" / "world_config.json"
            world_config = {}
            if world_config_path.exists():
                world_config = json.loads(world_config_path.read_text(encoding='utf-8'))

            # Get style suffix from Context Engine (single source of truth)
            style_suffix = ""
            if self._context_engine:
                style_suffix = self._context_engine.get_world_style()

            # Map model name
            model_map = {
                "nano_banana_pro": ImageModel.NANO_BANANA_PRO,
                "nano_banana": ImageModel.NANO_BANANA,
                "seedream": ImageModel.SEEDREAM
            }
            img_model = model_map.get(model.lower(), ImageModel.NANO_BANANA_PRO)

            handler = ImageHandler(project_path=self.project_path, context_engine=self._context_engine)
            generated = []
            skipped = []
            errors = []

            # Process each tag type
            for tag_type in tag_types:
                entities = world_config.get(f"{tag_type}s", [])
                if not entities:
                    continue

                for entity in entities:
                    tag = entity.get("tag", "")
                    name = entity.get("name", tag)
                    description = entity.get("description", "")

                    if not tag:
                        continue

                    # Check if reference already exists
                    ref_dir = self.project_path / "references" / tag
                    if ref_dir.exists() and not overwrite:
                        key_files = list(ref_dir.glob("*.key"))
                        if key_files:
                            skipped.append(tag)
                            continue

                    # Build prompt based on tag type
                    # NOTE: Style is handled via style_suffix, not inline in prompt
                    if tag_type == "character":
                        # Extract all visual attributes for characters
                        age = entity.get("age", "")
                        ethnicity = entity.get("ethnicity", "")
                        appearance = entity.get("appearance", entity.get("visual_appearance", description))
                        costume = entity.get("costume", "")

                        # Build comprehensive character prompt (no inline style)
                        char_prompt_parts = [f"Reference portrait of {name}"]
                        if age:
                            char_prompt_parts.append(f"Age: {age}")
                        if ethnicity:
                            char_prompt_parts.append(f"Ethnicity: {ethnicity}")
                        if appearance:
                            char_prompt_parts.append(f"Appearance: {appearance}")
                        if costume:
                            char_prompt_parts.append(f"Costume: {costume}")
                        char_prompt_parts.append("Composition: Character reference, neutral pose, clear lighting.")

                        prompt = ". ".join(char_prompt_parts)
                    elif tag_type == "location":
                        # Extract all location attributes
                        atmosphere = entity.get("atmosphere", "")
                        time_period = entity.get("time_period", "")
                        directional_views = entity.get("directional_views", {})
                        north_view = directional_views.get("north", "")

                        # Build comprehensive location prompt (no inline style)
                        loc_prompt_parts = [f"Reference image of {name} (NORTH VIEW)"]
                        if time_period:
                            loc_prompt_parts.append(f"Time Period: {time_period}")
                        if description:
                            loc_prompt_parts.append(f"Description: {description}")
                        if atmosphere:
                            loc_prompt_parts.append(f"Atmosphere: {atmosphere}")
                        if north_view:
                            loc_prompt_parts.append(f"North View: {north_view}")
                        loc_prompt_parts.append("Composition: Wide establishing shot facing NORTH, clear details.")

                        prompt = ". ".join(loc_prompt_parts)
                    else:  # prop
                        # Extract all prop attributes
                        appearance = entity.get("appearance", description)
                        significance = entity.get("significance", "")
                        associated_char = entity.get("associated_character", "")

                        # Build comprehensive prop prompt (no inline style)
                        prop_prompt_parts = [f"Reference image of {name}"]
                        if appearance:
                            prop_prompt_parts.append(f"Appearance: {appearance}")
                        if significance:
                            prop_prompt_parts.append(f"Significance: {significance}")
                        if associated_char:
                            prop_prompt_parts.append(f"Associated with: {associated_char}")
                        prop_prompt_parts.append("Composition: Product shot, clear details, neutral background.")

                        prompt = ". ".join(prop_prompt_parts)

                    # Create output path
                    ref_dir.mkdir(parents=True, exist_ok=True)
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_path = ref_dir / f"{tag}_reference_{timestamp}.png"

                    request = ImageRequest(
                        prompt=prompt,
                        output_path=output_path,
                        model=img_model,
                        aspect_ratio="16:9",
                        tag=tag,
                        prefix_type="recreate",  # Use recreate template for reference generation
                        style_suffix=style_suffix if style_suffix else None,
                        add_clean_suffix=True
                    )

                    try:
                        result = asyncio.run(handler.generate(request))
                        if result.success:
                            # Mark as key reference
                            key_marker = output_path.with_suffix(output_path.suffix + ".key")
                            key_marker.touch()
                            generated.append({"tag": tag, "path": str(output_path)})
                            logger.info(f"Generated reference for {tag}")
                        else:
                            errors.append({"tag": tag, "error": result.error})
                    except Exception as e:
                        errors.append({"tag": tag, "error": str(e)})

            return {
                "success": True,
                "generated": generated,
                "skipped": skipped,
                "errors": errors,
                "counts": {
                    "generated": len(generated),
                    "skipped": len(skipped),
                    "errors": len(errors)
                }
            }

        except Exception as e:
            return {"error": f"Reference generation failed: {e}"}

    def _wait_for_pipeline(
        self,
        pipeline_name: str = "any",
        timeout_seconds: int = 300
    ) -> Dict[str, Any]:
        """Wait for a running pipeline to complete."""
        import time

        start_time = time.time()
        poll_interval = 5

        while (time.time() - start_time) < timeout_seconds:
            status = self._get_e2e_pipeline_status()

            if pipeline_name == "any":
                # Check overall status
                if status.get("status") in ["complete", "failed"]:
                    return {
                        "success": True,
                        "status": status.get("status"),
                        "elapsed_seconds": int(time.time() - start_time),
                        "pipeline_status": status
                    }
            else:
                # Check specific stage
                stage_status = status.get("stages", {}).get(pipeline_name, {}).get("status")
                if stage_status in ["complete", "failed", "skipped"]:
                    return {
                        "success": True,
                        "pipeline": pipeline_name,
                        "status": stage_status,
                        "elapsed_seconds": int(time.time() - start_time)
                    }

            time.sleep(poll_interval)

        return {
            "success": False,
            "error": f"Timeout after {timeout_seconds} seconds",
            "last_status": self._get_e2e_pipeline_status()
        }

    def _get_e2e_pipeline_status(self) -> Dict[str, Any]:
        """Get detailed status of the end-to-end pipeline execution."""
        if not self._e2e_pipeline_state:
            return {
                "status": "not_started",
                "message": "No E2E pipeline has been run"
            }

        return {
            "status": self._e2e_pipeline_state.get("status", "unknown"),
            "started_at": self._e2e_pipeline_state.get("started_at"),
            "stages": self._e2e_pipeline_state.get("stages", {}),
            "config": self._e2e_pipeline_state.get("config", {}),
            "errors": self._e2e_pipeline_state.get("errors", [])
        }

    # =========================================================================
    # SELF-CORRECTION TOOLS IMPLEMENTATION
    # =========================================================================

    def _detect_missing_characters(self) -> Dict[str, Any]:
        """Detect consensus-approved character tags missing from world_config.json.

        Compares all_tags (consensus output) with characters array in world_config.json.
        Returns list of missing character tags.
        """
        if not self.project_path:
            return {"error": "No project loaded"}

        world_config_path = self.project_path / "world_bible" / "world_config.json"

        if not world_config_path.exists():
            return {"error": "world_config.json not found"}

        try:
            world_config = json.loads(world_config_path.read_text(encoding="utf-8"))

            # Get consensus-approved character tags from all_tags
            all_tags = world_config.get("all_tags", [])
            consensus_char_tags = {t for t in all_tags if t.startswith("CHAR_")}

            # Get character tags that have profiles in the characters array
            characters = world_config.get("characters", [])
            profiled_char_tags = {c.get("tag") for c in characters if c.get("tag")}

            # Find missing characters
            missing_tags = consensus_char_tags - profiled_char_tags

            result = {
                "success": True,
                "consensus_character_count": len(consensus_char_tags),
                "profiled_character_count": len(profiled_char_tags),
                "missing_count": len(missing_tags),
                "missing_tags": sorted(list(missing_tags)),
                "consensus_tags": sorted(list(consensus_char_tags)),
                "profiled_tags": sorted(list(profiled_char_tags))
            }

            if missing_tags:
                logger.warning(f"⚠️ Detected {len(missing_tags)} missing character(s): {missing_tags}")
            else:
                logger.info("✅ All consensus-approved characters have profiles in world_config.json")

            return result

        except Exception as e:
            logger.error(f"Error detecting missing characters: {e}")
            return {"error": str(e)}

    def _fix_missing_characters(
        self,
        missing_tags: List[str] = None,
        dry_run: bool = False,
        llm_provider: str = "gemini",
        llm_model: str = None
    ) -> Dict[str, Any]:
        """Automatically generate and insert missing character profiles.

        Uses LLM to generate character profiles based on pitch.md and script.md context.
        Inserts the generated profiles into world_config.json.

        Args:
            missing_tags: List of character tags to fix (auto-detected if None)
            dry_run: If True, only report what would be fixed
            llm_provider: LLM provider ('gemini', 'anthropic', 'grok')
            llm_model: Specific model ID (uses default for provider if None)
        """
        if not self.project_path:
            return {"error": "No project loaded"}

        # Auto-detect missing tags if not provided
        if not missing_tags:
            detection_result = self._detect_missing_characters()
            if detection_result.get("error"):
                return detection_result
            missing_tags = detection_result.get("missing_tags", [])

        if not missing_tags:
            return {
                "success": True,
                "message": "No missing characters to fix",
                "fixed_count": 0
            }

        logger.info(f"🔧 Fixing {len(missing_tags)} missing character(s): {missing_tags}")

        # Load context from pitch.md and script.md
        pitch_content = ""
        script_content = ""

        pitch_path = self.project_path / "world_bible" / "pitch.md"
        script_path = self.project_path / "scripts" / "script.md"

        if pitch_path.exists():
            pitch_content = pitch_path.read_text(encoding="utf-8")
        if script_path.exists():
            script_content = script_path.read_text(encoding="utf-8")

        if not pitch_content and not script_content:
            return {"error": "No story context found (pitch.md or script.md)"}

        # Load existing world_config
        world_config_path = self.project_path / "world_bible" / "world_config.json"
        world_config = json.loads(world_config_path.read_text(encoding="utf-8"))
        existing_characters = world_config.get("characters", [])

        # Get visual style for consistency
        visual_style = world_config.get("visual_style", "live_action")
        style_notes = world_config.get("style_notes", "")

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "message": f"Would generate profiles for: {missing_tags}",
                "missing_tags": missing_tags,
                "context_available": {
                    "pitch": bool(pitch_content),
                    "script": bool(script_content)
                }
            }

        # Generate character profiles using LLM
        fixed_characters = []
        errors = []

        for tag in missing_tags:
            try:
                profile = self._generate_character_profile(
                    tag=tag,
                    pitch_content=pitch_content,
                    script_content=script_content,
                    visual_style=visual_style,
                    style_notes=style_notes,
                    existing_characters=existing_characters,
                    llm_provider=llm_provider,
                    llm_model=llm_model
                )
                if profile:
                    fixed_characters.append(profile)
                    logger.info(f"✅ Generated profile for [{tag}]")
                else:
                    errors.append(f"Failed to generate profile for {tag}")
            except Exception as e:
                errors.append(f"Error generating {tag}: {str(e)}")
                logger.error(f"Error generating profile for {tag}: {e}")

        # Insert fixed characters into world_config
        if fixed_characters:
            world_config["characters"].extend(fixed_characters)
            world_config_path.write_text(
                json.dumps(world_config, indent=2, ensure_ascii=False),
                encoding="utf-8"
            )
            logger.info(f"✅ Inserted {len(fixed_characters)} character profile(s) into world_config.json")

        return {
            "success": len(errors) == 0,
            "fixed_count": len(fixed_characters),
            "fixed_tags": [c.get("tag") for c in fixed_characters],
            "errors": errors if errors else None,
            "message": f"Fixed {len(fixed_characters)} of {len(missing_tags)} missing characters"
        }

    def _generate_character_profile(
        self,
        tag: str,
        pitch_content: str,
        script_content: str,
        visual_style: str,
        style_notes: str,
        existing_characters: List[Dict],
        llm_provider: str = "gemini",
        llm_model: str = None
    ) -> Optional[Dict[str, Any]]:
        """Generate a character profile using LLM based on story context.

        Args:
            tag: Character tag (e.g., CHAR_MEI)
            pitch_content: Content from pitch.md
            script_content: Content from script.md
            visual_style: Visual style from world_config
            style_notes: Style notes from world_config
            existing_characters: List of existing character profiles
            llm_provider: LLM provider to use ('gemini', 'anthropic', 'grok')
            llm_model: Specific model ID (if None, uses default for provider)
        """
        import asyncio

        # Extract character name from tag
        char_name = tag.replace("CHAR_", "").replace("_", " ").title()

        # Build context about existing characters for relationship mapping
        existing_char_info = "\n".join([
            f"- [{c.get('tag')}] {c.get('name')}: {c.get('role', 'unknown role')}"
            for c in existing_characters
        ]) if existing_characters else "No other characters defined yet."

        prompt = f"""Generate a complete character profile for [{tag}] based on the story context below.

CHARACTER TAG: [{tag}]
LIKELY NAME: {char_name}

VISUAL STYLE: {visual_style}
STYLE NOTES: {style_notes}

EXISTING CHARACTERS:
{existing_char_info}

STORY PITCH:
{pitch_content[:3000] if pitch_content else "Not available"}

SCRIPT EXCERPTS (search for mentions of this character):
{script_content[:5000] if script_content else "Not available"}

Generate a JSON object with these EXACT fields (use the same structure as existing characters):
{{
    "tag": "{tag}",
    "name": "[Full character name]",
    "role": "[protagonist/antagonist/supporting/love_interest/mentor/ally]",
    "want": "[2-3 sentences: external goal]",
    "need": "[2-3 sentences: internal need]",
    "flaw": "[2-3 sentences: character flaw]",
    "arc_type": "[positive/negative/flat]",
    "age": "[age with context]",
    "ethnicity": "[cultural background]",
    "appearance": "[50-100 words: detailed physical description]",
    "costume": "[30-50 words: clothing description]",
    "visual_appearance": "[same as appearance]",
    "psychology": "[50-75 words: psychological profile]",
    "speech_patterns": "[30-50 words: how they speak]",
    "speech_style": "[formal/informal, direct/indirect]",
    "literacy_level": "[education level]",
    "physicality": "[30-50 words: movement and gestures]",
    "decision_heuristics": "[decision-making patterns]",
    "emotional_tells": {{
        "fear": "[physical response]",
        "anger": "[physical response]",
        "joy": "[physical response]",
        "sadness": "[physical response]",
        "vulnerability": "[physical response]"
    }},
    "key_moments": ["[moment1]", "[moment2]", "[moment3]"],
    "relationships": {{
        "[OTHER_CHAR_TAG]": "[relationship description]"
    }}
}}

IMPORTANT: Return ONLY the JSON object, no markdown formatting or explanation."""

        system_prompt = "You are a character development specialist. Generate detailed, consistent character profiles in valid JSON format."

        # Default models for each provider
        default_models = {
            "gemini": "gemini-2.5-flash-preview-05-20",
            "anthropic": "claude-haiku-4-5-20251001",
            "grok": "grok-4"
        }

        # Use provided model or default for provider
        model = llm_model or default_models.get(llm_provider, default_models["gemini"])

        try:
            response = None

            # Try primary provider
            if llm_provider == "gemini":
                try:
                    from greenlight.llm.api_clients import GeminiClient
                    client = GeminiClient()
                    response = client.generate_text(
                        prompt=prompt,
                        system=system_prompt,
                        model=model
                    )
                    logger.info(f"Generated character profile for {tag} using Gemini ({model})")
                except Exception as e:
                    logger.warning(f"Gemini failed for {tag}, falling back to Anthropic: {e}")
                    llm_provider = "anthropic"  # Fallback
                    model = default_models["anthropic"]

            if llm_provider == "anthropic" or response is None:
                try:
                    from greenlight.llm.api_clients import AnthropicClient
                    client = AnthropicClient()
                    response = client.generate_text(
                        prompt=prompt,
                        system=system_prompt,
                        model=model if llm_provider == "anthropic" else default_models["anthropic"]
                    )
                    logger.info(f"Generated character profile for {tag} using Anthropic")
                except Exception as e:
                    logger.error(f"Anthropic also failed for {tag}: {e}")
                    raise

            if response is None:
                raise ValueError("No LLM response received")

            # Parse the JSON response
            # Clean up response - remove markdown code blocks if present
            response_text = response.strip()
            if response_text.startswith("```"):
                # Remove markdown code block
                lines = response_text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].strip() == "```":
                    lines = lines[:-1]
                response_text = "\n".join(lines)

            profile = json.loads(response_text)

            # Ensure tag is correct
            profile["tag"] = tag

            return profile

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM response as JSON for {tag}: {e}")
            # Return a minimal fallback profile
            return {
                "tag": tag,
                "name": char_name,
                "role": "supporting",
                "want": "Character goal to be defined",
                "need": "Character need to be defined",
                "flaw": "Character flaw to be defined",
                "arc_type": "positive",
                "age": "",
                "ethnicity": "",
                "appearance": "Appearance to be defined based on story context",
                "costume": "Costume to be defined based on story context",
                "visual_appearance": "Appearance to be defined based on story context",
                "psychology": "",
                "speech_patterns": "",
                "speech_style": "",
                "literacy_level": "",
                "physicality": "",
                "decision_heuristics": "",
                "emotional_tells": {},
                "key_moments": [],
                "relationships": {}
            }
        except Exception as e:
            logger.error(f"Error generating character profile for {tag}: {e}")
            return None

    def _validate_world_config(self) -> Dict[str, Any]:
        """Validate that all consensus-approved tags have entries in world_config.json.

        Checks characters, locations, and props for completeness.
        """
        if not self.project_path:
            return {"error": "No project loaded"}

        world_config_path = self.project_path / "world_bible" / "world_config.json"

        if not world_config_path.exists():
            return {"error": "world_config.json not found"}

        try:
            world_config = json.loads(world_config_path.read_text(encoding="utf-8"))

            all_tags = set(world_config.get("all_tags", []))

            # Check characters
            char_tags = {t for t in all_tags if t.startswith("CHAR_")}
            profiled_chars = {c.get("tag") for c in world_config.get("characters", [])}
            missing_chars = char_tags - profiled_chars

            # Check locations
            loc_tags = {t for t in all_tags if t.startswith("LOC_")}
            profiled_locs = {l.get("tag") for l in world_config.get("locations", [])}
            missing_locs = loc_tags - profiled_locs

            # Check props
            prop_tags = {t for t in all_tags if t.startswith("PROP_")}
            profiled_props = {p.get("tag") for p in world_config.get("props", [])}
            missing_props = prop_tags - profiled_props

            # Validate JSON structure
            json_valid = True
            try:
                json.dumps(world_config)
            except Exception:
                json_valid = False

            all_valid = (
                len(missing_chars) == 0 and
                len(missing_locs) == 0 and
                len(missing_props) == 0 and
                json_valid
            )

            result = {
                "success": True,
                "valid": all_valid,
                "json_valid": json_valid,
                "characters": {
                    "consensus_count": len(char_tags),
                    "profiled_count": len(profiled_chars),
                    "missing": sorted(list(missing_chars))
                },
                "locations": {
                    "consensus_count": len(loc_tags),
                    "profiled_count": len(profiled_locs),
                    "missing": sorted(list(missing_locs))
                },
                "props": {
                    "consensus_count": len(prop_tags),
                    "profiled_count": len(profiled_props),
                    "missing": sorted(list(missing_props))
                }
            }

            if all_valid:
                logger.info("✅ world_config.json validation passed - all tags have entries")
            else:
                issues = []
                if missing_chars:
                    issues.append(f"{len(missing_chars)} missing characters")
                if missing_locs:
                    issues.append(f"{len(missing_locs)} missing locations")
                if missing_props:
                    issues.append(f"{len(missing_props)} missing props")
                if not json_valid:
                    issues.append("invalid JSON structure")
                logger.warning(f"⚠️ world_config.json validation failed: {', '.join(issues)}")

            return result

        except Exception as e:
            logger.error(f"Error validating world_config: {e}")
            return {"error": str(e)}