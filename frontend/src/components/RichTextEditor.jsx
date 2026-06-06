import React, { useRef, useCallback, useEffect, useState } from 'react';
import { Button } from './ui/button';
import { Badge } from './ui/badge';
import { Input } from './ui/input';
import {
  Bold, Italic, Underline, Link, List, ListOrdered, 
  AlignLeft, AlignCenter, AlignRight, 
  Image, ChevronDown, Type, Palette, ShieldOff, Code, Trash2
} from 'lucide-react';
import DOMPurify from 'dompurify';
import { toast } from 'sonner';
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
  const [unsubPopoverOpen, setUnsubPopoverOpen] = useState(false);
  const [unsubText, setUnsubText] = useState('Unsubscribe');
  const resizeStartData = useRef(null);

  // HTML edit mode
  const [htmlMode, setHtmlMode] = useState(false);
  const [htmlDraft, setHtmlDraft] = useState('');

  // Sanitize HTML for email use: allow common email tags + style/href, preserve {{vars}},
  // strip <script>, on* event handlers, javascript: URLs, etc.
  const sanitizeForEmail = useCallback((dirty) => {
    if (!dirty) return '';
    return DOMPurify.sanitize(dirty, {
      // Allow inline styles + safe email-friendly tags. DOMPurify removes <script>
      // and on* event handler attributes by default.
      ALLOWED_TAGS: [
        'a', 'b', 'i', 'em', 'strong', 'u', 'br', 'p', 'div', 'span',
        'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
        'ul', 'ol', 'li', 'blockquote', 'hr',
        'table', 'thead', 'tbody', 'tfoot', 'tr', 'td', 'th',
        'img', 'figure', 'figcaption',
        'pre', 'code', 'small', 'sub', 'sup',
      ],
      ALLOWED_ATTR: [
        'href', 'src', 'alt', 'title', 'class', 'style', 'width', 'height',
        'target', 'rel', 'align', 'valign', 'colspan', 'rowspan',
        'cellpadding', 'cellspacing', 'border', 'bgcolor',
        'data-unsubscribe',
      ],
      ALLOW_DATA_ATTR: false,
      // Block javascript:/vbscript:/data: protocols in URLs
      ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto|tel):|[^a-z]|[a-z+.\-]+(?:[^a-z+.\-:]|$))/i,
    });
  }, []);

  // Toggle visual <-> HTML mode. Going to HTML pulls current HTML from the editor;
  // coming back, sanitize and push it back into the contentEditable + onChange.
  const toggleHtmlMode = useCallback(() => {
    if (!htmlMode) {
      // Switching INTO HTML view — capture current value
      const current = editorRef.current?.innerHTML || value || '';
      setHtmlDraft(current);
      setHtmlMode(true);
    } else {
      // Switching BACK to visual — sanitize and apply
      const cleaned = sanitizeForEmail(htmlDraft);
      if (editorRef.current) {
        editorRef.current.innerHTML = cleaned;
      }
      onChange(cleaned);
      setHtmlMode(false);
    }
  }, [htmlMode, htmlDraft, sanitizeForEmail, onChange, value]);

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
      
      // Restore cursor position first if we have a saved range
      if (savedRange.current && editorRef.current) {
        editorRef.current.focus();
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(savedRange.current);
      } else {
        editorRef.current?.focus();
      }
      
      const selection = window.getSelection();
      
      // Check if an image is selected
      if (selectedImage) {
        // Wrap image in link
        const link = document.createElement('a');
        link.href = url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.style.display = 'inline-block';
        selectedImage.parentNode.insertBefore(link, selectedImage);
        link.appendChild(selectedImage);
        setSelectedImage(null);
        handleInput();
      } else if (selection && selection.rangeCount > 0 && !selection.isCollapsed) {
        // Wrap selected text with link
        const range = selection.getRangeAt(0);
        const selectedText = range.toString();
        
        if (selectedText) {
          // Create link element and wrap the selected content
          const link = document.createElement('a');
          link.href = url;
          link.target = '_blank';
          link.rel = 'noopener noreferrer';
          
          // Extract the selected content and put it in the link
          const contents = range.extractContents();
          link.appendChild(contents);
          range.insertNode(link);
          
          // Move cursor after the link
          range.setStartAfter(link);
          range.setEndAfter(link);
          selection.removeAllRanges();
          selection.addRange(range);
          
          handleInput();
        }
      } else {
        // No selection - insert the URL as linked text
        const linkHtml = `<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`;
        document.execCommand('insertHTML', false, linkHtml);
        handleInput();
      }
      setLinkUrl('');
      setLinkPopoverOpen(false);
    }
  };

  // Insert an unsubscribe link placeholder. The token {{unsubscribe_url}} is
  // resolved at send-time by the backend's `replace_variables` to the per-recipient,
  // per-user GET /api/unsubscribe/{user_id}/{email} endpoint.
  const insertUnsubscribeLink = () => {
    if (!editorRef.current) return;
    editorRef.current.focus();
    const text = (unsubText || 'Unsubscribe').trim() || 'Unsubscribe';
    const html = `<a href="{{unsubscribe_url}}" target="_blank" rel="noopener noreferrer">${text}</a>&nbsp;`;
    if (savedRange.current) {
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(savedRange.current);
    }
    document.execCommand('insertHTML', false, html);
    handleInput();
    setUnsubPopoverOpen(false);
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Validate file type — JPG, PNG, WEBP, GIF
    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp', 'image/gif'];
    if (!allowedTypes.includes((file.type || '').toLowerCase())) {
      alert('Unsupported image type. Please use JPG, PNG, WEBP, or GIF.');
      return;
    }

    // Validate file size (max 5MB)
    if (file.size > 5 * 1024 * 1024) {
      alert('Image size exceeds maximum allowed size of 5 MB');
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

  // Auto-link plain text — converts URLs / www. / emails to anchor tags.
  // Used both on paste and on blur so autolinks happen in real workflows.
  const autoLinkText = useCallback((rawText) => {
    if (!rawText) return '';
    // Order matters: emails first (more specific), then full URLs, then www.
    const escapeHtml = (s) =>
      s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    // First escape, then process the regexes — we need raw chars for matching, so do it in pieces.
    // Strategy: split by tokens that match either url/email/www, building HTML with anchors.
    const combined = /(\bhttps?:\/\/[^\s<>"]+|\bwww\.[^\s<>"]+|\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g;
    let result = '';
    let lastIdx = 0;
    rawText.replace(combined, (match, _g, idx) => {
      result += escapeHtml(rawText.slice(lastIdx, idx));
      let href = match;
      if (match.includes('@') && !match.includes('://')) {
        href = `mailto:${match}`;
      } else if (match.startsWith('www.')) {
        href = `https://${match}`;
      }
      result += `<a href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">${escapeHtml(match)}</a>`;
      lastIdx = idx + match.length;
      return match;
    });
    result += escapeHtml(rawText.slice(lastIdx));
    return result;
  }, []);

  const handlePaste = useCallback((e) => {
    e.preventDefault();
    const text = e.clipboardData.getData('text/plain');
    const html = autoLinkText(text);
    // Use insertHTML so any detected URLs/emails become real <a> tags.
    document.execCommand('insertHTML', false, html);
    handleInput();
  }, [handleInput, autoLinkText]);

  // Auto-link any standalone URLs/emails that already exist as plain text
  // (e.g. typed without spaces around them). Triggered on blur.
  const handleEditorBlur = useCallback(() => {
    if (!editorRef.current) return;
    const root = editorRef.current;
    const URL_RE = /(\bhttps?:\/\/[^\s<>"]+|\bwww\.[^\s<>"]+|\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})/g;
    let mutated = false;
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: (n) => {
        // Skip text already inside an <a> element.
        let p = n.parentNode;
        while (p && p !== root) {
          if (p.tagName && p.tagName.toLowerCase() === 'a') return NodeFilter.FILTER_REJECT;
          p = p.parentNode;
        }
        return URL_RE.test(n.nodeValue) ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      },
    });
    const textNodes = [];
    let node;
    while ((node = walker.nextNode())) textNodes.push(node);
    textNodes.forEach((textNode) => {
      // Reset regex (test() advances lastIndex)
      URL_RE.lastIndex = 0;
      const text = textNode.nodeValue;
      if (!URL_RE.test(text)) return;
      URL_RE.lastIndex = 0;
      const wrap = document.createElement('span');
      wrap.innerHTML = autoLinkText(text);
      textNode.replaceWith(...wrap.childNodes);
      mutated = true;
    });
    if (mutated) handleInput();
  }, [autoLinkText, handleInput]);

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

  // Delete the currently selected image (keeps surrounding text/content intact).
  const handleDeleteImage = useCallback(() => {
    if (!selectedImage) return;
    // If the image is wrapped in a parent <a> with no other content, remove the anchor.
    const parent = selectedImage.parentNode;
    selectedImage.remove();
    if (
      parent &&
      parent.tagName === 'A' &&
      parent.childNodes.length === 0
    ) {
      parent.remove();
    }
    setSelectedImage(null);
    handleInput();
  }, [selectedImage, handleInput]);

  // Press DEL / BACKSPACE while an image is selected → delete it.
  useEffect(() => {
    if (!selectedImage) return;
    const onKeyDown = (e) => {
      if (e.key === 'Delete' || e.key === 'Backspace') {
        e.preventDefault();
        handleDeleteImage();
      } else if (e.key === 'Escape') {
        // Deselect
        selectedImage.classList.remove('image-selected');
        setSelectedImage(null);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [selectedImage, handleDeleteImage]);

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

  // Render resize handles + floating Delete button for selected image
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
        {/* Floating action bar — appears just above the image */}
        <div
          style={{
            position: 'absolute',
            top: Math.max(top - 38, 4),
            left: left,
            zIndex: 20,
          }}
          onMouseDown={(e) => e.preventDefault()}  // Don't lose image selection
          data-testid="image-floating-toolbar"
        >
          <button
            type="button"
            onClick={handleDeleteImage}
            className="inline-flex items-center gap-1.5 px-2.5 py-1.5 bg-white border border-red-200 rounded-md shadow-md text-xs font-semibold text-red-600 hover:bg-red-50 hover:border-red-300 transition-colors"
            title="Delete image (Del / Backspace)"
            data-testid="delete-image-btn"
          >
            <Trash2 size={12} /> Delete Image
          </button>
        </div>
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

            {/* Unsubscribe link */}
            <Popover open={unsubPopoverOpen} onOpenChange={setUnsubPopoverOpen}>
              <PopoverTrigger asChild>
                <button
                  type="button"
                  className="p-2 rounded hover:bg-rose-100 text-rose-600"
                  title="Insert Unsubscribe Link"
                  data-testid="editor-insert-unsubscribe-btn"
                  onClick={() => {
                    // Save cursor before opening the popover so we can insert at the right place
                    const sel = window.getSelection();
                    if (sel && sel.rangeCount > 0) savedRange.current = sel.getRangeAt(0).cloneRange();
                  }}
                >
                  <ShieldOff size={18} />
                </button>
              </PopoverTrigger>
              <PopoverContent className="w-80">
                <div className="space-y-3">
                  <p className="text-sm font-medium">Insert Unsubscribe Link</p>
                  <p className="text-xs text-slate-500">
                    A unique unsubscribe URL is generated automatically for each recipient at send-time.
                  </p>
                  <Input
                    placeholder="Link text"
                    value={unsubText}
                    onChange={(e) => setUnsubText(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && insertUnsubscribeLink()}
                    data-testid="editor-unsubscribe-text-input"
                  />
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" size="sm" onClick={() => setUnsubPopoverOpen(false)}>
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={insertUnsubscribeLink}
                      data-testid="editor-unsubscribe-insert-btn"
                    >
                      Insert
                    </Button>
                  </div>
                </div>
              </PopoverContent>
            </Popover>

            {/* HTML mode toggle + Spellcheck verification */}
            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                onClick={() => {
                  // Insert a known-misspelled word at the caret so the user can SEE
                  // the browser's native red squiggle. Pure DOM mutation — no API.
                  if (htmlMode) {
                    setHtmlDraft((d) => (d || "") + " definately ");
                    toast.success("Inserted 'definately' into HTML — switch to Visual mode to see the underline.");
                    return;
                  }
                  if (!editorRef.current) return;
                  editorRef.current.focus();
                  // Try caret insert via execCommand; fall back to appending a text node.
                  let inserted = false;
                  try {
                    inserted = document.execCommand("insertText", false, " definately ");
                  } catch (e) { /* ignore */ }
                  if (!inserted) {
                    editorRef.current.appendChild(document.createTextNode(" definately "));
                  }
                  handleInput();
                  toast.success("Inserted 'definately' — your browser should underline it in red.");
                }}
                className="flex items-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium text-emerald-700 bg-emerald-50 hover:bg-emerald-100 border border-emerald-200 transition-colors"
                title="Insert the word 'definately' (misspelt) — the browser should underline it in red if spellcheck is working."
                data-testid="editor-verify-spellcheck-btn"
              >
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
                Spellcheck: Active · Verify
              </button>
              <Button
                type="button"
                size="sm"
                variant={htmlMode ? "default" : "ghost"}
                onClick={toggleHtmlMode}
                className={`flex items-center gap-1 ${htmlMode ? "bg-slate-800 hover:bg-slate-900 text-white" : "text-slate-600 hover:bg-slate-200"}`}
                data-testid="editor-html-mode-toggle"
                title={htmlMode ? "Back to visual editor" : "Edit as HTML"}
              >
                <Code size={14} />
                {htmlMode ? "Visual" : "HTML"}
              </Button>
            </div>
          </div>
          
          {/* Editable Area with Resize Handles */}
          <div className="relative">
            {htmlMode ? (
              <textarea
                value={htmlDraft}
                onChange={(e) => setHtmlDraft(e.target.value)}
                spellCheck={true}
                lang="en"
                autoCorrect="on"
                autoCapitalize="sentences"
                className="w-full min-h-[300px] max-h-[400px] overflow-y-auto p-4 outline-none font-mono text-xs bg-slate-900 text-slate-100 leading-relaxed"
                placeholder="<!-- Paste or write raw HTML here. Switch back to Visual to render it. -->"
                data-testid="rich-text-editor-html"
              />
            ) : (
              <div
                ref={editorRef}
                contentEditable
                spellCheck={true}
                lang="en"
                autoCorrect="on"
                autoCapitalize="sentences"
                onInput={handleInput}
                onPaste={handlePaste}
                onClick={handleImageClick}
                onBlur={(e) => { handleEditorBlur(e); saveCursorPosition(); }}
                onKeyUp={saveCursorPosition}
                className="min-h-[300px] max-h-[400px] overflow-y-auto p-4 outline-none prose prose-sm max-w-none"
                style={{
                  fontFamily: "'Public Sans', sans-serif",
                  lineHeight: 1.6,
                  /* Force the browser to render its native spell-check decoration */
                  textDecorationSkipInk: 'auto',
                }}
                data-placeholder={placeholder}
                data-testid="rich-text-editor"
                suppressContentEditableWarning={true}
              />
            )}
            {/* Image resize handles */}
            {!htmlMode && selectedImage && renderResizeHandles()}
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
            /* Make sure native spell-check decoration is never suppressed by Tailwind/prose */
            [contenteditable][spellcheck="true"] {
              -webkit-user-modify: read-write;
            }
            [contenteditable][spellcheck="true"] ::spelling-error {
              text-decoration: red wavy underline;
              text-decoration-skip-ink: none;
            }
            [contenteditable][spellcheck="true"] ::grammar-error {
              text-decoration: blue wavy underline;
              text-decoration-skip-ink: none;
            }
          `}</style>
        </div>
      ) : (
        <textarea
          value={plainTextValue}
          onChange={(e) => onPlainTextChange(e.target.value)}
          placeholder={placeholder}
          spellCheck={true}
          lang="en"
          autoCorrect="on"
          autoCapitalize="sentences"
          className="w-full min-h-[300px] max-h-[400px] overflow-y-auto p-4 border border-slate-200 rounded-md font-mono text-sm focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          data-testid="plain-text-editor"
        />
      )}
      
      {/* Variable + spell check hint */}
      <p className="text-xs text-slate-500" data-testid="editor-helper-text">
        Use {"{{variable_name}}"} syntax for personalization. Variables will be replaced with actual values when sending.
        {" "}
        <span className="text-slate-400">Spell check uses your browser&apos;s built-in spell checker.</span>
      </p>
    </div>
  );
}
