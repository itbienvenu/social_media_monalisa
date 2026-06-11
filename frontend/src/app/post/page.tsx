'use client';
import { useState, ChangeEvent, useEffect, useRef } from 'react';
import { apiFetch } from '../../utils/api';

export default function PostPage() {
    const [content, setContent] = useState('');
    const [platforms, setPlatforms] = useState<string[]>([]);
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [message, setMessage] = useState('');
    const [mediaUrl, setMediaUrl] = useState('');
    const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
    const [uploadProgress, setUploadProgress] = useState(0);
    const [isReel, setIsReel] = useState(false);

    // Audio & Slideshow compilation state
    const [audioFile, setAudioFile] = useState<File | null>(null);
    const [musicVolume, setMusicVolume] = useState<number>(0.2);
    const [videoVolume, setVideoVolume] = useState<number>(1.0);
    const [slideshowDuration, setSlideshowDuration] = useState<number>(10);

    // Real-time local media URLs for preview
    const [videoLocalUrl, setVideoLocalUrl] = useState<string>('');
    const [audioLocalUrl, setAudioLocalUrl] = useState<string>('');
    const [imageLocalUrls, setImageLocalUrls] = useState<string[]>([]);
    
    // Playback sync refs and states
    const videoRef = useRef<HTMLVideoElement | null>(null);
    const audioRef = useRef<HTMLAudioElement | null>(null);
    const [isPreviewPlaying, setIsPreviewPlaying] = useState(false);
    const [currentSlideIndex, setCurrentSlideIndex] = useState(0);
    const [manualSlideIndex, setManualSlideIndex] = useState(0);

    // Facebook Pages target selection
    const [facebookPages, setFacebookPages] = useState<{ target_id: string; target_name: string }[]>([]);
    const [selectedFacebookPage, setSelectedFacebookPage] = useState<string>('');
    const [loadingPages, setLoadingPages] = useState<boolean>(false);

    // Account connections
    const [connections, setConnections] = useState<{ platform: string; connected: boolean }[]>([]);
    const [loadingConnections, setLoadingConnections] = useState(true);

    const API_URL = process.env.NEXT_PUBLIC_API_URL;

    useEffect(() => {
        const fetchConnections = async () => {
            try {
                const res = await apiFetch(`${API_URL}/connections`);
                if (res.ok) {
                    setConnections(await res.json());
                }
            } catch (err) {
                console.error("Failed to fetch connections:", err);
            } finally {
                setLoadingConnections(false);
            }
        };
        fetchConnections();
    }, [API_URL]);

    // Sync local object URLs for preview files
    useEffect(() => {
        const imgUrls: string[] = [];
        let vidUrl = '';
        selectedFiles.forEach(f => {
            if (f.type.startsWith('image/')) {
                imgUrls.push(URL.createObjectURL(f));
            } else if (f.type.startsWith('video/')) {
                vidUrl = URL.createObjectURL(f);
            }
        });
        setImageLocalUrls(imgUrls);
        setVideoLocalUrl(vidUrl);
        setCurrentSlideIndex(0);
        setManualSlideIndex(0);

        return () => {
            imgUrls.forEach(url => URL.revokeObjectURL(url));
            if (vidUrl) URL.revokeObjectURL(vidUrl);
        };
    }, [selectedFiles]);

    useEffect(() => {
        let audUrl = '';
        if (audioFile) {
            audUrl = URL.createObjectURL(audioFile);
        }
        setAudioLocalUrl(audUrl);

        return () => {
            if (audUrl) URL.revokeObjectURL(audUrl);
        };
    }, [audioFile]);

    // Slideshow interval cycling
    useEffect(() => {
        let timer: any;
        if (isPreviewPlaying && isReel && imageLocalUrls.length > 0) {
            const durationPerImage = (slideshowDuration / imageLocalUrls.length) * 1000;
            timer = setInterval(() => {
                setCurrentSlideIndex(prev => (prev + 1) % imageLocalUrls.length);
            }, durationPerImage);
        } else {
            setCurrentSlideIndex(0);
        }
        return () => clearInterval(timer);
    }, [isPreviewPlaying, isReel, imageLocalUrls, slideshowDuration]);

    // Update video and audio volumes instantly
    useEffect(() => {
        if (videoRef.current) {
            videoRef.current.volume = videoVolume;
        }
    }, [videoVolume, videoLocalUrl]);

    useEffect(() => {
        if (audioRef.current) {
            audioRef.current.volume = musicVolume;
        }
    }, [musicVolume, audioLocalUrl]);

    const togglePlayPreview = () => {
        if (isPreviewPlaying) {
            if (videoRef.current) videoRef.current.pause();
            if (audioRef.current) audioRef.current.pause();
            setIsPreviewPlaying(false);
        } else {
            if (videoRef.current) {
                videoRef.current.currentTime = 0;
                videoRef.current.play().catch(e => console.error("Video play error:", e));
            }
            if (audioRef.current) {
                audioRef.current.currentTime = 0;
                audioRef.current.play().catch(e => console.error("Audio play error:", e));
            }
            setIsPreviewPlaying(true);
        }
    };

    const handleVideoEnded = () => {
        if (videoRef.current) {
            videoRef.current.currentTime = 0;
            videoRef.current.play().catch(() => {});
        }
        if (audioRef.current) {
            audioRef.current.currentTime = 0;
            audioRef.current.play().catch(() => {});
        }
    };

    const fetchFacebookPages = async () => {
        setLoadingPages(true);
        try {
            const res = await apiFetch(`${API_URL}/facebook/targets`);
            if (res.ok) {
                const data = await res.json();
                const pagesOnly = data.filter((t: any) => t.target_type === 'page');
                setFacebookPages(pagesOnly);
                if (pagesOnly.length > 0) {
                    setSelectedFacebookPage(pagesOnly[0].target_id);
                }
            }
        } catch (err) {
            console.error("Failed to fetch Facebook pages:", err);
        } finally {
            setLoadingPages(false);
        }
    };

    const togglePlatform = (p: string) => {
        setPlatforms(prev => {
            const next = prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p];
            if (p === 'facebook' && next.includes('facebook') && facebookPages.length === 0) {
                fetchFacebookPages();
            }
            return next;
        });
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
        const res = await apiFetch(`${API_URL}/media/upload-url?filename=${filename}&content_type=${file.type}`, {
            method: 'POST'
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
            let finalAudioUrl = '';

            // Handle Multiple File Upload if selected
            if (selectedFiles.length > 0) {
                for (let i = 0; i < selectedFiles.length; i++) {
                    setMessage(`Uploading image ${i + 1} of ${selectedFiles.length}...`);
                    const url = await uploadFile(selectedFiles[i]);
                    finalMediaUrls.push(url);
                    setUploadProgress(Math.floor(10 + ((i + 1) / selectedFiles.length) * 40));
                }
            }

            // Upload audio file if selected
            if (audioFile) {
                setMessage("Uploading background audio...");
                finalAudioUrl = await uploadFile(audioFile);
            }

            // Validation for TikTok/Instagram
            const hasMedia = finalMediaUrls.length > 0 || mediaUrl;
            if ((platforms.includes('tiktok') || platforms.includes('instagram')) && !hasMedia) {
                throw new Error("Media is required for TikTok or Instagram!");
            }

            setMessage('Publishing post...');
            // 3. Create Post
            const res = await apiFetch(`${API_URL}/posts`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    content: content,
                    media_key: finalMediaUrls[0] || mediaUrl || undefined,
                    media_keys: finalMediaUrls.length > 0 ? finalMediaUrls : (mediaUrl ? [mediaUrl] : undefined),
                    platforms: platforms,
                    is_reel: isReel,
                    facebook_page_id: platforms.includes('facebook') && selectedFacebookPage ? selectedFacebookPage : undefined,
                    audio_key: finalAudioUrl || undefined,
                    music_volume: musicVolume,
                    video_volume: videoVolume,
                    slideshow_duration: slideshowDuration
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
            <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-5 gap-8 items-start">
                
                {/* Form Column */}
                <div className="lg:col-span-3 bg-white rounded-xl shadow-md p-8">
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

                        {/* Reel Toggle */}
                        <div className="flex items-center space-x-3 bg-blue-50 p-4 rounded-lg border border-blue-200">
                            <input
                                type="checkbox"
                                id="isReel"
                                checked={isReel}
                                onChange={e => setIsReel(e.target.checked)}
                                className="h-5 w-5 text-blue-600 focus:ring-blue-500 border-gray-300 rounded cursor-pointer"
                            />
                            <div className="select-none cursor-pointer">
                                <label htmlFor="isReel" className="block text-sm font-semibold text-blue-900 cursor-pointer">
                                    Publish Video as Reel / Short
                                </label>
                                <span className="block text-xs text-blue-700">
                                    If enabled, video uploads will be published as Reels (Facebook) instead of standard feed posts.
                                </span>
                            </div>
                        </div>

                        {/* Background Music & Slideshow Settings */}
                        {(isReel || selectedFiles.some(f => f.type.startsWith('video/'))) && (
                            <div className="bg-gray-50 p-5 rounded-lg border border-gray-200 space-y-4">
                                <h3 className="text-sm font-semibold text-gray-800 flex items-center">
                                    🎵 Background Music & Slideshow settings
                                </h3>
                                
                                {/* Background Music Upload */}
                                <div>
                                    <label className="block text-xs font-medium text-gray-500 mb-1">
                                        Upload Background Music (MP3 / Audio)
                                    </label>
                                    <input
                                        type="file"
                                        accept="audio/*"
                                        onChange={e => {
                                            if (e.target.files && e.target.files.length > 0) {
                                                setAudioFile(e.target.files[0]);
                                            } else {
                                                setAudioFile(null);
                                            }
                                        }}
                                        className="w-full text-xs text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-xs file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100"
                                    />
                                    {audioFile && (
                                        <p className="text-xs text-green-600 mt-1">
                                            ✓ Selected: {audioFile.name}
                                        </p>
                                    )}
                                </div>

                                {/* Volume Sliders */}
                                {audioFile && (
                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-xs font-medium text-gray-600 mb-1">
                                                Music Volume: {Math.round(musicVolume * 100)}%
                                            </label>
                                            <input
                                                type="range"
                                                min="0"
                                                max="1"
                                                step="0.05"
                                                value={musicVolume}
                                                onChange={e => setMusicVolume(parseFloat(e.target.value))}
                                                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-xs font-medium text-gray-600 mb-1">
                                                Original Video Volume: {Math.round(videoVolume * 100)}%
                                            </label>
                                            <input
                                                type="range"
                                                min="0"
                                                max="1"
                                                step="0.05"
                                                value={videoVolume}
                                                onChange={e => setVideoVolume(parseFloat(e.target.value))}
                                                className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                                            />
                                        </div>
                                    </div>
                                )}

                                {/* Slideshow Duration (Only if we have images and are compiling to Reel) */}
                                {isReel && selectedFiles.length > 0 && selectedFiles.every(f => f.type.startsWith('image/')) && (
                                    <div>
                                        <label className="block text-xs font-medium text-gray-600 mb-1">
                                            Slideshow Duration (seconds): {slideshowDuration}s
                                        </label>
                                        <input
                                            type="range"
                                            min="3"
                                            max="30"
                                            step="1"
                                            value={slideshowDuration}
                                            onChange={e => setSlideshowDuration(parseInt(e.target.value))}
                                            className="w-full h-1.5 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                                        />
                                        <p className="text-[10px] text-gray-500 mt-1">
                                            Images will be compiled into a {slideshowDuration}s slideshow Reel video.
                                        </p>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Platforms */}
                        <div>
                            <label className="block text-sm font-semibold text-gray-700 mb-2">Select Target Platforms</label>
                            {loadingConnections ? (
                                <p className="text-sm text-gray-500 animate-pulse">Checking connected accounts...</p>
                            ) : (
                                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                                    {[
                                        { id: 'facebook', name: 'Facebook', color: 'bg-[#1877F2] border-[#1877F2] text-white', icon: '📘' },
                                        { id: 'instagram', name: 'Instagram', color: 'bg-gradient-to-r from-[#833AB4] via-[#FD1D1D] to-[#FCAF45] border-transparent text-white', icon: '📸' },
                                        { id: 'tiktok', name: 'TikTok', color: 'bg-black border-black text-white', icon: '🎵' },
                                        { id: 'linkedin', name: 'LinkedIn', color: 'bg-[#0077b5] border-[#0077b5] text-white', icon: '💼' }
                                    ].map(p => {
                                        const conn = connections.find(c => c.platform === p.id);
                                        const isConnected = conn ? conn.connected : false;
                                        const isSelected = platforms.includes(p.id);
                                        
                                        return (
                                            <button
                                                key={p.id}
                                                type="button"
                                                disabled={!isConnected}
                                                onClick={() => togglePlatform(p.id)}
                                                className={`relative flex flex-col items-center justify-center p-4 rounded-xl border text-sm font-bold transition-all duration-200 select-none ${
                                                    !isConnected 
                                                        ? 'bg-gray-50 border-gray-200 text-gray-400 cursor-not-allowed opacity-60' 
                                                        : isSelected
                                                            ? `${p.color} shadow-lg ring-2 ring-offset-2 ring-blue-500 transform scale-[1.02]`
                                                            : 'bg-white border-gray-300 text-gray-700 hover:bg-gray-50'
                                                }`}
                                            >
                                                <span className="text-2xl mb-1">{p.icon}</span>
                                                <span className="capitalize">{p.name}</span>
                                                {!isConnected && (
                                                    <span className="absolute top-1.5 right-1.5 text-[9px] bg-gray-200 text-gray-600 px-1 py-0.5 rounded font-bold">
                                                        Offline
                                                    </span>
                                                )}
                                                {isConnected && !isSelected && (
                                                    <span className="absolute top-1.5 right-1.5 text-[9px] bg-green-100 text-green-700 px-1 py-0.5 rounded font-bold">
                                                        Ready
                                                    </span>
                                                )}
                                                {isConnected && isSelected && (
                                                    <span className="absolute top-1.5 right-1.5 text-[9px] bg-white text-blue-600 px-1 py-0.5 rounded font-black shadow-sm">
                                                        ✓
                                                    </span>
                                                )}
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                            {!loadingConnections && connections.filter(c => c.connected).length === 0 && (
                                <p className="text-xs text-red-500 mt-2 font-semibold">
                                    No accounts connected. Please go to the <a href="/dashboard" className="underline font-bold text-blue-600">Dashboard</a> to connect accounts before posting.
                                </p>
                            )}
                        </div>

                        {/* Facebook Page Selection */}
                        {platforms.includes('facebook') && (
                            <div className="bg-blue-50/50 border border-blue-100 rounded-lg p-4 space-y-2">
                                <label className="block text-sm font-semibold text-blue-900">
                                    Publishing Target for Facebook
                                </label>
                                {loadingPages ? (
                                    <p className="text-sm text-gray-500 animate-pulse">Loading pages...</p>
                                ) : facebookPages.length > 0 ? (
                                    <select
                                        value={selectedFacebookPage}
                                        onChange={e => setSelectedFacebookPage(e.target.value)}
                                        className="w-full p-2.5 bg-white border border-blue-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                                    >
                                        {facebookPages.map(page => (
                                            <option key={page.target_id} value={page.target_id}>
                                                {page.target_name} ({page.target_id})
                                            </option>
                                        ))}
                                    </select>
                                ) : (
                                    <div className="text-sm text-amber-700 bg-amber-50 border border-amber-200 p-3 rounded">
                                        No connected Facebook Pages found. Make sure you connected your account with proper permissions, or try reconnecting under "Connect Accounts".
                                    </div>
                                )}
                            </div>
                        )}

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

                {/* Live Preview Panel Column */}
                <div className="lg:col-span-2 space-y-6 lg:sticky lg:top-8 bg-white rounded-xl shadow-md p-8 flex flex-col items-center">
                    <h2 className="text-lg font-bold text-gray-800 flex items-center gap-2 self-start w-full border-b pb-3">
                        📱 Real-Time Social Preview
                    </h2>
                    
                    {/* Mobile Phone Mockup */}
                    <div className="w-full max-w-[290px] mx-auto bg-black rounded-[40px] border-[8px] border-gray-900 shadow-2xl relative overflow-hidden aspect-[9/16] flex flex-col justify-between">
                        {/* Top notch */}
                        <div className="absolute top-0 left-1/2 transform -translate-x-1/2 w-24 h-4 bg-gray-900 rounded-b-xl z-20 flex items-center justify-center">
                            <div className="w-10 h-1 bg-gray-800 rounded-full"></div>
                        </div>
                        
                        {/* Main Preview Screen */}
                        <div className="relative flex-grow w-full h-full bg-gray-950 flex items-center justify-center text-gray-400 overflow-hidden">
                            {videoLocalUrl ? (
                                <video
                                    ref={videoRef}
                                    src={videoLocalUrl}
                                    onEnded={handleVideoEnded}
                                    playsInline
                                    muted={videoVolume === 0}
                                    className="w-full h-full object-cover"
                                />
                            ) : imageLocalUrls.length > 0 ? (
                                isReel ? (
                                    /* Compiled Slideshow Reels view */
                                    <div className="w-full h-full relative">
                                        <img
                                            src={imageLocalUrls[currentSlideIndex]}
                                            alt={`Slide ${currentSlideIndex + 1}`}
                                            className="w-full h-full object-cover transition-all duration-500 ease-in-out transform scale-105"
                                        />
                                        <div className="absolute top-4 right-4 bg-black/60 px-2 py-1 rounded text-[10px] text-white font-mono z-10">
                                            Slideshow: {currentSlideIndex + 1}/{imageLocalUrls.length}
                                        </div>
                                    </div>
                                ) : (
                                    /* Swipeable Carousel view */
                                    <div className="w-full h-full relative group">
                                        <img
                                            src={imageLocalUrls[manualSlideIndex]}
                                            alt={`Carousel Slide ${manualSlideIndex + 1}`}
                                            className="w-full h-full object-cover"
                                        />
                                        <div className="absolute top-4 right-4 bg-black/60 px-2 py-1 rounded text-[10px] text-white z-10">
                                            Carousel: {manualSlideIndex + 1}/{imageLocalUrls.length}
                                        </div>
                                        
                                        {/* Navigation arrows */}
                                        {imageLocalUrls.length > 1 && (
                                            <>
                                                <button
                                                    type="button"
                                                    onClick={() => setManualSlideIndex(prev => (prev - 1 + imageLocalUrls.length) % imageLocalUrls.length)}
                                                    className="absolute left-2 top-1/2 transform -translate-y-1/2 bg-black/50 p-1.5 rounded-full text-white hover:bg-black/80 text-xs pointer-events-auto z-10"
                                                >
                                                    ◀
                                                </button>
                                                <button
                                                    type="button"
                                                    onClick={() => setManualSlideIndex(prev => (prev + 1) % imageLocalUrls.length)}
                                                    className="absolute right-2 top-1/2 transform -translate-y-1/2 bg-black/50 p-1.5 rounded-full text-white hover:bg-black/80 text-xs pointer-events-auto z-10"
                                                >
                                                    ▶
                                                </button>
                                            </>
                                        )}
                                    </div>
                                )
                            ) : mediaUrl ? (
                                <img src={mediaUrl} alt="Preview Url" className="w-full h-full object-cover" />
                            ) : (
                                <div className="p-6 text-center text-xs space-y-2 select-none">
                                    <div className="text-3xl">📭</div>
                                    <p className="font-semibold text-gray-500">No media uploaded yet</p>
                                    <p className="text-[10px] text-gray-600">Select images or videos to preview in real-time</p>
                                </div>
                            )}
                            
                            {/* Hidden/background Audio tag for sync playback */}
                            {audioLocalUrl && (
                                <audio
                                    ref={audioRef}
                                    src={audioLocalUrl}
                                    loop
                                    playsInline
                                />
                            )}
                            
                            {/* Reels Mock Overlay layout */}
                            {(videoLocalUrl || imageLocalUrls.length > 0 || mediaUrl) && (
                                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex flex-col justify-end p-4 pointer-events-none text-white z-10">
                                    {/* Right Sidebar Icons (simulated interaction) */}
                                    <div className="absolute right-3 bottom-24 flex flex-col items-center space-y-4 text-white text-xs opacity-90">
                                        <div className="flex flex-col items-center">
                                            <span className="text-lg">❤️</span>
                                            <span className="text-[9px]">1.2K</span>
                                        </div>
                                        <div className="flex flex-col items-center">
                                            <span className="text-lg">💬</span>
                                            <span className="text-[9px]">45</span>
                                        </div>
                                        <div className="flex flex-col items-center">
                                            <span className="text-lg">🔄</span>
                                            <span className="text-[9px]">Share</span>
                                        </div>
                                    </div>

                                    {/* Caption & Account detail */}
                                    <div className="max-w-[80%] space-y-1.5 text-left">
                                        <div className="flex items-center gap-2">
                                            <div className="w-6 h-6 rounded-full bg-blue-600 border border-white flex items-center justify-center text-[10px] font-bold">
                                                M
                                            </div>
                                            <span className="font-semibold text-xs truncate">monalisa_user</span>
                                        </div>
                                        <p className="text-[11px] leading-relaxed line-clamp-3 font-normal opacity-90 break-words">
                                            {content || "Your post description will appear here..."}
                                        </p>
                                        
                                        {/* Spinning sound icon if audio exists */}
                                        {audioFile && (
                                            <div className="flex items-center gap-1.5 text-[10px] text-gray-200 mt-2">
                                                <span className={`inline-block ${isPreviewPlaying ? 'animate-spin' : ''}`}>🎵</span>
                                                <span className="truncate max-w-[120px] font-mono">{audioFile.name}</span>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            )}
                        </div>

                        {/* Home indicator bar */}
                        <div className="h-4 bg-black flex items-center justify-center">
                            <div className="w-20 h-1 bg-gray-800 rounded-full"></div>
                        </div>
                    </div>

                    {/* Preview Audio Mixer Controls */}
                    {(videoLocalUrl || (imageLocalUrls.length > 0 && isReel)) && (
                        <div className="w-full max-w-[290px] mx-auto bg-white border border-gray-200 rounded-xl p-4 shadow-sm space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-xs font-semibold text-gray-700">Preview Mixer</span>
                                <button
                                    type="button"
                                    onClick={togglePlayPreview}
                                    className={`px-3 py-1 rounded text-xs font-semibold transition ${isPreviewPlaying ? 'bg-amber-100 text-amber-700 hover:bg-amber-200' : 'bg-green-100 text-green-700 hover:bg-green-200'}`}
                                >
                                    {isPreviewPlaying ? '⏸ Pause Preview' : '▶ Play Preview'}
                                </button>
                            </div>
                            {audioFile && (
                                <div className="text-[10px] text-gray-500 bg-gray-50 p-2 rounded flex justify-between">
                                    <span>Audio status:</span>
                                    <span className="font-semibold text-blue-600">
                                        {isPreviewPlaying ? 'Playing' : 'Paused'}
                                    </span>
                                </div>
                            )}
                        </div>
                    )}
                </div>

            </div>
        </div>
    );
}
