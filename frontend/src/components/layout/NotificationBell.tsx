import { useState, useEffect } from "react";
import { Bell, Check, Trash2, ShieldAlert, Settings, Info, AlertTriangle, AlertCircle } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { cn } from "@/lib/utils";
import { notificationsAPI, Notification } from "@/lib/api";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function NotificationBell() {
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isOpen, setIsOpen] = useState(false);

  const fetchNotifications = async () => {
    try {
      const [notifsRes, unreadRes] = await Promise.all([
        notificationsAPI.getNotifications(20, 0),
        notificationsAPI.getUnreadCount()
      ]);
      setNotifications(notifsRes.notifications);
      setUnreadCount(unreadRes.unread_count);
    } catch (e) {
      console.error("Failed to fetch notifications", e);
    }
  };

  useEffect(() => {
    fetchNotifications();
    // Poll every 30 seconds
    const interval = setInterval(fetchNotifications, 30000);
    return () => clearInterval(interval);
  }, []);

  const markAsRead = async (id: number) => {
    try {
      await notificationsAPI.markAsRead(id);
      setNotifications(notifications.map(n => n.id === id ? { ...n, status: 'read' } : n));
      setUnreadCount(Math.max(0, unreadCount - 1));
    } catch (e) {
      console.error("Failed to mark read", e);
    }
  };

  const markAllAsRead = async () => {
    try {
      await notificationsAPI.markAllAsRead();
      setNotifications(notifications.map(n => ({ ...n, status: 'read' })));
      setUnreadCount(0);
    } catch (e) {
      console.error("Failed to mark all read", e);
    }
  };

  const getIcon = (type: string, severity: string) => {
    if (type === 'drift') return <ShieldAlert className="w-4 h-4 text-rose-400" />;
    if (type === 'repair') return <Settings className="w-4 h-4 text-amber-400" />;
    if (type === 'billing') return <AlertTriangle className="w-4 h-4 text-amber-400" />;
    
    if (severity === 'high' || severity === 'critical') return <AlertCircle className="w-4 h-4 text-rose-400" />;
    if (severity === 'warning') return <AlertTriangle className="w-4 h-4 text-amber-400" />;
    return <Info className="w-4 h-4 text-indigo-400" />;
  };

  return (
    <Popover open={isOpen} onOpenChange={setIsOpen}>
      <PopoverTrigger asChild>
        <button className="relative p-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/[0.05] transition-colors">
          <Bell className="w-4.5 h-4.5" style={{ width: "1.1rem", height: "1.1rem" }} />
          {unreadCount > 0 && (
            <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-indigo-500 ring-2 ring-[#020817]" />
          )}
        </button>
      </PopoverTrigger>
      
      <PopoverContent align="end" className="w-[380px] p-0 bg-[#0d1829] border border-white/[0.08] shadow-2xl rounded-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3 border-b border-white/[0.06] bg-white/[0.02]">
          <h3 className="font-semibold text-sm text-white">Notifications</h3>
          {unreadCount > 0 && (
            <Button variant="ghost" size="sm" onClick={markAllAsRead} className="h-auto text-xs py-1 px-2 text-slate-400 hover:text-white">
              <Check className="w-3.5 h-3.5 mr-1" />
              Mark all read
            </Button>
          )}
        </div>
        
        <div className="max-h-[400px] overflow-y-auto">
          {notifications.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-slate-500">
              No notifications yet.
            </div>
          ) : (
            <div className="flex flex-col">
              <AnimatePresence>
                {notifications.map(n => (
                  <motion.div
                    key={n.id}
                    layout
                    initial={{ opacity: 0, y: -10 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={cn(
                      "flex items-start gap-3 p-4 border-b border-white/[0.03] transition-colors relative group",
                      n.status === 'unread' ? "bg-indigo-500/[0.03]" : "opacity-75"
                    )}
                  >
                    <div className={cn(
                      "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center border",
                      n.status === 'unread' ? "border-indigo-500/30 bg-indigo-500/10" : "border-white/10 bg-white/5"
                    )}>
                      {getIcon(n.type, n.severity)}
                    </div>
                    
                    <div className="flex-1 min-w-0 pr-6">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="font-medium text-sm text-slate-200 line-clamp-1">{n.title}</span>
                        {n.status === 'unread' && (
                          <span className="w-1.5 h-1.5 rounded-full bg-indigo-500 flex-shrink-0" />
                        )}
                      </div>
                      <p className="text-xs text-slate-400 line-clamp-2 leading-relaxed">
                        {n.message}
                      </p>
                      <div className="mt-2 text-[10px] text-slate-500 font-medium">
                        {new Date(n.created_at).toLocaleString()}
                      </div>
                    </div>
                    
                    {n.status === 'unread' && (
                      <button 
                        onClick={() => markAsRead(n.id)}
                        className="absolute right-4 top-4 p-1.5 rounded-md text-slate-500 opacity-0 group-hover:opacity-100 hover:text-white hover:bg-white/10 transition-all"
                        title="Mark as read"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </motion.div>
                ))}
              </AnimatePresence>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
