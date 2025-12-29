'use client';
import { useState } from 'react';

export default function ConnectPage() {
    const [loading, setLoading] = useState(false);
    const API_URL = process.env.NEXT_PUBLIC_API_URL;
    const USER_ID = "test-user"; // Hardcoded for MVP

    const handleConnect = async (platform: string) => {
        setLoading(true);
        try {
            const res = await fetch(`${API_URL}/auth/${platform}/connect?user_id=${USER_ID}`, {
                method: 'POST'
            });
            const data = await res.json();

            if (data.url) {
                window.location.href = data.url;
            } else {
                alert('Failed to get auth URL');
            }
        } catch (e) {
            console.error(e);
            alert('Error connecting to ' + platform);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 p-8">
            <div className="max-w-2xl mx-auto bg-white rounded-xl shadow-md overflow-hidden">
                <div className="p-8">
                    <h1 className="text-2xl font-bold mb-6 text-gray-800">Connect Your Accounts</h1>

                    <div className="space-y-4">
                        {/* Facebook */}
                        <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                            <div className="flex items-center space-x-3">
                                <span className="text-2xl">📘</span>
                                <div>
                                    <h3 className="font-semibold">Facebook</h3>
                                    <p className="text-sm text-gray-500">Pages & Groups</p>
                                </div>
                            </div>
                            <button
                                onClick={() => handleConnect('facebook')}
                                disabled={loading}
                                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                            >
                                Connect
                            </button>
                        </div>

                        {/* Instagram */}
                        <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                            <div className="flex items-center space-x-3">
                                <span className="text-2xl">📸</span>
                                <div>
                                    <h3 className="font-semibold">Instagram</h3>
                                    <p className="text-sm text-gray-500">Business Accounts</p>
                                </div>
                            </div>
                            <button
                                onClick={() => handleConnect('instagram')}
                                disabled={loading}
                                className="px-4 py-2 bg-pink-600 text-white rounded hover:bg-pink-700 disabled:opacity-50"
                            >
                                Connect
                            </button>
                        </div>

                        {/* TikTok */}
                        <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                            <div className="flex items-center space-x-3">
                                <span className="text-2xl">🎵</span>
                                <div>
                                    <h3 className="font-semibold">TikTok</h3>
                                    <p className="text-sm text-gray-500">Video Publishing</p>
                                </div>
                            </div>
                            <button
                                onClick={() => handleConnect('tiktok')}
                                disabled={loading}
                                className="px-4 py-2 bg-black text-white rounded hover:bg-gray-800 disabled:opacity-50"
                            >
                                Connect
                            </button>
                        </div>

                        {/* LinkedIn */}
                        <div className="flex items-center justify-between p-4 border border-gray-200 rounded-lg opacity-50">
                            <div className="flex items-center space-x-3">
                                <span className="text-2xl">💼</span>
                                <div>
                                    <h3 className="font-semibold">LinkedIn</h3>
                                    <p className="text-sm text-gray-500">Coming Soon</p>
                                </div>
                            </div>
                            <button disabled className="px-4 py-2 bg-gray-300 text-white rounded cursor-not-allowed">
                                Connect
                            </button>
                        </div>
                    </div>

                    <div className="mt-8 text-center">
                        <a href="/" className="text-blue-500 hover:underline">← Back to Dashboard</a>
                    </div>
                </div>
            </div>
        </div>
    );
}
