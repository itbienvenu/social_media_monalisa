"use client";

import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import SocialConnectModal from "../../components/SocialConnectModal";

function decodeJwt(token: string) {
    try {
        const base64Url = token.split('.')[1];
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

    if (loading) return <div>Loading dashboard...</div>;

    return (
        <div className="min-h-screen bg-gray-50 p-8">
            <main className="max-w-4xl mx-auto space-y-8">
                <div className="flex justify-between items-center">
                    <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
                    <button onClick={() => { localStorage.removeItem('token'); router.push('/login'); }} className="text-red-600 hover:text-red-800 text-sm">Logout</button>
                </div>

                {/* Connections Section */}
                <div className="bg-white p-6 rounded-lg shadow">
                    <div className="flex justify-between items-center mb-4">
                        <h2 className="text-xl font-semibold text-gray-800">Connected Accounts</h2>
                        <button
                            onClick={() => setIsConnectModalOpen(true)}
                            className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
                        >
                            Connect New Account
                        </button>
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-4">
                        {connections.map((conn) => (
                            <div key={conn.platform} className={`p-4 rounded-lg border flex flex-col items-center gap-3 ${conn.connected ? 'border-green-200 bg-green-50' : 'border-gray-200 bg-gray-50'}`}>
                                <h3 className="capitalize font-medium">{conn.platform}</h3>
                                {conn.connected ? (
                                    <>
                                        <span className="text-xs px-2 py-1 bg-green-200 text-green-800 rounded-full">Connected</span>
                                        <button
                                            onClick={() => handleDisconnect(conn.platform)}
                                            disabled={disconnectLoading === conn.platform}
                                            className="text-xs text-red-600 hover:underline mt-2 disabled:opacity-50"
                                        >
                                            {disconnectLoading === conn.platform ? 'Disconnecting...' : 'Disconnect'}
                                        </button>
                                    </>
                                ) : (
                                    <>
                                        <span className="text-xs px-2 py-1 bg-gray-200 text-gray-600 rounded-full">Not Connected</span>
                                        <a
                                            href={`/connect`}
                                            className="text-xs text-blue-600 hover:underline mt-2"
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
                                className="text-sm bg-gray-100 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-200 transition disabled:opacity-50 flex items-center gap-2"
                            >
                                {syncLoading && (
                                    <svg className="animate-spin h-4 w-4 text-gray-600" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                    </svg>
                                )}
                                {syncLoading ? 'Syncing...' : 'Sync Posts'}
                            </button>
                            <a href="/post" className="text-sm bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition">
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
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Content</th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Date</th>
                                    </tr>
                                </thead>
                                <tbody className="bg-white divide-y divide-gray-200">
                                    {posts.map((post) => (
                                        <tr key={post.id}>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900 max-w-xs truncate">{post.content}</td>
                                            <td className="px-6 py-4 whitespace-nowrap">
                                                <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full 
                                                    ${post.status === 'completed' ? 'bg-green-100 text-green-800' :
                                                        post.status === 'failed' ? 'bg-red-100 text-red-800' :
                                                            'bg-yellow-100 text-yellow-800'}`}>
                                                    {post.status}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                                {new Date(post.created_at).toLocaleDateString()}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </main>

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
