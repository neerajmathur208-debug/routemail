import React, { useRef, useMemo, useCallback } from 'react';
import ReactQuill from 'react-quill';
import 'react-quill/dist/quill.snow.css';
import { Button } from './ui/button';
import { Badge } from './ui/badge';

// Custom styles to override Quill defaults
const editorStyles = `
  .email-editor .ql-container {
    font-family: 'Public Sans', sans-serif;
    font-size: 14px;
    min-height: 300px;
  }
  .email-editor .ql-editor {
    min-height: 300px;
    line-height: 1.6;
  }
  .email-editor .ql-toolbar {
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    background: #f8fafc;
    border-color: #e2e8f0;
  }
  .email-editor .ql-container {
    border-bottom-left-radius: 6px;
    border-bottom-right-radius: 6px;
    border-color: #e2e8f0;
  }
  .email-editor .ql-editor:focus {
    outline: none;
  }
  .email-editor .ql-editor.ql-blank::before {
    color: #94a3b8;
    font-style: normal;
  }
`;

export default function RichTextEditor({ 
  value, 
  onChange, 
  placeholder = "Write your email content here...",
  variables = [],
  showPlainText = false,
  plainTextValue = "",
  onPlainTextChange = () => {}
}) {
  const quillRef = useRef(null);
  
  const modules = useMemo(() => ({
    toolbar: [
      ['bold', 'italic', 'underline'],
      [{ 'list': 'ordered'}, { 'list': 'bullet' }],
      ['link'],
      ['clean']
    ],
  }), []);

  const formats = useMemo(() => [
    'bold', 'italic', 'underline',
    'list', 'bullet',
    'link'
  ], []);

  const insertVariable = useCallback((variable) => {
    const quill = quillRef.current?.getEditor();
    if (quill) {
      const range = quill.getSelection(true);
      const variableText = `{{${variable}}}`;
      quill.insertText(range.index, variableText);
      quill.setSelection(range.index + variableText.length);
    }
  }, []);

  return (
    <div className="space-y-4">
      {/* Inject custom styles */}
      <style>{editorStyles}</style>
      
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
        <div className="email-editor">
          <ReactQuill
            ref={quillRef}
            theme="snow"
            value={value}
            onChange={onChange}
            modules={modules}
            formats={formats}
            placeholder={placeholder}
          />
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
