import { useState, useCallback } from 'react';

export interface DragPosition {
  x: number;
  y: number;
}

export function useDraggable(initial: DragPosition) {
  const [position, setPosition] = useState<DragPosition>(initial);

  const onMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const startX = e.clientX - position.x;
      const startY = e.clientY - position.y;
      const handleMouseMove = (ev: MouseEvent) => {
        setPosition({ x: ev.clientX - startX, y: ev.clientY - startY });
      };
      const handleMouseUp = () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
      };
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    },
    [position],
  );

  return { position, onMouseDown, setPosition };
}
