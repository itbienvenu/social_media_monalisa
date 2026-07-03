'use client';

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import SocialConnectModal from "../../components/SocialConnectModal";
import { apiFetch } from "../../utils/api";

// Helper Functions
function decodeJwt(token: string | null | undefined) {
    if (!token) return null;
    try {
        const parts = token.split('.');
        if (parts.length < 2) return null;
        const base64Url = parts[1];
        const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
        const jsonPayload = decodeURIComponent(atob(base64).split('').map(function(c) {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
        return JSON.parse(jsonPayload);
    } catch (e) {
        return null;
    }
}

function isVideoUrl(url: string) {
    const videoExtensions = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"];
    const lower = url.toLowerCase();
    return videoExtensions.some(ext => lower.endsWith(ext) || lower.includes(`${ext}?`));
}

// Beautiful SVG Icons for Sidebar
const LinkIcon = () => (
  <svg className="w-5 h-5 mr-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
  </svg>
);

const ChartIcon = () => (
  <svg className="w-5 h-5 mr-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h2a2 2 0 002-2z" />
  </svg>
);

const CreateIcon = () => (
  <svg className="w-5 h-5 mr-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const SettingsIcon = () => (
  <svg className="w-5 h-5 mr-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
  </svg>
);

const HelpIcon = () => (
  <svg className="w-5 h-5 mr-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const LogoutIcon = () => (
  <svg className="w-5 h-5 mr-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
  </svg>
);

const HomeIcon = () => (
  <svg className="w-4 h-4 text-gray-400 hover:text-gray-600 transition cursor-pointer" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
  </svg>
);

const ShieldIcon = () => (
  <svg className="w-6 h-6 text-[#FF4747] mr-3 mt-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
  </svg>
);

const ArrowInIcon = () => (
  <svg className="w-4 h-4 mr-2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M11 16l-4-4m0 0l4-4m-4 4h14m-5 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
  </svg>
);

const UserAvatar = () => (
  <div className="w-10 h-10 rounded-full overflow-hidden border border-gray-600 bg-gray-700 flex items-center justify-center shrink-0 shadow-sm relative">
    <svg className="w-6 h-6 text-gray-300" fill="currentColor" viewBox="0 0 24 24">
      <path d="M24 20.993V24H0v-2.996A14.977 14.977 0 0112.004 15c4.904 0 9.26 2.354 11.996 5.993zM16.002 8.999a4 4 0 11-8 0 4 4 0 018 0z" />
    </svg>
  </div>
);

// Platform Icons
const FacebookIcon = () => (
  <svg className="w-6 h-6 text-[#1877F2]" fill="currentColor" viewBox="0 0 24 24">
    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
  </svg>
);

const InstagramIcon = () => (
  <svg className="w-6 h-6 text-[#E1306C]" fill="none" stroke="currentColor" strokeWidth={2} viewBox="0 0 24 24">
    <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
    <path d="M16 11.37A4 4 0 1112.63 8 4 4 0 0116 11.37z" />
    <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
  </svg>
);

const LinkedinIcon = () => (
  <svg className="w-6 h-6 text-[#0A66C2]" fill="currentColor" viewBox="0 0 24 24">
    <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
  </svg>
);

const TiktokIcon = () => (
  <svg className="w-6 h-6 text-black" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12.53.02C13.84 0 15.14.01 16.44 0c.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.59-1 .01 2.62.02 5.24 0 7.86a7.35 7.35 0 0 1-.95 3.47c-.89 1.45-2.26 2.62-3.86 3.19-1.6.58-3.37.58-4.96.01a7.27 7.27 0 0 1-3.87-3.2 7.27 7.27 0 0 1-.94-3.48c.01-2 .76-3.95 2.13-5.4 1.38-1.45 3.33-2.29 5.37-2.38v4.14c-1.05.02-2.11.37-2.92 1.05-.81.68-1.32 1.69-1.43 2.75-.15 1.42.36 2.89 1.38 3.86 1.02.97 2.49 1.37 3.87 1.07 1.38-.3 2.53-1.33 2.99-2.67.2-.59.27-1.22.25-1.84V.02h-.03z" />
  </svg>
);

const StatusBadge = ({ connected, count }: { connected: boolean; count?: number }) => {
  if (connected) {
    return (
      <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-green-50 text-green-700 border border-green-100">
        <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>
        {count && count > 1 ? `${count} Accounts Connected` : 'Connected'}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold bg-gray-50 text-gray-500 border border-gray-200">
      <span className="w-1.5 h-1.5 rounded-full bg-gray-400"></span>
      Not Connected
    </span>
  );
};

function DashboardContent() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const [connections, setConnections] = useState<any[]>([]);
    const [posts, setPosts] = useState<any[]>([]);
    const [notifications, setNotifications] = useState<any[]>([]);
    const [isNotificationsOpen, setIsNotificationsOpen] = useState(false);
    const [loading, setLoading] = useState(true);
    const [syncLoading, setSyncLoading] = useState(false);
    const [disconnectLoading, setDisconnectLoading] = useState<string | null>(null);
    const [connectLoading, setConnectLoading] = useState<string | null>(null);
    const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);
    const [userProfile, setUserProfile] = useState<any>(null);

    // Sidebar View Navigation
    const [activeSidebarTab, setActiveSidebarTab] = useState<'connect' | 'analytics' | 'settings' | 'help'>(() => {
        const tab = searchParams?.get('tab');
        if (tab === 'connect' || tab === 'analytics' || tab === 'settings' || tab === 'help') {
            return tab;
        }
        return 'connect';
    });

    // Metrics Modal States
    const [activeMetricsPost, setActiveMetricsPost] = useState<any | null>(null);
    const [metrics, setMetrics] = useState<any | null>(null);
    const [metricsLoading, setMetricsLoading] = useState(false);
    const [activeTab, setActiveTab] = useState<'all' | 'posts' | 'reels'>('all');

    // Edit Post States
    const [activeEditPost, setActiveEditPost] = useState<any | null>(null);
    const [editContent, setEditContent] = useState("");
    const [editLoading, setEditLoading] = useState(false);

    // Advanced Analytics States
    const [analyticsSummary, setAnalyticsSummary] = useState<any>(null);
    const [contentPerformance, setContentPerformance] = useState<any[]>([]);
    const [peakTimes, setPeakTimes] = useState<any[]>([]);
    const [historicalTrends, setHistoricalTrends] = useState<any[]>([]);
    const [analyticsLoading, setAnalyticsLoading] = useState<boolean>(false);

    const fetchAnalytics = async () => {
        setAnalyticsLoading(true);
        try {
            const [summaryRes, perfRes, peakRes, trendRes] = await Promise.all([
                apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/analytics/summary`),
                apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/analytics/content-performance`),
                apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/analytics/peak-times`),
                apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/analytics/trends`)
            ]);

            if (summaryRes.ok) setAnalyticsSummary(await summaryRes.json());
            if (perfRes.ok) setContentPerformance(await perfRes.json());
            if (peakRes.ok) setPeakTimes(await peakRes.json());
            if (trendRes.ok) setHistoricalTrends(await trendRes.json());
        } catch (e) {
            console.error("Error fetching analytics:", e);
        } finally {
            setAnalyticsLoading(false);
        }
    };

    useEffect(() => {
        if (activeSidebarTab === 'analytics') {
            fetchAnalytics();
        }
    }, [activeSidebarTab]);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const [connRes, postsRes, notifRes, profileRes] = await Promise.all([
                    apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/connections`),
                    apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/posts`),

                    apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/notifications`),
                    apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/me`)
                ]);

                if (connRes.ok) {
                    const text = await connRes.text();
                    try {
                        setConnections(JSON.parse(text));
                    } catch (e) {
                        console.error("Failed to parse connections JSON:", text);
                        setConnections([]);
                    }
                }

                if (postsRes.ok) {
                    const text = await postsRes.text();
                    try {
                        setPosts(JSON.parse(text));
                    } catch (e) {
                        console.error("Failed to parse posts JSON:", text);
                        setPosts([]);
                    }
                } else {
                    setPosts([]);
                }

                if (notifRes.ok) {
                    const text = await notifRes.text();
                    try {
                        setNotifications(JSON.parse(text));
                    } catch (e) {
                        console.error("Failed to parse notifications JSON:", text);
                        setNotifications([]);
                    }
                } else {
                    setNotifications([]);
                }

                if (profileRes && profileRes.ok) {
                    try {
                        setUserProfile(await profileRes.json());
                    } catch (e) {
                        console.error("Failed to parse profile JSON", e);
                    }
                }

                setLoading(false);
            } catch (e) {
                console.error("Error fetching data:", e);
                setLoading(false);
            }
        };

        fetchData();
    }, []);

    // Poll for notifications and posts updates every 8 seconds
    useEffect(() => {
        const interval = setInterval(async () => {
            try {
                const [postsRes, notifRes] = await Promise.all([
                    apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/posts`),
                    apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/notifications`)
                ]);

                if (postsRes.ok) {
                    setPosts(await postsRes.json());
                }
                if (notifRes.ok) {
                    setNotifications(await notifRes.json());
                }
            } catch (e) {
                console.error("Error polling notifications/posts:", e);
            }
        }, 8000);

        return () => clearInterval(interval);
    }, []);

    const handleMarkAsRead = async (id: string) => {
        try {
            const res = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/notifications/${id}/read`, {
                method: 'POST'
            });
            if (res.ok) {
                setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
            }
        } catch (e) {
            console.error(e);
        }
    };

    const handleMarkAllAsRead = async () => {
        try {
            const res = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/notifications/read-all`, {
                method: 'POST'
            });
            if (res.ok) {
                setNotifications(prev => prev.map(n => ({ ...n, read: true })));
            }
        } catch (e) {
            console.error(e);
        }
    };

    const handleConnect = async (platform: string) => {
        setConnectLoading(platform);
        try {
            const res = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/${platform}/connect`, {
                method: 'POST'
            });

            if (!res.ok) {
                const errText = await res.text();
                alert(`Failed to connect: ${errText}`);
                return;
            }

            const data = await res.json();
            if (data.url) {
                window.location.href = data.url;
            } else {
                alert("Failed to get auth URL");
            }
        } catch (e) {
            console.error("Connection error:", e);
            alert("Error connecting to " + platform);
        } finally {
            setConnectLoading(null);
        }
    };

    const handleDisconnect = async (accountId: string, displayName: string) => {
        if (!confirm(`Are you sure you want to disconnect ${displayName}?`)) return;

        setDisconnectLoading(accountId);
        try {
            const res = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/connections/${accountId}`, {
                method: 'DELETE'
            });
            if (res.ok) {
                setConnections(prev => prev.filter(c => c.id !== accountId));
            }
        } catch (e) {
            console.error("Failed to disconnect account:", e);
        } finally {
            setDisconnectLoading(null);
        }
    };

    const handleTogglePreference = async (targetId: string, currentIsPreferred: boolean) => {
        let preferredIds: string[] = [];
        connections.forEach(conn => {
            if (conn.targets) {
                conn.targets.forEach((tgt: any) => {
                    if (tgt.is_preferred) {
                        if (tgt.target_id !== targetId) {
                            preferredIds.push(tgt.target_id);
                        }
                    } else {
                        if (tgt.target_id === targetId) {
                            preferredIds.push(tgt.target_id);
                        }
                    }
                });
            }
        });

        try {
            const res = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/connections/preferences`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ preferred_target_ids: preferredIds })
            });
            if (res.ok) {
                setConnections(prev => prev.map(conn => {
                    if (!conn.targets) return conn;
                    return {
                        ...conn,
                        targets: conn.targets.map((tgt: any) => {
                            if (tgt.target_id === targetId) {
                                return { ...tgt, is_preferred: !currentIsPreferred };
                            }
                            return tgt;
                        })
                    };
                }));
            }
        } catch (e) {
            console.error("Error setting target preference:", e);
        }
    };

    const handleSync = async () => {
        setSyncLoading(true);
        try {
            await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/posts/sync`, {
                method: 'POST'
            });
            const res = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/posts`);
            if (res.ok) setPosts(await res.json());
            await fetchAnalytics();
        } catch (e) {
            console.error(e);
        } finally {
            setSyncLoading(false);
        }
    };


    const handleViewMetrics = async (post: any) => {
        setActiveMetricsPost(post);
        setMetrics(null);
        setMetricsLoading(true);
        
        try {
            const res = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/posts/${post.id}/metrics`);
            if (res.ok) {
                setMetrics(await res.json());
            } else {
                console.error("Failed to fetch metrics");
            }
        } catch (e) {
            console.error("Error fetching metrics:", e);
        } finally {
            setMetricsLoading(false);
        }
    };

    const handleEditPost = (post: any) => {
        setActiveEditPost(post);
        setEditContent(post.content);
    };

    const handleSaveEdit = async () => {
        if (!activeEditPost) return;
        setEditLoading(true);
        try {
            const res = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/posts/${activeEditPost.id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ content: editContent })
            });
            if (res.ok) {
                setPosts(prev => prev.map(p => p.id === activeEditPost.id ? { ...p, content: editContent } : p));
                setActiveEditPost(null);
            } else {
                alert("Failed to update post: " + await res.text());
            }
        } catch (e) {
            console.error(e);
            alert("An error occurred while updating the post.");
        } finally {
            setEditLoading(false);
        }
    };

    const handleDeletePost = async (post: any) => {
        const hasInstagram = post.platforms && post.platforms.includes("instagram");
        const confirmMessage = hasInstagram
            ? "This post was published to Instagram. Note that Instagram's API does not support deleting posts/Reels automatically. Deleting this post will remove it from this dashboard and other connected platforms (like Facebook), but you must manually delete it from the Instagram app/website on a real device.\n\nAre you sure you want to proceed?"
            : "Are you sure you want to delete this post/reel from this dashboard and the connected platforms? This action is permanent and cannot be undone.";

        if (!confirm(confirmMessage)) {
            return;
        }

        try {
            const res = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/posts/${post.id}`, {
                method: 'DELETE'
            });
            if (res.ok) {
                setPosts(prev => prev.filter(p => p.id !== post.id));
            } else {
                alert("Failed to delete post: " + await res.text());
            }
        } catch (e) {
            console.error(e);
            alert("An error occurred while deleting the post.");
        }
    };

    const handleLogout = async () => {
        try {
            await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/logout`, {
                method: 'POST'
            });
        } catch (e) {
            console.error('Logout error:', e);
        }
        router.push('/login');
    };

    // Auto-refresh metrics while modal is open
    useEffect(() => {
        if (!activeMetricsPost) return;

        const interval = setInterval(async () => {
            try {
                const res = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/posts/${activeMetricsPost.id}/metrics`);
                if (res.ok) {
                    const data = await res.json();
                    setMetrics(data);
                }
            } catch (e) {
                console.error("Error polling metrics:", e);
            }
        }, 4000);

        return () => clearInterval(interval);
    }, [activeMetricsPost]);

    const filteredPosts = posts.filter((post) => {
        if (activeTab === 'posts') return !post.is_reel;
        if (activeTab === 'reels') return post.is_reel;
        return true;
    });

    if (loading) {
        return (
            <div className="min-h-screen bg-slate-50 flex flex-col items-center justify-center space-y-4">
                <svg className="animate-spin h-10 w-10 text-[#FF4747]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                </svg>
                <span className="text-sm text-gray-500 font-semibold">Loading Rhongi Dashboard...</span>
            </div>
        );
    }

    // Prepare helper maps for social connection cards
    const platformDetails: Record<string, { title: string; subtitle: string; desc: string; icon: React.ReactNode }> = {
        facebook: {
            title: "Facebook",
            subtitle: "Pages & Groups",
            desc: "Publish to your Pages, manage incoming messages, and track audience engagement metrics in real-time.",
            icon: <FacebookIcon />
        },
        instagram: {
            title: "Instagram",
            subtitle: "Business Profiles",
            desc: "Schedule posts, Stories, and Reels directly. Analyze follower growth and content performance over time.",
            icon: <InstagramIcon />
        },
        linkedin: {
            title: "LinkedIn",
            subtitle: "Personal & Company",
            desc: "Build your professional network. Share articles, updates, and track company page analytics efficiently.",
            icon: <LinkedinIcon />
        },
        tiktok: {
            title: "TikTok",
            subtitle: "Creator & Business",
            desc: "Plan your video content calendar. Upload drafts, schedule posts, and monitor video views and engagement.",
            icon: <TiktokIcon />
        }
    };

    const isPlatformConnected = (platformName: string) => {
        const conn = connections.find(c => c.platform === platformName);
        return conn ? conn.connected : false;
    };

    return (
        <div className="flex min-h-screen bg-[#F8F9FA] text-gray-800 font-sans">
            
            {/* Sidebar Navigation */}
            <aside className="w-72 bg-[#212529] text-white flex flex-col justify-between shrink-0 shadow-xl border-r border-gray-900/40 relative z-30">
                <div className="p-6 flex-1 flex flex-col">
                    
                    {/* Sidebar Brand Header */}
                    <div className="flex items-center space-x-3.5 mb-8 pb-4 border-b border-gray-800">
                        <UserAvatar />
                        <div className="min-w-0">
                            <h2 className="text-[15px] font-bold text-white tracking-wide truncate">
                                {userProfile?.full_name || userProfile?.email?.split('@')[0] || "Rhongi Dashboard"}
                            </h2>
                            <p className="text-[11px] text-gray-400 font-semibold tracking-wider uppercase">
                                Growth Agency
                            </p>
                        </div>
                    </div>

                    {/* New Post Button */}
                    <button
                        onClick={() => router.push('/post')}
                        className="w-full bg-[#FF4747] hover:bg-[#e03e3e] active:scale-[0.98] text-white py-3.5 px-4 rounded-xl font-bold flex items-center justify-center transition-all shadow-md shadow-[#FF4747]/20 mb-8 cursor-pointer text-sm tracking-wide"
                    >
                        <span className="text-lg mr-2 leading-none font-black">+</span> New Post
                    </button>

                    {/* Menu Navigation Links */}
                    <nav className="space-y-1.5 flex-1">
                        <button
                            onClick={() => setActiveSidebarTab('connect')}
                            className={activeSidebarTab === 'connect' 
                                ? "w-full text-left bg-white/10 text-white border-l-[3.5px] border-[#FF4747] pl-3 pr-4 py-3 rounded-r-xl flex items-center transition-all font-bold text-[14px]"
                                : "w-full text-left text-gray-400 hover:text-white hover:bg-white/5 border-l-[3.5px] border-transparent pl-3 pr-4 py-3 rounded-r-xl flex items-center transition-all font-semibold text-[14px]"
                            }
                        >
                            <LinkIcon />
                            Connect Accounts
                        </button>

                        <button
                            onClick={() => setActiveSidebarTab('analytics')}
                            className={activeSidebarTab === 'analytics'
                                ? "w-full text-left bg-white/10 text-white border-l-[3.5px] border-[#FF4747] pl-3 pr-4 py-3 rounded-r-xl flex items-center transition-all font-bold text-[14px]"
                                : "w-full text-left text-gray-400 hover:text-white hover:bg-white/5 border-l-[3.5px] border-transparent pl-3 pr-4 py-3 rounded-r-xl flex items-center transition-all font-semibold text-[14px]"
                            }
                        >
                            <ChartIcon />
                            Analytics
                        </button>

                        <button
                            onClick={() => router.push('/post')}
                            className="w-full text-left text-gray-400 hover:text-white hover:bg-white/5 border-l-[3.5px] border-transparent pl-3 pr-4 py-3 rounded-r-xl flex items-center transition-all font-semibold text-[14px]"
                        >
                            <CreateIcon />
                            Create Content
                        </button>

                        <button
                            onClick={() => setActiveSidebarTab('settings')}
                            className={activeSidebarTab === 'settings'
                                ? "w-full text-left bg-white/10 text-white border-l-[3.5px] border-[#FF4747] pl-3 pr-4 py-3 rounded-r-xl flex items-center transition-all font-bold text-[14px]"
                                : "w-full text-left text-gray-400 hover:text-white hover:bg-white/5 border-l-[3.5px] border-transparent pl-3 pr-4 py-3 rounded-r-xl flex items-center transition-all font-semibold text-[14px]"
                            }
                        >
                            <SettingsIcon />
                            Settings
                        </button>
                    </nav>
                </div>

                {/* Sidebar Footer */}
                <div className="p-6 border-t border-gray-800 space-y-1.5 bg-[#1B1E21]">
                    <button
                        onClick={() => setActiveSidebarTab('help')}
                        className={activeSidebarTab === 'help'
                            ? "w-full text-left bg-white/10 text-white border-l-[3.5px] border-[#FF4747] pl-3 pr-4 py-2.5 rounded-r-xl flex items-center transition-all font-bold text-[13px]"
                            : "w-full text-left text-gray-400 hover:text-white hover:bg-white/5 border-l-[3.5px] border-transparent pl-3 pr-4 py-2.5 rounded-r-xl flex items-center transition-all font-semibold text-[13px]"
                        }
                    >
                        <HelpIcon />
                        Help Center
                    </button>

                    <button
                        onClick={handleLogout}
                        className="w-full text-left text-gray-400 hover:text-red-400 hover:bg-red-500/5 border-l-[3.5px] border-transparent pl-3 pr-4 py-2.5 rounded-r-xl flex items-center transition-all font-semibold text-[13px]"
                    >
                        <LogoutIcon />
                        Logout
                    </button>
                </div>
            </aside>

            {/* Main Content Area */}
            <main className="flex-1 min-w-0 p-8 md:p-12 overflow-y-auto max-h-screen">
                
                {/* Main Header / Breadcrumbs and Notifications */}
                <div className="flex justify-between items-center mb-8 border-b border-gray-200/60 pb-5">
                    {/* Breadcrumbs */}
                    <div className="flex items-center space-x-2 text-xs font-bold text-gray-500">
                        <HomeIcon />
                        <span className="text-gray-300">›</span>
                        <span className="text-gray-700 capitalize">
                            {activeSidebarTab === 'connect' ? 'Connect Accounts' : activeSidebarTab}
                        </span>
                    </div>

                    {/* Quick Profile Badge & Notification bell */}
                    <div className="flex items-center gap-4 relative">
                        
                        {/* Notification Bell Dropdown */}
                        <div className="relative">
                            <button
                                onClick={() => setIsNotificationsOpen(!isNotificationsOpen)}
                                className="p-2.5 text-gray-500 hover:text-gray-800 hover:bg-gray-100 rounded-xl transition-all relative focus:outline-none border border-gray-200 bg-white shadow-sm cursor-pointer active:scale-95"
                                title="Notifications"
                            >
                                <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
                                </svg>
                                {notifications.filter(n => !n.read).length > 0 && (
                                    <span className="absolute -top-1 -right-1 block h-5 w-5 rounded-full bg-[#FF4747] text-[10px] font-black text-white flex items-center justify-center animate-pulse shadow-sm">
                                        {notifications.filter(n => !n.read).length}
                                    </span>
                                )}
                            </button>

                            {/* Notifications Menu list */}
                            {isNotificationsOpen && (
                                <div className="absolute right-0 mt-3 w-80 bg-white rounded-2xl shadow-xl border border-gray-100/90 z-50 overflow-hidden py-1 max-h-96 flex flex-col animate-fadeIn">
                                    <div className="px-4 py-3 bg-gray-50 border-b border-gray-100 flex justify-between items-center shrink-0">
                                        <span className="font-bold text-xs text-gray-800 uppercase tracking-wider">Notifications</span>
                                        {notifications.some(n => !n.read) && (
                                            <button
                                                onClick={handleMarkAllAsRead}
                                                className="text-xs text-[#FF4747] hover:text-[#e03e3e] font-bold cursor-pointer"
                                            >
                                                Mark all read
                                            </button>
                                        )}
                                    </div>
                                    <div className="overflow-y-auto flex-1">
                                        {notifications.length === 0 ? (
                                            <div className="px-4 py-8 text-center text-gray-400 text-xs font-semibold">
                                                No notifications yet.
                                            </div>
                                        ) : (
                                            notifications.map((notif) => (
                                                <div
                                                    key={notif.id}
                                                    onClick={() => !notif.read && handleMarkAsRead(notif.id)}
                                                    className={`px-4 py-3 border-b border-gray-50 last:border-0 hover:bg-gray-50 transition cursor-pointer flex gap-3 ${!notif.read ? 'bg-blue-50/20' : ''}`}
                                                >
                                                    <div className="mt-0.5 shrink-0">
                                                        {notif.type === 'error' ? (
                                                            <span className="h-2 w-2 rounded-full bg-red-500 block" />
                                                        ) : notif.type === 'success' ? (
                                                            <span className="h-2 w-2 rounded-full bg-green-500 block" />
                                                        ) : (
                                                            <span className="h-2 w-2 rounded-full bg-blue-500 block" />
                                                        )}
                                                    </div>
                                                    <div className="flex-1 space-y-0.5 min-w-0">
                                                        <div className={`text-xs ${!notif.read ? 'font-bold text-gray-900' : 'font-semibold text-gray-600'}`}>
                                                            {notif.title}
                                                        </div>
                                                        <div className="text-[11px] text-gray-500 leading-normal break-words">
                                                            {notif.message}
                                                        </div>
                                                        <div className="text-[9px] text-gray-400 font-medium">
                                                            {new Date(notif.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                                        </div>
                                                    </div>
                                                </div>
                                            ))
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Top Bar User display */}
                        <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 bg-white border border-gray-200 rounded-xl shadow-sm text-xs font-bold text-gray-700">
                            <span className="w-2 h-2 rounded-full bg-green-500"></span>
                            <span>{userProfile?.email || "active_session"}</span>
                        </div>
                    </div>
                </div>

                {/* VIEW: CONNECT ACCOUNTS */}
                {activeSidebarTab === 'connect' && (
                    <div className="space-y-8 animate-fadeIn">
                        {/* Title and Intro */}
                        <div>
                            <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-2">
                                Connect your Social Accounts
                            </h1>
                            <p className="text-sm text-gray-500 max-w-3xl leading-relaxed font-medium">
                                Link your profiles to Rhongi to start scheduling posts, analyzing performance, and managing your digital presence from one centralized hub.
                            </p>
                        </div>

                        {/* Grid of 4 Platform cards */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {['facebook', 'instagram', 'linkedin', 'tiktok'].map((platform) => {
                                const details = platformDetails[platform];
                                const platformAccs = connections.filter(c => c.platform === platform);
                                const connected = platformAccs.length > 0;
                                const isConnecting = connectLoading === platform;

                                return (
                                    <div 
                                        key={platform} 
                                        className="bg-white border border-gray-150/70 p-6 rounded-2xl shadow-sm flex flex-col justify-between hover:shadow-md transition-shadow duration-300"
                                    >
                                        <div>
                                            {/* Card Top: Circle Icon & Connection Status */}
                                            <div className="flex justify-between items-start mb-4">
                                                <div className="w-12 h-12 rounded-full bg-slate-50 flex items-center justify-center shadow-inner border border-gray-100">
                                                    {details.icon}
                                                </div>
                                                <StatusBadge connected={connected} count={platformAccs.length} />
                                            </div>

                                            {/* Card Middle: Platform Info */}
                                            <div className="mb-6">
                                                <h3 className="text-lg font-bold text-gray-900">
                                                    {details.title}{' '}
                                                    <span className="text-xs text-gray-400 font-semibold block sm:inline sm:ml-1.5">
                                                        {details.subtitle}
                                                    </span>
                                                </h3>
                                                <p className="text-xs text-gray-500 leading-relaxed mt-2 font-medium">
                                                    {details.desc}
                                                </p>
                                            </div>
                                        </div>

                                        {/* Card Action Button */}
                                        <div>
                                            <button
                                                onClick={() => handleConnect(platform)}
                                                disabled={isConnecting}
                                                className="w-full border border-gray-200 hover:border-[#FF4747] text-gray-700 hover:text-[#FF4747] hover:bg-[#FF4747]/5 active:scale-[0.99] transition-all py-2.5 px-4 rounded-xl text-xs font-bold flex items-center justify-center disabled:opacity-50 cursor-pointer"
                                            >
                                                {isConnecting ? (
                                                    <span className="flex items-center gap-1">
                                                        <svg className="animate-spin h-4 w-4 text-[#FF4747]" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                                        </svg>
                                                        Connecting...
                                                    </span>
                                                ) : (
                                                    <>
                                                        <ArrowInIcon />
                                                        {connected ? 'Link Another Account' : `Connect ${details.title}`}
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>

                        {/* Active Social Connections Section */}
                        <div className="bg-white border border-gray-150 rounded-2xl p-6 shadow-sm space-y-6">
                            <div>
                                <h2 className="text-lg font-bold text-gray-900 mb-1">Active Connections</h2>
                                <p className="text-xs text-gray-400 font-semibold">Manage your connected platform accounts, publishing targets and target preferences.</p>
                            </div>

                            {connections.length === 0 ? (
                                <div className="text-center py-8 border border-dashed border-gray-200 rounded-xl text-gray-400 font-semibold text-xs">
                                    No social accounts connected yet. Link an account using the cards above.
                                </div>
                            ) : (
                                <div className="divide-y divide-gray-100 space-y-6">
                                    {connections.map((conn) => (
                                        <div key={conn.id} className="pt-6 first:pt-0 space-y-4">
                                            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                                                <div className="flex items-center gap-3">
                                                    {conn.profile_picture ? (
                                                        <img src={conn.profile_picture} alt={conn.display_name || conn.username} className="w-10 h-10 rounded-full object-cover border border-gray-200" />
                                                    ) : (
                                                        <div className="w-10 h-10 rounded-full bg-gray-100 border border-gray-200 flex items-center justify-center font-bold text-gray-500 capitalize text-sm">
                                                            {(conn.display_name || conn.username || conn.platform)[0]}
                                                        </div>
                                                    )}
                                                    <div>
                                                        <div className="flex items-center gap-2">
                                                            <h4 className="text-sm font-bold text-gray-900">{conn.display_name || conn.username}</h4>
                                                            <span className="px-2 py-0.5 rounded-full text-[10px] font-black uppercase tracking-wider bg-gray-100 text-gray-500 border border-gray-150 capitalize">
                                                                {conn.platform}
                                                            </span>
                                                        </div>
                                                        <p className="text-[10px] text-gray-400 font-semibold tracking-tight">Account ID: {conn.id}</p>
                                                    </div>
                                                </div>

                                                <button
                                                    onClick={() => handleDisconnect(conn.id, conn.display_name || conn.username || conn.platform)}
                                                    disabled={disconnectLoading === conn.id}
                                                    className="border border-red-200 text-red-600 hover:bg-red-50 py-1.5 px-3 rounded-lg text-xs font-bold transition-all disabled:opacity-50 active:scale-95 cursor-pointer flex items-center gap-1.5"
                                                >
                                                    {disconnectLoading === conn.id ? (
                                                        <svg className="animate-spin h-3.5 w-3.5 text-red-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                                        </svg>
                                                    ) : null}
                                                    Disconnect
                                                </button>
                                            </div>

                                            {/* Targets / Pages under this account */}
                                            {conn.targets && conn.targets.length > 0 && (
                                                <div className="pl-4 sm:pl-12 border-l-2 border-gray-100 space-y-2">
                                                    <p className="text-[9px] font-black uppercase tracking-wider text-gray-400">Linked Targets & Pages</p>
                                                    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                                        {conn.targets.map((tgt: any) => (
                                                            <div key={tgt.id} className="flex items-center justify-between p-3 bg-slate-50/60 border border-gray-150 rounded-xl hover:bg-slate-50 transition-colors">
                                                                <div className="flex items-center gap-3">
                                                                    {tgt.profile_picture ? (
                                                                        <img src={tgt.profile_picture} alt={tgt.target_name} className="w-8 h-8 rounded-full object-cover border border-gray-200" />
                                                                    ) : (
                                                                        <div className="w-8 h-8 rounded-full bg-white border border-gray-200 flex items-center justify-center text-xs font-bold text-gray-400 capitalize">
                                                                            {tgt.target_name[0]}
                                                                        </div>
                                                                    )}
                                                                    <div>
                                                                        <p className="text-xs font-bold text-gray-800 leading-tight">{tgt.target_name}</p>
                                                                        <p className="text-[10px] text-gray-400 font-semibold capitalize leading-none mt-0.5">{tgt.target_type}</p>
                                                                    </div>
                                                                </div>

                                                                <button
                                                                    onClick={() => handleTogglePreference(tgt.target_id, tgt.is_preferred)}
                                                                    className={`p-1.5 rounded-lg border transition-all cursor-pointer ${tgt.is_preferred ? 'bg-amber-50 border-amber-200 text-amber-500' : 'bg-white border-gray-200 text-gray-400 hover:text-amber-500 hover:border-amber-200'}`}
                                                                    title={tgt.is_preferred ? "Remove preferred publishing target" : "Mark as preferred publishing target"}
                                                                >
                                                                    <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                                                                        <path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z" />
                                                                    </svg>
                                                                </button>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>

                        {/* Secure Connection Shield Card */}
                        <div className="bg-white border border-gray-150/80 p-5 rounded-2xl shadow-sm flex items-start">
                            <ShieldIcon />
                            <div>
                                <h4 className="text-xs font-extrabold text-gray-900 tracking-wide uppercase mb-1">
                                    Secure Connection
                                </h4>
                                <p className="text-[11px] text-gray-400 font-semibold leading-relaxed">
                                    We use official API integrations to securely connect to your accounts. Rhongi will never post without your explicit permission or store your direct login credentials.
                                </p>
                            </div>
                        </div>
                    </div>
                )}

                {/* VIEW: ANALYTICS & ACTIVITY FEED */}
                {activeSidebarTab === 'analytics' && (
                    <div className="space-y-6 animate-fadeIn">
                        {/* Title and Sync controls */}
                        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-gray-200/60 pb-5">
                            <div>
                                <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-1">
                                    Analytics & Activity Feed
                                </h1>
                                <p className="text-sm text-gray-600 font-medium">
                                    Track published metrics and update content schedules across all channels.
                                </p>
                            </div>
                            <div className="flex gap-2">
                                <button
                                    onClick={handleSync}
                                    disabled={syncLoading}
                                    className="text-xs bg-white border border-gray-200 text-gray-700 px-4 py-2.5 rounded-xl hover:bg-gray-50 transition-all disabled:opacity-50 flex items-center gap-2 font-bold cursor-pointer shadow-sm"
                                >
                                    {syncLoading ? (
                                        <svg className="animate-spin h-4 w-4 text-gray-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                    ) : '🔄'}
                                    {syncLoading ? 'Syncing...' : 'Sync Posts'}
                                </button>
                                <button 
                                    onClick={() => router.push('/post')}
                                    className="text-xs bg-[#FF4747] hover:bg-[#e03e3e] text-white px-4 py-2.5 rounded-xl transition-all font-bold cursor-pointer shadow-sm"
                                >
                                    Create Post
                                </button>
                            </div>
                        </div>

                        {/* ADVANCED DEEP ANALYTICS BOARD */}
                        {analyticsLoading ? (
                            <div className="flex justify-center items-center py-12">
                                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-[#FF4747]"></div>
                            </div>
                        ) : (
                            <div className="space-y-6">
                                {/* Row 1: Summary Cards */}
                                <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                                    <div className="bg-white border border-gray-200/80 p-5 rounded-2xl shadow-sm hover:shadow-md transition duration-200 border-t-4 border-t-blue-500">
                                        <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-1">Total Views / Reach</p>
                                        <p className="text-3xl font-black text-gray-900">{analyticsSummary?.total_views?.toLocaleString() || 0}</p>
                                        <div className="text-[11px] text-gray-600 mt-1.5 font-medium flex items-center gap-1">
                                            <span>🌐</span> across all channels
                                        </div>
                                    </div>
                                    <div className="bg-white border border-gray-200/80 p-5 rounded-2xl shadow-sm hover:shadow-md transition duration-200 border-t-4 border-t-rose-500">
                                        <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-1">Likes & Reactions</p>
                                        <p className="text-3xl font-black text-gray-900">{analyticsSummary?.total_likes?.toLocaleString() || 0}</p>
                                        <div className="text-[11px] text-rose-600 mt-1.5 font-semibold flex items-center gap-1">
                                            <span>❤️</span> engagement rate
                                        </div>
                                    </div>
                                    <div className="bg-white border border-gray-200/80 p-5 rounded-2xl shadow-sm hover:shadow-md transition duration-200 border-t-4 border-t-indigo-500">
                                        <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-1">Comments</p>
                                        <p className="text-3xl font-black text-gray-900">{analyticsSummary?.total_comments?.toLocaleString() || 0}</p>
                                        <div className="text-[11px] text-indigo-600 mt-1.5 font-semibold flex items-center gap-1">
                                            <span>💬</span> conversations
                                        </div>
                                    </div>
                                    <div className="bg-white border border-gray-200/80 p-5 rounded-2xl shadow-sm hover:shadow-md transition duration-200 border-t-4 border-t-violet-500">
                                        <p className="text-[11px] font-bold uppercase tracking-wider text-gray-500 mb-1">Shares & Reposts</p>
                                        <p className="text-3xl font-black text-gray-900">{analyticsSummary?.total_shares?.toLocaleString() || 0}</p>
                                        <div className="text-[11px] text-violet-600 mt-1.5 font-semibold flex items-center gap-1">
                                            <span>🔁</span> organic distribution
                                        </div>
                                    </div>
                                </div>

                                {/* Row 2: Charts Grid */}
                                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                                    {/* Left: Trend Line Chart */}
                                    <div className="bg-white border border-gray-200/80 p-6 rounded-2xl shadow-sm">
                                        <h3 className="text-sm font-extrabold text-gray-900 mb-1 uppercase tracking-wider">Engagement Trend (Last 30 Days)</h3>
                                        <p className="text-xs text-gray-500 font-medium mb-5">Total interactions (likes, comments, shares) captured daily</p>
                                        
                                        {historicalTrends && historicalTrends.length > 1 ? (
                                            <div className="w-full flex gap-3">
                                                {/* Y-Axis Labels */}
                                                {(() => {
                                                    const maxVal = Math.max(...historicalTrends.map((t: any) => t.likes + t.comments + t.shares), 10);
                                                    return (
                                                        <div className="flex flex-col justify-between text-[10px] text-gray-500 font-bold h-40 pb-6 shrink-0 w-8 text-right select-none">
                                                            <span>{maxVal.toLocaleString()}</span>
                                                            <span>{Math.round(maxVal / 2).toLocaleString()}</span>
                                                            <span>0</span>
                                                        </div>
                                                    );
                                                })()}
                                                
                                                <div className="w-full">
                                                    <svg className="w-full h-40 overflow-visible" viewBox="0 0 500 150" preserveAspectRatio="none">
                                                        <defs>
                                                            <linearGradient id="chart-gradient" x1="0" y1="0" x2="0" y2="1">
                                                                <stop offset="0%" stopColor="#FF4747" stopOpacity="0.2" />
                                                                <stop offset="100%" stopColor="#FF4747" stopOpacity="0.0" />
                                                            </linearGradient>
                                                        </defs>
                                                        {/* Grid lines */}
                                                        <line x1="0" y1="10" x2="500" y2="10" stroke="#f1f5f9" strokeWidth="1" strokeDasharray="3,3" />
                                                        <line x1="0" y1="75" x2="500" y2="75" stroke="#f1f5f9" strokeWidth="1" strokeDasharray="3,3" />
                                                        <line x1="0" y1="140" x2="500" y2="140" stroke="#e2e8f0" strokeWidth="1" />
                                                        
                                                        {/* SVG line and path */}
                                                        {(() => {
                                                            const paddingY = 10;
                                                            const width = 500;
                                                            const height = 150;
                                                            const maxVal = Math.max(...historicalTrends.map((t: any) => t.likes + t.comments + t.shares), 10);
                                                            const points = historicalTrends.map((t: any, index: number) => {
                                                                const x = (index / (historicalTrends.length - 1 || 1)) * width;
                                                                const y = height - paddingY - ((t.likes + t.comments + t.shares) / maxVal) * (height - 2 * paddingY);
                                                                return { x, y, val: t.likes + t.comments + t.shares };
                                                            });
                                                            
                                                            const linePointsStr = points.map(p => `${p.x},${p.y}`).join(" ");
                                                            const fillPointsStr = `0,140 ${linePointsStr} 500,140`;
                                                            
                                                            return (
                                                                <>
                                                                    <polygon points={fillPointsStr} fill="url(#chart-gradient)" />
                                                                    <polyline points={linePointsStr} fill="none" stroke="#FF4747" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
                                                                    {points.map((p, idx) => (
                                                                        <g key={idx} className="group">
                                                                            <circle cx={p.x} cy={p.y} r="4.5" fill="white" stroke="#FF4747" strokeWidth="3" className="transition-all duration-150 cursor-pointer hover:r-6" />
                                                                            <title>{`Engagement: ${p.val}`}</title>
                                                                        </g>
                                                                    ))}
                                                                </>
                                                            );
                                                        })()}
                                                    </svg>
                                                    <div className="flex justify-between text-[10px] text-gray-500 font-extrabold uppercase mt-2 select-none">
                                                        <span>{historicalTrends[0]?.date}</span>
                                                        <span>{historicalTrends[Math.floor(historicalTrends.length / 2)]?.date}</span>
                                                        <span>{historicalTrends[historicalTrends.length - 1]?.date}</span>
                                                    </div>
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="h-40 flex items-center justify-center border border-dashed border-gray-200 rounded-xl bg-gray-50/50">
                                                <p className="text-gray-550 font-semibold text-xs">Accumulating timeline trends... check back tomorrow.</p>
                                            </div>
                                        )}
                                    </div>

                                    {/* Right: Content Format Comparison */}
                                    <div className="bg-white border border-gray-200/80 p-6 rounded-2xl shadow-sm">
                                        <h3 className="text-sm font-extrabold text-gray-900 mb-1 uppercase tracking-wider">Content Format Breakdown</h3>
                                        <p className="text-xs text-gray-500 font-medium mb-5">Compare average views and engagement by post type</p>
                                        
                                        {contentPerformance && contentPerformance.length > 0 ? (
                                            <div className="space-y-5 py-1">
                                                {contentPerformance.map((perf, idx) => {
                                                    const maxLikes = Math.max(...contentPerformance.map(p => p.avg_likes), 1);
                                                    const maxViews = Math.max(...contentPerformance.map(p => p.avg_views), 1);
                                                    const likesPercent = (perf.avg_likes / maxLikes) * 100;
                                                    const viewsPercent = (perf.avg_views / maxViews) * 100;
                                                    
                                                    return (
                                                        <div key={idx} className="space-y-2 p-3 bg-slate-50/50 rounded-xl border border-slate-100">
                                                            <div className="flex justify-between items-center">
                                                                <span className="text-xs font-black text-gray-800 uppercase tracking-wide flex items-center gap-1.5">
                                                                    <span className={perf.format.toLowerCase() === 'reels' ? 'text-indigo-500' : 'text-blue-500'}>
                                                                        {perf.format.toLowerCase() === 'reels' ? '🎬' : '📝'}
                                                                    </span>
                                                                    {perf.format}
                                                                </span>
                                                                <span className="text-[10px] text-gray-650 font-bold bg-white px-2 py-0.5 rounded-md border border-gray-200/50">{perf.post_count} posts</span>
                                                            </div>
                                                            {/* Views progress bar */}
                                                            <div className="space-y-1">
                                                                <div className="flex justify-between text-[10px] text-gray-600 font-semibold">
                                                                    <span>Avg Views</span>
                                                                    <span className="font-bold text-gray-900">{Math.round(perf.avg_views).toLocaleString()}</span>
                                                                </div>
                                                                <div className="w-full bg-gray-200 h-2.5 rounded-full overflow-hidden">
                                                                    <div className="bg-gradient-to-r from-blue-500 to-indigo-500 h-full rounded-full transition-all duration-500" style={{ width: `${viewsPercent}%` }} />
                                                                </div>
                                                            </div>
                                                            {/* Likes progress bar */}
                                                            <div className="space-y-1">
                                                                <div className="flex justify-between text-[10px] text-gray-600 font-semibold">
                                                                    <span>Avg Likes</span>
                                                                    <span className="font-bold text-gray-900">{Math.round(perf.avg_likes).toLocaleString()}</span>
                                                                </div>
                                                                <div className="w-full bg-gray-200 h-2.5 rounded-full overflow-hidden">
                                                                    <div className="bg-[#FF4747] h-full rounded-full transition-all duration-500" style={{ width: `${likesPercent}%` }} />
                                                                </div>
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>
                                        ) : (
                                            <div className="h-40 flex items-center justify-center border border-dashed border-gray-200 rounded-xl bg-gray-50/50">
                                                <p className="text-gray-550 font-semibold text-xs">No format comparison data. Post more Reels and Standard posts to unlock.</p>
                                            </div>
                                        )}
                                    </div>
                                </div>

                                {/* Row 3: Optimal Posting Times Heatmap */}
                                <div className="bg-white border border-gray-200/80 p-6 rounded-2xl shadow-sm">
                                    <div className="flex justify-between items-start mb-2">
                                        <div>
                                            <h3 className="text-sm font-extrabold text-gray-900 uppercase tracking-wider">Optimal Posting Heatmap</h3>
                                            <p className="text-xs text-gray-500 font-medium">Identify the best hour of the day and day of the week to post content (based on average engagement rate)</p>
                                        </div>
                                    </div>
                                    
                                    {peakTimes && peakTimes.length > 0 ? (
                                        <div className="mt-6 overflow-x-auto pb-2">
                                            <div className="min-w-[750px] space-y-2.5 pr-2">
                                                {/* Hour indicators header aligned perfectly */}
                                                <div 
                                                    className="grid items-center text-[10px] text-gray-500 font-bold uppercase tracking-wider mb-1"
                                                    style={{ gridTemplateColumns: '80px 1fr' }}
                                                >
                                                    <div className="text-left font-black text-gray-800">Day / Hour</div>
                                                    <div 
                                                        className="grid gap-1.5 text-center font-bold"
                                                        style={{ gridTemplateColumns: 'repeat(24, minmax(0, 1fr))' }}
                                                    >
                                                        {Array.from({ length: 24 }).map((_, h) => (
                                                            <div key={h} className="text-[10px] text-gray-650 font-bold">{h.toString().padStart(2, '0')}</div>
                                                        ))}
                                                    </div>
                                                </div>
                                                
                                                {/* Matrix Rows */}
                                                {(() => {
                                                    const DAYS_LABEL = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
                                                    const heatmapMatrix = Array(7).fill(0).map(() => Array(24).fill(0));
                                                    let maxEngagement = 0;
                                                    peakTimes.forEach((pt: any) => {
                                                        const d = pt.day_of_week;
                                                        const h = pt.hour_of_day;
                                                        heatmapMatrix[d][h] = pt.avg_engagement;
                                                        if (pt.avg_engagement > maxEngagement) {
                                                            maxEngagement = pt.avg_engagement;
                                                        }
                                                    });
                                                    
                                                    return heatmapMatrix.map((rowArr, d) => (
                                                        <div 
                                                            key={d} 
                                                            className="grid items-center"
                                                            style={{ gridTemplateColumns: '80px 1fr' }}
                                                        >
                                                            <div className="text-xs font-extrabold text-gray-800">{DAYS_LABEL[d]}</div>
                                                            <div 
                                                                className="grid gap-1.5"
                                                                style={{ gridTemplateColumns: 'repeat(24, minmax(0, 1fr))' }}
                                                            >
                                                                {rowArr.map((val, h) => {
                                                                    const percent = maxEngagement > 0 ? val / maxEngagement : 0;
                                                                    const backgroundColor = val > 0 
                                                                        ? `rgba(255, 71, 71, ${0.12 + percent * 0.88})` 
                                                                        : 'rgba(241, 245, 249, 0.7)';
                                                                    const title = val > 0 
                                                                        ? `${DAYS_LABEL[d]} at ${h.toString().padStart(2, '0')}:00\nAverage Engagement score: ${Math.round(val)}`
                                                                        : `${DAYS_LABEL[d]} at ${h.toString().padStart(2, '0')}:00\nNo post data`;
                                                                    return (
                                                                        <div 
                                                                            key={h} 
                                                                            className="aspect-square rounded-md border border-white hover:border-gray-500 cursor-pointer transition-all duration-150 hover:scale-110 shadow-sm"
                                                                            style={{ backgroundColor }}
                                                                            title={title}
                                                                        />
                                                                    );
                                                                })}
                                                            </div>
                                                        </div>
                                                    ));
                                                })()}
                                            </div>
                                            <div className="flex justify-end items-center mt-4 gap-2 text-[10px] font-extrabold uppercase text-gray-500 select-none">
                                                <span>Less Engaged</span>
                                                <div className="flex gap-1">
                                                    <div className="w-4 h-3.5 rounded-[4px] bg-red-100" />
                                                    <div className="w-4 h-3.5 rounded-[4px] bg-red-300" />
                                                    <div className="w-4 h-3.5 rounded-[4px] bg-red-500" />
                                                    <div className="w-4 h-3.5 rounded-[4px] bg-[#FF4747]" />
                                                </div>
                                                <span>More Engaged</span>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="h-32 flex items-center justify-center border border-dashed border-gray-200 rounded-xl bg-gray-50/50 mt-4">
                                            <p className="text-gray-500 font-semibold text-xs">Analyze post metrics over multiple time slots to render your hourly engagement map.</p>
                                        </div>
                                    )}
                                </div>
                            </div>
                        )}

                        {(!posts || posts.length === 0) ? (
                            <div className="bg-white border border-gray-150 p-12 rounded-2xl text-center shadow-sm">
                                <p className="text-gray-400 font-semibold text-sm mb-4">No published posts or activity logs found.</p>
                                <button
                                    onClick={() => router.push('/post')}
                                    className="px-5 py-2.5 bg-[#FF4747] hover:bg-[#e03e3e] text-white rounded-xl text-xs font-bold transition-all shadow-md cursor-pointer"
                                >
                                    Write your first post
                                </button>
                            </div>
                        ) : (
                            <div className="bg-white border border-gray-150 rounded-2xl shadow-sm overflow-hidden p-6">
                                {/* Filter Tabs */}
                                <div className="flex border-b border-gray-200 mb-6 space-x-6">
                                    <button
                                        onClick={() => setActiveTab('all')}
                                        className={`pb-3.5 text-xs font-extrabold uppercase tracking-wider transition-all relative ${
                                            activeTab === 'all'
                                                ? 'text-[#FF4747] font-black'
                                                : 'text-gray-400 hover:text-gray-600'
                                        }`}
                                    >
                                        All Activities
                                        {activeTab === 'all' && (
                                            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#FF4747] rounded-full"></span>
                                        )}
                                    </button>
                                    <button
                                        onClick={() => setActiveTab('posts')}
                                        className={`pb-3.5 text-xs font-extrabold uppercase tracking-wider transition-all relative ${
                                            activeTab === 'posts'
                                                ? 'text-[#FF4747] font-black'
                                                : 'text-gray-400 hover:text-gray-600'
                                        }`}
                                    >
                                        Standard Posts
                                        {activeTab === 'posts' && (
                                            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#FF4747] rounded-full"></span>
                                        )}
                                    </button>
                                    <button
                                        onClick={() => setActiveTab('reels')}
                                        className={`pb-3.5 text-xs font-extrabold uppercase tracking-wider transition-all relative ${
                                            activeTab === 'reels'
                                                ? 'text-[#FF4747] font-black'
                                                : 'text-gray-400 hover:text-gray-600'
                                        }`}
                                    >
                                        Reels & Videos
                                        {activeTab === 'reels' && (
                                            <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-[#FF4747] rounded-full"></span>
                                        )}
                                    </button>
                                </div>

                                {filteredPosts.length === 0 ? (
                                    <p className="text-gray-400 text-center py-12 font-semibold text-xs border border-dashed border-gray-100 rounded-xl bg-gray-50/50">
                                        {activeTab === 'posts' 
                                            ? "No standard feed posts found." 
                                            : "No reels or short-form videos found."}
                                    </p>
                                ) : (
                                    <div className="overflow-x-auto">
                                        <table className="min-w-full divide-y divide-gray-150">
                                            <thead>
                                                <tr className="bg-gray-50/75">
                                                    <th className="px-6 py-3 text-left text-[10px] font-extrabold text-gray-400 uppercase tracking-wider rounded-l-xl">Content</th>
                                                    <th className="px-6 py-3 text-left text-[10px] font-extrabold text-gray-400 uppercase tracking-wider">Type</th>
                                                    <th className="px-6 py-3 text-left text-[10px] font-extrabold text-gray-400 uppercase tracking-wider">Platforms</th>
                                                    <th className="px-6 py-3 text-left text-[10px] font-extrabold text-gray-400 uppercase tracking-wider">Status</th>
                                                    <th className="px-6 py-3 text-left text-[10px] font-extrabold text-gray-400 uppercase tracking-wider">Date</th>
                                                    <th className="px-6 py-3 text-left text-[10px] font-extrabold text-gray-400 uppercase tracking-wider rounded-r-xl">Actions</th>
                                                </tr>
                                            </thead>
                                            <tbody className="bg-white divide-y divide-gray-100">
                                                {filteredPosts.map((post) => (
                                                    <tr key={post.id} className="hover:bg-slate-50/50 transition">
                                                        <td className="px-6 py-4 whitespace-nowrap text-xs text-gray-800 max-w-xs truncate">
                                                            <div className="flex items-center gap-3">
                                                                {post.media_keys && post.media_keys.length > 0 && (
                                                                    isVideoUrl(post.media_keys[0]) ? (
                                                                        <video 
                                                                            src={post.media_keys[0]} 
                                                                            preload="metadata"
                                                                            className="w-10 h-10 object-cover rounded-lg border shadow-sm bg-black shrink-0"
                                                                        />
                                                                    ) : (
                                                                        <img 
                                                                            src={post.media_keys[0]} 
                                                                            alt="post thumbnail" 
                                                                            className="w-10 h-10 object-cover rounded-lg border shadow-sm shrink-0"
                                                                        />
                                                                    )
                                                                )}
                                                                <span className="font-semibold text-gray-700">{post.content}</span>
                                                            </div>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            {post.is_reel ? (
                                                                <span className="px-2.5 py-1 inline-flex text-[10px] font-extrabold rounded-full bg-purple-50 text-purple-700 border border-purple-100 shadow-sm">
                                                                    Reel
                                                                </span>
                                                            ) : (
                                                                <span className="px-2.5 py-1 inline-flex text-[10px] font-extrabold rounded-full bg-blue-50 text-blue-700 border border-blue-100 shadow-sm">
                                                                    Feed Post
                                                                </span>
                                                            )}
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            <div className="flex gap-1.5 flex-wrap max-w-[150px]">
                                                                {post.platforms && post.platforms.map((p: string) => {
                                                                    let emoji = "🌐";
                                                                    if (p === "facebook") emoji = "📘";
                                                                    if (p === "instagram") emoji = "📸";
                                                                    if (p === "tiktok") emoji = "🎵";
                                                                    if (p === "linkedin") emoji = "💼";
                                                                    return (
                                                                        <span key={p} className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-extrabold bg-gray-50 text-gray-600 border border-gray-150 capitalize" title={p}>
                                                                            <span>{emoji}</span>
                                                                            <span>{p}</span>
                                                                        </span>
                                                                    );
                                                                })}
                                                            </div>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap">
                                                            <span className={`px-2.5 py-0.5 inline-flex text-[10px] leading-5 font-black rounded-full capitalize
                                                                ${post.status === 'completed' || post.status === 'success' || post.status === 'synced' || post.status === 'published' ? 'bg-green-50 text-green-700 border border-green-100' :
                                                                    post.status === 'failed' ? 'bg-red-50 text-red-700 border border-red-100' :
                                                                        post.status === 'partial' ? 'bg-amber-50 text-amber-700 border border-amber-100' :
                                                                            'bg-yellow-50 text-yellow-700 border border-yellow-100'}`}>
                                                                {post.status}
                                                            </span>
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-xs text-gray-500 font-semibold">
                                                            {new Date(post.created_at).toLocaleDateString()}
                                                        </td>
                                                        <td className="px-6 py-4 whitespace-nowrap text-xs text-gray-500">
                                                            <div className="flex gap-2">
                                                                <button
                                                                    onClick={() => handleViewMetrics(post)}
                                                                    className="bg-blue-50 text-blue-600 hover:bg-blue-100 px-3 py-1.5 rounded-lg text-[10px] font-bold transition shadow-sm cursor-pointer"
                                                                >
                                                                    Insights
                                                                </button>
                                                                <button
                                                                    onClick={() => handleEditPost(post)}
                                                                    className="bg-yellow-50 text-yellow-700 hover:bg-yellow-100 px-3 py-1.5 rounded-lg text-[10px] font-bold transition shadow-sm cursor-pointer"
                                                                >
                                                                    Edit
                                                                </button>
                                                                <button
                                                                    onClick={() => handleDeletePost(post)}
                                                                    className="bg-red-50 text-red-600 hover:bg-red-100 px-3 py-1.5 rounded-lg text-[10px] font-bold transition shadow-sm cursor-pointer"
                                                                >
                                                                    Delete
                                                                </button>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                ))}
                                            </tbody>
                                        </table>
                                    </div>
                                )}
                            </div>
                        )}
                    </div>
                )}

                {/* VIEW: SETTINGS */}
                {activeSidebarTab === 'settings' && (
                    <div className="space-y-6 animate-fadeIn">
                        <div>
                            <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-2">
                                Settings & Configurations
                            </h1>
                            <p className="text-sm text-gray-500 font-semibold">
                                Manage agency profiles, key settings, and security tokens.
                            </p>
                        </div>

                        <div className="bg-white border border-gray-150 p-8 rounded-2xl shadow-sm max-w-2xl space-y-6">
                            <div className="border-b border-gray-100 pb-4">
                                <h3 className="text-base font-bold text-gray-800">User Profile Details</h3>
                                <p className="text-xs text-gray-400 font-medium">Verify your login details and platform credentials.</p>
                            </div>

                            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                                <div>
                                    <label className="text-[10px] font-extrabold uppercase tracking-wider text-gray-400 block mb-1">
                                        Full Name
                                    </label>
                                    <span className="text-sm font-bold text-gray-700 block">
                                        {userProfile?.full_name || 'Not set'}
                                    </span>
                                </div>
                                <div>
                                    <label className="text-[10px] font-extrabold uppercase tracking-wider text-gray-400 block mb-1">
                                        Email Address
                                    </label>
                                    <span className="text-sm font-bold text-gray-700 block">
                                        {userProfile?.email || 'Not set'}
                                    </span>
                                </div>
                                <div>
                                    <label className="text-[10px] font-extrabold uppercase tracking-wider text-gray-400 block mb-1">
                                        Account Type
                                    </label>
                                    <span className="text-sm font-bold text-gray-700 block">
                                        Rhongi Agency Administrator
                                    </span>
                                </div>
                                <div>
                                    <label className="text-[10px] font-extrabold uppercase tracking-wider text-gray-400 block mb-1">
                                        User ID
                                    </label>
                                    <span className="text-xs font-mono font-bold text-gray-500 block truncate" title={userProfile?.id}>
                                        {userProfile?.id || 'fetching...'}
                                    </span>
                                </div>
                            </div>
                        </div>
                    </div>
                )}

                {/* VIEW: HELP CENTER */}
                {activeSidebarTab === 'help' && (
                    <div className="space-y-6 animate-fadeIn">
                        <div>
                            <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-2">
                                Help & Support Center
                            </h1>
                            <p className="text-sm text-gray-500 font-semibold">
                                Answers to frequently asked questions about connections and publishing.
                            </p>
                        </div>

                        <div className="bg-white border border-gray-150 p-8 rounded-2xl shadow-sm max-w-2xl space-y-6">
                            <div className="space-y-4">
                                <div className="border-b border-gray-100 pb-3 last:border-0">
                                    <h4 className="text-sm font-bold text-gray-800 mb-1">How do I connect my Facebook Pages?</h4>
                                    <p className="text-xs text-gray-500 leading-relaxed font-semibold">
                                        Navigate to the "Connect Accounts" tab, click "Connect Facebook", and authorize Rhongi inside your Facebook account. Please ensure you authorize the specific Pages and Groups you wish to schedule posts for.
                                    </p>
                                </div>

                                <div className="border-b border-gray-100 pb-3 last:border-0">
                                    <h4 className="text-sm font-bold text-gray-800 mb-1">Why is my video publishing failing on Instagram?</h4>
                                    <p className="text-xs text-gray-500 leading-relaxed font-semibold">
                                        Instagram only supports video publishing on Business Profiles. Please verify that your Instagram account is linked to a Facebook Page and converted to an Instagram Business Profile.
                                    </p>
                                </div>

                                <div className="border-b border-gray-100 pb-3 last:border-0">
                                    <h4 className="text-sm font-bold text-gray-800 mb-1">Can I delete reels once published?</h4>
                                    <p className="text-xs text-gray-500 leading-relaxed font-semibold">
                                        While you can delete standard posts across connected accounts automatically, Instagram's API doesn't support automatic reel deletion. If you delete a Reel on Rhongi, you must manually delete it on your physical phone's Instagram app.
                                    </p>
                                </div>
                            </div>
                        </div>
                    </div>
                )}
            </main>

            {/* Insights / Metrics Modal */}
            {activeMetricsPost && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 transition-all duration-300">
                    <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden border border-gray-100 transform transition-all animate-scaleUp">
                        {/* Modal Header */}
                        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 px-6 py-4 text-white flex justify-between items-center shadow-md">
                            <h3 className="text-sm font-black uppercase tracking-wider">Post Insights & Analytics</h3>
                            <button 
                                onClick={() => setActiveMetricsPost(null)}
                                className="text-white hover:text-gray-200 transition text-2xl font-bold leading-none cursor-pointer"
                            >
                                &times;
                            </button>
                        </div>
                        
                        {/* Modal Body */}
                        <div className="p-6 space-y-6 max-h-[75vh] overflow-y-auto">
                            {/* Post Content Preview */}
                            <div className="bg-gray-50 rounded-xl p-4 border border-gray-150">
                                <span className="text-[10px] font-black text-gray-400 uppercase tracking-wider">Post Message</span>
                                <p className="text-gray-700 text-xs font-semibold mt-1.5 whitespace-pre-wrap">{activeMetricsPost.content}</p>
                                {activeMetricsPost.media_keys && activeMetricsPost.media_keys.length > 0 && (
                                     <div className="flex flex-col gap-3 mt-3">
                                         {activeMetricsPost.media_keys.map((url: string, idx: number) => {
                                             const isVideo = isVideoUrl(url);
                                             return isVideo ? (
                                                 <video 
                                                     key={idx}
                                                     src={url}
                                                     controls
                                                     className="w-full max-h-60 rounded-xl border border-gray-200 shadow-md bg-black"
                                                 />
                                             ) : (
                                                 <img 
                                                     key={idx} 
                                                     src={url} 
                                                     alt={`upload-${idx}`} 
                                                     className="w-full max-h-60 object-cover rounded-xl border border-gray-200 shadow-md"
                                                 />
                                             );
                                         })}
                                     </div>
                                 )}
                             </div>

                            {metricsLoading ? (
                                <div className="flex flex-col items-center justify-center py-12 space-y-3">
                                    <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    <span className="text-xs text-gray-500 font-bold">Fetching real-time insights...</span>
                                </div>
                            ) : metrics ? (
                                <div className="space-y-6">
                                    {/* Overall Metrics Grid */}
                                    <div>
                                        <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-wider mb-3">Total Engagement</h4>
                                        <div className="grid grid-cols-2 gap-4">
                                            {/* Views */}
                                            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded-xl p-4 flex flex-col justify-between shadow-sm">
                                                <span className="text-[10px] font-extrabold text-blue-600 uppercase">Estimated Reach</span>
                                                <span className="text-xl font-bold text-blue-900 mt-2">{metrics.total?.views || 0}</span>
                                            </div>
                                            {/* Likes */}
                                            <div className="bg-gradient-to-br from-pink-50 to-rose-50 border border-pink-100 rounded-xl p-4 flex flex-col justify-between shadow-sm">
                                                <span className="text-[10px] font-extrabold text-pink-600 uppercase">Reactions</span>
                                                <span className="text-xl font-bold text-rose-900 mt-2">{metrics.total?.likes || 0}</span>
                                            </div>
                                            {/* Comments */}
                                            <div className="bg-gradient-to-br from-purple-50 to-violet-50 border border-purple-100 rounded-xl p-4 flex flex-col justify-between shadow-sm">
                                                <span className="text-[10px] font-extrabold text-purple-600 uppercase">Comments</span>
                                                <span className="text-xl font-bold text-purple-900 mt-2">{metrics.total?.comments || 0}</span>
                                            </div>
                                            {/* Shares */}
                                            <div className="bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-100 rounded-xl p-4 flex flex-col justify-between shadow-sm">
                                                <span className="text-[10px] font-extrabold text-emerald-600 uppercase">Shares</span>
                                                <span className="text-xl font-bold text-emerald-900 mt-2">{metrics.total?.shares || 0}</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Breakdown by Platform */}
                                    {metrics.platforms && Object.keys(metrics.platforms).length > 0 && (
                                        <div>
                                            <h4 className="text-[10px] font-black text-gray-400 uppercase tracking-wider mb-3">Breakdown by Platform</h4>
                                            <div className="space-y-2.5">
                                                {Object.entries(metrics.platforms).map(([platform, platMetrics]: [string, any]) => (
                                                    <div key={platform} className="p-4 border border-gray-150 rounded-xl hover:bg-gray-50 transition space-y-3 bg-white">
                                                        <div className="flex justify-between items-center">
                                                            <span className="capitalize font-extrabold text-gray-700 flex items-center gap-2 text-xs">
                                                                <span className={`w-2.5 h-2.5 rounded-full ${
                                                                    platform === 'facebook' ? 'bg-[#1877F2]' : 
                                                                    platform === 'instagram' ? 'bg-[#E1306C]' : 
                                                                    platform === 'linkedin' ? 'bg-[#0A66C2]' : 
                                                                    platform === 'tiktok' ? 'bg-black' : 'bg-gray-400'
                                                                }`}></span>
                                                                {platform}
                                                            </span>
                                                            <div className="flex items-center gap-4 text-[10px] font-bold text-gray-500">
                                                                <span>{platMetrics.views || 0} views</span>
                                                                <span>{platMetrics.likes || 0} likes</span>
                                                                <span>{platMetrics.comments || 0} comments</span>
                                                            </div>
                                                        </div>

                                                        {platMetrics.permalink && (
                                                            <div className="pt-2 border-t border-gray-100">
                                                                <a 
                                                                    href={
                                                                        platMetrics.permalink.startsWith('http://') || 
                                                                        platMetrics.permalink.startsWith('https://') 
                                                                            ? platMetrics.permalink 
                                                                            : `https://www.facebook.com${platMetrics.permalink.startsWith('/') ? '' : '/'}${platMetrics.permalink}`
                                                                    }
                                                                    target="_blank"
                                                                    rel="noopener noreferrer"
                                                                    className={`w-full text-center block px-3 py-1.5 rounded-lg text-[10px] transition-all font-bold uppercase tracking-wider border ${
                                                                        platform === 'facebook' ? 'bg-blue-50 text-blue-600 hover:bg-blue-100 border-blue-100' :
                                                                        platform === 'instagram' ? 'bg-pink-50 text-pink-600 hover:bg-pink-100 border-pink-100' :
                                                                        platform === 'linkedin' ? 'bg-sky-50 text-sky-600 hover:bg-sky-100 border-sky-100' :
                                                                        'bg-gray-50 text-gray-600 hover:bg-gray-100 border-gray-100'
                                                                    }`}
                                                                >
                                                                    View Live Post ↗
                                                                </a>
                                                            </div>
                                                        )}

                                                        {/* Video processing progress */}
                                                        {platMetrics.video_status && (
                                                            <div className="bg-gray-50 border border-gray-150 rounded-xl p-3.5 space-y-2">
                                                                <div className="flex justify-between items-center text-[10px]">
                                                                    <span className="font-extrabold text-gray-500 uppercase tracking-wider">Video Status</span>
                                                                    <span className={`px-2.5 py-0.5 inline-flex text-[9px] leading-5 font-bold rounded-full capitalize
                                                                        ${platMetrics.video_status === 'ready' ? 'bg-green-100 text-green-800' :
                                                                          platMetrics.video_status === 'processing' ? 'bg-yellow-100 text-yellow-800 animate-pulse' :
                                                                          'bg-red-100 text-red-800'}`}>
                                                                        {platMetrics.video_status}
                                                                    </span>
                                                                </div>
                                                                {platMetrics.video_status === 'processing' && (
                                                                    <div className="space-y-1">
                                                                        <div className="w-full bg-gray-200 rounded-full h-1.5">
                                                                            <div 
                                                                                className="bg-blue-600 h-1.5 rounded-full transition-all duration-500" 
                                                                                style={{ width: `${platMetrics.video_progress || 0}%` }}
                                                                            ></div>
                                                                        </div>
                                                                        <div className="text-right text-[9px] font-black text-gray-400">
                                                                            {platMetrics.video_progress || 0}% Processed
                                                                        </div>
                                                                    </div>
                                                                )}
                                                                {platMetrics.video_status === 'ready' && (
                                                                    <p className="text-[10px] text-green-700 font-bold flex items-center gap-1.5">
                                                                        ✓ This Reel is live and fully processed.
                                                                    </p>
                                                                )}
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="text-center py-8 text-gray-500 font-bold text-xs">
                                    Failed to load metrics. Please try again.
                                </div>
                            )}
                        </div>
                        
                        {/* Modal Footer */}
                        <div className="bg-gray-50 px-6 py-4 flex justify-end border-t border-gray-100">
                            <button
                                onClick={() => setActiveMetricsPost(null)}
                                className="bg-gray-200 text-gray-800 px-4 py-2 rounded-xl font-bold hover:bg-gray-300 transition text-xs shadow-sm cursor-pointer"
                            >
                                Close
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Edit Post Modal */}
            {activeEditPost && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 transition-all duration-300">
                    <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden border border-gray-100 transform transition-all animate-scaleUp">
                        {/* Modal Header */}
                        <div className="bg-gradient-to-r from-yellow-500 to-amber-600 px-6 py-4 text-white flex justify-between items-center shadow-md">
                            <h3 className="text-sm font-black uppercase tracking-wider">Edit Post Message</h3>
                            <button 
                                onClick={() => setActiveEditPost(null)}
                                className="text-white hover:text-gray-200 transition text-2xl font-bold leading-none cursor-pointer"
                            >
                                &times;
                            </button>
                        </div>
                        
                        {/* Modal Body */}
                        <div className="p-6 space-y-4">
                            <div>
                                <label className="block text-[10px] font-black text-gray-400 uppercase tracking-wider mb-2">
                                    Post / Reel Caption
                                </label>
                                <textarea
                                    value={editContent}
                                    onChange={(e) => setEditContent(e.target.value)}
                                    rows={5}
                                    className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-yellow-500/20 focus:border-yellow-500 text-gray-700 text-xs font-semibold resize-none shadow-inner bg-slate-50/50"
                                    placeholder="Update your post message here..."
                                />
                            </div>
                            
                            {activeEditPost.media_keys && activeEditPost.media_keys.length > 0 && (
                                 <div>
                                     <span className="block text-[10px] font-black text-gray-400 uppercase tracking-wider mb-2">Media Attachment</span>
                                     {isVideoUrl(activeEditPost.media_keys[0]) ? (
                                         <video 
                                             src={activeEditPost.media_keys[0]} 
                                             preload="metadata"
                                             className="w-full max-h-40 object-cover rounded-xl border shadow-sm bg-black"
                                         />
                                     ) : (
                                         <img 
                                             src={activeEditPost.media_keys[0]} 
                                             alt="post media" 
                                             className="w-full max-h-40 object-cover rounded-xl border shadow-sm"
                                         />
                                     )}
                                 </div>
                            )}
                        </div>
                        
                        {/* Modal Footer */}
                        <div className="bg-gray-50 px-6 py-4 flex justify-end gap-3 border-t border-gray-100">
                            <button
                                onClick={() => setActiveEditPost(null)}
                                className="bg-gray-200 text-gray-800 px-4 py-2 rounded-xl font-bold hover:bg-gray-300 transition text-xs shadow-sm cursor-pointer"
                                disabled={editLoading}
                            >
                                Cancel
                            </button>
                            <button
                                onClick={handleSaveEdit}
                                className="bg-yellow-500 hover:bg-yellow-600 text-white px-4 py-2 rounded-xl font-bold transition text-xs shadow-sm flex items-center gap-2 cursor-pointer"
                                disabled={editLoading}
                            >
                                {editLoading ? 'Saving...' : 'Save Changes'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <SocialConnectModal
                isOpen={isConnectModalOpen}
                onClose={() => setIsConnectModalOpen(false)}
            />
        </div>
    );
}

export default function Dashboard() {
    return (
        <Suspense fallback={
            <div className="min-h-screen bg-slate-50 flex items-center justify-center">
                <span className="text-sm text-gray-500 font-semibold">Loading Dashboard Layout...</span>
            </div>
        }>
            <DashboardContent />
        </Suspense>
    );
}
