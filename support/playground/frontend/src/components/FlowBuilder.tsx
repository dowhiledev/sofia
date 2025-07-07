import { useCallback, useState, useRef, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  addEdge,
  type OnConnect,
  type Node,
  type Edge,
} from '@xyflow/react';
import { Toolbar } from './Toolbar';
import { StepNode } from './nodes/StepNode';
import { ToolNode } from './nodes/ToolNode';
import { GroupNode } from './nodes/GroupNode';
import { RouteEdge } from './edges/RouteEdge';
import { ToolEdge } from './edges/ToolEdge';
import { CustomContextMenu } from './context-menu/CustomContextMenu';
import { FlowProvider, useFlowContext } from '../context/FlowContext';
import { NodeEditDialogs } from './dialogs/NodeEditDialogs';
import { FlowGroupEditDialog } from './dialogs/FlowGroupEditDialog';
import { ExportDialog } from './dialogs/ExportDialog';
import { ImportDialog } from './dialogs/ImportDialog';
import { KeyboardShortcuts } from './KeyboardShortcuts';
import { SearchFilter } from './SearchFilter';
import { autoArrangeNodes } from '../utils/autoArrange';
import {
  copyNodeToClipboard,
  getClipboardData,
  hasClipboardData,
  cloneNodeWithNewId,
} from '../utils/clipboard';
import { useUndoRedo } from '../hooks/useUndoRedo';
import {
  bulkDeleteNodes,
  bulkDuplicateNodes,
  bulkGroupNodes,
} from '../utils/bulkOperations';
import { detachNode } from '../utils/detachNodes';
import type { StepNodeData, ToolNodeData, FlowGroupData } from '../types';

// Component to trigger editing from outside the context
function EditTrigger({
  editTrigger,
  setEditTrigger
}: {
  editTrigger: { nodeId: string; nodeType: 'step' | 'tool'; nodeData: StepNodeData | ToolNodeData } | null;
  setEditTrigger: (trigger: null) => void;
}) {
  const { setEditingNode } = useFlowContext();

  useEffect(() => {
    if (editTrigger) {
      setEditingNode(editTrigger.nodeId, editTrigger.nodeType, editTrigger.nodeData);
      setEditTrigger(null);
    }
  }, [editTrigger, setEditingNode, setEditTrigger]);

  return null;
}

// Utility function to calculate group bounds based on child nodes
const calculateGroupBounds = (groupNode: Node, childNodes: Node[]) => {
  if (childNodes.length === 0) {
    return {
      position: groupNode.position,
      size: { width: groupNode.style?.width as number || 400, height: groupNode.style?.height as number || 300 }
    };
  }

  // Debug logging to verify all child nodes are being considered
  // Debug: Calculate bounds for group with child nodes

  // Calculate absolute positions of child nodes with proper dimensions
  const childAbsolutePositions = childNodes.map(child => ({
    x: groupNode.position.x + child.position.x,
    y: groupNode.position.y + child.position.y,
    width: child.type === 'step' ? 280 : 200, // step node width : tool node width
    height: child.type === 'step' ? 140 : 100, // step node height : tool node height
  }));

  const padding = 60; // Consistent padding
  const minX = Math.min(...childAbsolutePositions.map(pos => pos.x));
  const minY = Math.min(...childAbsolutePositions.map(pos => pos.y));
  const maxX = Math.max(...childAbsolutePositions.map(pos => pos.x + pos.width));
  const maxY = Math.max(...childAbsolutePositions.map(pos => pos.y + pos.height));

  // Calculate required bounds
  const requiredPosition = { x: minX - padding, y: minY - padding };

  // Current group bounds
  const currentPosition = groupNode.position;
  const currentSize = {
    width: groupNode.style?.width as number || 400,
    height: groupNode.style?.height as number || 300
  };

  // Calculate final bounds ensuring consistent padding on all sides
  // If we need to expand the group, ensure the padding is consistent
  const finalPosition = {
    x: Math.min(currentPosition.x, requiredPosition.x),
    y: Math.min(currentPosition.y, requiredPosition.y),
  };

  // Calculate the size based on the final position to ensure consistent padding
  const finalSize = {
    width: Math.max(currentSize.width, (maxX - finalPosition.x) + padding),
    height: Math.max(currentSize.height, (maxY - finalPosition.y) + padding),
  };

  // Calculate final bounds ensuring consistent padding
  return {
    position: finalPosition,
    size: finalSize
  };
};

// Define custom node types
const nodeTypes = {
  step: StepNode,
  tool: ToolNode,
  group: GroupNode,
};

// Define custom edge types
const edgeTypes = {
  route: RouteEdge,
  tool: ToolEdge,
};

const initialNodes: Node[] = [
  // General Knowledge Bot - Simple linear flow
  {
    id: 'greet',
    type: 'step',
    position: { x: 100, y: 100 },
    data: {
      step_id: 'greet',
      description: 'Greet the user warmly and introduce yourself as a general knowledge assistant. Present them with a list of available topics they can ask questions about: Science, History, Geography, Literature, Technology, Sports, Arts, Current Events. Ask them which topic they would like to explore and what specific question they have.',
      available_tools: [],
      routes: [
        { target: 'science', condition: 'User wants to ask about science topics' },
        { target: 'history', condition: 'User wants to ask about history topics' },
        { target: 'geography', condition: 'User wants to ask about geography topics' },
        { target: 'literature', condition: 'User wants to ask about literature topics' },
        { target: 'technology', condition: 'User wants to ask about technology topics' },
        { target: 'sports', condition: 'User wants to ask about sports topics' },
        { target: 'arts', condition: 'User wants to ask about arts topics' },
        { target: 'current_events', condition: 'User wants to ask about current events' },
        { target: 'end', condition: 'User wants to end the conversation' }
      ]
    },
  },
  {
    id: 'science',
    type: 'step',
    position: { x: 400, y: 50 },
    data: {
      step_id: 'science',
      description: 'Answer the user\'s science-related question thoroughly and clearly. Provide accurate information about physics, chemistry, biology, astronomy, or any other science topic. Use examples and analogies when helpful to explain complex concepts. After answering, ask if they have any more questions about science or if they\'d like to explore a different topic.',
      available_tools: [],
      routes: [
        { target: 'greet', condition: 'User asks about a different topic' },
        { target: 'end', condition: 'User wants to end the conversation' }
      ]
    },
  },
  {
    id: 'history',
    type: 'step',
    position: { x: 400, y: 150 },
    data: {
      step_id: 'history',
      description: 'Answer the user\'s history-related question with detailed and accurate information. Cover topics like world history, ancient civilizations, wars, historical figures, and important events. Provide context and explain the significance of historical events or figures. After answering, ask if they have any more questions about history or if they\'d like to explore a different topic.',
      available_tools: [],
      routes: [
        { target: 'greet', condition: 'User asks about a different topic' },
        { target: 'end', condition: 'User wants to end the conversation' }
      ]
    },
  },
  {
    id: 'geography',
    type: 'step',
    position: { x: 400, y: 250 },
    data: {
      step_id: 'geography',
      description: 'Answer the user\'s geography-related question comprehensively. Cover topics like countries, capitals, landmarks, physical geography, climate, and cultural geography. Provide interesting facts and context about places and geographical features. After answering, ask if they have any more questions about geography or if they\'d like to explore a different topic.',
      available_tools: [],
      routes: [
        { target: 'greet', condition: 'User asks about a different topic' },
        { target: 'end', condition: 'User wants to end the conversation' }
      ]
    },
  },
  {
    id: 'literature',
    type: 'step',
    position: { x: 700, y: 50 },
    data: {
      step_id: 'literature',
      description: 'Answer the user\'s literature-related question with depth and insight. Cover topics like famous authors, classic and modern books, poetry, literary movements, and analysis. Provide recommendations and explain the significance of literary works. After answering, ask if they have any more questions about literature or if they\'d like to explore a different topic.',
      available_tools: [],
      routes: [
        { target: 'greet', condition: 'User asks about a different topic' },
        { target: 'end', condition: 'User wants to end the conversation' }
      ]
    },
  },
  {
    id: 'technology',
    type: 'step',
    position: { x: 700, y: 150 },
    data: {
      step_id: 'technology',
      description: 'Answer the user\'s technology-related question clearly and accurately. Cover topics like computers, internet, software, hardware, innovations, gadgets, and emerging technologies. Explain technical concepts in an accessible way and discuss the impact of technology on society. After answering, ask if they have any more questions about technology or if they\'d like to explore a different topic.',
      available_tools: [],
      routes: [
        { target: 'greet', condition: 'User asks about a different topic' },
        { target: 'end', condition: 'User wants to end the conversation' }
      ]
    },
  },
  {
    id: 'sports',
    type: 'step',
    position: { x: 700, y: 250 },
    data: {
      step_id: 'sports',
      description: 'Answer the user\'s sports-related question with enthusiasm and detailed information. Cover topics like Olympic Games, football, basketball, tennis, soccer, and other sports. Provide statistics, historical context, and interesting facts about athletes and sporting events. After answering, ask if they have any more questions about sports or if they\'d like to explore a different topic.',
      available_tools: [],
      routes: [
        { target: 'greet', condition: 'User asks about a different topic' },
        { target: 'end', condition: 'User wants to end the conversation' }
      ]
    },
  },
  {
    id: 'arts',
    type: 'step',
    position: { x: 1000, y: 50 },
    data: {
      step_id: 'arts',
      description: 'Answer the user\'s arts-related question with appreciation and detailed knowledge. Cover topics like painting, sculpture, music, theater, architecture, and famous artists. Provide context about artistic movements, techniques, and the cultural significance of artworks. After answering, ask if they have any more questions about arts or if they\'d like to explore a different topic.',
      available_tools: [],
      routes: [
        { target: 'greet', condition: 'User asks about a different topic' },
        { target: 'end', condition: 'User wants to end the conversation' }
      ]
    },
  },
  {
    id: 'current_events',
    type: 'step',
    position: { x: 1000, y: 150 },
    data: {
      step_id: 'current_events',
      description: 'Answer the user\'s questions about current events and recent developments. Cover topics like recent news, global trends, political events, social issues, and cultural phenomena. Provide balanced and factual information while being mindful of different perspectives. After answering, ask if they have any more questions about current events or if they\'d like to explore a different topic.',
      available_tools: [],
      routes: [
        { target: 'greet', condition: 'User asks about a different topic' },
        { target: 'end', condition: 'User wants to end the conversation' }
      ]
    },
  },
  {
    id: 'end',
    type: 'step',
    position: { x: 1000, y: 250 },
    data: {
      step_id: 'end',
      description: 'Thank the user for their curiosity and interest in learning. Encourage them to keep exploring and learning new things. Let them know they can return anytime with more questions. End the conversation on a positive and encouraging note.',
      available_tools: [],
      routes: []
    },
  },
];

const initialEdges: Edge[] = [
  // Route edges from greet to all topic steps
  {
    id: 'greet-science',
    source: 'greet',
    target: 'science',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to ask about science topics' },
  },
  {
    id: 'greet-history',
    source: 'greet',
    target: 'history',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to ask about history topics' },
  },
  {
    id: 'greet-geography',
    source: 'greet',
    target: 'geography',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to ask about geography topics' },
  },
  {
    id: 'greet-literature',
    source: 'greet',
    target: 'literature',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to ask about literature topics' },
  },
  {
    id: 'greet-technology',
    source: 'greet',
    target: 'technology',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to ask about technology topics' },
  },
  {
    id: 'greet-sports',
    source: 'greet',
    target: 'sports',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to ask about sports topics' },
  },
  {
    id: 'greet-arts',
    source: 'greet',
    target: 'arts',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to ask about arts topics' },
  },
  {
    id: 'greet-current_events',
    source: 'greet',
    target: 'current_events',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to ask about current events' },
  },
  {
    id: 'greet-end',
    source: 'greet',
    target: 'end',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to end the conversation' },
  },

  // Route edges from topic steps back to greet or to end
  {
    id: 'science-greet',
    source: 'science',
    target: 'greet',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User asks about a different topic' },
  },
  {
    id: 'science-end',
    source: 'science',
    target: 'end',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to end the conversation' },
  },
  {
    id: 'history-greet',
    source: 'history',
    target: 'greet',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User asks about a different topic' },
  },
  {
    id: 'history-end',
    source: 'history',
    target: 'end',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to end the conversation' },
  },
  {
    id: 'geography-greet',
    source: 'geography',
    target: 'greet',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User asks about a different topic' },
  },
  {
    id: 'geography-end',
    source: 'geography',
    target: 'end',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to end the conversation' },
  },
  {
    id: 'literature-greet',
    source: 'literature',
    target: 'greet',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User asks about a different topic' },
  },
  {
    id: 'literature-end',
    source: 'literature',
    target: 'end',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to end the conversation' },
  },
  {
    id: 'technology-greet',
    source: 'technology',
    target: 'greet',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User asks about a different topic' },
  },
  {
    id: 'technology-end',
    source: 'technology',
    target: 'end',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to end the conversation' },
  },
  {
    id: 'sports-greet',
    source: 'sports',
    target: 'greet',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User asks about a different topic' },
  },
  {
    id: 'sports-end',
    source: 'sports',
    target: 'end',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to end the conversation' },
  },
  {
    id: 'arts-greet',
    source: 'arts',
    target: 'greet',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User asks about a different topic' },
  },
  {
    id: 'arts-end',
    source: 'arts',
    target: 'end',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to end the conversation' },
  },
  {
    id: 'current_events-greet',
    source: 'current_events',
    target: 'greet',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User asks about a different topic' },
  },
  {
    id: 'current_events-end',
    source: 'current_events',
    target: 'end',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to end the conversation' },
  },
];

interface FlowBuilderProps {
  onPreview?: (nodes: Node[], edges: Edge[], agent: string, persona: string) => void;
  onSaveConfig?: (nodes: Node[], edges: Edge[], agent: string, persona: string) => void;
  highlightedNodeId?: string | null;
}

export default function FlowBuilder({ onPreview, onSaveConfig, highlightedNodeId }: FlowBuilderProps) {
  const [nodes, setNodes, onNodesChangeBase] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [filteredNodeIds, setFilteredNodeIds] = useState<string[] | null>(null);
  const [editingFlowGroup, setEditingFlowGroup] = useState<{
    id: string;
    data: FlowGroupData;
  } | null>(null);
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [showImportDialog, setShowImportDialog] = useState(false);
  const [agentName, setAgentName] = useState('general_knowledge_bot');
  const [persona, setPersona] = useState('You are a friendly and knowledgeable general knowledge assistant. You have extensive knowledge across various topics including science, history, geography, literature, technology, sports, arts, and current events. You explain concepts clearly and provide accurate, helpful information. You\'re enthusiastic about learning and sharing knowledge, and you encourage curiosity and further exploration of topics.');
  const [contextMenu, setContextMenu] = useState<{
    x?: number;
    y?: number;
    nodeId?: string;
    nodeType?: string;
    edgeId?: string;
    visible?: boolean;
  }>({});
  const [editTrigger, setEditTrigger] = useState<{
    nodeId: string;
    nodeType: 'step' | 'tool';
    nodeData: StepNodeData | ToolNodeData;
  } | null>(null);

  const reactFlowWrapper = useRef<HTMLDivElement>(null);

  // Initialize undo/redo system
  const {
    undo,
    redo,
    canUndo,
    canRedo,
    saveState,
  } = useUndoRedo(initialNodes, initialEdges, {
    maxHistorySize: 50,
    saveDescription: true,
  });

  // Undo handler that integrates with React Flow state
  const handleUndo = useCallback(() => {
    const result = undo(nodes, edges);
    if (result) {
      setNodes(result.nodes);
      setEdges(result.edges);
    }
  }, [undo, nodes, edges, setNodes, setEdges]);

  // Redo handler that integrates with React Flow state
  const handleRedo = useCallback(() => {
    const result = redo(nodes, edges);
    if (result) {
      setNodes(result.nodes);
      setEdges(result.edges);
    }
  }, [redo, nodes, edges, setNodes, setEdges]);

  // Enhanced state setters that save undo states
  const setNodesWithUndo = useCallback((nodesOrFn: Node[] | ((prev: Node[]) => Node[]), description?: string) => {
    const prevNodes = nodes;
    const prevEdges = edges;

    // Save state before change
    saveState(prevNodes, prevEdges, description);

    // Apply the change
    if (typeof nodesOrFn === 'function') {
      setNodes(nodesOrFn);
    } else {
      setNodes(nodesOrFn);
    }
  }, [nodes, edges, saveState, setNodes]);

  const setEdgesWithUndo = useCallback((edgesOrFn: Edge[] | ((prev: Edge[]) => Edge[]), description?: string) => {
    const prevNodes = nodes;
    const prevEdges = edges;

    // Save state before change
    saveState(prevNodes, prevEdges, description);

    // Apply the change
    if (typeof edgesOrFn === 'function') {
      setEdges(edgesOrFn);
    } else {
      setEdges(edgesOrFn);
    }
  }, [nodes, edges, saveState, setEdges]);

  // Bulk operations handlers
  const handleBulkDelete = useCallback(() => {
    const selectedNodeIds = nodes.filter(node => node.selected).map(node => node.id);
    if (selectedNodeIds.length === 0) return;

    const result = bulkDeleteNodes({
      selectedNodeIds,
      nodes,
      edges,
    });

    setNodesWithUndo(result.nodes, `Delete ${selectedNodeIds.length} nodes`);
    setEdges(result.edges);
  }, [nodes, edges, setNodesWithUndo, setEdges]);

  const handleBulkDuplicate = useCallback(() => {
    const selectedNodeIds = nodes.filter(node => node.selected).map(node => node.id);
    if (selectedNodeIds.length === 0) return;

    const result = bulkDuplicateNodes({
      selectedNodeIds,
      nodes,
      edges,
    });

    setNodesWithUndo(result.nodes, `Duplicate ${selectedNodeIds.length} nodes`);
    setEdges(result.edges);
  }, [nodes, edges, setNodesWithUndo, setEdges]);

  const handleBulkGroup = useCallback(() => {
    const selectedNodeIds = nodes.filter(node => node.selected).map(node => node.id);
    const result = bulkGroupNodes({
      selectedNodeIds,
      nodes,
      edges,
    });

    if (result.nodes !== nodes) {
      setNodesWithUndo(result.nodes, `Group ${selectedNodeIds.length} nodes into flow`);
    }
  }, [nodes, edges, setNodesWithUndo]);

  const handleDetachNode = useCallback((nodeId: string, detachType: 'all' | 'tools' | 'steps' = 'all') => {
    const result = detachNode({
      nodeId,
      nodes,
      edges,
      detachType,
    });

    setEdges(result.edges);
  }, [nodes, edges, setEdges]);

  // Export/Import handlers
  const handleExportYaml = useCallback(() => {
    setShowExportDialog(true);
  }, []);

  const handleImportYaml = useCallback(() => {
    setShowImportDialog(true);
  }, []);

  const handleNewConfig = useCallback(() => {
    // Clear current flow and reset to empty state
    setNodesWithUndo([], 'New configuration');
    setEdges([]);
    setAgentName('my-agent');
    setPersona('A helpful assistant');
  }, [setNodesWithUndo, setEdges]);

  const handleImportFlow = useCallback((mergeResult: any) => {
    // Add imported nodes alongside existing ones using merge import
    setNodesWithUndo([...nodes, ...mergeResult.nodes], 'Merge import YAML configuration');
    setEdges([...edges, ...mergeResult.edges]);

    // Update agent configuration if provided
    if (mergeResult.config.name) setAgentName(mergeResult.config.name);
    if (mergeResult.config.persona) setPersona(mergeResult.config.persona);
  }, [nodes, edges, setNodesWithUndo, setEdges]);

  const handleAgentConfigChange = useCallback((name: string, newPersona: string) => {
    setAgentName(name);
    setPersona(newPersona);
  }, []);

  const handlePreview = useCallback(() => {
    if (onPreview) onPreview(nodes, edges, agentName, persona);
  }, [onPreview, nodes, edges, agentName, persona]);

  const handleSaveConfig = useCallback(() => {
    if (onSaveConfig) onSaveConfig(nodes, edges, agentName, persona);
  }, [onSaveConfig, nodes, edges, agentName, persona]);


  // Custom onNodesChange handler that auto-resizes groups when children move
  const onNodesChange = useCallback((changes: any[]) => {
    onNodesChangeBase(changes);

    // Check if any changes involve moving nodes that are children of groups
    const moveChanges = changes.filter(change => change.type === 'position' && change.position);

    if (moveChanges.length > 0) {
      // Use setTimeout to update group sizes after the position changes are applied
      setTimeout(() => {
        setNodes(currentNodes => {
          const updatedNodes = [...currentNodes];
          const groupNodes = updatedNodes.filter(node => node.type === 'group');

          groupNodes.forEach(groupNode => {
            const childNodes = updatedNodes.filter(node => node.parentId === groupNode.id);
            if (childNodes.length > 0) {
              const bounds = calculateGroupBounds(groupNode, childNodes);

              // Update group size and position if they changed significantly
              const currentWidth = groupNode.style?.width as number || 0;
              const currentHeight = groupNode.style?.height as number || 0;
              const currentX = groupNode.position.x;
              const currentY = groupNode.position.y;

              const sizeChanged = Math.abs(bounds.size.width - currentWidth) > 10 ||
                                Math.abs(bounds.size.height - currentHeight) > 10;
              const positionChanged = Math.abs(bounds.position.x - currentX) > 5 ||
                                    Math.abs(bounds.position.y - currentY) > 5;

              if (sizeChanged || positionChanged) {
                const groupIndex = updatedNodes.findIndex(n => n.id === groupNode.id);
                if (groupIndex !== -1) {
                  // Calculate the position delta to adjust child nodes
                  const deltaX = bounds.position.x - currentX;
                  const deltaY = bounds.position.y - currentY;

                  // Update group node
                  updatedNodes[groupIndex] = {
                    ...groupNode,
                    position: bounds.position,
                    style: {
                      ...groupNode.style,
                      width: bounds.size.width,
                      height: bounds.size.height,
                    },
                  };

                  // Adjust child node positions if group position changed
                  if (deltaX !== 0 || deltaY !== 0) {
                    childNodes.forEach(childNode => {
                      const childIndex = updatedNodes.findIndex(n => n.id === childNode.id);
                      if (childIndex !== -1) {
                        updatedNodes[childIndex] = {
                          ...childNode,
                          position: {
                            x: childNode.position.x - deltaX,
                            y: childNode.position.y - deltaY,
                          },
                        };
                      }
                    });
                  }
                }
              }
            }
          });

          return updatedNodes;
        });
      }, 0);
    }
  }, [onNodesChangeBase, setNodes]);

  // Auto-arrange on startup - only run once when component mounts with initial data
  useEffect(() => {
    // Only run if we have initial data and haven't arranged yet
    if (nodes.length > 0 && edges.length > 0) {
      const arrangedNodes = autoArrangeNodes(nodes, edges);
      setNodes(arrangedNodes);
    }
  }, []); // Empty dependency array - only run once on mount

  // Keyboard shortcuts for undo/redo
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Check for Cmd+Z (undo) or Ctrl+Z (undo)
      if ((event.metaKey || event.ctrlKey) && event.key === 'z' && !event.shiftKey) {
        event.preventDefault();
        handleUndo();
      }
      // Check for Cmd+Shift+Z (redo) or Ctrl+Shift+Z (redo) or Ctrl+Y (redo)
      else if (
        ((event.metaKey || event.ctrlKey) && event.key === 'z' && event.shiftKey) ||
        (event.ctrlKey && event.key === 'y')
      ) {
        event.preventDefault();
        handleRedo();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [handleUndo, handleRedo]);

  // Handle node highlighting from chat
  useEffect(() => {
    if (highlightedNodeId) {
      // Add highlighting to nodes without affecting layout
      setNodes((currentNodes) =>
        currentNodes.map((node) => ({
          ...node,
          className: node.id === highlightedNodeId ||
                     (node.data?.step_id === highlightedNodeId) ||
                     (node.data?.flow_id === highlightedNodeId)
                     ? 'highlighted-node'
                     : undefined,
          style: {
            ...node.style,
            ...(node.id === highlightedNodeId ||
                (node.data?.step_id === highlightedNodeId) ||
                (node.data?.flow_id === highlightedNodeId)
              ? {
                  boxShadow: '0 0 20px rgba(59, 130, 246, 0.8)',
                  outline: '3px solid rgba(59, 130, 246, 0.6)',
                  outlineOffset: '2px'
                }
              : {
                  boxShadow: undefined,
                  outline: undefined,
                  outlineOffset: undefined
                })
          }
        }))
      );
    } else {
      // Remove highlighting from all nodes
      setNodes((currentNodes) =>
        currentNodes.map((node) => ({
          ...node,
          className: undefined,
          style: {
            ...node.style,
            boxShadow: undefined,
            outline: undefined,
            outlineOffset: undefined
          }
        }))
      );
    }
  }, [highlightedNodeId, setNodes]);

  // Context menu handlers
  const handleNodeContextMenu = useCallback((event: React.MouseEvent, node: Node) => {
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      nodeId: node.id,
      nodeType: node.type,
      visible: true,
    });
  }, []);

  const handleEdgeContextMenu = useCallback((event: React.MouseEvent, edge: Edge) => {
    event.preventDefault();
    event.stopPropagation();
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      edgeId: edge.id,
      visible: true,
    });
  }, []);

  const handlePaneContextMenu = useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    setContextMenu({
      x: event.clientX,
      y: event.clientY,
      visible: true,
    });
  }, []);

  const clearContextMenu = useCallback(() => {
    setContextMenu({ visible: false });
  }, []);

  // Auto arrange handler
  const handleAutoArrange = useCallback(() => {
    const arrangedNodes = autoArrangeNodes(nodes, edges);

    // The autoArrangeNodes function now handles group optimization internally,
    // so we can directly set the arranged nodes
    setNodesWithUndo(arrangedNodes, 'Auto-arrange nodes');
  }, [nodes, edges, setNodesWithUndo]);

  const isValidConnection = useCallback((connection: any) => {
    const { source, target, sourceHandle, targetHandle } = connection;

    // Prevent self-connections
    if (source === target) return false;

    // Prevent duplicate connections
    const existingConnection = edges.find(
      (edge) => edge.source === source && edge.target === target &&
                edge.sourceHandle === sourceHandle && edge.targetHandle === targetHandle
    );
    if (existingConnection) return false;

    // Validate connection types
    if (sourceHandle === 'step-output' && targetHandle === 'step-input') {
      return true; // Step to step connection
    }
    if (sourceHandle === 'tool-output' && targetHandle === 'tool-input') {
      return true; // Step to tool connection
    }

    // Invalid connection type
    return false;
  }, [edges]);

  const onConnect: OnConnect = useCallback(
    (params) => {
      // Validate connection before creating edge
      if (!isValidConnection(params)) {
        return;
      }

      let edgeType: string;
      let edgeData: any = {};

      // Determine edge type based on source and target handles
      if (params.sourceHandle === 'step-output' && params.targetHandle === 'step-input') {
        edgeType = 'route';
        edgeData = { condition: 'Add condition...' };
      } else if (params.sourceHandle === 'tool-output' && params.targetHandle === 'tool-input') {
        edgeType = 'tool';
      } else {
        // Default fallback
        edgeType = 'route';
      }

      setEdges((eds) => addEdge({
        ...params,
        type: edgeType,
        data: edgeData,
      }, eds));
    },
    [setEdges, isValidConnection]
  );

  const handleUpdateNode = useCallback((nodeId: string, data: Partial<StepNodeData | ToolNodeData>) => {
    setNodes((nds) =>
      nds.map((node) =>
        node.id === nodeId
          ? { ...node, data: { ...node.data, ...data } }
          : node
      )
    );
  }, [setNodes]);

  const handleUpdateFlow = useCallback((flowId: string, data: Partial<FlowGroupData>) => {
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === flowId && node.type === 'group') {
          // Update group node data and visual properties
          const updatedNode = {
            ...node,
            data: { ...node.data, ...data },
          };

          // Update visual properties if provided
          if (data.color) {
            updatedNode.style = {
              ...node.style,
              backgroundColor: `${data.color}0D`, // 5% opacity
              border: `2px dashed ${data.color}4D`, // 30% opacity
            };
          }

          return updatedNode;
        }
        return node;
      })
    );
  }, [setNodes]);

  const handleNodeDoubleClick = useCallback((_event: React.MouseEvent, node: Node) => {
    if (node.type === 'group') {
      // Create FlowGroupData from group node
      const nodeData = node.data as any;
      const flowGroupData: FlowGroupData = {
        flow_id: nodeData.flow_id || node.id,
        description: nodeData.description || '',
        enters: nodeData.enters || [],
        exits: nodeData.exits || [],
        nodeIds: nodes.filter(n => n.parentId === node.id).map(n => n.id),
        components: nodeData.components || {},
        metadata: nodeData.metadata || {},
        color: nodeData.color || '#3B82F6',
        position: node.position,
        size: {
          width: node.style?.width as number || 400,
          height: node.style?.height as number || 300,
        },
      };

      setEditingFlowGroup({
        id: node.id,
        data: flowGroupData,
      });
    }
  }, [nodes]);

  const createFlowGroup = useCallback((selectedNodeIds: string[]) => {
    if (selectedNodeIds.length === 0) return;

    const selectedNodes = nodes.filter(node => selectedNodeIds.includes(node.id));

    // Filter for step nodes only - tools cannot be grouped
    const stepNodes = selectedNodes.filter(node => node.type === 'step');

    if (stepNodes.length < 2) {
      console.warn('Flow groups can only contain step nodes. At least 2 step nodes are required.');
      return;
    }

    const flowId = `flow_${Date.now()}`;
    const stepNodeIds = stepNodes.map(node => node.id);

    // Calculate bounding box for the group
    const padding = 60; // Padding around the nodes
    const minX = Math.min(...stepNodes.map(n => n.position.x));
    const minY = Math.min(...stepNodes.map(n => n.position.y));
    const maxX = Math.max(...stepNodes.map(n => n.position.x + 280)); // step node width
    const maxY = Math.max(...stepNodes.map(n => n.position.y + 140)); // step node height

    // Group position and size
    const groupPosition = { x: minX - padding, y: minY - padding };
    const groupSize = {
      width: (maxX - minX) + (padding * 2),
      height: (maxY - minY) + (padding * 2)
    };

    // Create group node
    const groupNode: Node = {
      id: flowId,
      type: 'group',
      position: groupPosition,
      style: {
        width: groupSize.width,
        height: groupSize.height,
        backgroundColor: 'rgba(59, 130, 246, 0.05)',
        border: '2px dashed rgba(59, 130, 246, 0.3)',
        borderRadius: 8,
      },
      data: {
        label: `Flow Group (${stepNodes.length} steps)`,
        flow_id: flowId,
        description: '',
        enters: [],
        exits: [],
        nodeIds: stepNodeIds,
        components: {},
        metadata: {},
        color: '#3B82F6',
      },
      zIndex: -1, // Ensure group node is rendered behind children
      selectable: true, // Allow selection for ungrouping
      draggable: true, // Allow dragging the entire group
    };

    // Update child nodes to be relative to parent
    const updatedNodes = nodes.map(node => {
      if (stepNodeIds.includes(node.id)) {
        return {
          ...node,
          parentId: flowId,
          extent: 'parent' as const,
          position: {
            x: node.position.x - groupPosition.x,
            y: node.position.y - groupPosition.y,
          },
        };
      }
      return node;
    });

    // Add group node FIRST, then updated children (order is crucial for React Flow)
    setNodesWithUndo([groupNode, ...updatedNodes], `Create flow group with ${stepNodes.length} steps`);

    // Deselect nodes after grouping
    setNodes(nds => nds.map(node => ({ ...node, selected: false })));
  }, [nodes, setNodes]);

  const handleUngroupFlow = useCallback(() => {
    const selectedGroupNodes = nodes.filter(node => node.selected && node.type === 'group');

    if (selectedGroupNodes.length === 0) {
      return;
    }

    selectedGroupNodes.forEach(groupNode => {
      // Find all child nodes of this group
      const childNodes = nodes.filter(node => node.parentId === groupNode.id);

      // Update child nodes to have absolute positions and remove parent relationship
      const updatedChildNodes = childNodes.map(childNode => ({
        ...childNode,
        parentId: undefined,
        extent: undefined,
        position: {
          x: groupNode.position.x + childNode.position.x,
          y: groupNode.position.y + childNode.position.y,
        },
      }));

      // Remove group node and update children
      setNodesWithUndo(
        nds =>
          nds.filter(node => node.id !== groupNode.id)
             .map(node => {
               const updatedChild = updatedChildNodes.find(child => child.id === node.id);
               return updatedChild || node;
             }),
        `Ungroup flow ${groupNode.id}`
      );
    });
  }, [nodes, setNodes]);
  const handleCreateFlowGroup = useCallback(() => {
    const selectedNodes = nodes.filter(node => node.selected);
    const selectedStepNodes = selectedNodes.filter(node => node.type === 'step');

    if (selectedStepNodes.length >= 2) {
      createFlowGroup(selectedStepNodes.map(node => node.id));
    }
  }, [nodes, createFlowGroup]);

  const handleSaveFlowGroup = useCallback((data: FlowGroupData) => {
    if (editingFlowGroup) {
      handleUpdateFlow(editingFlowGroup.id, data);
      setEditingFlowGroup(null);
    }
  }, [editingFlowGroup, handleUpdateFlow]);

  const handleCloseFlowGroupDialog = useCallback(() => {
    setEditingFlowGroup(null);
  }, []);

  // Get count of selected step nodes (only step nodes can be grouped)
  const selectedStepNodesCount = nodes.filter(node => node.selected && node.type === 'step').length;

  const addStepNode = useCallback(() => {
    const id = `step-${Date.now()}`;
    // Default position when adding from context menu
    const position = {
      x: 100 + (nodes.length % 5) * 300, // Spread new nodes horizontally
      y: 100 + Math.floor(nodes.length / 5) * 200, // Stack vertically after 5 nodes
    };

    const newNode: Node = {
      id,
      type: 'step',
      position,
      data: {
        step_id: `step_${nodes.length + 1}`,
        description: 'New step description',
        available_tools: [],
        routes: [],
      },
    };

    setNodesWithUndo([...nodes, newNode], 'Add step node');
  }, [nodes, setNodesWithUndo]);

  const addToolNode = useCallback(() => {
    const id = `tool-${Date.now()}`;
    // Default position when adding from context menu
    const position = {
      x: 200 + (nodes.length % 5) * 300, // Offset tools slightly from steps
      y: 150 + Math.floor(nodes.length / 5) * 200,
    };

    const newNode: Node = {
      id,
      type: 'tool',
      position,
      data: {
        name: `tool_${nodes.length + 1}`,
        description: 'New tool description',
        parameters: {},
      },
    };

    setNodesWithUndo([...nodes, newNode], 'Add tool node');
  }, [nodes, setNodesWithUndo]);

  const deleteNode = useCallback(() => {
    if (contextMenu.nodeId) {
      setNodesWithUndo(
        nodes.filter((node) => node.id !== contextMenu.nodeId),
        'Delete node'
      );
      setEdgesWithUndo(
        edges.filter((edge) =>
          edge.source !== contextMenu.nodeId && edge.target !== contextMenu.nodeId
        ),
        'Delete node edges'
      );
    }
  }, [contextMenu.nodeId, nodes, edges, setNodesWithUndo, setEdgesWithUndo]);

  const deleteEdge = useCallback(() => {
    if (contextMenu.edgeId) {
      setEdgesWithUndo(
        edges.filter((edge) => edge.id !== contextMenu.edgeId),
        'Delete edge'
      );
    }
  }, [contextMenu.edgeId, edges, setEdgesWithUndo]);

  const editNode = useCallback(() => {
    if (contextMenu.nodeId && contextMenu.nodeType) {
      const node = nodes.find(n => n.id === contextMenu.nodeId);
      if (node) {
        if (node.type === 'group') {
          // Handle group node editing
          handleNodeDoubleClick(null as any, node);
        } else if (node.type === 'step' || node.type === 'tool') {
          // For step/tool nodes, set edit trigger state
          setEditTrigger({
            nodeId: node.id,
            nodeType: node.type as 'step' | 'tool',
            nodeData: node.data
          });
        }
      }
    }
  }, [contextMenu.nodeId, contextMenu.nodeType, nodes, handleNodeDoubleClick]);

  const copyNode = useCallback(() => {
    if (contextMenu.nodeId) {
      const node = nodes.find(n => n.id === contextMenu.nodeId);
      if (node) {
        copyNodeToClipboard(node);
      }
    }
  }, [contextMenu.nodeId, nodes]);

  // Search and filter handlers
  const handleFilter = useCallback((nodeIds: string[]) => {
    setFilteredNodeIds(nodeIds);
  }, []);

  const handleClearFilter = useCallback(() => {
    setFilteredNodeIds(null);
  }, []);

  // Get visible nodes based on filter
  const visibleNodes = filteredNodeIds
    ? nodes.map(node => ({
        ...node,
        hidden: !filteredNodeIds.includes(node.id)
      }))
    : nodes;

  const pasteNode = useCallback(() => {
    const clipboardData = getClipboardData();
    if (clipboardData && clipboardData.type === 'node') {
      const originalNode = clipboardData.data as Node;
      // Default position when pasting from context menu
      const position = {
        x: 300 + (nodes.length % 5) * 300,
        y: 200 + Math.floor(nodes.length / 5) * 200,
      };

      const newNode = cloneNodeWithNewId(originalNode);
      newNode.position = position;

      setNodesWithUndo([...nodes, newNode], 'Paste node');
    }
  }, [nodes, setNodesWithUndo]);

  return (
    <FlowProvider
      nodes={nodes}
      edges={edges}
      onUpdateNode={handleUpdateNode}
      onUpdateFlow={handleUpdateFlow}
    >
      <div className="h-full w-full relative">
        {/* Flow Builder */}
        <div className="h-full w-full" ref={reactFlowWrapper}>
          {/* Top Toolbar */}
          <div className="absolute top-4 left-4 right-4 z-10 flex justify-center">
            <Toolbar
              onAutoArrange={handleAutoArrange}
              onCreateFlowGroup={handleCreateFlowGroup}
              onUngroupFlow={handleUngroupFlow}
              selectedNodesCount={selectedStepNodesCount}
              onUndo={handleUndo}
              onRedo={handleRedo}
              canUndo={canUndo}
              canRedo={canRedo}
              onBulkDelete={handleBulkDelete}
              onBulkDuplicate={handleBulkDuplicate}
              onBulkGroup={handleBulkGroup}
              onExportYaml={handleExportYaml}
              onImportYaml={handleImportYaml}
              onNewConfig={handleNewConfig}
              onSaveConfig={handleSaveConfig}
              onPreview={handlePreview}
            />
          </div>

          {/* Floating Search Filter */}
          <div className="absolute top-4 right-4 z-10">
            <SearchFilter
              nodes={nodes}
              onFilter={handleFilter}
              onClearFilter={handleClearFilter}
            />
          </div>

          <ReactFlow
            nodes={visibleNodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeContextMenu={handleNodeContextMenu}
            onEdgeContextMenu={handleEdgeContextMenu}
            onPaneContextMenu={handlePaneContextMenu}
            onNodeDoubleClick={handleNodeDoubleClick}
            isValidConnection={isValidConnection}
            nodeTypes={nodeTypes}
            edgeTypes={edgeTypes}
            minZoom={0.3}
            maxZoom={1.0}
            defaultViewport={{ x: 0, y: 0, zoom: 0.6 }}
            snapToGrid={true}
            snapGrid={[20, 20]}
            fitView
            fitViewOptions={{ padding: 0.2, maxZoom: 0.8 }}
            multiSelectionKeyCode={["Meta", "Control"]}
            selectionKeyCode={null}
            deleteKeyCode={["Delete", "Backspace"]}
            selectNodesOnDrag={false}
          >
          <Background
            gap={20}
            color="#374151"
            style={{ backgroundColor: 'var(--background)' }}
            className=""
          />
          <Controls />

          {/* Arrow marker definition */}
          <svg style={{ position: 'absolute', top: 0, left: 0 }}>
            <defs>
              <marker
                id="arrow-marker"
                markerWidth="10"
                markerHeight="10"
                refX="9"
                refY="3"
                orient="auto"
                markerUnits="strokeWidth"
              >
                <path
                  d="M0,0 L0,6 L9,3 z"
                  fill="#374151"
                  className="dark:fill-gray-300"
                />
              </marker>
            </defs>
          </svg>
        </ReactFlow>

        {/* Custom Context Menu */}
        <CustomContextMenu
          x={contextMenu.x || 0}
          y={contextMenu.y || 0}
          visible={!!contextMenu.visible}
          onClose={clearContextMenu}
          onAddStepNode={addStepNode}
          onAddToolNode={addToolNode}
          onEdit={contextMenu.nodeId ? editNode : undefined}
          onCopy={contextMenu.nodeId ? copyNode : undefined}
          onPaste={hasClipboardData() ? pasteNode : undefined}
          onDelete={contextMenu.nodeId ? deleteNode : contextMenu.edgeId ? deleteEdge : undefined}
          onDetach={contextMenu.nodeId ? (type) => handleDetachNode(contextMenu.nodeId!, type) : undefined}
          isOnNode={!!contextMenu.nodeId}
          isOnEdge={!!contextMenu.edgeId}
          nodeType={contextMenu.nodeType}
        />

        <NodeEditDialogs />
        <EditTrigger editTrigger={editTrigger} setEditTrigger={setEditTrigger} />

        {editingFlowGroup && (
          <FlowGroupEditDialog
            open={true}
            onClose={handleCloseFlowGroupDialog}
            onSave={handleSaveFlowGroup}
            flowData={editingFlowGroup.data as FlowGroupData}
            availableStepIds={nodes.filter(node => node.type === 'step').map(node => node.id)}
          />
        )}

        <ExportDialog
          open={showExportDialog}
          onClose={() => setShowExportDialog(false)}
          nodes={nodes}
          edges={edges}
          agentName={agentName}
          persona={persona}
        />

        <ImportDialog
          open={showImportDialog}
          onClose={() => setShowImportDialog(false)}
          nodes={nodes}
          edges={edges}
          onImport={handleImportFlow}
          onAgentConfigChange={handleAgentConfigChange}
        />

        <KeyboardShortcuts />
        </div>
      </div>
    </FlowProvider>
  );
}
