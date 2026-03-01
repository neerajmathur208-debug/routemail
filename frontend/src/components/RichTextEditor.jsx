import React, { useRef, useCallback, useEffect, useState } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import { 
  Bold, Italic, Underline, Link, List, ListOrdered, 
  AlignLeft, AlignCenter, AlignRight, 
  Image, ChevronDown, Type, Palette
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from './ui/popover';

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
  const fileInputRef = useRef(null);
  const isInitialized = useRef(false);
  const savedRange = useRef(null); // Store cursor position
  const [linkUrl, setLinkUrl] = useState('');
  const [linkPopoverOpen, setLinkPopoverOpen] = useState(false);
  const [colorPopoverOpen, setColorPopoverOpen] = useState(false);
  const [selectedColor, setSelectedColor] = useState('#000000');
  const [selectedImage, setSelectedImage] = useState(null);
  const [imageResizing, setImageResizing] = useState(false);
  const resizeStartData = useRef(null);

  const fontSizes = [
    { label: 'Small', value: '12px' },
    { label: 'Normal', value: '16px' },
    { label: 'Large', value: '20px' },
    { label: 'Extra Large', value: '24px' },
  ];

  const colors = [
    '#000000', '#374151', '#6b7280', '#9ca3af',
    '#ef4444', '#f97316', '#eab308', '#22c55e',
    '#14b8a6', '#3b82f6', '#6366f1', '#8b5cf6',
    '#ec4899', '#f43f5e',
  ];

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

  // Save cursor position when editor loses focus
  const saveCursorPosition = useCallback(() => {
    const selection = window.getSelection();
    if (selection && selection.rangeCount > 0 && editorRef.current?.contains(selection.anchorNode)) {
      savedRange.current = selection.getRangeAt(0).cloneRange();
    }
  }, []);

  // Restore cursor position
  const restoreCursorPosition = useCallback(() => {
    if (savedRange.current && editorRef.current) {
      editorRef.current.focus();
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(savedRange.current);
    }
  }, []);

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
  const formatAlignLeft = () => execCommand('justifyLeft');
  const formatAlignCenter = () => execCommand('justifyCenter');
  const formatAlignRight = () => execCommand('justifyRight');

  const changeFontSize = (size) => {
    editorRef.current?.focus();
    // Create a span with the font size
    const selection = window.getSelection();
    if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
      const range = selection.getRangeAt(0);
      const span = document.createElement('span');
      span.style.fontSize = size;
      range.surroundContents(span);
      handleInput();
    } else {
      // If no selection, apply to next typed text
      document.execCommand('fontSize', false, '7');
      // Find and replace the font size
      const fontElements = editorRef.current?.querySelectorAll('font[size="7"]');
      fontElements?.forEach(el => {
        const span = document.createElement('span');
        span.style.fontSize = size;
        span.innerHTML = el.innerHTML;
        el.parentNode?.replaceChild(span, el);
      });
      handleInput();
    }
  };

  const changeColor = (color) => {
    setSelectedColor(color);
    execCommand('foreColor', color);
    setColorPopoverOpen(false);
  };

  const insertLink = () => {
    if (linkUrl) {
      // Ensure URL has protocol
      let url = linkUrl.trim();
      if (!url.match(/^https?:\/\//)) {
        url = 'https://' + url;
      }
      
      editorRef.current?.focus();
      const selection = window.getSelection();
      
      // Check if an image is selected
      if (selectedImage) {
        // Wrap image in link
        const link = document.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.style.display = 'inline-block';
        selectedImage.parentNode.insertBefore(link, selectedImage);
        link.appendChild(selectedImage);
        setSelectedImage(null);
        handleInput();
      } else if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
        // Create link for selected text
        const range = selection.getRangeAt(0);
        const link = document.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.appendChild(range.extractContents());
        range.insertNode(link);
        // Move cursor after link
        range.setStartAfter(link);
        range.collapse(true);
        selection.removeAllRanges();
        selection.addRange(range);
        handleInput();
      } else {
        // Insert link text if no selection
        const linkHtml = `<a href="${url}" target="_blank">${url}</a>`;
        document.execCommand('insertHTML', false, linkHtml);
        handleInput();
      }
      setLinkUrl('');
      setLinkPopoverOpen(false);
    }
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }

    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      alert('Image size must be less than 2MB');
      return;
    }

    // Convert to base64
    const reader = new FileReader();
    reader.onload = (event) => {
      const base64 = event.target?.result;
      editorRef.current?.focus();
      
      // Create img element with proper attributes for email compatibility
      const img = new window.Image();
      img.onload = () => {
        // Calculate initial width (max 600px for email compatibility)
        const maxWidth = 600;
        const initialWidth = Math.min(img.naturalWidth, maxWidth);
        
        // Insert image with width attribute for email clients
        const imgHtml = `<img src="${base64}" width="${initialWidth}" style="max-width:100%; height:auto;" />`;
        document.execCommand('insertHTML', false, imgHtml);
        handleInput();
      };
      img.src = base64;
    };
    reader.readAsDataURL(file);
    
    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const insertVariable = useCallback((variable) => {
    const variableText = `{{${variable}}}`;
    
    // Restore saved cursor position first
    if (savedRange.current && editorRef.current) {
      editorRef.current.focus();
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(savedRange.current);
      
      // Insert at cursor position
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const textNode = document.createTextNode(variableText);
      range.insertNode(textNode);
      
      // Move cursor after inserted text
      range.setStartAfter(textNode);
      range.setEndAfter(textNode);
      selection.removeAllRanges();
      selection.addRange(range);
      
      // Update saved position
      savedRange.current = range.cloneRange();
    } else {
      // Fallback: focus and try current selection
      editorRef.current?.focus();
      const selection = window.getSelection();
      if (selection && selection.rangeCount > 0 && editorRef.current?.contains(selection.anchorNode)) {
        const range = selection.getRangeAt(0);
        range.deleteContents();
        const textNode = document.createTextNode(variableText);
        range.insertNode(textNode);
        range.setStartAfter(textNode);
        range.setEndAfter(textNode);
        selection.removeAllRanges();
        selection.addRange(range);
      } else {
        // Last resort: append to end
        if (editorRef.current) {
          editorRef.current.innerHTML += variableText;
        }
      }
    }
    
    handleInput();
  }, [handleInput]);

  const handlePaste = useCallback((e) => {
    e.preventDefault();
    const text = e.clipboardData.getData('text/plain');
    document.execCommand('insertText', false, text);
    handleInput();
  }, [handleInput]);

  // Image resize functionality
  const handleImageClick = useCallback((e) => {
    if (e.target.tagName === 'IMG') {
      e.preventDefault();
      e.stopPropagation();
      
      // Deselect previous image
      const prevSelected = editorRef.current?.querySelector('img.image-selected');
      if (prevSelected) {
        prevSelected.classList.remove('image-selected');
      }
      
      // Select new image
      e.target.classList.add('image-selected');
      setSelectedImage(e.target);
    } else {
      // Click outside image - deselect
      const prevSelected = editorRef.current?.querySelector('img.image-selected');
      if (prevSelected) {
        prevSelected.classList.remove('image-selected');
      }
      setSelectedImage(null);
    }
  }, []);

  const handleResizeStart = useCallback((e, corner) => {
    if (!selectedImage) return;
    e.preventDefault();
    e.stopPropagation();
    
    const rect = selectedImage.getBoundingClientRect();
    resizeStartData.current = {
      startX: e.clientX,
      startY: e.clientY,
      startWidth: rect.width,
      startHeight: rect.height,
      aspectRatio: rect.width / rect.height,
      corner
    };
    setImageResizing(true);
  }, [selectedImage]);

  const handleResizeMove = useCallback((e) => {
    if (!imageResizing || !selectedImage || !resizeStartData.current) return;
    e.preventDefault();
    
    const { startX, startY, startWidth, startHeight, aspectRatio, corner } = resizeStartData.current;
    let deltaX = e.clientX - startX;
    let deltaY = e.clientY - startY;
    
    // Calculate new dimensions based on corner
    let newWidth, newHeight;
    
    if (corner === 'se') {
      newWidth = startWidth + deltaX;
    } else if (corner === 'sw') {
      newWidth = startWidth - deltaX;
    } else if (corner === 'ne') {
      newWidth = startWidth + deltaX;
    } else if (corner === 'nw') {
      newWidth = startWidth - deltaX;
    }
    
    // Maintain aspect ratio
    newWidth = Math.max(50, newWidth); // Minimum 50px
    newHeight = newWidth / aspectRatio;
    
    // Apply dimensions
    selectedImage.style.width = `${Math.round(newWidth)}px`;
    selectedImage.style.height = 'auto';
    selectedImage.setAttribute('width', Math.round(newWidth));
    selectedImage.removeAttribute('height'); // Remove height to maintain aspect ratio
  }, [imageResizing, selectedImage]);

  const handleResizeEnd = useCallback(() => {
    if (!imageResizing) return;
    
    setImageResizing(false);
    resizeStartData.current = null;
    handleInput(); // Trigger onChange to save the new dimensions
  }, [imageResizing, handleInput]);

  // Add mouse event listeners for resize
  useEffect(() => {
    if (imageResizing) {
      document.addEventListener('mousemove', handleResizeMove);
      document.addEventListener('mouseup', handleResizeEnd);
      return () => {
        document.removeEventListener('mousemove', handleResizeMove);
        document.removeEventListener('mouseup', handleResizeEnd);
      };
    }
  }, [imageResizing, handleResizeMove, handleResizeEnd]);

  // Render resize handles for selected image
  const renderResizeHandles = () => {
    if (!selectedImage) return null;
    
    const rect = selectedImage.getBoundingClientRect();
    const editorRect = editorRef.current?.getBoundingClientRect();
    if (!editorRect) return null;
    
    const top = rect.top - editorRect.top;
    const left = rect.left - editorRect.left;
    const width = rect.width;
    const height = rect.height;
    
    const handleStyle = {
      position: 'absolute',
      width: '10px',
      height: '10px',
      backgroundColor: '#3b82f6',
      border: '2px solid white',
      borderRadius: '2px',
      zIndex: 10,
      boxShadow: '0 1px 3px rgba(0,0,0,0.3)'
    };
    
    return (
      <>
        {/* Corner handles */}
        <div
          style={{ ...handleStyle, top: top - 5, left: left - 5, cursor: 'nwse-resize' }}
          onMouseDown={(e) => handleResizeStart(e, 'nw')}
        />
        <div
          style={{ ...handleStyle, top: top - 5, left: left + width - 5, cursor: 'nesw-resize' }}
          onMouseDown={(e) => handleResizeStart(e, 'ne')}
        />
        <div
          style={{ ...handleStyle, top: top + height - 5, left: left - 5, cursor: 'nesw-resize' }}
          onMouseDown={(e) => handleResizeStart(e, 'sw')}
        />
        <div
          style={{ ...handleStyle, top: top + height - 5, left: left + width - 5, cursor: 'nwse-resize' }}
          onMouseDown={(e) => handleResizeStart(e, 'se')}
        />
      </>
    );
  };

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

  const ToolbarDivider = () => (
    <div className="w-px h-6 bg-slate-300 mx-1" />
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
                className="cursor-pointer hover:bg-blue-600 hover:text-white hover:border-blue-600 transition-colors"
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
          <div className="flex flex-wrap items-center gap-1 p-2 bg-slate-50 border-b border-slate-200">
            {/* Font Size Dropdown */}
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <button
                  type="button"
                  className="flex items-center gap-1 px-2 py-1.5 rounded hover:bg-slate-200 text-slate-600 text-sm"
                  title="Font Size"
                >
                  <Type size={16} />
                  <ChevronDown size={14} />
                </button>
              </DropdownMenuTrigger>
              <DropdownMenuContent>
                {fontSizes.map((size) => (
                  <DropdownMenuItem
                    key={size.value}
                    onClick={() => changeFontSize(size.value)}
                    style={{ fontSize: size.value }}
                  >
                    {size.label}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuContent>
            </DropdownMenu>

            {/* Color Picker */}
            <Popover open={colorPopoverOpen} onOpenChange={setColorPopoverOpen}>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className="flex items-center gap-1 px-2 py-1.5 rounded hover:bg-slate-200 text-slate-600"
                  title="Text Color"
                >
                  <Palette size={16} />
                  <div 
                    className="w-3 h-3 rounded-sm border border-slate-300"
                    style={{ backgroundColor: selectedColor }}
                  />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-2">
                <div className="grid grid-cols-7 gap-1">
                  {colors.map((color) => (
                    <button
                      key={color}
                      type="button"
                      onClick={() => changeColor(color)}
                      className={`w-6 h-6 rounded border-2 transition-all ${
                        selectedColor === color ? 'border-blue-500 scale-110' : 'border-transparent hover:border-slate-300'
                      }`}
                      style={{ backgroundColor: color }}
                      title={color}
                    />
                  ))}
                </div>
                <div className="mt-2 flex items-center gap-2">
                  <input
                    type="color"
                    value={selectedColor}
                    onChange={(e) => changeColor(e.target.value)}
                    className="w-8 h-8 cursor-pointer"
                    title="Custom color"
                  />
                  <span className="text-xs text-slate-500">Custom</span>
                </div>
              </PopoverContent>
            </Popover>

            <ToolbarDivider />

            {/* Basic Formatting */}
            <ToolbarButton onClick={formatBold} title="Bold (Ctrl+B)">
              <Bold size={18} />
            </ToolbarButton>
            <ToolbarButton onClick={formatItalic} title="Italic (Ctrl+I)">
              <Italic size={18} />
            </ToolbarButton>
            <ToolbarButton onClick={formatUnderline} title="Underline (Ctrl+U)">
              <Underline size={18} />
            </ToolbarButton>

            <ToolbarDivider />

            {/* Alignment */}
            <ToolbarButton onClick={formatAlignLeft} title="Align Left">
              <AlignLeft size={18} />
            </ToolbarButton>
            <ToolbarButton onClick={formatAlignCenter} title="Align Center">
              <AlignCenter size={18} />
            </ToolbarButton>
            <ToolbarButton onClick={formatAlignRight} title="Align Right">
              <AlignRight size={18} />
            </ToolbarButton>

            <ToolbarDivider />

            {/* Lists */}
            <ToolbarButton onClick={formatUnorderedList} title="Bullet List">
              <List size={18} />
            </ToolbarButton>
            <ToolbarButton onClick={formatOrderedList} title="Numbered List">
              <ListOrdered size={18} />
            </ToolbarButton>

            <ToolbarDivider />

            {/* Link */}
            <Popover open={linkPopoverOpen} onOpenChange={setLinkPopoverOpen}>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className="p-2 rounded hover:bg-slate-200 text-slate-600"
                  title="Insert Link"
                >
                  <Link size={18} />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-80">
                <div className="space-y-3">
                  <p className="text-sm font-medium">Insert Link</p>
                  <Input
                    placeholder="https://example.com"
                    value={linkUrl}
                    onChange={(e) => setLinkUrl(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && insertLink()}
                  />
                  <div className="flex justify-end gap-2">
                    <Button 
                      variant="outline" 
                      size="sm"
                      onClick={() => {
                        setLinkUrl('');
                        setLinkPopoverOpen(false);
                      }}
                    >
                      Cancel
                    </Button>
                    <Button 
                      size="sm"
                      onClick={insertLink}
                      disabled={!linkUrl}
                    >
                      Insert
                    </Button>
                  </div>
                </div>
              </PopoverContent>
            </Popover>

            {/* Image Upload */}
            <ToolbarButton 
              onClick={() => fileInputRef.current?.click()} 
              title="Insert Image"
            >
              <Image size={18} />
            </ToolbarButton>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/*"
              onChange={handleImageUpload}
              className="hidden"
            />
          </div>
          
          {/* Editable Area with Resize Handles */}
          <div className="relative">
            <div
              ref={editorRef}
              contentEditable
              onInput={handleInput}
              onPaste={handlePaste}
              onClick={handleImageClick}
              className="min-h-[300px] p-4 outline-none prose prose-sm max-w-none"
              style={{ 
                fontFamily: "'Public Sans', sans-serif",
                lineHeight: 1.6
              }}
              data-placeholder={placeholder}
              data-testid="rich-text-editor"
              suppressContentEditableWarning={true}
            />
            {/* Image resize handles */}
            {selectedImage && renderResizeHandles()}
          </div>
          
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
            [contenteditable] img {
              max-width: 100%;
              height: auto;
              border-radius: 4px;
              margin: 8px 0;
              cursor: pointer;
            }
            [contenteditable] img.image-selected {
              outline: 2px solid #3b82f6;
              outline-offset: 2px;
            }
          `}</style>
        </div>
      ) : (
        <textarea
          value={plainTextValue}
          onChange={(e) => onPlainTextChange(e.target.value)}
          placeholder={placeholder}
          className="w-full min-h-[300px] p-4 border border-slate-200 rounded-md font-mono text-sm resize-y focus:ring-2 focus:ring-blue-500 focus:border-transparent"
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
