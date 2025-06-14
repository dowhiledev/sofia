import { useCallback, useState, useRef, useEffect } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  useNodesState,
  useEdgesState,
  addEdge,
  useReactFlow,
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
import { ContextMenu } from './context-menu/ContextMenu';
import { FlowProvider } from '../context/FlowContext';
import { NodeEditDialogs } from './dialogs/NodeEditDialogs';
import { FlowGroupEditDialog } from './dialogs/FlowGroupEditDialog';
import { ExportImportDialog } from './dialogs/ExportImportDialog';
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
import type { StepNodeData, ToolNodeData, FlowGroupData } from '../types';

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
  // Ungrouped step nodes
  {
    id: 'start',
    type: 'step',
    position: { x: 100, y: 100 },
    data: {
      step_id: 'start',
      description: 'Greet the customer and ask how can I help them.',
      available_tools: ['get_available_coffee_options'],
      routes: [
        {
          target: 'take_coffee_order',
          condition: 'Customer is ready to place a new order'
        }
      ]
    },
  },
  {
    id: 'finalize_order',
    type: 'step',
    position: { x: 800, y: 100 },
    data: {
      step_id: 'finalize_order',
      description: 'Confirm order details and process payment.',
      available_tools: ['process_payment', 'send_receipt'],
      routes: [
        {
          target: 'end',
          condition: 'Payment successful'
        }
      ]
    },
  },
  {
    id: 'end',
    type: 'step',
    position: { x: 1100, y: 100 },
    data: {
      step_id: 'end',
      description: 'Thank the customer and end the conversation.',
      available_tools: [],
      routes: []
    },
  },

  // Group 1: Order Management (will contain grouped step nodes)
  {
    id: 'group_order_management',
    type: 'group',
    position: { x: 300, y: 200 },
    style: {
      width: 500,
      height: 300,
      backgroundColor: 'rgba(59, 130, 246, 0.05)',
      border: '2px dashed rgba(59, 130, 246, 0.3)',
      borderRadius: 8,
    },
    data: {
      label: 'Order Management Flow',
      flow_id: 'group_order_management',
      description: 'Handles customer order taking and modifications',
      enters: [],
      exits: [],
      nodeIds: ['take_coffee_order', 'modify_order'],
      components: {},
      metadata: {},
      color: '#3B82F6',
    },
    zIndex: -1,
    selectable: true,
    draggable: true,
  },

  // Grouped step nodes (children of group_order_management)
  {
    id: 'take_coffee_order',
    type: 'step',
    parentId: 'group_order_management',
    extent: 'parent' as const,
    position: { x: 60, y: 60 },  // Relative to parent group
    data: {
      step_id: 'take_coffee_order',
      description: 'Ask the customer for their coffee preference and size.',
      available_tools: ['get_available_coffee_options', 'add_to_cart'],
      routes: [
        {
          target: 'modify_order',
          condition: 'Customer wants to modify order'
        },
        {
          target: 'finalize_order',
          condition: 'User wants to finalize the order'
        }
      ]
    },
  },
  {
    id: 'modify_order',
    type: 'step',
    parentId: 'group_order_management',
    extent: 'parent' as const,
    position: { x: 60, y: 180 },  // Relative to parent group
    data: {
      step_id: 'modify_order',
      description: 'Allow customer to modify their order (add/remove items).',
      available_tools: ['add_to_cart', 'remove_item', 'clear_cart'],
      routes: [
        {
          target: 'finalize_order',
          condition: 'Customer is satisfied with changes'
        }
      ]
    },
  },

  // Group 2: Customer Support (will contain grouped step nodes)
  {
    id: 'group_customer_support',
    type: 'group',
    position: { x: 100, y: 600 },
    style: {
      width: 400,
      height: 250,
      backgroundColor: 'rgba(34, 197, 94, 0.05)',
      border: '2px dashed rgba(34, 197, 94, 0.3)',
      borderRadius: 8,
    },
    data: {
      label: 'Customer Support Flow',
      flow_id: 'group_customer_support',
      description: 'Handles customer inquiries and complaints',
      enters: [],
      exits: [],
      nodeIds: ['handle_complaint', 'provide_info'],
      components: {},
      metadata: {},
      color: '#22C55E',
    },
    zIndex: -1,
    selectable: true,
    draggable: true,
  },

  // Grouped step nodes (children of group_customer_support)
  {
    id: 'handle_complaint',
    type: 'step',
    parentId: 'group_customer_support',
    extent: 'parent' as const,
    position: { x: 60, y: 60 },
    data: {
      step_id: 'handle_complaint',
      description: 'Listen to customer complaint and offer solutions.',
      available_tools: ['escalate_to_manager', 'offer_discount'],
      routes: [
        {
          target: 'provide_info',
          condition: 'Need to provide additional information'
        }
      ]
    },
  },
  {
    id: 'provide_info',
    type: 'step',
    parentId: 'group_customer_support',
    extent: 'parent' as const,
    position: { x: 60, y: 150 },
    data: {
      step_id: 'provide_info',
      description: 'Provide information about policies, hours, etc.',
      available_tools: ['get_store_hours', 'get_policies'],
      routes: []
    },
  },

  // Tool nodes (not grouped)
  {
    id: 'get_available_coffee_options',
    type: 'tool',
    position: { x: 50, y: 350 },
    data: {
      name: 'get_available_coffee_options',
      description: 'Gets the available coffee options',
      parameters: {},
    },
  },
  {
    id: 'add_to_cart',
    type: 'tool',
    position: { x: 250, y: 350 },
    data: {
      name: 'add_to_cart',
      description: 'Adds an item to the cart',
      parameters: {
        coffee_type: { type: 'string', description: 'Coffee type (e.g., Espresso, Latte)' },
        size: { type: 'string', description: 'Size of the coffee (Small, Medium, Large)' },
        price: { type: 'number', description: 'Price of the coffee' }
      },
    },
  },
  {
    id: 'remove_item',
    type: 'tool',
    position: { x: 450, y: 350 },
    data: {
      name: 'remove_item',
      description: 'Removes an item from the cart',
      parameters: {
        item_id: { type: 'string', description: 'ID of the item to remove' }
      },
    },
  },
  {
    id: 'clear_cart',
    type: 'tool',
    position: { x: 650, y: 350 },
    data: {
      name: 'clear_cart',
      description: 'Clears all items from the cart',
      parameters: {},
    },
  },
  {
    id: 'process_payment',
    type: 'tool',
    position: { x: 950, y: 350 },
    data: {
      name: 'process_payment',
      description: 'Processes customer payment',
      parameters: {
        amount: { type: 'number', description: 'Payment amount' },
        payment_method: { type: 'string', description: 'Payment method (card, cash, etc.)' }
      },
    },
  },
  {
    id: 'send_receipt',
    type: 'tool',
    position: { x: 1150, y: 350 },
    data: {
      name: 'send_receipt',
      description: 'Sends receipt to customer',
      parameters: {
        email: { type: 'string', description: 'Customer email' },
        order_details: { type: 'object', description: 'Order details' }
      },
    },
  },
  {
    id: 'escalate_to_manager',
    type: 'tool',
    position: { x: 650, y: 650 },
    data: {
      name: 'escalate_to_manager',
      description: 'Escalates issue to manager',
      parameters: {
        issue_description: { type: 'string', description: 'Description of the issue' }
      },
    },
  },
  {
    id: 'offer_discount',
    type: 'tool',
    position: { x: 650, y: 750 },
    data: {
      name: 'offer_discount',
      description: 'Offers discount to customer',
      parameters: {
        discount_percentage: { type: 'number', description: 'Discount percentage' }
      },
    },
  },
  {
    id: 'get_store_hours',
    type: 'tool',
    position: { x: 650, y: 850 },
    data: {
      name: 'get_store_hours',
      description: 'Gets store operating hours',
      parameters: {},
    },
  },
  {
    id: 'get_policies',
    type: 'tool',
    position: { x: 650, y: 950 },
    data: {
      name: 'get_policies',
      description: 'Gets store policies information',
      parameters: {},
    },
  },
];

const initialEdges: Edge[] = [
  // Route edges (step-to-step connections)
  {
    id: 'start-take_coffee_order',
    source: 'start',
    target: 'take_coffee_order',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'Customer is ready to place a new order' },
  },
  {
    id: 'take_coffee_order-modify_order',
    source: 'take_coffee_order',
    target: 'modify_order',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'Customer wants to modify order' },
  },
  {
    id: 'take_coffee_order-finalize_order',
    source: 'take_coffee_order',
    target: 'finalize_order',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'User wants to finalize the order' },
  },
  {
    id: 'modify_order-finalize_order',
    source: 'modify_order',
    target: 'finalize_order',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'Customer is satisfied with changes' },
  },
  {
    id: 'finalize_order-end',
    source: 'finalize_order',
    target: 'end',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'Payment successful' },
  },
  {
    id: 'handle_complaint-provide_info',
    source: 'handle_complaint',
    target: 'provide_info',
    sourceHandle: 'step-output',
    targetHandle: 'step-input',
    type: 'route',
    data: { condition: 'Need to provide additional information' },
  },

  // Tool edges (step-to-tool connections)
  {
    id: 'start-get_available_coffee_options',
    source: 'start',
    target: 'get_available_coffee_options',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
  {
    id: 'take_coffee_order-get_available_coffee_options',
    source: 'take_coffee_order',
    target: 'get_available_coffee_options',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
  {
    id: 'take_coffee_order-add_to_cart',
    source: 'take_coffee_order',
    target: 'add_to_cart',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
  {
    id: 'modify_order-add_to_cart',
    source: 'modify_order',
    target: 'add_to_cart',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
  {
    id: 'modify_order-remove_item',
    source: 'modify_order',
    target: 'remove_item',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
  {
    id: 'modify_order-clear_cart',
    source: 'modify_order',
    target: 'clear_cart',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
  {
    id: 'finalize_order-process_payment',
    source: 'finalize_order',
    target: 'process_payment',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
  {
    id: 'finalize_order-send_receipt',
    source: 'finalize_order',
    target: 'send_receipt',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
  {
    id: 'handle_complaint-escalate_to_manager',
    source: 'handle_complaint',
    target: 'escalate_to_manager',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
  {
    id: 'handle_complaint-offer_discount',
    source: 'handle_complaint',
    target: 'offer_discount',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
  {
    id: 'provide_info-get_store_hours',
    source: 'provide_info',
    target: 'get_store_hours',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
  {
    id: 'provide_info-get_policies',
    source: 'provide_info',
    target: 'get_policies',
    sourceHandle: 'tool-output',
    targetHandle: 'tool-input',
    type: 'tool',
  },
];

interface FlowBuilderProps {
  onPreview?: (nodes: Node[], edges: Edge[], agent: string, persona: string) => void;
  onSaveConfig?: (nodes: Node[], edges: Edge[], agent: string, persona: string) => void;
}

export default function FlowBuilder({ onPreview, onSaveConfig }: FlowBuilderProps) {
  const [nodes, setNodes, onNodesChangeBase] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);
  const [filteredNodeIds, setFilteredNodeIds] = useState<string[] | null>(null);
  const [editingFlowGroup, setEditingFlowGroup] = useState<{
    id: string;
    data: FlowGroupData;
  } | null>(null);
  const [showExportImportDialog, setShowExportImportDialog] = useState(false);
  const [agentName, setAgentName] = useState('my-agent');
  const [persona, setPersona] = useState('A helpful assistant');
  const [contextMenu, setContextMenu] = useState<{
    x: number;
    y: number;
    visible: boolean;
    nodeId?: string;
    nodeType?: string;
  }>({
    x: 0,
    y: 0,
    visible: false,
  });

  const reactFlowWrapper = useRef<HTMLDivElement>(null);
  const { screenToFlowPosition } = useReactFlow();

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

  // Export/Import handlers
  const handleExportYaml = useCallback(() => {
    setShowExportImportDialog(true);
  }, []);

  const handleImportYaml = useCallback(() => {
    setShowExportImportDialog(true);
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

  // Context menu handlers
  const handleContextMenu = useCallback((event: React.MouseEvent) => {
    event.preventDefault();
    const reactFlowBounds = reactFlowWrapper.current?.getBoundingClientRect();
    if (reactFlowBounds) {
      setContextMenu({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
        visible: true,
      });
    }
  }, []);

  const handleNodeContextMenu = useCallback((event: React.MouseEvent, node: Node) => {
    event.preventDefault();
    const reactFlowBounds = reactFlowWrapper.current?.getBoundingClientRect();
    if (reactFlowBounds) {
      setContextMenu({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
        visible: true,
        nodeId: node.id,
        nodeType: node.type,
      });
    }
  }, []);

  const closeContextMenu = useCallback(() => {
    setContextMenu(prev => ({ ...prev, visible: false }));
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
    const position = screenToFlowPosition({
      x: contextMenu.x - 100,
      y: contextMenu.y - 50,
    });

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
  }, [contextMenu.x, contextMenu.y, screenToFlowPosition, nodes, setNodesWithUndo]);

  const addToolNode = useCallback(() => {
    const id = `tool-${Date.now()}`;
    const position = screenToFlowPosition({
      x: contextMenu.x - 90,
      y: contextMenu.y - 50,
    });

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
  }, [contextMenu.x, contextMenu.y, screenToFlowPosition, nodes, setNodesWithUndo]);

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

  const editNode = useCallback(() => {
    if (contextMenu.nodeId && contextMenu.nodeType) {
      const node = nodes.find(n => n.id === contextMenu.nodeId);
      if (node) {
        if (node.type === 'group') {
          // Handle group node editing
          handleNodeDoubleClick(null as any, node);
        }
        // For step/tool nodes, editing is handled by clicking the edit button within the node
        // We could potentially trigger it here as well if needed
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
      const position = screenToFlowPosition({
        x: contextMenu.x - 100,
        y: contextMenu.y - 50,
      });

      const newNode = cloneNodeWithNewId(originalNode);
      newNode.position = position;

      setNodesWithUndo([...nodes, newNode], 'Paste node');
    }
  }, [contextMenu.x, contextMenu.y, screenToFlowPosition, nodes, setNodesWithUndo]);

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
          {/* Floating Toolbar */}
          <div className="absolute top-4 left-4 z-10">
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
            onContextMenu={handleContextMenu}
            onNodeContextMenu={handleNodeContextMenu}
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
          <Background gap={20}/>
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
                />
              </marker>
            </defs>
          </svg>
        </ReactFlow>

        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          visible={contextMenu.visible}
          onClose={closeContextMenu}
          onAddStepNode={addStepNode}
          onAddToolNode={addToolNode}
          onEdit={contextMenu.nodeId ? editNode : undefined}
          onCopy={contextMenu.nodeId ? copyNode : undefined}
          onPaste={hasClipboardData() ? pasteNode : undefined}
          onDelete={contextMenu.nodeId ? deleteNode : undefined}
          isOnNode={!!contextMenu.nodeId}
          nodeType={contextMenu.nodeType}
        />

        <NodeEditDialogs />

        {editingFlowGroup && (
          <FlowGroupEditDialog
            open={true}
            onClose={handleCloseFlowGroupDialog}
            onSave={handleSaveFlowGroup}
            flowData={editingFlowGroup.data as FlowGroupData}
            availableStepIds={nodes.filter(node => node.type === 'step').map(node => node.id)}
          />
        )}

        <ExportImportDialog
          open={showExportImportDialog}
          onClose={() => setShowExportImportDialog(false)}
          nodes={nodes}
          edges={edges}
          onImport={handleImportFlow}
          agentName={agentName}
          persona={persona}
          onAgentConfigChange={handleAgentConfigChange}
        />

        <KeyboardShortcuts />
        </div>
      </div>
    </FlowProvider>
  );
}
