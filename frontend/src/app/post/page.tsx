'use client';
import { useState, ChangeEvent } from 'react';

export default function PostPage() {
    const [content, setContent] = useState('');
    const [platforms, setPlatforms] = useState<string[]>([]);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [message, setMessage] = useState('');
    const [mediaUrl, setMediaUrl] = useState('');
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [uploadProgress, setUploadProgress] = useState(0);

    const API_URL = process.env.NEXT_PUBLIC_API_URL;

    const togglePlatform = (p: string) => {
        setPlatforms(prev =>
            prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]
        );
    };

    const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            setSelectedFiles(Array.from(e.target.files));
            setMediaUrl(''); // Reset manual URL if files selected
        }
    };

    const uploadFile = async (file: File) => {
        const token = localStorage.getItem('token');
        if (!token) throw new Error("Not authenticated");

        // 1. Get Presigned URL
        const filename = `${Date.now()}-${file.name}`;
        const res = await fetch(`${API_URL}/media/upload-url?filename=${filename}&content_type=${file.type}`, {
            method: 'POST',
            headers: { 'Authorization': `Bearer ${token}` }
        });

        if (!res.ok) throw new Error("Failed to get upload URL");

        const { upload_url, public_url } = await res.json();

        // 2. Upload to MinIO/S3
        // Note: No Auth header for the direct PUT to S3/MinIO!
        const uploadRes = await fetch(upload_url, {
            method: 'PUT',
            body: file,
            headers: {
                'Content-Type': file.type
            }
        });

        if (!uploadRes.ok) throw new Error("Failed to upload file to storage");

        return public_url;
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        const token = localStorage.getItem('token');

        if (!token) {
            window.location.href = '/login';
            return;
        }

        if (platforms.length === 0) {
            alert("Select at least one platform");
            return;
        }

        setIsSubmitting(true);
        setMessage('');
        setUploadProgress(10);

        try {
            let finalMediaUrls: string[] = [];

            // Handle Multiple File Upload if selected
            if (selectedFiles.length > 0) {
                for (let i = 0; i < selectedFiles.length; i++) {
                    setMessage(`Uploading image ${i + 1} of ${selectedFiles.length}...`);
                    const url = await uploadFile(selectedFiles[i]);
                    finalMediaUrls.push(url);
                    setUploadProgress(Math.floor(10 + ((i + 1) / selectedFiles.length) * 40));
                }
            }

            // Validation for TikTok/Instagram
            const hasMedia = finalMediaUrls.length > 0 || mediaUrl;
            if ((platforms.includes('tiktok') || platforms.includes('instagram')) && !hasMedia) {
                throw new Error("Media is required for TikTok or Instagram!");
            }

            setMessage('Publishing post...');
            // 3. Create Post
            const res = await fetch(`${API_URL}/posts`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${token}`
                },
                body: JSON.stringify({
                    content: content,
                    media_key: finalMediaUrls[0] || mediaUrl || undefined,
                    media_keys: finalMediaUrls.length > 0 ? finalMediaUrls : (mediaUrl ? [mediaUrl] : undefined),
                    platforms: platforms
                })
            });

            const data = await res.json();

            if (res.ok) {
                setUploadProgress(100);
                setMessage(`Success! Post ID: ${data.id}`);
                setContent('');
                setPlatforms([]);
                setSelectedFiles([]);
                setMediaUrl('');
                setTimeout(() => {
                    window.location.href = '/dashboard';
                }, 1500);
            } else {
                setMessage(`Error: ${data.detail || 'Failed to post'}`);
            }
        } catch (err: any) {
            console.error(err);
            setMessage(err.message || 'Network error occurred');
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
                            />
                        </div>

                        {/* File Upload */}
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Upload Image/Video</label>
                            <div className="border-2 border-dashed border-gray-300 rounded-lg p-6 text-center hover:bg-gray-50 transition">
                                <input
                                    type="file"
                                    multiple
                                    onChange={handleFileChange}
                                    accept="image/*,video/*"
                                    className="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                                />
                                {selectedFiles.length > 0 && (
                                    <div className="mt-2 text-sm text-green-600 text-left">
                                        <p className="font-semibold">{selectedFiles.length} file(s) selected:</p>
                                        <ul className="list-disc list-inside text-xs mt-1">
                                            {selectedFiles.map((f, i) => (
                                                <li key={i}>{f.name}</li>
                                            ))}
                                        </ul>
                                    </div>
                                )}
                            </div>
                        </div>

                        {/* OR Manual URL */}
                        <div className="relative flex py-2 items-center">
                            <div className="flex-grow border-t border-gray-200"></div>
                            <span className="flex-shrink-0 mx-4 text-gray-400 text-xs">OR USE URL</span>
                            <div className="flex-grow border-t border-gray-200"></div>
                        </div>

                        <div>
                            <input
                                type="url"
                                value={mediaUrl}
                                onChange={e => setMediaUrl(e.target.value)}
                                disabled={selectedFiles.length > 0}
                                className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 disabled:bg-gray-100"
                                placeholder="https://example.com/image.jpg"
                            />
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
                                        className={`px-4 py-2 rounded-full border capitalize transition ${platforms.includes(p)
                                            ? 'bg-blue-600 text-white border-blue-600 shadow-md transform scale-105'
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
                            className="w-full bg-blue-600 text-white py-3 rounded-lg font-semibold hover:bg-blue-700 disabled:opacity-50 transition shadow-lg"
                        >
                            {isSubmitting ? (
                                <span className="flex items-center justify-center gap-2">
                                    Publishing... {uploadProgress > 0 && `${uploadProgress}%`}
                                </span>
                            ) : 'Publish Now'}
                        </button>

                        {/* Status Message */}
                        {message && (
                            <div className={`p-4 rounded-lg mt-4 text-center ${message.includes('Error') || message.includes('Failed') ? 'bg-red-50 text-red-700' : 'bg-blue-50 text-blue-700'}`}>
                                {message}
                            </div>
                        )}

                    </form>

                    <div className="mt-8 text-center">
                        <a href="/dashboard" className="text-blue-500 hover:underline">← Back to Dashboard</a>
                    </div>
                </div>
            </div>
        </div>
    );
}
