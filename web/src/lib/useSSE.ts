import { useEffect, useRef, useState, useCallback } from 'react';
import { useAppStore } from './store';

interface SSEEvent {
  event: string;
  data: Record<string, unknown>;
}

interface UseSSEOptions {
  onEvent?: (event: SSEEvent) => void;
  onError?: (error: Event) => void;
  onOpen?: () => void;
  autoReconnect?: boolean;
  reconnectDelay?: number;
}

interface UseSSEReturn {
  isConnected: boolean;
  lastEvent: SSEEvent | null;
  error: string | null;
  connect: () => void;
  disconnect: () => void;
}

/**
 * Hook for subscribing to Server-Sent Events from the pipeline.
 *
 * @param pipelineId - The pipeline ID to subscribe to (null to disconnect)
 * @param options - Configuration options
 * @returns SSE connection state and controls
 *
 * @example
 * ```tsx
 * const { isConnected, lastEvent, error } = usePipelineSSE(pipelineId, {
 *   onEvent: (event) => {
 *     if (event.event === 'reference_generated') {
 *       // Update UI with new reference image
 *     }
 *   }
 * });
 * ```
 */
export function usePipelineSSE(
  pipelineId: string | null,
  options: UseSSEOptions = {}
): UseSSEReturn {
  const {
    onEvent,
    onError,
    onOpen,
    autoReconnect = true,
    reconnectDelay = 3000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState<SSEEvent | null>(null);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const shouldReconnectRef = useRef(true);

  // Get store actions for updating references/keyframes/frames
  const { addProcessLog, updatePipelineProcess } = useAppStore();

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;

    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    setIsConnected(false);
  }, []);

  const connect = useCallback(() => {
    if (!pipelineId) return;

    shouldReconnectRef.current = true;
    setError(null);

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const url = `${apiBase}/api/pipelines/stream/${encodeURIComponent(pipelineId)}`;

    const eventSource = new EventSource(url);
    eventSourceRef.current = eventSource;

    eventSource.onopen = () => {
      setIsConnected(true);
      setError(null);
      onOpen?.();
    };

    eventSource.onerror = (event) => {
      setIsConnected(false);
      setError('Connection lost');
      onError?.(event);

      // Auto-reconnect
      if (autoReconnect && shouldReconnectRef.current) {
        reconnectTimeoutRef.current = setTimeout(() => {
          connect();
        }, reconnectDelay);
      }
    };

    // Listen for all event types
    const eventTypes = [
      'pass_start',
      'pass_complete',
      'reference_generated',
      'keyframe_generated',
      'prompt_written',
      'frame_generated',
      'story_phase_complete',
      'storyboard_complete',
      'error',
      'paused'
    ];

    eventTypes.forEach((eventType) => {
      eventSource.addEventListener(eventType, (event) => {
        try {
          const data = JSON.parse((event as MessageEvent).data);
          const sseEvent: SSEEvent = { event: eventType, data };

          setLastEvent(sseEvent);
          onEvent?.(sseEvent);

          // Handle specific events for store updates
          handleEventForStore(pipelineId, sseEvent);

        } catch (e) {
          console.error('Failed to parse SSE event:', e);
        }
      });
    });
  }, [pipelineId, onEvent, onError, onOpen, autoReconnect, reconnectDelay]);

  // Handle events by updating the Zustand store
  const handleEventForStore = useCallback((processId: string, event: SSEEvent) => {
    switch (event.event) {
      case 'pass_start':
        addProcessLog(
          processId,
          `Pass ${event.data.pass}: ${event.data.name}`,
          'info'
        );
        break;

      case 'pass_complete':
        addProcessLog(processId, `Pass ${event.data.pass} complete`, 'success');
        break;

      case 'reference_generated':
        addProcessLog(
          processId,
          `${(event.data.type as string).charAt(0).toUpperCase() + (event.data.type as string).slice(1)} reference: ${event.data.tag}`,
          'success'
        );
        break;

      case 'keyframe_generated':
        addProcessLog(
          processId,
          `Key frame: ${event.data.frame_id}`,
          'success'
        );
        break;

      case 'frame_generated':
        addProcessLog(
          processId,
          `Frame: ${event.data.frame_id}`,
          'success'
        );
        break;

      case 'story_phase_complete':
        updatePipelineProcess(processId, {
          status: 'complete',
          progress: 1,
          endTime: new Date()
        });
        break;

      case 'storyboard_complete':
        updatePipelineProcess(processId, {
          status: 'complete',
          progress: 1,
          endTime: new Date()
        });
        break;

      case 'error':
        addProcessLog(
          processId,
          `Error: ${event.data.message}`,
          'error'
        );
        updatePipelineProcess(processId, {
          status: 'error',
          error: event.data.message as string,
          endTime: new Date()
        });
        break;
    }
  }, [addProcessLog, updatePipelineProcess]);

  // Connect when pipelineId changes
  useEffect(() => {
    if (pipelineId) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [pipelineId, connect, disconnect]);

  return {
    isConnected,
    lastEvent,
    error,
    connect,
    disconnect
  };
}

/**
 * Hook for subscribing to reference generation events.
 * Automatically updates the store when new references are generated.
 */
export function useReferenceSSE(pipelineId: string | null) {
  const [references, setReferences] = useState<Map<string, { type: string; tag: string; name: string; imagePath: string }>>(new Map());

  const handleEvent = useCallback((event: SSEEvent) => {
    if (event.event === 'reference_generated') {
      const { type, tag, name, image_path } = event.data as {
        type: string;
        tag: string;
        name: string;
        image_path: string;
      };

      setReferences((prev) => {
        const next = new Map(prev);
        next.set(tag, { type, tag, name, imagePath: image_path });
        return next;
      });
    }
  }, []);

  const { isConnected, error } = usePipelineSSE(pipelineId, {
    onEvent: handleEvent
  });

  return { references, isConnected, error };
}

/**
 * Hook for subscribing to frame generation events.
 * Automatically updates when new frames are generated.
 */
export function useFrameSSE(pipelineId: string | null) {
  const [frames, setFrames] = useState<Map<string, { frameId: string; sceneNumber: number; imagePath: string }>>(new Map());

  const handleEvent = useCallback((event: SSEEvent) => {
    if (event.event === 'frame_generated' || event.event === 'keyframe_generated') {
      const { frame_id, scene_number, image_path } = event.data as {
        frame_id: string;
        scene_number: number;
        image_path: string;
      };

      setFrames((prev) => {
        const next = new Map(prev);
        next.set(frame_id, { frameId: frame_id, sceneNumber: scene_number, imagePath: image_path });
        return next;
      });
    }
  }, []);

  const { isConnected, error } = usePipelineSSE(pipelineId, {
    onEvent: handleEvent
  });

  return { frames, isConnected, error };
}
