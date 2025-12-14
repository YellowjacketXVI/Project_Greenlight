"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { cn } from "@/lib/utils";
import { User, MapPin, Package } from "lucide-react";

export interface MentionEntity {
  tag: string;
  name: string;
  type: "character" | "location" | "prop";
}

interface MentionInputProps {
  value: string;
  onChange: (value: string) => void;
  entities: MentionEntity[];
  placeholder?: string;
  className?: string;
}

// Convert display format (@Name) to storage format ([TAG])
export function displayToStorage(text: string, entities: MentionEntity[]): string {
  let result = text;
  for (const entity of entities) {
    // Match @Name (case insensitive)
    const regex = new RegExp(`@${entity.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\b`, 'gi');
    result = result.replace(regex, `[${entity.tag}]`);
  }
  return result;
}

// Convert storage format ([TAG]) to display format (@Name)
export function storageToDisplay(text: string, entities: MentionEntity[]): string {
  let result = text;
  for (const entity of entities) {
    const regex = new RegExp(`\\[${entity.tag}\\]`, 'g');
    result = result.replace(regex, `@${entity.name}`);
  }
  return result;
}

const getEntityIcon = (type: string) => {
  switch (type) {
    case "character": return <User className="h-3 w-3" />;
    case "location": return <MapPin className="h-3 w-3" />;
    case "prop": return <Package className="h-3 w-3" />;
    default: return null;
  }
};

const getEntityColor = (type: string) => {
  switch (type) {
    case "character": return "text-blue-400 bg-blue-500/10";
    case "location": return "text-green-400 bg-green-500/10";
    case "prop": return "text-orange-400 bg-orange-500/10";
    default: return "text-muted-foreground bg-secondary";
  }
};

export function MentionInput({ value, onChange, entities, placeholder, className }: MentionInputProps) {
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [suggestions, setSuggestions] = useState<MentionEntity[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [mentionStart, setMentionStart] = useState<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleInput = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newValue = e.target.value;
    const cursorPos = e.target.selectionStart;
    onChange(newValue);

    // Check if we're typing a mention
    const textBeforeCursor = newValue.slice(0, cursorPos);
    const mentionMatch = textBeforeCursor.match(/@(\w*)$/);

    if (mentionMatch) {
      const query = mentionMatch[1].toLowerCase();
      setMentionStart(cursorPos - mentionMatch[0].length);
      
      // Filter entities by query
      const filtered = entities.filter(e => 
        e.name.toLowerCase().includes(query) || 
        e.tag.toLowerCase().includes(query)
      ).slice(0, 8);
      
      setSuggestions(filtered);
      setShowSuggestions(filtered.length > 0);
      setSelectedIndex(0);
    } else {
      setShowSuggestions(false);
      setMentionStart(null);
    }
  }, [entities, onChange]);

  const insertMention = useCallback((entity: MentionEntity) => {
    if (mentionStart === null || !textareaRef.current) return;

    const cursorPos = textareaRef.current.selectionStart;
    const before = value.slice(0, mentionStart);
    const after = value.slice(cursorPos);
    const newValue = `${before}@${entity.name} ${after}`;
    
    onChange(newValue);
    setShowSuggestions(false);
    setMentionStart(null);

    // Focus and set cursor position
    setTimeout(() => {
      if (textareaRef.current) {
        const newPos = mentionStart + entity.name.length + 2; // +2 for @ and space
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(newPos, newPos);
      }
    }, 0);
  }, [mentionStart, value, onChange]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!showSuggestions) return;

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setSelectedIndex(i => Math.min(i + 1, suggestions.length - 1));
        break;
      case "ArrowUp":
        e.preventDefault();
        setSelectedIndex(i => Math.max(i - 1, 0));
        break;
      case "Enter":
      case "Tab":
        if (suggestions[selectedIndex]) {
          e.preventDefault();
          insertMention(suggestions[selectedIndex]);
        }
        break;
      case "Escape":
        setShowSuggestions(false);
        break;
    }
  }, [showSuggestions, suggestions, selectedIndex, insertMention]);

  // Close suggestions when clicking outside
  useEffect(() => {
    const handleClick = (e: MouseEvent) => {
      if (textareaRef.current && !textareaRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener("click", handleClick);
    return () => document.removeEventListener("click", handleClick);
  }, []);

  return (
    <div className="relative">
      <textarea
        ref={textareaRef}
        value={value}
        onChange={handleInput}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className={cn(
          "w-full p-4 bg-card border border-border rounded-lg font-mono text-sm resize-none",
          "focus:outline-none focus:ring-2 focus:ring-primary/50",
          className
        )}
      />
      {/* Suggestions dropdown */}
      {showSuggestions && suggestions.length > 0 && (
        <div className="absolute z-50 mt-1 w-64 bg-popover border border-border rounded-lg shadow-lg overflow-hidden">
          {suggestions.map((entity, idx) => (
            <button
              key={entity.tag}
              onClick={() => insertMention(entity)}
              className={cn(
                "w-full flex items-center gap-2 px-3 py-2 text-sm text-left transition-colors",
                idx === selectedIndex ? "bg-primary/20" : "hover:bg-secondary"
              )}
            >
              <span className={cn("p-1 rounded", getEntityColor(entity.type))}>
                {getEntityIcon(entity.type)}
              </span>
              <div className="flex-1 min-w-0">
                <div className="font-medium truncate">{entity.name}</div>
                <div className="text-xs text-muted-foreground truncate">[{entity.tag}]</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}


