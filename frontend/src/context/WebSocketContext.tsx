/**
 * context/WebSocketContext.tsx
 * =============================
 * STEP 5 — WebSocket Real-Time Communication & Live Notifications
 *
 * Provides reactive WebSocket state, event subscription helpers,
 * live in-app notification center, and auto-dispatching toasts.
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import toast from 'react-hot-toast';
import { wsService, type ConnectionStatus, type WSEvent } from '../services/websocket';
import { useAuth } from '../store/authContext';

export interface InAppNotification {
  id: string;
  ticket_id?: string;
  title: string;
  message: string;
  timestamp: string;
  read: boolean;
  type?: 'info' | 'warning' | 'error' | 'success';
}

interface WebSocketContextType {
  status: ConnectionStatus;
  notifications: InAppNotification[];
  unreadCount: number;
  markAllAsRead: () => void;
  clearNotifications: () => void;
  subscribe: (eventType: string, callback: (event: WSEvent) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextType | undefined>(undefined);

export const WebSocketProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user } = useAuth();
  const [status, setStatus] = useState<ConnectionStatus>(wsService.getStatus());
  const [notifications, setNotifications] = useState<InAppNotification[]>([]);

  // 1. Connection Lifecycle tied to Auth User
  useEffect(() => {
    const unsubStatus = wsService.onStatusChange((newStatus) => {
      setStatus(newStatus);
    });

    const token = localStorage.getItem('token');
    if (user && token) {
      wsService.connect(token);
    } else {
      wsService.disconnect();
    }

    return () => {
      unsubStatus();
    };
  }, [user]);

  // 2. Global Event Listeners & Live Toasts
  useEffect(() => {
    // A. Direct in-app notification created
    const unsubNotif = wsService.on('notification.created', (wsEvent) => {
      const data = wsEvent.data;
      const notifItem: InAppNotification = {
        id: wsEvent.event_id || String(Date.now()),
        ticket_id: data.ticket_id,
        title: data.title || 'Nouvelle notification',
        message: data.message || '',
        timestamp: wsEvent.timestamp,
        read: false,
        type: 'info',
      };

      setNotifications((prev) => [notifItem, ...prev.slice(0, 49)]); // keep last 50
      toast(data.title || 'Nouvelle notification', {
        icon: '🔔',
        duration: 4500,
      });
    });

    // B. SLA Risk & Breach alerts
    const unsubSLARisk = wsService.on('sla.at_risk', (wsEvent) => {
      const d = wsEvent.data;
      const title = `⚠️ Risque SLA : #${(d.ticket_number || d.ticket_id || '').slice(-6).toUpperCase()}`;
      const msg = `${d.subject || 'Ticket'} — ${d.crossed_threshold_label || 'Seuil critique franchi'}`;

      const notifItem: InAppNotification = {
        id: wsEvent.event_id,
        ticket_id: d.ticket_id,
        title,
        message: msg,
        timestamp: wsEvent.timestamp,
        read: false,
        type: 'warning',
      };
      setNotifications((prev) => [notifItem, ...prev.slice(0, 49)]);
      toast(title, { icon: '⚠️', duration: 5000 });
    });

    const unsubSLABreach = wsService.on('sla.breached', (wsEvent) => {
      const d = wsEvent.data;
      const title = `🔴 SLA DÉPASSÉ : #${(d.ticket_number || d.ticket_id || '').slice(-6).toUpperCase()}`;
      const msg = `${d.subject || 'Ticket'} — Échéance de résolution dépassée`;

      const notifItem: InAppNotification = {
        id: wsEvent.event_id,
        ticket_id: d.ticket_id,
        title,
        message: msg,
        timestamp: wsEvent.timestamp,
        read: false,
        type: 'error',
      };
      setNotifications((prev) => [notifItem, ...prev.slice(0, 49)]);
      toast.error(title, { duration: 6000 });
    });

    // C. Ticket assignment
    const unsubAssigned = wsService.on('ticket.assigned', (wsEvent) => {
      const d = wsEvent.data;
      const title = `Ticket #${(d.ticket_number || d.ticket_id || '').slice(-6).toUpperCase()} assigné`;
      const notifItem: InAppNotification = {
        id: wsEvent.event_id,
        ticket_id: d.ticket_id,
        title,
        message: d.subject || '',
        timestamp: wsEvent.timestamp,
        read: false,
        type: 'info',
      };
      setNotifications((prev) => [notifItem, ...prev.slice(0, 49)]);
    });

    return () => {
      unsubNotif();
      unsubSLARisk();
      unsubSLABreach();
      unsubAssigned();
    };
  }, []);

  const markAllAsRead = useCallback(() => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
  }, []);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const subscribe = useCallback((eventType: string, callback: (event: WSEvent) => void) => {
    return wsService.on(eventType, callback);
  }, []);

  const unreadCount = notifications.filter((n) => !n.read).length;

  return (
    <WebSocketContext.Provider
      value={{
        status,
        notifications,
        unreadCount,
        markAllAsRead,
        clearNotifications,
        subscribe,
      }}
    >
      {children}
    </WebSocketContext.Provider>
  );
};

export const useWebSocket = () => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};
