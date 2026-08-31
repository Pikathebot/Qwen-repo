"use client";

import React, { useState, useRef, useEffect, KeyboardEvent } from "react";
import { Attachment } from "@/lib/types";
import { uploadAttachmentApi } from "@/lib/api";

interface ComposerProps {
  onSendMessage: (text: string, attachments?: Attachment[]) => void;
  isLoading: boolean;
  onAbort?: () => void;
  disabled?: boolean;
  placeholder?: string;
  activeSessionId?: string;
  activeProjectId?: string;
}

export function Composer({
  onSendMessage,
  isLoading,
  onAbort,
  disabled,
  placeholder = "Message Jarvis...",
  activeSessionId,
  activeProjectId,
}: ComposerProps) {
  const [text, setText] = useState("");
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isLoading && textareaRef.current) {
      textareaRef.current.focus();
    }
  }, [isLoading]);

  // Adjust height dynamically up to 180px
  const handleInput = () => {
    const el = textareaRef.current;
    if (el) {
      el.style.height = "auto";
      el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const filesArray = Array.from(e.target.files);
      setAttachedFiles((prev) => [...prev, ...filesArray]);
    }
    // Reset file input so same file can be selected again if needed
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = async () => {
    const trimmed = text.trim();
    if ((!trimmed && attachedFiles.length === 0) || isLoading || disabled || uploading) return;

    let uploadedAttachments: Attachment[] = [];

    // Upload any pending attached files first
    if (attachedFiles.length > 0) {
      try {
        setUploading(true);
        const uploadPromises = attachedFiles.map((file) =>
          uploadAttachmentApi(file, activeSessionId, activeProjectId)
        );
        uploadedAttachments = await Promise.all(uploadPromises);
      } catch (err: unknown) {
        console.error("Error uploading attachments:", err);
      } finally {
        setUploading(false);
      }
    }

    const messageText = trimmed || (uploadedAttachments.length > 0 ? `Uploaded ${uploadedAttachments.length} file(s): ${uploadedAttachments.map(a => a.filename).join(", ")}` : "");
    onSendMessage(messageText, uploadedAttachments);
    setText("");
    setAttachedFiles([]);
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  };

  return (
    <div className="relative p-4 bg-void/80 border-t border-subtle backdrop-blur-md">
      <div className="max-w-4xl mx-auto flex flex-col bg-surface rounded-2xl border border-subtle focus-within:border-cyan-accent/50 focus-within:ring-1 focus-within:ring-cyan-accent/20 transition-all p-2 shadow-lg">
        {/* Attachment Chips Bar */}
        {attachedFiles.length > 0 && (
          <div className="flex items-center gap-1.5 flex-wrap px-2 pt-1 pb-2 border-b border-subtle/40 mb-1">
            {attachedFiles.map((f, i) => (
              <div
                key={`${f.name}-${i}`}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-void border border-subtle text-xs text-text-main font-mono animate-in fade-in"
              >
                <svg className="w-3.5 h-3.5 text-cyan-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
                <span className="truncate max-w-[150px]">{f.name}</span>
                <span className="text-[10px] text-text-muted/60">({(f.size / 1024).toFixed(0)}KB)</span>
                <button
                  type="button"
                  onClick={() => removeFile(i)}
                  className="text-text-muted hover:text-rose-accent ml-0.5"
                  title="Remove Attachment"
                >
                  ✕
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-end gap-2">
          {/* Paperclip Attachment Button */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            onChange={handleFileSelect}
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            disabled={disabled || isLoading || uploading}
            className="p-2 rounded-xl text-text-muted hover:text-text-main hover:bg-white/5 transition-colors disabled:opacity-40"
            title="Attach Files (.py, .ts, .txt, .pdf, .json, etc.)"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
            </svg>
          </button>

          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => {
              setText(e.target.value);
              handleInput();
            }}
            onKeyDown={handleKeyDown}
            placeholder={
              uploading
                ? "Uploading attachments..."
                : isLoading
                ? "Jarvis is processing..."
                : placeholder
            }
            disabled={disabled || isLoading || uploading}
            rows={1}
            className="flex-1 bg-transparent text-sm text-text-main placeholder:text-text-muted/50 resize-none px-2 py-1.5 focus:outline-none max-h-[180px] font-sans"
          />

          <div className="flex items-center gap-1.5 pb-0.5 pr-0.5">
            {isLoading ? (
              <button
                onClick={onAbort}
                className="p-2 rounded-xl bg-rose-accent/20 hover:bg-rose-accent/30 text-rose-accent transition-colors shadow-sm"
                title="Stop Generation"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" />
                </svg>
              </button>
            ) : (
              <button
                onClick={handleSubmit}
                disabled={(!text.trim() && attachedFiles.length === 0) || disabled || uploading}
                className="p-2 rounded-xl bg-cyan-accent text-void font-bold hover:bg-cyan-400 disabled:opacity-30 disabled:cursor-not-allowed transition-all shadow-sm active:scale-95"
                title="Send Message (Enter)"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </div>
      <div className="text-[11px] text-center text-text-muted/40 mt-2 font-mono">
        Enter to send · Shift+Enter for new line · 100% Offline Local Engine
      </div>
    </div>
  );
}
