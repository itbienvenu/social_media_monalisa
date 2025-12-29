'use client';
import { useState } from 'react';

export default function PostPage() {
    const [content, setContent] = useState('');
    const [platforms, setPlatforms] = useState<string[]>([]);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [message, setMessage] = useState('');
    const [mediaUrl, setMediaUrl] = useState('');

    const API_URL = process.env.NEXT_PUBLIC_API_URL;
    const USER_ID = "test-user";

    const togglePlatform = (p: string) => {
        setPlatforms(prev =>
            prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]
        );
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (platforms.length === 0) {
            alert("Select at least one platform");
            return;
        }

        setIsSubmitting(true);
        setMessage('');

        try {
            const res = await fetch(`${API_URL}/posts`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_id: USER_ID,
                    content: content,
                    media_url: mediaUrl || undefined, // Send undefined if empty
                    platforms: platforms
                })
            });
            const data = await res.json();

            if (res.ok) {
                setMessage(`Success! Post ID: ${data.post_id}`);
                setContent('');
                setPlatforms([]);
            } else {
                setMessage(`Error: ${data.detail || 'Failed to post'}`);
            }
        } catch (err) {
            console.error(err);
            setMessage('Network error occurred');
        } finally {
            setIsSubmitting(false);
        }
    };

    return (
        <div className="min-h-screen bg-gray-50 p-8">
            <div className="max-w-2xl mx-auto bg-white rounded-xl shadow-md overflow-hidden">
                <div className="p-8">
                    <h1 className="text-2xl font-bold mb-6 text-gray-800">Create New Post</h1>

                    <form onSubmit={handleSubmit} className="space-y-6">

                        {/* Content */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Message</label>
                            <textarea
                                value={content}
                                onChange={e => setContent(e.target.value)}
                                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 h-32"
                                placeholder="What's on your mind?"
                                required
                            />
                        </div>

                        {/* Media URL (Temporary until we add upload) */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Media URL (Optional)</label>
                            <input
                                type="url"
                                value={mediaUrl}
                                onChange={e => setMediaUrl(e.target.value)}
                                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                                placeholder="https://example.com/image.jpg"
                            />
                            <p className="text-xs text-gray-500 mt-1">Required for TikTok/Instagram</p>
                        </div>

                        {/* Platforms */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Select Platforms</label>
                            <div className="flex space-x-4">
                                {['facebook', 'instagram', 'tiktok', 'linkedin'].map(p => (
                                    <button
                                        key={p}
                                        type="button"
                                        onClick={() => togglePlatform(p)}
                                        className={`px-4 py-2 rounded-full border capitalize ${platforms.includes(p)
                                                ? 'bg-blue-600 text-white border-blue-600'
                                                : 'bg-white text-gray-700 border-gray-300 hover:bg-gray-50'
                                            }`}
                                    >
                                        {p}
                                    </button>
                                ))}
                            </div>
                        </div>

                        {/* Submit */}
                        <button
                            type="submit"
                            disabled={isSubmitting}
                            className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50"
                        >
                            {isSubmitting ? 'Publishing...' : 'Publish Now'}
                        </button>

                        {/* Status Message */}
                        {message && (
                            <div className={`p-4 rounded-lg mt-4 ${message.includes('Error') ? 'bg-red-50 text-red-700' : 'bg-green-50 text-green-700'}`}>
                                {message}
                            </div>
                        )}

                    </form>

                    <div className="mt-8 text-center">
                        <a href="/" className="text-blue-500 hover:underline">← Back to Dashboard</a>
                    </div>
                </div>
            </div>
        </div>
    );
}
