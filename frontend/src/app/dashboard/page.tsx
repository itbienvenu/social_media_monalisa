"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import SocialConnectModal from "../../components/SocialConnectModal";

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

function DashboardContent() {
    const router = useRouter();
    const [connections, setConnections] = useState<any[]>([]);
    const [posts, setPosts] = useState<any[]>([]);
    const [loading, setLoading] = useState(true);
    const [syncLoading, setSyncLoading] = useState(false);
    const [disconnectLoading, setDisconnectLoading] = useState<string | null>(null);
    const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);

    // Metrics Modal States
    const [activeMetricsPost, setActiveMetricsPost] = useState<any | null>(null);
    const [metrics, setMetrics] = useState<any | null>(null);
    const [metricsLoading, setMetricsLoading] = useState(false);

    useEffect(() => {
        const token = localStorage.getItem('token');
        if (!token) {
            router.push('/login');
            return;
        }

        const payload = decodeJwt(token);
        if (!payload || !payload.sub) {
            console.error("Invalid or unparseable token, redirecting to login");
            localStorage.removeItem('token');
            router.push('/login');
            return;
        }

        const fetchData = async () => {
            try {
                const [connRes, postsRes] = await Promise.all([
                    fetch(`${process.env.NEXT_PUBLIC_API_URL}/connections`, {
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'ngrok-skip-browser-warning': 'true'
                        }
                    }),
                    fetch(`${process.env.NEXT_PUBLIC_API_URL}/posts`, {
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'ngrok-skip-browser-warning': 'true'
                        }
                    })
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

                setLoading(false);
            } catch (e) {
                console.error("Error fetching data:", e);
                setLoading(false);
            }
        };

        fetchData();
    }, [router]);

    const handleDisconnect = async (platform: string) => {
        const token = localStorage.getItem('token');
        if (!confirm(`Are you sure you want to disconnect ${platform}?`)) return;

        setDisconnectLoading(platform);
        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/connections/${platform}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'ngrok-skip-browser-warning': 'true'
                }
            });
            if (res.ok) {
                // Update state
                setConnections(prev => prev.map(c => c.platform === platform ? { ...c, connected: false } : c));
            }
        } catch (e) {
            console.error(e);
        } finally {
            setDisconnectLoading(null);
        }
    };

    const handleSync = async () => {
        setSyncLoading(true);
        const token = localStorage.getItem('token');
        if (!token) {
            router.push('/login');
            return;
        }

        const payload = decodeJwt(token);
        if (!payload || !payload.sub) {
            console.error("Invalid token, redirecting to login");
            localStorage.removeItem('token');
            router.push('/login');
            return;
        }

        try {
            await fetch(`${process.env.NEXT_PUBLIC_API_URL}/posts/sync`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'ngrok-skip-browser-warning': 'true'
                }
            });
            // Refresh posts
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/posts`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'ngrok-skip-browser-warning': 'true'
                }
            });
            if (res.ok) setPosts(await res.json());
        } catch (e) {
            console.error(e);
        } finally {
            setSyncLoading(false);
        }
    };

    const handleViewMetrics = async (post: any) => {
        const token = localStorage.getItem('token');
        if (!token) {
            router.push('/login');
            return;
        }

        const payload = decodeJwt(token);
        if (!payload || !payload.sub) {
            console.error("Invalid token, redirecting to login");
            localStorage.removeItem('token');
            router.push('/login');
            return;
        }

        setActiveMetricsPost(post);
        setMetrics(null);
        setMetricsLoading(true);
        
        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/posts/${post.id}/metrics`, {
                headers: {
                    'Authorization': `Bearer ${token}`,
                    'ngrok-skip-browser-warning': 'true'
                }
            });
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

    if (loading) return <div>Loading dashboard...</div>;

    return (
        <div className="min-h-screen bg-gray-50 p-8">
            <main className="max-w-4xl mx-auto space-y-8">
                <div className="flex justify-between items-center">
                    <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
                    <button onClick={() => { localStorage.removeItem('token'); router.push('/login'); }} className="text-red-600 hover:text-red-800 text-sm font-semibold">Logout</button>
                </div>

                {/* Connections Section */}
                <div className="bg-white p-6 rounded-lg shadow">
                    <div className="flex justify-between items-center mb-4">
                        <h2 className="text-xl font-semibold text-gray-800">Connected Accounts</h2>
                        <button
                            onClick={() => setIsConnectModalOpen(true)}
                            className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition font-semibold"
                        >
                            Connect New Account
                        </button>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                        {connections.map((conn) => (
                            <div key={conn.platform} className={`p-4 rounded-lg border flex flex-col items-center gap-3 ${conn.connected ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'}`}>
                                <h3 className="capitalize font-semibold">{conn.platform}</h3>
                                {conn.connected ? (
                                    <>
                                        <span className="text-xs px-2 py-1 bg-green-200 text-green-800 rounded-full font-medium">Connected</span>
                                        <button
                                            onClick={() => handleDisconnect(conn.platform)}
                                            disabled={disconnectLoading === conn.platform}
                                            className="text-xs text-red-600 hover:underline mt-2 disabled:opacity-50 font-semibold"
                                        >
                                            {disconnectLoading === conn.platform ? 'Disconnecting...' : 'Disconnect'}
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <span className="text-xs px-2 py-1 bg-gray-200 text-gray-600 rounded-full font-medium">Not Connected</span>
                                        <a
                                            href={`/connect`}
                                            className="text-xs text-blue-600 hover:underline mt-2 font-semibold"
                                        >
                                            Connect
                                        </a>
                                    </>
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Posts Section */}
                <div className="bg-white p-6 rounded-lg shadow">
                    <div className="flex justify-between items-center mb-4">
                        <h2 className="text-xl font-semibold text-gray-800">Activity Feed</h2>
                        <div className="flex gap-2">
                            <button
                                onClick={handleSync}
                                disabled={syncLoading}
                                className="text-sm bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition disabled:opacity-50 flex items-center gap-2 font-semibold"
                            >
                                {syncLoading && (
                                    <svg className="animate-spin h-4 w-4 text-gray-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                )}
                                {syncLoading ? 'Syncing...' : 'Sync Posts'}
                            </button>
                            <a href="/post" className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition font-semibold">
                                Create Post
                            </a>
                        </div>
                    </div>

                    {(!posts || posts.length === 0) ? (
                        <p className="text-gray-500 text-center py-8">No posts yet. Create your first one!</p>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="min-w-full divide-y divide-gray-200">
                                <thead className="bg-gray-50">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Content</th>
                                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Status</th>
                                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Date</th>
                                        <th className="px-6 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-gray-200">
                                    {posts.map((post) => (
                                        <tr key={post.id} className="hover:bg-gray-50 transition">
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 max-w-xs truncate">
                                                <div className="flex items-center gap-3">
                                                    {post.media_keys && post.media_keys.length > 0 && (
                                                        <img 
                                                            src={post.media_keys[0]} 
                                                            alt="post thumbnail" 
                                                            className="w-10 h-10 object-cover rounded-lg border shadow-sm"
                                                        />
                                                    )}
                                                    <span>{post.content}</span>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                <span className={`px-2.5 py-1 inline-flex text-xs leading-5 font-semibold rounded-full 
                                                    ${post.status === 'completed' || post.status === 'success' || post.status === 'synced' ? 'bg-green-100 text-green-800' :
                                                        post.status === 'failed' ? 'bg-red-100 text-red-800' :
                                                            'bg-yellow-100 text-yellow-800'}`}>
                                                    {post.status}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                {new Date(post.created_at).toLocaleDateString()}
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                <button
                                                    onClick={() => handleViewMetrics(post)}
                                                    className="bg-blue-50 text-blue-600 hover:bg-blue-100 px-3 py-1.5 rounded-lg text-xs font-bold transition shadow-sm"
                                                >
                                                    Insights
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </main>

            {/* Insights Modal */}
            {activeMetricsPost && (
                <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center p-4 z-50 transition-all duration-300">
                    <div className="bg-white rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden border border-gray-100 transform transition-all">
                        {/* Modal Header */}
                        <div className="bg-gradient-to-r from-blue-600 to-indigo-700 px-6 py-4 text-white flex justify-between items-center shadow-md">
                            <h3 className="text-lg font-bold">Post Insights & Analytics</h3>
                            <button 
                                onClick={() => setActiveMetricsPost(null)}
                                className="text-white hover:text-gray-200 transition text-2xl font-bold leading-none"
                            >
                                &times;
                            </button>
                        </div>
                        
                        {/* Modal Body */}
                        <div className="p-6 space-y-6 max-h-[80vh] overflow-y-auto">
                            {/* Post Content Preview */}
                            <div className="bg-gray-50 rounded-xl p-4 border border-gray-100">
                                <span className="text-xs font-bold text-gray-400 uppercase tracking-wider">Post Message</span>
                                <p className="text-gray-700 text-sm mt-1.5 whitespace-pre-wrap">{activeMetricsPost.content}</p>
                                {activeMetricsPost.media_keys && activeMetricsPost.media_keys.length > 0 && (
                                    <div className="flex gap-2 mt-3 overflow-x-auto py-1">
                                        {activeMetricsPost.media_keys.map((url: string, idx: number) => (
                                            <img 
                                                key={idx} 
                                                src={url} 
                                                alt={`upload-${idx}`} 
                                                className="w-16 h-16 object-cover rounded-lg border border-gray-200 shadow-sm"
                                            />
                                        ))}
                                    </div>
                                )}
                            </div>

                            {metricsLoading ? (
                                <div className="flex flex-col items-center justify-center py-12 space-y-3">
                                    <svg className="animate-spin h-8 w-8 text-blue-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                    <span className="text-sm text-gray-500 font-semibold">Fetching real-time insights...</span>
                                </div>
                            ) : metrics ? (
                                <div className="space-y-6">
                                    {/* Overall Metrics Grid */}
                                    <div>
                                        <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Total Engagement</h4>
                                        <div className="grid grid-cols-2 gap-4">
                                            {/* Views */}
                                            <div className="bg-gradient-to-br from-blue-50 to-indigo-50 border border-blue-100 rounded-xl p-4 flex flex-col justify-between shadow-sm">
                                                <span className="text-xs font-bold text-blue-600 uppercase">Estimated Reach</span>
                                                <span className="text-2xl font-bold text-blue-900 mt-2">{metrics.total.views}</span>
                                            </div>
                                            {/* Likes */}
                                            <div className="bg-gradient-to-br from-pink-50 to-rose-50 border border-pink-100 rounded-xl p-4 flex flex-col justify-between shadow-sm">
                                                <span className="text-xs font-bold text-pink-600 uppercase">Reactions</span>
                                                <span className="text-2xl font-bold text-rose-900 mt-2">{metrics.total.likes}</span>
                                            </div>
                                            {/* Comments */}
                                            <div className="bg-gradient-to-br from-purple-50 to-violet-50 border border-purple-100 rounded-xl p-4 flex flex-col justify-between shadow-sm">
                                                <span className="text-xs font-bold text-purple-600 uppercase">Comments</span>
                                                <span className="text-2xl font-bold text-purple-900 mt-2">{metrics.total.comments}</span>
                                            </div>
                                            {/* Shares */}
                                            <div className="bg-gradient-to-br from-emerald-50 to-teal-50 border border-emerald-100 rounded-xl p-4 flex flex-col justify-between shadow-sm">
                                                <span className="text-xs font-bold text-emerald-600 uppercase">Shares</span>
                                                <span className="text-2xl font-bold text-emerald-900 mt-2">{metrics.total.shares}</span>
                                            </div>
                                        </div>
                                    </div>

                                    {/* Breakdown by Platform */}
                                    {Object.keys(metrics.platforms).length > 0 && (
                                        <div>
                                            <h4 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">Breakdown by Platform</h4>
                                            <div className="space-y-2">
                                                {Object.entries(metrics.platforms).map(([platform, platMetrics]: [string, any]) => (
                                                    <div key={platform} className="flex justify-between items-center p-3.5 border border-gray-100 rounded-xl hover:bg-gray-50 transition">
                                                        <span className="capitalize font-semibold text-gray-700 flex items-center gap-2">
                                                            <span className={`w-2.5 h-2.5 rounded-full ${platform === 'facebook' ? 'bg-blue-600' : 'bg-gray-400'}`}></span>
                                                            {platform}
                                                        </span>
                                                        <div className="flex gap-4 text-xs font-bold text-gray-500">
                                                            <span>{platMetrics.views} views</span>
                                                            <span>{platMetrics.likes} likes</span>
                                                            <span>{platMetrics.comments} comments</span>
                                                        </div>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            ) : (
                                <div className="text-center py-8 text-gray-500 font-medium">
                                    Failed to load metrics. Please try again.
                                </div>
                            )}
                        </div>
                        
                        {/* Modal Footer */}
                        <div className="bg-gray-50 px-6 py-4 flex justify-end">
                            <button
                                onClick={() => setActiveMetricsPost(null)}
                                className="bg-gray-200 text-gray-800 px-4 py-2 rounded-xl font-bold hover:bg-gray-300 transition text-sm shadow-sm"
                            >
                                Close
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
        <Suspense fallback={<div>Loading...</div>}>
            <DashboardContent />
        </Suspense>
    );
}
