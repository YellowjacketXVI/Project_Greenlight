"""
Greenlight Settings Dialog

Configuration dialog for application settings.
"""

import customtkinter as ctk
from typing import Dict, Optional, Callable, Any

from greenlight.ui.theme import theme


class SettingsDialog(ctk.CTkToplevel):
    """
    Settings configuration dialog.
    
    Features:
    - LLM provider configuration
    - API key management
    - UI preferences
    - Project defaults
    """
    
    def __init__(
        self,
        master,
        config: Dict[str, Any] = None,
        on_save: Callable[[Dict], None] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        
        self.config = config or {}
        self.on_save = on_save
        
        self.title("Settings")
        self.geometry("600x500")
        self.resizable(False, False)
        
        # Make modal
        self.transient(master)
        self.grab_set()
        
        self._setup_ui()
    
    def _setup_ui(self) -> None:
        """Set up the UI components."""
        self.configure(fg_color=theme.colors.bg_medium)
        
        # Tab view
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=theme.spacing.md, pady=theme.spacing.md)
        
        # Create tabs
        self.tabview.add("LLM Providers")
        self.tabview.add("UI Preferences")
        self.tabview.add("Project Defaults")
        
        self._setup_llm_tab()
        self._setup_ui_tab()
        self._setup_project_tab()
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.md)
        
        cancel_btn = ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            command=self.destroy,
            **theme.get_button_style("secondary")
        )
        cancel_btn.pack(side="right", padx=theme.spacing.sm)
        
        save_btn = ctk.CTkButton(
            btn_frame, text="Save", width=100,
            command=self._save_settings,
            **theme.get_button_style("primary")
        )
        save_btn.pack(side="right")
    
    def _setup_llm_tab(self) -> None:
        """Set up the LLM providers tab."""
        tab = self.tabview.tab("LLM Providers")
        
        # Anthropic
        anthropic_frame = ctk.CTkFrame(tab, fg_color=theme.colors.bg_light)
        anthropic_frame.pack(fill="x", pady=theme.spacing.sm)
        
        ctk.CTkLabel(anthropic_frame, text="Anthropic (Claude)", **theme.get_label_style()).pack(anchor="w", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        self.anthropic_key = ctk.CTkEntry(
            anthropic_frame, placeholder_text="API Key",
            show="*", **theme.get_entry_style()
        )
        self.anthropic_key.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        # OpenAI
        openai_frame = ctk.CTkFrame(tab, fg_color=theme.colors.bg_light)
        openai_frame.pack(fill="x", pady=theme.spacing.sm)
        
        ctk.CTkLabel(openai_frame, text="OpenAI (GPT)", **theme.get_label_style()).pack(anchor="w", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        self.openai_key = ctk.CTkEntry(
            openai_frame, placeholder_text="API Key",
            show="*", **theme.get_entry_style()
        )
        self.openai_key.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        # Google
        google_frame = ctk.CTkFrame(tab, fg_color=theme.colors.bg_light)
        google_frame.pack(fill="x", pady=theme.spacing.sm)
        
        ctk.CTkLabel(google_frame, text="Google (Gemini)", **theme.get_label_style()).pack(anchor="w", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        self.google_key = ctk.CTkEntry(
            google_frame, placeholder_text="API Key",
            show="*", **theme.get_entry_style()
        )
        self.google_key.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)
    
    def _setup_ui_tab(self) -> None:
        """Set up the UI preferences tab."""
        tab = self.tabview.tab("UI Preferences")
        
        # Theme
        theme_frame = ctk.CTkFrame(tab, fg_color=theme.colors.bg_light)
        theme_frame.pack(fill="x", pady=theme.spacing.sm)
        
        ctk.CTkLabel(theme_frame, text="Theme", **theme.get_label_style()).pack(anchor="w", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        self.theme_var = ctk.StringVar(value="dark")
        theme_menu = ctk.CTkOptionMenu(
            theme_frame, values=["dark", "light", "system"],
            variable=self.theme_var
        )
        theme_menu.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        # Font size
        font_frame = ctk.CTkFrame(tab, fg_color=theme.colors.bg_light)
        font_frame.pack(fill="x", pady=theme.spacing.sm)
        
        ctk.CTkLabel(font_frame, text="Font Size", **theme.get_label_style()).pack(anchor="w", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        self.font_slider = ctk.CTkSlider(font_frame, from_=10, to=18, number_of_steps=8)
        self.font_slider.set(13)
        self.font_slider.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)
    
    def _setup_project_tab(self) -> None:
        """Set up the project defaults tab."""
        tab = self.tabview.tab("Project Defaults")
        
        # Default LLM
        llm_frame = ctk.CTkFrame(tab, fg_color=theme.colors.bg_light)
        llm_frame.pack(fill="x", pady=theme.spacing.sm)
        
        ctk.CTkLabel(llm_frame, text="Default LLM Provider", **theme.get_label_style()).pack(anchor="w", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        self.default_llm = ctk.CTkOptionMenu(
            llm_frame, values=["anthropic", "openai", "google"]
        )
        self.default_llm.pack(fill="x", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        # Auto-save
        auto_frame = ctk.CTkFrame(tab, fg_color=theme.colors.bg_light)
        auto_frame.pack(fill="x", pady=theme.spacing.sm)
        
        self.auto_save = ctk.CTkCheckBox(
            auto_frame, text="Enable auto-save"
        )
        self.auto_save.pack(anchor="w", padx=theme.spacing.md, pady=theme.spacing.sm)
        
        self.auto_regen = ctk.CTkCheckBox(
            auto_frame, text="Auto-queue regeneration on edit"
        )
        self.auto_regen.pack(anchor="w", padx=theme.spacing.md, pady=theme.spacing.sm)
    
    def _save_settings(self) -> None:
        """Save settings and close."""
        font_size = int(self.font_slider.get())

        # Apply font size immediately to theme
        theme.set_font_size(font_size)

        settings = {
            'llm': {
                'anthropic_key': self.anthropic_key.get(),
                'openai_key': self.openai_key.get(),
                'google_key': self.google_key.get(),
            },
            'ui': {
                'theme': self.theme_var.get(),
                'font_size': font_size,
            },
            'project': {
                'default_llm': self.default_llm.get(),
                'auto_save': self.auto_save.get(),
                'auto_regen': self.auto_regen.get(),
            }
        }

        if self.on_save:
            self.on_save(settings)

        self.destroy()

