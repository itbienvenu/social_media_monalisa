"use client";

import { useState } from 'react';
import { apiFetch } from '../utils/api';

// User might not have heroicons, check package later. For now I'll use text X or assume standard Setup.
// Actually, safest to use standard SVGs if I don't know the deps.
// I will use simple SVGs to be safe.

interface SocialConnectModalProps {
    isOpen: boolean;
    onClose: () => void;
}

export default function SocialConnectModal({ isOpen, onClose }: SocialConnectModalProps) {
    const socialPlatforms = [
        { name: 'Facebook', id: 'facebook', color: 'bg-[#1877F2]', hover: 'hover:bg-[#1559b3]' },
        { name: 'Instagram', id: 'instagram', color: 'bg-gradient-to-r from-[#833AB4] via-[#FD1D1D] to-[#FCAF45]', hover: 'hover:opacity-90' },
        { name: 'LinkedIn', id: 'linkedin', color: 'bg-[#0077b5]', hover: 'hover:bg-[#005e93]' },
        { name: 'TikTok', id: 'tiktok', color: 'bg-[#000000]', hover: 'hover:bg-[#333333]' },
    ];

    const [loadingPlatform, setLoadingPlatform] = useState<string | null>(null);

    const handleConnect = async (platform: string) => {
        setLoadingPlatform(platform);
        const token = localStorage.getItem('token');
        if (!token) {
            alert("You must be logged in to connect accounts.");
            setLoadingPlatform(null);
            return;
        }

        try {
            const res = await apiFetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/${platform}/connect`, {
                method: 'POST'
            });

            if (!res.ok) {
                const errText = await res.text();
                console.error("Connect failed:", errText);
                alert(`Failed to initiate connection: ${errText}`);
                return;
            }

            const data = await res.json();
            if (data.url) {
                // Redirect user to the OAuth provider
                window.location.href = data.url;
            } else {
                console.error("No URL returned:", data);
                alert("Service returned invalid response.");
            }

        } catch (e) {
            console.error("Connection error:", e);
            alert("An error occurred while connecting.");
        } finally {
            setLoadingPlatform(null);
        }
    };

    if (!isOpen) return null;

    return (
        <div className="fixed inset-0 z-50 overflow-y-auto">
            {/* Backdrop */}
            <div className="fixed inset-0 bg-black/50 transition-opacity" onClick={onClose}></div>

            <div className="flex min-h-screen items-center justify-center p-4 text-center sm:p-0">
                <div className="relative transform overflow-hidden rounded-lg bg-white text-left shadow-xl transition-all sm:my-8 sm:w-full sm:max-w-lg z-10">
                    <div className="bg-white px-4 pb-4 pt-5 sm:p-6 sm:pb-4">
                        <div className="sm:flex sm:items-start">
                            <div className="mt-3 text-center sm:ml-4 sm:mt-0 sm:text-left w-full">
                                <div className="flex justify-between items-center mb-4">
                                    <h3 className="text-xl font-semibold leading-6 text-gray-900" id="modal-title">
                                        Connect a Social Account
                                    </h3>
                                    <button
                                        type="button"
                                        className="rounded-md bg-white text-gray-400 hover:text-gray-500 focus:outline-none"
                                        onClick={onClose}
                                    >
                                        <span className="sr-only">Close</span>
                                        <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" strokeWidth="1.5" stroke="currentColor" aria-hidden="true">
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                        </svg>
                                    </button>
                                </div>
                                <div className="mt-2">
                                    <p className="text-sm text-gray-500 mb-6">
                                        Select a platform to connect. You will be redirected to verify your account.
                                    </p>

                                    <div className="grid grid-cols-1 gap-3">
                                        {socialPlatforms.map((platform) => (
                                            <button
                                                key={platform.id}
                                                onClick={() => handleConnect(platform.id)}
                                                disabled={loadingPlatform === platform.id}
                                                className={`w-full flex items-center justify-center gap-3 px-4 py-3 border border-transparent text-base font-medium rounded-md text-white shadow-sm ${platform.color} ${platform.hover} transition-all duration-200 disabled:opacity-50 disabled:cursor-wait`}
                                            >
                                                <span>{loadingPlatform === platform.id ? 'Connecting...' : `Connect ${platform.name}`}</span>
                                            </button>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    );
}
