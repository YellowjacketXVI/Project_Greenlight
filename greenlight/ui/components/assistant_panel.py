"""
Greenlight Assistant Panel

Bottom panel for Omni Mind AI assistant interaction.
Features conversation history, new conversation, and project-aware context.
"""

import customtkinter as ctk
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from pathlib import Path
import json
import uuid

from greenlight.ui.theme import theme


class ThinkingIndicator(ctk.CTkFrame):
    """Animated thinking/processing indicator with status updates."""

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.configure(
            fg_color=theme.colors.bg_medium,
            corner_radius=12
        )

        self._frame_index = 0
        self._is_animating = False
        self._is_destroyed = False
        self._status_text = "Thinking..."

        # Container for spinner and text
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(padx=theme.spacing.md, pady=theme.spacing.sm)

        # Spinner label
        self._spinner_label = ctk.CTkLabel(
            container,
            text=self.SPINNER_FRAMES[0],
            font=(theme.fonts.family, 16),
            text_color=theme.colors.primary
        )
        self._spinner_label.pack(side="left", padx=(0, 8))

        # Status text
        self._status_label = ctk.CTkLabel(
            container,
            text=self._status_text,
            text_color=theme.colors.text_muted,
            font=(theme.fonts.family, 12)
        )
        self._status_label.pack(side="left")

    def start(self, initial_status: str = "Thinking...") -> None:
        """Start the animation."""
        if self._is_destroyed:
            return
        self._status_text = initial_status
        try:
            self._status_label.configure(text=initial_status)
        except Exception:
            return
        self._is_animating = True
        self._animate()

    def stop(self) -> None:
        """Stop the animation."""
        self._is_animating = False

    def destroy(self) -> None:
        """Override destroy to prevent animation callbacks after destruction."""
        self._is_destroyed = True
        self._is_animating = False
        super().destroy()

    def set_status(self, status: str) -> None:
        """Update the status text."""
        if self._is_destroyed:
            return
        self._status_text = status
        try:
            self._status_label.configure(text=status)
        except Exception:
            pass  # Widget may have been destroyed

    def _animate(self) -> None:
        """Animate the spinner."""
        if not self._is_animating or self._is_destroyed:
            return

        try:
            self._frame_index = (self._frame_index + 1) % len(self.SPINNER_FRAMES)
            self._spinner_label.configure(text=self.SPINNER_FRAMES[self._frame_index])
            self.after(100, self._animate)
        except Exception:
            # Widget was destroyed, stop animation
            self._is_animating = False


class MessageBubble(ctk.CTkFrame):
    """A chat message bubble with syntax highlighting support."""

    # Highlighting patterns for different content types
    # TAG patterns: [CHAR_NAME], [LOC_NAME], [PROP_NAME], [CONCEPT_NAME], [EVENT_NAME], [ENV_NAME]
    TAG_PREFIXES = ['CHAR_', 'LOC_', 'PROP_', 'CONCEPT_', 'EVENT_', 'ENV_']

    # Document names to highlight
    DOCUMENT_NAMES = [
        'script.md', 'pitch.md', 'world_config.json', 'visual_script.json',
        'beat_sheet.json', 'style_guide.md', 'project.json', 'pre_script_outline.md'
    ]

    # Process/Pipeline names to highlight
    PROCESS_NAMES = [
        'Writer Pipeline', 'Director Pipeline', 'World Bible Pipeline',
        'Storyboard Pipeline', 'Reference Pipeline', 'Assembly Pipeline'
    ]

    def __init__(
        self,
        master,
        message: str,
        is_user: bool = True,
        timestamp: datetime = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.configure(
            fg_color=theme.colors.primary if is_user else theme.colors.bg_light,
            corner_radius=8  # Tighter corner radius
        )

        # Calculate font sizes - assistant messages smaller, user messages normal
        assistant_font_size = max(8, theme.fonts.size_normal // 2)
        user_font_size = theme.fonts.size_normal  # User messages at normal size

        # Message text with increased wraplength (2.5x from 400 to 1000)
        # For assistant messages, use a text widget for highlighting support
        if not is_user:
            self._create_highlighted_text(message, assistant_font_size)
        else:
            # User messages use simple label at normal font size
            label = ctk.CTkLabel(
                self,
                text=message,
                wraplength=1000,  # 2.5x increase from 400
                justify="right",
                text_color=theme.colors.text_primary,
                font=(theme.fonts.family, user_font_size)
            )
            label.pack(padx=theme.spacing.sm, pady=theme.spacing.xs)  # Tighter padding

    def _create_highlighted_text(self, message: str, font_size: int = None) -> None:
        """Create a text widget with syntax highlighting for assistant messages."""
        import re
        import tkinter as tk

        # Use reduced font size (1/2 of normal) if not specified
        if font_size is None:
            font_size = max(8, theme.fonts.size_normal // 2)

        # Use a Text widget for rich formatting
        text_widget = tk.Text(
            self,
            wrap="word",
            width=100,  # Characters wide (increased for smaller font)
            height=self._calculate_height(message),
            bg=theme.colors.bg_light,
            fg=theme.colors.text_primary,
            font=(theme.fonts.family, font_size),
            relief="flat",
            padx=4,  # Tighter padding
            pady=4,  # Tighter padding
            cursor="arrow",
            state="normal"
        )
        text_widget.pack(padx=theme.spacing.xs, pady=theme.spacing.xs, fill="x")  # Tighter pack

        # Configure highlight tags with reduced font size
        text_widget.tag_configure("tag_char", foreground="#00D4AA", font=(theme.fonts.family, font_size, "bold"))
        text_widget.tag_configure("tag_loc", foreground="#FFB347", font=(theme.fonts.family, font_size, "bold"))
        text_widget.tag_configure("tag_prop", foreground="#87CEEB", font=(theme.fonts.family, font_size, "bold"))
        text_widget.tag_configure("tag_concept", foreground="#DDA0DD", font=(theme.fonts.family, font_size, "bold"))
        text_widget.tag_configure("tag_event", foreground="#F0E68C", font=(theme.fonts.family, font_size, "bold"))
        text_widget.tag_configure("tag_env", foreground="#98FB98", font=(theme.fonts.family, font_size, "bold"))
        text_widget.tag_configure("document", foreground="#ADD8E6", font=(theme.fonts.family, font_size, "italic"))
        text_widget.tag_configure("process", foreground="#FFD700", font=(theme.fonts.family, font_size, "bold"))
        text_widget.tag_configure("scene_frame", foreground="#FF69B4", font=(theme.fonts.family, font_size, "bold"))

        # Insert text and apply highlighting
        text_widget.insert("1.0", message)
        self._apply_highlighting(text_widget, message)

        # Make read-only
        text_widget.configure(state="disabled")

    def _calculate_height(self, message: str) -> int:
        """Calculate appropriate height for the text widget."""
        lines = message.count('\n') + 1
        # Estimate wrapped lines (80 chars per line)
        estimated_wrapped = len(message) // 80 + 1
        total_lines = max(lines, estimated_wrapped)
        return min(max(2, total_lines), 20)  # Min 2, max 20 lines

    def _apply_highlighting(self, text_widget, message: str) -> None:
        """Apply syntax highlighting to the text widget."""
        import re

        # Highlight TAG notation: [CHAR_NAME], [LOC_NAME], etc.
        tag_pattern = r'\[(CHAR_|LOC_|PROP_|CONCEPT_|EVENT_|ENV_)[A-Z0-9_]+\]'
        for match in re.finditer(tag_pattern, message):
            start_idx = f"1.0+{match.start()}c"
            end_idx = f"1.0+{match.end()}c"
            prefix = match.group(1)
            tag_name = {
                'CHAR_': 'tag_char',
                'LOC_': 'tag_loc',
                'PROP_': 'tag_prop',
                'CONCEPT_': 'tag_concept',
                'EVENT_': 'tag_event',
                'ENV_': 'tag_env'
            }.get(prefix, 'tag_char')
            text_widget.tag_add(tag_name, start_idx, end_idx)

        # Highlight scene.frame.camera notation: 1.2.cA, 2.3.cB, etc.
        scene_pattern = r'\b\d+\.\d+\.c[A-Z]\b'
        for match in re.finditer(scene_pattern, message):
            start_idx = f"1.0+{match.start()}c"
            end_idx = f"1.0+{match.end()}c"
            text_widget.tag_add("scene_frame", start_idx, end_idx)

        # Highlight document names
        for doc_name in self.DOCUMENT_NAMES:
            pattern = re.escape(doc_name)
            for match in re.finditer(pattern, message, re.IGNORECASE):
                start_idx = f"1.0+{match.start()}c"
                end_idx = f"1.0+{match.end()}c"
                text_widget.tag_add("document", start_idx, end_idx)

        # Highlight process names
        for process_name in self.PROCESS_NAMES:
            pattern = re.escape(process_name)
            for match in re.finditer(pattern, message, re.IGNORECASE):
                start_idx = f"1.0+{match.start()}c"
                end_idx = f"1.0+{match.end()}c"
                text_widget.tag_add("process", start_idx, end_idx)


class Conversation:
    """Represents a single conversation with history."""

    def __init__(self, conversation_id: str = None, project_path: str = None):
        self.id = conversation_id or str(uuid.uuid4())[:8]
        self.project_path = project_path
        self.messages: List[Dict] = []
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.title = "New Conversation"

    def add_message(self, role: str, content: str) -> None:
        """Add a message to the conversation."""
        self.messages.append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        self.updated_at = datetime.now()

        # Auto-generate title from first user message
        if len(self.messages) == 1 and role == 'user':
            self.title = content[:50] + ('...' if len(content) > 50 else '')

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        # Convert project_path to string if it's a Path object
        project_path_str = str(self.project_path) if self.project_path else None
        return {
            'id': self.id,
            'project_path': project_path_str,
            'messages': self.messages,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'title': self.title
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'Conversation':
        """Create from dictionary."""
        conv = cls(data.get('id'), data.get('project_path'))
        conv.messages = data.get('messages', [])
        conv.title = data.get('title', 'Conversation')
        if data.get('created_at'):
            conv.created_at = datetime.fromisoformat(data['created_at'])
        if data.get('updated_at'):
            conv.updated_at = datetime.fromisoformat(data['updated_at'])
        return conv


class ConversationHistory:
    """Manages conversation history storage."""

    def __init__(self, storage_path: Path = None):
        self.storage_path = storage_path or Path.home() / '.greenlight' / 'conversations'
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.conversations: Dict[str, Conversation] = {}
        self._load_conversations()

    def _load_conversations(self) -> None:
        """Load conversations from storage."""
        history_file = self.storage_path / 'history.json'
        if history_file.exists():
            try:
                data = json.loads(history_file.read_text(encoding='utf-8'))
                for conv_data in data.get('conversations', []):
                    conv = Conversation.from_dict(conv_data)
                    self.conversations[conv.id] = conv
            except Exception:
                pass  # Start fresh if corrupted

    def save(self) -> None:
        """Save conversations to storage."""
        history_file = self.storage_path / 'history.json'
        data = {
            'conversations': [c.to_dict() for c in self.conversations.values()]
        }
        history_file.write_text(json.dumps(data, indent=2), encoding='utf-8')

    def create_conversation(self, project_path: str = None) -> Conversation:
        """Create a new conversation."""
        conv = Conversation(project_path=project_path)
        self.conversations[conv.id] = conv
        self.save()
        return conv

    def get_conversation(self, conv_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self.conversations.get(conv_id)

    def get_recent(self, limit: int = 10, project_path: str = None) -> List[Conversation]:
        """Get recent conversations, optionally filtered by project."""
        convs = list(self.conversations.values())
        if project_path:
            convs = [c for c in convs if c.project_path == project_path]
        convs.sort(key=lambda c: c.updated_at, reverse=True)
        return convs[:limit]

    def delete_conversation(self, conv_id: str) -> None:
        """Delete a conversation."""
        if conv_id in self.conversations:
            del self.conversations[conv_id]
            self.save()


class AssistantPanel(ctk.CTkFrame):
    """
    Omni Mind assistant panel.

    Features:
    - Chat interface with conversation history
    - New conversation / history navigation
    - Voice input support
    - File attachment
    - Action buttons
    - Project-aware context
    """

    def __init__(
        self,
        master,
        on_message: Callable[[str], None] = None,
        project_path: str = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.on_message = on_message
        self._project_path = project_path
        self._expanded = True

        # Conversation management
        self._history = ConversationHistory()
        self._current_conversation: Optional[Conversation] = None
        self._history_visible = False

        # Thinking indicator state
        self._thinking_indicator: Optional[ThinkingIndicator] = None
        self._is_thinking = False

        # Tag autocomplete state
        self._tag_cache: List[Dict[str, str]] = []  # [{name, type, description}]
        self._autocomplete_popup: Optional[ctk.CTkFrame] = None
        self._autocomplete_visible = False
        self._autocomplete_selection = 0
        self._autocomplete_trigger_pos = 0

        self._setup_ui()

        # Start with a new conversation
        self._new_conversation()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.configure(
            fg_color=theme.colors.bg_dark,
            corner_radius=0,
            height=250
        )
        
        # Header
        header = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium, height=35)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        title = ctk.CTkLabel(
            header,
            text="💬 Omni Mind Assistant",
            **theme.get_label_style()
        )
        title.pack(side="left", padx=theme.spacing.md)

        # Toggle button
        self.toggle_btn = ctk.CTkButton(
            header,
            text="▼" if self._expanded else "▲",
            width=30,
            fg_color="transparent",
            hover_color=theme.colors.bg_hover,
            command=self._toggle_expand
        )
        self.toggle_btn.pack(side="right", padx=theme.spacing.sm)

        # History button
        self.history_btn = ctk.CTkButton(
            header,
            text="📜",
            width=30,
            fg_color="transparent",
            hover_color=theme.colors.bg_hover,
            command=self._toggle_history
        )
        self.history_btn.pack(side="right", padx=2)

        # New conversation button
        self.new_conv_btn = ctk.CTkButton(
            header,
            text="➕",
            width=30,
            fg_color="transparent",
            hover_color=theme.colors.bg_hover,
            command=self._new_conversation
        )
        self.new_conv_btn.pack(side="right", padx=2)

        # History panel (hidden by default)
        self.history_panel = ctk.CTkFrame(self, fg_color=theme.colors.bg_medium)
        # Don't pack yet - will be shown when toggled
        
        # Chat area
        self.chat_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent"
        )
        self.chat_frame.pack(fill="both", expand=True, padx=theme.spacing.md, pady=theme.spacing.sm)
        
        # Input area
        input_frame = ctk.CTkFrame(self, fg_color="transparent")
        input_frame.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.md)
        
        # Attachment button
        attach_btn = ctk.CTkButton(
            input_frame,
            text="📎",
            width=35,
            fg_color="transparent",
            hover_color=theme.colors.bg_hover,
            command=self._attach_file
        )
        attach_btn.pack(side="left")
        
        # Text input with autocomplete support
        self.input_var = ctk.StringVar()
        self.input_var.trace_add("write", self._on_input_change)
        self.input_entry = ctk.CTkEntry(
            input_frame,
            placeholder_text="Type a message or command... (use @ for tags)",
            textvariable=self.input_var,
            **theme.get_entry_style()
        )
        self.input_entry.pack(side="left", fill="x", expand=True, padx=theme.spacing.sm)
        self.input_entry.bind("<Return>", self._on_return_key)
        self.input_entry.bind("<Up>", self._on_autocomplete_up)
        self.input_entry.bind("<Down>", self._on_autocomplete_down)
        self.input_entry.bind("<Escape>", self._hide_autocomplete)
        self.input_entry.bind("<Tab>", self._on_autocomplete_select)

        # Voice button
        voice_btn = ctk.CTkButton(
            input_frame,
            text="🎤",
            width=35,
            fg_color="transparent",
            hover_color=theme.colors.bg_hover,
            command=self._voice_input
        )
        voice_btn.pack(side="left")
        
        # Send button
        send_btn = ctk.CTkButton(
            input_frame,
            text="Send",
            width=60,
            command=self._send_message,
            **theme.get_button_style("primary")
        )
        send_btn.pack(side="left", padx=(theme.spacing.sm, 0))
        
        # Welcome message will be added in _new_conversation

    def _toggle_expand(self) -> None:
        """Toggle panel expansion."""
        self._expanded = not self._expanded
        if self._expanded:
            self.configure(height=250)
            self.toggle_btn.configure(text="▼")
        else:
            self.configure(height=35)
            self.toggle_btn.configure(text="▲")

    def _toggle_history(self) -> None:
        """Toggle conversation history panel."""
        self._history_visible = not self._history_visible
        if self._history_visible:
            self._show_history_panel()
        else:
            self.history_panel.pack_forget()

    def _show_history_panel(self) -> None:
        """Show the conversation history panel."""
        # Clear existing content
        for widget in self.history_panel.winfo_children():
            widget.destroy()

        # Header
        header = ctk.CTkFrame(self.history_panel, fg_color="transparent")
        header.pack(fill="x", padx=theme.spacing.sm, pady=theme.spacing.sm)

        ctk.CTkLabel(header, text="📜 Conversation History", **theme.get_label_style()).pack(side="left")

        # Conversation list
        convs = self._history.get_recent(limit=10, project_path=self._project_path)

        if not convs:
            ctk.CTkLabel(
                self.history_panel,
                text="No previous conversations",
                text_color=theme.colors.text_secondary
            ).pack(pady=theme.spacing.md)
        else:
            for conv in convs:
                btn = ctk.CTkButton(
                    self.history_panel,
                    text=f"💬 {conv.title}",
                    anchor="w",
                    fg_color="transparent",
                    hover_color=theme.colors.bg_hover,
                    command=lambda c=conv: self._load_conversation(c)
                )
                btn.pack(fill="x", padx=theme.spacing.sm, pady=2)

        # Pack the history panel
        self.history_panel.pack(fill="both", expand=True, before=self.chat_frame)

    def _new_conversation(self) -> None:
        """Start a new conversation."""
        # Save current conversation if exists
        if self._current_conversation and self._current_conversation.messages:
            self._history.save()

        # Create new conversation
        self._current_conversation = self._history.create_conversation(self._project_path)

        # Clear chat display
        for widget in self.chat_frame.winfo_children():
            widget.destroy()

        # Hide history panel if visible
        if self._history_visible:
            self.history_panel.pack_forget()
            self._history_visible = False

        # Add welcome message
        self._add_assistant_message(
            "Hello! I'm Omni Mind, your AI assistant. "
            "I can help you create and manage your storyboard project. "
            "What would you like to work on?"
        )

    def _load_conversation(self, conversation: Conversation) -> None:
        """Load a previous conversation."""
        self._current_conversation = conversation

        # Clear chat display
        for widget in self.chat_frame.winfo_children():
            widget.destroy()

        # Hide history panel
        if self._history_visible:
            self.history_panel.pack_forget()
            self._history_visible = False

        # Replay messages
        for msg in conversation.messages:
            if msg['role'] == 'user':
                bubble = MessageBubble(self.chat_frame, message=msg['content'], is_user=True)
                bubble.pack(anchor="e", pady=2)
            else:
                bubble = MessageBubble(self.chat_frame, message=msg['content'], is_user=False)
                bubble.pack(anchor="w", pady=2)

    def _send_message(self, event=None) -> None:
        """Send a message."""
        message = self.input_var.get().strip()
        if not message:
            return

        # Check if project is selected (block if not)
        if not self._project_path:
            self._add_system_message(
                "⚠️ **No Project Selected**\n\n"
                "Please select a project from the sidebar before sending requests.\n\n"
                "I need project context to help you effectively with:\n"
                "• Writing stories and scripts\n"
                "• Directing storyboards\n"
                "• Managing world bible content\n\n"
                "💡 Click on a project in the left panel to get started."
            )
            return

        # Add user message
        self._add_user_message(message)

        # Clear input
        self.input_var.set("")

        # Show thinking indicator
        self.show_thinking("🧠 Processing your request...")

        # Trigger callback
        if self.on_message:
            self.on_message(message)

    def _add_system_message(self, message: str) -> None:
        """Add a system/warning message to the chat."""
        # Create a distinct system message bubble
        bubble = ctk.CTkFrame(
            self.chat_frame,
            fg_color=theme.colors.warning if hasattr(theme.colors, 'warning') else "#FFA500",
            corner_radius=12
        )

        label = ctk.CTkLabel(
            bubble,
            text=message,
            wraplength=400,
            justify="left",
            text_color=theme.colors.bg_dark
        )
        label.pack(padx=theme.spacing.md, pady=theme.spacing.sm)
        bubble.pack(anchor="w", pady=2, padx=4)

    def _add_user_message(self, message: str) -> None:
        """Add a user message to the chat."""
        bubble = MessageBubble(
            self.chat_frame,
            message=message,
            is_user=True
        )
        bubble.pack(anchor="e", pady=2)

        # Add to current conversation
        if self._current_conversation:
            self._current_conversation.add_message('user', message)
            self._history.save()

    def _add_assistant_message(self, message: str) -> None:
        """Add an assistant message to the chat."""
        bubble = MessageBubble(
            self.chat_frame,
            message=message,
            is_user=False
        )
        bubble.pack(anchor="w", pady=2)

        # Add to current conversation
        if self._current_conversation:
            self._current_conversation.add_message('assistant', message)
            self._history.save()

    def add_response(self, message: str) -> None:
        """Add an assistant response (public method)."""
        # Hide thinking indicator when response arrives
        self.hide_thinking()
        self._add_assistant_message(message)

    def show_thinking(self, initial_status: str = "🧠 Thinking...") -> None:
        """Show the thinking indicator with animation."""
        if self._is_thinking:
            return

        self._is_thinking = True
        self._thinking_indicator = ThinkingIndicator(self.chat_frame)
        self._thinking_indicator.pack(anchor="w", pady=2)
        self._thinking_indicator.start(initial_status)

        # Scroll to bottom
        self.chat_frame._parent_canvas.yview_moveto(1.0)

    def hide_thinking(self) -> None:
        """Hide the thinking indicator."""
        if not self._is_thinking:
            return

        self._is_thinking = False
        if self._thinking_indicator:
            try:
                self._thinking_indicator.stop()
                self._thinking_indicator.destroy()
            except Exception:
                pass  # Widget may already be destroyed
            self._thinking_indicator = None

    def update_thinking_status(self, status: str) -> None:
        """Update the thinking indicator status text."""
        if self._thinking_indicator and self._is_thinking:
            try:
                self._thinking_indicator.set_status(status)
            except Exception:
                pass  # Widget may have been destroyed

    def _attach_file(self) -> None:
        """Handle file attachment."""
        from tkinter import filedialog

        filetypes = [
            ("All supported", "*.md *.txt *.json *.png *.jpg *.jpeg"),
            ("Markdown", "*.md"),
            ("Text", "*.txt"),
            ("JSON", "*.json"),
            ("Images", "*.png *.jpg *.jpeg"),
            ("All files", "*.*"),
        ]

        filepath = filedialog.askopenfilename(
            title="Attach File",
            filetypes=filetypes
        )

        if filepath:
            from pathlib import Path
            filename = Path(filepath).name
            self._add_assistant_message(f"📎 Attached: {filename}")

            # Store attachment for context
            if not hasattr(self, '_attachments'):
                self._attachments = []
            self._attachments.append(filepath)

            # Notify via callback if available
            if self.on_message:
                self.on_message(f"[ATTACHMENT: {filepath}]")

    def _voice_input(self) -> None:
        """Handle voice input."""
        # Voice input requires additional dependencies (speech_recognition)
        # For now, show a message about the feature
        self._add_assistant_message(
            "🎤 Voice input is available when speech recognition is configured.\n\n"
            "To enable:\n"
            "1. Install: pip install SpeechRecognition pyaudio\n"
            "2. Configure microphone in settings"
        )

        # Attempt to use speech recognition if available
        try:
            import speech_recognition as sr

            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                self._add_assistant_message("🎤 Listening... (speak now)")
                self.update()  # Force UI update

                try:
                    audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
                    text = recognizer.recognize_google(audio)

                    # Add recognized text to input
                    current = self.input_var.get()
                    self.input_var.set(f"{current} {text}".strip())
                    self._add_assistant_message(f"🎤 Heard: \"{text}\"")

                except sr.WaitTimeoutError:
                    self._add_assistant_message("🎤 No speech detected. Try again.")
                except sr.UnknownValueError:
                    self._add_assistant_message("🎤 Could not understand audio. Try again.")
                except sr.RequestError as e:
                    self._add_assistant_message(f"🎤 Speech service error: {e}")

        except ImportError:
            pass  # Already showed the installation message
    
    def show_actions(self, actions: List[Dict]) -> None:
        """Show action buttons."""
        action_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        action_frame.pack(anchor="w", pady=theme.spacing.sm)

        for action in actions:
            btn = ctk.CTkButton(
                action_frame,
                text=action.get('label', 'Action'),
                command=action.get('callback'),
                **theme.get_button_style("secondary")
            )
            btn.pack(side="left", padx=2)

    def set_project_path(self, project_path: str) -> None:
        """Set the current project path and optionally start a new conversation."""
        old_path = self._project_path
        self._project_path = project_path

        # If project changed, start a new conversation
        if old_path != project_path:
            self._new_conversation()
            # Load tags for autocomplete
            self._tag_cache = []  # Clear old cache
            self.load_tags_from_project()

            if project_path:
                project_name = Path(project_path).name
                tag_count = len(self._tag_cache)
                self._add_assistant_message(
                    f"📂 Project loaded: **{project_name}**\n\n"
                    f"I'm now focused on this project. {tag_count} tags loaded for @autocomplete.\n\n"
                    "How can I help?"
                )

    def get_conversation_context(self) -> List[Dict]:
        """Get the current conversation messages for LLM context."""
        if self._current_conversation:
            return self._current_conversation.messages.copy()
        return []

    def get_current_conversation_id(self) -> Optional[str]:
        """Get the current conversation ID."""
        if self._current_conversation:
            return self._current_conversation.id
        return None

    # ==================== Tag Autocomplete ====================

    def set_tag_cache(self, tags: List[Dict[str, str]]) -> None:
        """Set the tag cache for autocomplete. Each tag: {name, type, description}."""
        self._tag_cache = tags

    def load_tags_from_project(self) -> None:
        """Load tags from the current project's world_config.json."""
        if not self._project_path:
            return

        try:
            import json
            config_path = Path(self._project_path) / "world_config.json"
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                tags = []
                # Characters
                for char in config.get("characters", []):
                    tag_name = char.get("tag", "")
                    if tag_name:
                        tags.append({
                            "name": tag_name,
                            "type": "character",
                            "description": char.get("description", "")[:100]
                        })
                # Locations
                for loc in config.get("locations", []):
                    tag_name = loc.get("tag", "")
                    if tag_name:
                        tags.append({
                            "name": tag_name,
                            "type": "location",
                            "description": loc.get("description", "")[:100]
                        })
                # Props
                for prop in config.get("props", []):
                    tag_name = prop.get("tag", "")
                    if tag_name:
                        tags.append({
                            "name": tag_name,
                            "type": "prop",
                            "description": prop.get("description", "")[:100]
                        })

                self._tag_cache = tags
        except Exception as e:
            logger.warning(f"Failed to load tags from project: {e}")

    def _on_input_change(self, *args) -> None:
        """Handle input text changes for autocomplete trigger."""
        text = self.input_var.get()

        # Find the last @ symbol
        at_pos = text.rfind('@')
        if at_pos >= 0:
            # Get text after @
            query = text[at_pos + 1:]
            # Only show autocomplete if we're still typing the tag (no space after @)
            if ' ' not in query and len(query) <= 30:
                self._autocomplete_trigger_pos = at_pos
                self._show_autocomplete(query)
                return

        self._hide_autocomplete()

    def _show_autocomplete(self, query: str = "") -> None:
        """Show autocomplete popup with filtered suggestions."""
        # Load tags if not cached
        if not self._tag_cache:
            self.load_tags_from_project()

        if not self._tag_cache:
            return

        # Filter tags by query
        query_lower = query.lower()
        filtered = [
            t for t in self._tag_cache
            if query_lower in t["name"].lower() or query_lower in t.get("description", "").lower()
        ][:8]  # Max 8 suggestions

        if not filtered:
            self._hide_autocomplete()
            return

        # Create or update popup
        if self._autocomplete_popup:
            self._autocomplete_popup.destroy()

        self._autocomplete_popup = ctk.CTkFrame(
            self.winfo_toplevel(),
            fg_color=theme.colors.bg_medium,
            corner_radius=8,
            border_width=1,
            border_color=theme.colors.accent
        )

        self._autocomplete_items = []
        for i, tag in enumerate(filtered):
            item_frame = ctk.CTkFrame(
                self._autocomplete_popup,
                fg_color=theme.colors.bg_hover if i == self._autocomplete_selection else "transparent",
                corner_radius=4
            )
            item_frame.pack(fill="x", padx=2, pady=1)
            item_frame.tag_data = tag
            item_frame.index = i

            # Tag type color
            type_colors = {
                "character": "#4A90D9",
                "location": "#4CAF50",
                "prop": "#FF9800"
            }
            type_color = type_colors.get(tag["type"], theme.colors.text_muted)

            # Tag name with type indicator
            name_label = ctk.CTkLabel(
                item_frame,
                text=f"@{tag['name']}",
                font=(theme.fonts.family, 12, "bold"),
                text_color=type_color,
                anchor="w"
            )
            name_label.pack(side="left", padx=8, pady=4)

            # Type badge
            type_label = ctk.CTkLabel(
                item_frame,
                text=tag["type"][:4].upper(),
                font=(theme.fonts.family, 9),
                text_color=theme.colors.text_muted
            )
            type_label.pack(side="right", padx=8)

            # Bind click
            item_frame.bind("<Button-1>", lambda e, idx=i: self._select_autocomplete(idx))
            name_label.bind("<Button-1>", lambda e, idx=i: self._select_autocomplete(idx))

            self._autocomplete_items.append(item_frame)

        # Position popup above input
        self.update_idletasks()
        x = self.input_entry.winfo_rootx()
        y = self.input_entry.winfo_rooty() - (len(filtered) * 30 + 10)

        self._autocomplete_popup.place(x=x - self.winfo_toplevel().winfo_rootx(),
                                        y=y - self.winfo_toplevel().winfo_rooty(),
                                        width=300)
        self._autocomplete_visible = True
        self._autocomplete_selection = 0
        self._update_autocomplete_selection()

    def _hide_autocomplete(self, event=None) -> None:
        """Hide the autocomplete popup."""
        if self._autocomplete_popup:
            self._autocomplete_popup.destroy()
            self._autocomplete_popup = None
        self._autocomplete_visible = False
        self._autocomplete_selection = 0

    def _update_autocomplete_selection(self) -> None:
        """Update visual selection in autocomplete popup."""
        if not hasattr(self, '_autocomplete_items'):
            return
        for i, item in enumerate(self._autocomplete_items):
            if i == self._autocomplete_selection:
                item.configure(fg_color=theme.colors.bg_hover)
            else:
                item.configure(fg_color="transparent")

    def _on_autocomplete_up(self, event) -> None:
        """Handle up arrow in autocomplete."""
        if self._autocomplete_visible and hasattr(self, '_autocomplete_items'):
            self._autocomplete_selection = max(0, self._autocomplete_selection - 1)
            self._update_autocomplete_selection()
            return "break"

    def _on_autocomplete_down(self, event) -> None:
        """Handle down arrow in autocomplete."""
        if self._autocomplete_visible and hasattr(self, '_autocomplete_items'):
            max_idx = len(self._autocomplete_items) - 1
            self._autocomplete_selection = min(max_idx, self._autocomplete_selection + 1)
            self._update_autocomplete_selection()
            return "break"

    def _on_autocomplete_select(self, event) -> None:
        """Handle Tab key to select autocomplete item."""
        if self._autocomplete_visible:
            self._select_autocomplete(self._autocomplete_selection)
            return "break"

    def _select_autocomplete(self, index: int) -> None:
        """Select an autocomplete item and insert it."""
        if not hasattr(self, '_autocomplete_items') or index >= len(self._autocomplete_items):
            return

        item = self._autocomplete_items[index]
        tag_data = item.tag_data
        tag_name = tag_data["name"]

        # Replace text from @ to current position with the tag
        text = self.input_var.get()
        new_text = text[:self._autocomplete_trigger_pos] + f"@{tag_name} "
        self.input_var.set(new_text)

        # Move cursor to end
        self.input_entry.icursor(len(new_text))

        self._hide_autocomplete()

    def _on_return_key(self, event) -> None:
        """Handle Return key - select autocomplete or send message."""
        if self._autocomplete_visible:
            self._select_autocomplete(self._autocomplete_selection)
            return "break"
        else:
            self._send_message(event)
