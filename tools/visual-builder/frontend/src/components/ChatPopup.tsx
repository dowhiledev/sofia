import { useCallback, useEffect, useRef, useState, forwardRef, useImperativeHandle } from 'react';
import { Dialog, DialogContent, DialogTitle } from './ui/dialog';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { ChevronDown, ChevronUp, Send, X } from 'lucide-react';
import { exportToYaml } from '../utils/nomosYaml';
import * as yaml from 'js-yaml';
import { NomosClient, SessionData } from 'nomos-sdk';
import type { Node, Edge } from '@xyflow/react';
import { useDraggable } from '../hooks/useDraggable';

interface EnvVar { key: string; value: string }

export interface ChatPopupRef {
  reset: () => void;
}

interface ChatPopupProps {
  open: boolean;
  onClose: () => void;
  nodes: Node[];
  edges: Edge[];
  agentName: string;
  persona: string;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const STORAGE_KEY = 'nomos-chat-state';

export const ChatPopup = forwardRef<ChatPopupRef, ChatPopupProps>(function ChatPopup({
  open,
  onClose,
  nodes,
  edges,
  agentName,
  persona,
}, ref) {
  const [provider, setProvider] = useState('openai');
  const [model, setModel] = useState('gpt-3.5-turbo');
  const [envVars, setEnvVars] = useState<EnvVar[]>([]);
  const [showEnv, setShowEnv] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [sessionData, setSessionData] = useState<SessionData | undefined>();
  const clientRef = useRef<NomosClient>();
  const { position, onMouseDown, setPosition } = useDraggable({ x: 0, y: 0 });

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (parsed.provider) setProvider(parsed.provider);
        if (parsed.model) setModel(parsed.model);
        if (Array.isArray(parsed.envVars)) setEnvVars(parsed.envVars);
        if (Array.isArray(parsed.messages)) setMessages(parsed.messages);
        if (parsed.sessionData) setSessionData(parsed.sessionData);
      }
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    const state = { provider, model, envVars, messages, sessionData };
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    } catch {
      /* ignore */
    }
  }, [provider, model, envVars, messages, sessionData]);

  const resetBackend = useCallback(async () => {
    const result = exportToYaml(nodes, edges, agentName, persona);
    const lines = result.yaml.split('\n');
    const header = lines.slice(0, 4);
    const body = lines.slice(4).join('\n');
    const config = yaml.load(body) as any;
    config.llm = { provider, model };
    const finalYaml = [...header, yaml.dump(config, { indent: 2, lineWidth: 100, noRefs: true, sortKeys: false, styles: { '!!str': 'literal' } })].join('\n');
    await fetch('http://localhost:8000/reset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ yaml: finalYaml, env: Object.fromEntries(envVars.map(v => [v.key, v.value])) }),
    });
    clientRef.current = new NomosClient('http://localhost:8000');
    const res = await clientRef.current.chat({ user_input: '' });
    setSessionData(res.session_data);
    setMessages([{ role: 'assistant', content: JSON.stringify(res.response) }]);
  }, [nodes, edges, agentName, persona, provider, model, envVars]);

  useImperativeHandle(ref, () => ({ reset: resetBackend }), [resetBackend]);

  useEffect(() => {
    if (open) {
      resetBackend();
      setPosition({
        x: window.innerWidth - 340,
        y: window.innerHeight - 420,
      });
    }
  }, [open, resetBackend]);

  const sendMessage = useCallback(async () => {
    if (!input.trim() || !clientRef.current) return;
    const req = { user_input: input, session_data: sessionData };
    const res = await clientRef.current.chat(req);
    setSessionData(res.session_data);
    setMessages(m => [...m, { role: 'user', content: input }, { role: 'assistant', content: JSON.stringify(res.response) }]);
    setInput('');
  }, [input, sessionData]);

  const addEnv = () => setEnvVars(v => [...v, { key: '', value: '' }]);
  const updateEnv = (index: number, key: string, value: string) => {
    setEnvVars(v => v.map((item, i) => (i === index ? { key, value } : item)));
  };
  const removeEnv = (index: number) => setEnvVars(v => v.filter((_, i) => i !== index));

  if (!open) return null;

  return (
    <div className="fixed z-50 w-80" style={{ left: position.x, top: position.y }}>
      <Dialog open={open} onOpenChange={onClose}>
        <DialogContent showCloseButton={false} className="p-0 shadow-lg">
          <div className="flex items-center justify-between p-2 border-b cursor-move" onMouseDown={onMouseDown}>
            <DialogTitle className="text-sm">Chat Preview</DialogTitle>
            <Button variant="ghost" size="sm" onClick={onClose} className="h-6 w-6 p-0">
              <X className="w-3 h-3" />
            </Button>
          </div>
          <div className="p-3 space-y-2">
            <div className="flex gap-2">
              <Input value={provider} onChange={e => setProvider(e.target.value)} placeholder="Provider" />
              <Input value={model} onChange={e => setModel(e.target.value)} placeholder="Model" />
            </div>
            <Button variant="ghost" size="sm" onClick={() => setShowEnv(!showEnv)} className="flex items-center gap-1">
              {showEnv ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              Env Vars
            </Button>
            {showEnv && (
              <div className="space-y-1">
                {envVars.map((ev, i) => (
                  <div key={i} className="flex gap-1">
                    <Input value={ev.key} onChange={e => updateEnv(i, e.target.value, ev.value)} placeholder="KEY" />
                    <Input value={ev.value} onChange={e => updateEnv(i, ev.key, e.target.value)} placeholder="Value" />
                    <Button variant="ghost" size="icon" onClick={() => removeEnv(i)} className="h-8 w-8">x</Button>
                  </div>
                ))}
                <Button variant="ghost" size="sm" onClick={addEnv}>Add</Button>
              </div>
            )}
            <div className="border rounded p-2 h-48 overflow-y-auto bg-muted text-sm space-y-1">
              {messages.map((m, i) => (
                <div key={i} className={m.role === 'user' ? 'text-right' : 'text-left'}>
                  <span>{m.content}</span>
                </div>
              ))}
            </div>
            <div className="flex gap-1">
              <Textarea value={input} onChange={e => setInput(e.target.value)} className="flex-1" rows={2} />
              <Button variant="default" size="icon" onClick={sendMessage} className="h-8 w-8">
                <Send className="w-3 h-3" />
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
});

ChatPopup.displayName = 'ChatPopup';

