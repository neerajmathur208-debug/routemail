import React, { useRef, useCallback, useEffect } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Bold, Italic, Underline, Link, List, ListOrdered, Undo, Type } from 'lucide-react';

export default function RichTextEditor({ 
  value, 
  onChange, 
  placeholder = "Write your email content here...",
  variables = [],
  showPlainText = false,
  plainTextValue = "",
  onPlainTextChange = () => {}
}) {
  const editorRef = useRef(null);
  const isInitialized = useRef(false);

  // Initialize editor content
  useEffect(() => {
    if (editorRef.current && !isInitialized.current && value) {
      editorRef.current.innerHTML = value;
      isInitialized.current = true;
    }
  }, [value]);

  // Update content when value changes externally
  useEffect(() => {
    if (editorRef.current && value !== editorRef.current.innerHTML) {
      const selection = window.getSelection();
      const range = selection?.rangeCount > 0 ? selection.getRangeAt(0) : null;
      
      if (document.activeElement !== editorRef.current) {
        editorRef.current.innerHTML = value || '';
      }
    }
  }, [value]);

  const handleInput = useCallback(() => {
    if (editorRef.current) {
      onChange(editorRef.current.innerHTML);
    }
  }, [onChange]);

  const execCommand = useCallback((command, value = null) => {
    editorRef.current?.focus();
    document.execCommand(command, false, value);
    handleInput();
  }, [handleInput]);

  const formatBold = () => execCommand('bold');
  const formatItalic = () => execCommand('italic');
  const formatUnderline = () => execCommand('underline');
  const formatOrderedList = () => execCommand('insertOrderedList');
  const formatUnorderedList = () => execCommand('insertUnorderedList');

  const insertLink = () => {
    const url = prompt('Enter URL:');
    if (url) {
      execCommand('createLink', url);
    }
  };

  const insertVariable = useCallback((variable) => {
    editorRef.current?.focus();
    const variableText = `{{${variable}}}`;
    
    // Insert at cursor position
    const selection = window.getSelection();
    if (selection && selection.rangeCount > 0) {
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const textNode = document.createTextNode(variableText);
      range.insertNode(textNode);
      
      // Move cursor after inserted text
      range.setStartAfter(textNode);
      range.setEndAfter(textNode);
      selection.removeAllRanges();
      selection.addRange(range);
    } else {
      // Fallback: append to end
      editorRef.current.innerHTML += variableText;
    }
    
    handleInput();
  }, [handleInput]);

  const handlePaste = useCallback((e) => {
    e.preventDefault();
    const text = e.clipboardData.getData('text/plain');
    document.execCommand('insertText', false, text);
    handleInput();
  }, [handleInput]);

  const ToolbarButton = ({ onClick, active, children, title }) => (
    <button
      type="button"
      onClick={onClick}
      title={title}
      className={`p-2 rounded hover:bg-slate-200 transition-colors ${
        active ? 'bg-slate-200 text-slate-900' : 'text-slate-600'
      }`}
    >
      {children}
    </button>
  );

  return (
    <div className="space-y-4">
      {/* Variables Panel */}
      {variables.length > 0 && (
        <div className="bg-slate-50 border border-slate-200 rounded-md p-4">
          <p className="text-sm font-medium text-slate-700 mb-2">
            Available Variables (click to insert):
          </p>
          <div className="flex flex-wrap gap-2">
            {variables.map((variable) => (
              <Badge
                key={variable}
                variant="outline"
                className="cursor-pointer hover:bg-electric-blue hover:text-white hover:border-electric-blue transition-colors"
                onClick={() => insertVariable(variable)}
                data-testid={`variable-${variable}`}
              >
                {`{{${variable}}}`}
              </Badge>
            ))}
          </div>
        </div>
      )}

      {/* Editor */}
      {!showPlainText ? (
        <div className="border border-slate-200 rounded-md overflow-hidden">
          {/* Toolbar */}
          <div className="flex items-center gap-1 p-2 bg-slate-50 border-b border-slate-200">
            <ToolbarButton onClick={formatBold} title="Bold">
              <Bold size={18} />
            </ToolbarButton>
            <ToolbarButton onClick={formatItalic} title="Italic">
              <Italic size={18} />
            </ToolbarButton>
            <ToolbarButton onClick={formatUnderline} title="Underline">
              <Underline size={18} />
            </ToolbarButton>
            <div className="w-px h-6 bg-slate-300 mx-1" />
            <ToolbarButton onClick={formatUnorderedList} title="Bullet List">
              <List size={18} />
            </ToolbarButton>
            <ToolbarButton onClick={formatOrderedList} title="Numbered List">
              <ListOrdered size={18} />
            </ToolbarButton>
            <div className="w-px h-6 bg-slate-300 mx-1" />
            <ToolbarButton onClick={insertLink} title="Insert Link">
              <Link size={18} />
            </ToolbarButton>
          </div>
          
          {/* Editable Area */}
          <div
            ref={editorRef}
            contentEditable
            onInput={handleInput}
            onPaste={handlePaste}
            className="min-h-[300px] p-4 outline-none prose prose-sm max-w-none"
            style={{ 
              fontFamily: "'Public Sans', sans-serif",
              lineHeight: 1.6
            }}
            data-placeholder={placeholder}
            data-testid="rich-text-editor"
            suppressContentEditableWarning={true}
          />
          
          <style>{`
            [contenteditable]:empty:before {
              content: attr(data-placeholder);
              color: #94a3b8;
              pointer-events: none;
            }
            [contenteditable] a {
              color: #2563eb;
              text-decoration: underline;
            }
            [contenteditable] ul, [contenteditable] ol {
              padding-left: 1.5em;
              margin: 0.5em 0;
            }
            [contenteditable] li {
              margin: 0.25em 0;
            }
          `}</style>
        </div>
      ) : (
        <textarea
          value={plainTextValue}
          onChange={(e) => onPlainTextChange(e.target.value)}
          placeholder={placeholder}
          className="w-full min-h-[300px] p-4 border border-slate-200 rounded-md font-mono text-sm resize-y focus:ring-2 focus:ring-electric-blue focus:border-transparent"
          data-testid="plain-text-editor"
        />
      )}
      
      {/* Variable hint */}
      <p className="text-xs text-slate-500">
        Use {"{{variable_name}}"} syntax for personalization. Variables will be replaced with actual values when sending.
      </p>
    </div>
  );
}
