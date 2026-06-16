'use client';

import { useState, ChangeEvent, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch } from '../../utils/api';

// Platform Icons for Pills
const InstagramIcon = () => (
  <svg className="w-4 h-4 mr-1.5 inline-block text-current shrink-0" fill="none" stroke="currentColor" strokeWidth={2.5} viewBox="0 0 24 24">
    <rect x="2" y="2" width="20" height="20" rx="5" ry="5" />
    <path d="M16 11.37A4 4 0 1112.63 8 4 4 0 0116 11.37z" />
    <line x1="17.5" y1="6.5" x2="17.51" y2="6.5" />
  </svg>
);

const FacebookIcon = () => (
  <svg className="w-4 h-4 mr-1.5 inline-block text-current shrink-0" fill="currentColor" viewBox="0 0 24 24">
    <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
  </svg>
);

const LinkedInIcon = () => (
  <svg className="w-4 h-4 mr-1.5 inline-block text-current shrink-0" fill="currentColor" viewBox="0 0 24 24">
    <path d="M19 0h-14c-2.761 0-5 2.239-5 5v14c0 2.761 2.239 5 5 5h14c2.762 0 5-2.239 5-5v-14c0-2.761-2.238-5-5-5zm-11.751 20.107h-3.02v-9.302h3.02v9.302zm-1.51-10.597c-.967 0-1.75-.783-1.75-1.75s.783-1.75 1.75-1.75 1.75.783 1.75 1.75-.783 1.75-1.75 1.75zm13.261 10.597h-3.02v-4.72c0-1.126-.022-2.578-1.57-2.578-1.572 0-1.813 1.229-1.813 2.497v4.801h-3.02v-9.302h2.9v1.27h.041c.404-.766 1.392-1.573 2.864-1.573 3.064 0 3.63 2.017 3.63 4.639v4.966z" />
  </svg>
);

const TikTokIcon = () => (
  <svg className="w-4 h-4 mr-1.5 inline-block text-current shrink-0" fill="currentColor" viewBox="0 0 24 24">
    <path d="M12.53.02C13.84 0 15.14.01 16.44 0c.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.59-1 .01 2.62.02 5.24 0 7.86a7.35 7.35 0 0 1-.95 3.47c-.89 1.45-2.26 2.62-3.86 3.19-1.6.58-3.37.58-4.96.01a7.27 7.27 0 0 1-3.87-3.2 7.27 7.27 0 0 1-.94-3.48c.01-2 .76-3.95 2.13-5.4 1.38-1.45 3.33-2.29 5.37-2.38v4.14c-1.05.02-2.11.37-2.92 1.05-.81.68-1.32 1.69-1.43 2.75-.15 1.42.36 2.89 1.38 3.86 1.02.97 2.49 1.37 3.87 1.07 1.38-.3 2.53-1.33 2.99-2.67.2-.59.27-1.22.25-1.84V.02h-.03z" />
  </svg>
);

// Sidebar Nav Icons
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
  <svg className="w-4 h-4 text-gray-400 hover:text-gray-600 transition shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
  </svg>
);

const UserAvatar = () => (
  <div className="w-10 h-10 rounded-full overflow-hidden border border-gray-600 bg-gray-700 flex items-center justify-center shrink-0 shadow-sm relative">
    <svg className="w-6 h-6 text-gray-300" fill="currentColor" viewBox="0 0 24 24">
      <path d="M24 20.993V24H0v-2.996A14.977 14.977 0 0112.004 15c4.904 0 9.26 2.354 11.996 5.993zM16.002 8.999a4 4 0 11-8 0 4 4 0 018 0z" />
    </svg>
  </div>
);

function isVideoUrl(url: string) {
    const videoExtensions = [".mp4", ".mov", ".avi", ".mkv", ".webm", ".3gp"];
    const lower = url.toLowerCase();
    return videoExtensions.some(ext => lower.endsWith(ext) || lower.includes(`${ext}?`));
}

export default function PostPage() {
    const router = useRouter();
    const [title, setTitle] = useState('');
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
    const [filePreviews, setFilePreviews] = useState<Record<string, string>>({});
    
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
    const [userProfile, setUserProfile] = useState<any>(null);

    // UI Configuration States
    const [previewPlatformTab, setPreviewPlatformTab] = useState<string>('instagram');
    const [isAdvancedOpen, setIsAdvancedOpen] = useState(false);

    // Scheduling States
    const [isScheduled, setIsScheduled] = useState(false);
    const [scheduledAt, setScheduledAt] = useState('');
    const [timezone, setTimezone] = useState(Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC');

    const fileInputRef = useRef<HTMLInputElement | null>(null);
    const API_URL = process.env.NEXT_PUBLIC_API_URL;

    // Fetch Connections and Profile info
    useEffect(() => {
        const fetchMetadata = async () => {
            try {
                const [connRes, profileRes] = await Promise.all([
                    apiFetch(`${API_URL}/connections`),
                    apiFetch(`${API_URL}/auth/me`)
                ]);
                if (connRes.ok) {
                    setConnections(await connRes.json());
                }
                if (profileRes.ok) {
                    setUserProfile(await profileRes.json());
                }
            } catch (err) {
                console.error("Failed to fetch connection metadata:", err);
            } finally {
                setLoadingConnections(false);
            }
        };
        fetchMetadata();
    }, [API_URL]);

    // Manage object URLs for filePreviews
    useEffect(() => {
        const previewsMap: Record<string, string> = {};
        selectedFiles.forEach(file => {
            const key = `${file.name}-${file.size}`;
            previewsMap[key] = URL.createObjectURL(file);
        });
        setFilePreviews(previewsMap);

        return () => {
            Object.values(previewsMap).forEach(url => URL.revokeObjectURL(url));
        };
    }, [selectedFiles]);

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

    // Auto toggle preview platform tab to match selection
    useEffect(() => {
        if (platforms.length > 0 && !platforms.includes(previewPlatformTab)) {
            setPreviewPlatformTab(platforms[0]);
        }
    }, [platforms, previewPlatformTab]);

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

    const moveFileUp = (index: number) => {
        if (index === 0) return;
        setSelectedFiles(prev => {
            const next = [...prev];
            const temp = next[index];
            next[index] = next[index - 1];
            next[index - 1] = temp;
            return next;
        });
    };

    const moveFileDown = (index: number) => {
        setSelectedFiles(prev => {
            if (index >= prev.length - 1) return prev;
            const next = [...prev];
            const temp = next[index];
            next[index] = next[index + 1];
            next[index + 1] = temp;
            return next;
        });
    };

    const removeFile = (index: number) => {
        setSelectedFiles(prev => prev.filter((_, i) => i !== index));
    };

    const uploadFile = async (file: File) => {
        const token = localStorage.getItem('token');
        if (!token) throw new Error("Not authenticated");

        const filename = `${Date.now()}-${file.name}`;
        const res = await apiFetch(`${API_URL}/media/upload-url?filename=${filename}&content_type=${file.type}`, {
            method: 'POST'
        });

        if (!res.ok) throw new Error("Failed to get upload URL");

        const { upload_url, public_url } = await res.json();

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

    const handleSaveDraft = () => {
        if (!title && !content) {
            alert("Please enter a Title or Caption to save as a draft.");
            return;
        }
        localStorage.setItem("rhongi_draft", JSON.stringify({ title, content, platforms }));
        alert("Draft saved successfully to local storage!");
    };

    const handleAIAssist = () => {
        if (!title) {
            alert("Please enter a Post Title first to guide the AI Assist.");
            return;
        }
        const templates = [
            `🚀 Exciting news! We are officially launching our new feature suite today. Stay tuned for more updates on how you can supercharge your workflow! #innovation #launch`,
            `✨ Big things are happening! Check out our latest announcement about ${title}. We can't wait for you to try it out. Let us know what you think in the comments! 👇`,
            `📅 Mark your calendars! We are hosting a live session to talk about ${title}. Swipe up or click the link in our bio to register. See you there! 💻`
        ];
        const selected = templates[Math.floor(Math.random() * templates.length)];
        setContent(selected);
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

            if (selectedFiles.length > 0) {
                for (let i = 0; i < selectedFiles.length; i++) {
                    setMessage(`Uploading image ${i + 1} of ${selectedFiles.length}...`);
                    const url = await uploadFile(selectedFiles[i]);
                    finalMediaUrls.push(url);
                    setUploadProgress(Math.floor(10 + ((i + 1) / selectedFiles.length) * 40));
                }
            }

            if (audioFile) {
                setMessage("Uploading background audio...");
                finalAudioUrl = await uploadFile(audioFile);
            }

            if (isScheduled) {
                if (!scheduledAt) {
                    throw new Error("Please select a date and time to schedule the post.");
                }
                const schedTime = new Date(scheduledAt).getTime();
                if (schedTime <= Date.now()) {
                    throw new Error("Scheduled time must be in the future.");
                }
            }

            const hasMedia = finalMediaUrls.length > 0 || mediaUrl;
            if ((platforms.includes('tiktok') || platforms.includes('instagram')) && !hasMedia) {
                throw new Error("Media is required for TikTok or Instagram!");
            }

            setMessage(isScheduled ? 'Scheduling post...' : 'Publishing post...');
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
                    slideshow_duration: slideshowDuration,
                    scheduled_at: isScheduled && scheduledAt ? scheduledAt : undefined,
                    timezone: isScheduled ? timezone : undefined
                })
            });

            const data = await res.json();

            if (res.ok) {
                setUploadProgress(100);
                
                if (data.status === 'processing' && data.job_id) {
                    setMessage(isScheduled ? `Processing media for scheduling...` : `Processing media... This may take a moment.`);
                    
                    const pollJobStatus = async (jobId: string, attempts = 0) => {
                        if (attempts >= 60) {
                            setMessage(isScheduled ? `Scheduling processed but took longer than expected.` : `Processing taking longer than expected. Post ID: ${data.id}`);
                            setTimeout(() => {
                                window.location.href = '/dashboard';
                            }, 2000);
                            return;
                        }
                        
                        try {
                            const jobRes = await apiFetch(`${API_URL}/jobs/${jobId}`);
                            if (jobRes.ok) {
                                const jobData = await jobRes.json();
                                if (jobData.status === 'completed' || jobData.status === 'failed') {
                                    setMessage(isScheduled ? `Success! Post scheduled.` : `Success! Post ID: ${data.id}`);
                                    setContent('');
                                    setTitle('');
                                    setPlatforms([]);
                                    setSelectedFiles([]);
                                    setMediaUrl('');
                                    setIsScheduled(false);
                                    setScheduledAt('');
                                    setTimeout(() => {
                                        window.location.href = '/dashboard';
                                    }, 1500);
                                } else {
                                    setTimeout(() => pollJobStatus(jobId, attempts + 1), 5000);
                                }
                            } else {
                                setMessage(isScheduled ? `Success! Post scheduled.` : `Success! Post ID: ${data.id}`);
                                setTimeout(() => {
                                    window.location.href = '/dashboard';
                                }, 1500);
                            }
                        } catch (e) {
                            console.error('Error polling job status:', e);
                            setMessage(isScheduled ? `Success! Post scheduled.` : `Success! Post ID: ${data.id}`);
                            setTimeout(() => {
                                window.location.href = '/dashboard';
                            }, 1500);
                        }
                    };
                    
                    pollJobStatus(data.job_id);
                } else {
                    setMessage(isScheduled ? `Success! Post scheduled.` : `Success! Post ID: ${data.id}`);
                    setContent('');
                    setTitle('');
                    setPlatforms([]);
                    setSelectedFiles([]);
                    setMediaUrl('');
                    setIsScheduled(false);
                    setScheduledAt('');
                    setTimeout(() => {
                        window.location.href = '/dashboard';
                    }, 1500);
                }
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

    const handleLogout = async () => {
        try {
            await apiFetch(`${API_URL}/auth/logout`, {
                method: 'POST'
            });
        } catch (e) {
            console.error('Logout error:', e);
        }
        router.push('/login');
    };

    const isPlatformConnected = (platformName: string) => {
        const conn = connections.find(c => c.platform === platformName);
        return conn ? conn.connected : false;
    };

    return (
        <div className="flex flex-col lg:flex-row min-h-screen bg-[#F8F9FA] text-gray-800 font-sans">
            
            {/* Mobile Header / Top Nav */}
            <header className="lg:hidden bg-[#212529] text-white px-4 py-3.5 flex items-center justify-between shadow-md shrink-0">
                <div className="flex items-center space-x-2.5">
                    <div className="w-8 h-8 rounded-lg bg-[#FF4747] flex items-center justify-center font-black text-white text-sm">R</div>
                    <span className="font-extrabold text-sm tracking-wide">Rhongi Dashboard</span>
                </div>
                <div className="flex items-center gap-3">
                    <button 
                        onClick={() => router.push('/dashboard')} 
                        className="text-xs text-gray-300 border border-gray-700 px-3 py-1.5 rounded-lg font-bold"
                    >
                        Dashboard
                    </button>
                    <button 
                        onClick={handleLogout} 
                        className="text-xs text-red-400 font-extrabold"
                    >
                        Logout
                    </button>
                </div>
            </header>

            {/* Sidebar Navigation (Desktop) */}
            <aside className="hidden lg:flex w-72 bg-[#212529] text-white flex-col justify-between shrink-0 shadow-xl border-r border-gray-900/40 relative z-30">
                <div className="p-6 flex-1 flex flex-col">
                    
                    {/* Brand Header */}
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
                            onClick={() => router.push('/dashboard?tab=connect')}
                            className="w-full text-left text-gray-400 hover:text-white hover:bg-white/5 border-l-[3.5px] border-transparent pl-3 pr-4 py-3 rounded-r-xl flex items-center transition-all font-semibold text-[14px]"
                        >
                            <LinkIcon />
                            Connect Accounts
                        </button>

                        <button
                            onClick={() => router.push('/dashboard?tab=analytics')}
                            className="w-full text-left text-gray-400 hover:text-white hover:bg-white/5 border-l-[3.5px] border-transparent pl-3 pr-4 py-3 rounded-r-xl flex items-center transition-all font-semibold text-[14px]"
                        >
                            <ChartIcon />
                            Analytics
                        </button>

                        <button
                            onClick={() => router.push('/post')}
                            className="w-full text-left bg-white/10 text-white border-l-[3.5px] border-[#FF4747] pl-3 pr-4 py-3 rounded-r-xl flex items-center transition-all font-bold text-[14px]"
                        >
                            <CreateIcon />
                            Create Content
                        </button>

                        <button
                            onClick={() => router.push('/dashboard?tab=settings')}
                            className="w-full text-left text-gray-400 hover:text-white hover:bg-white/5 border-l-[3.5px] border-transparent pl-3 pr-4 py-3 rounded-r-xl flex items-center transition-all font-semibold text-[14px]"
                        >
                            <SettingsIcon />
                            Settings
                        </button>
                    </nav>
                </div>

                {/* Sidebar Footer */}
                <div className="p-6 border-t border-gray-800 space-y-1.5 bg-[#1B1E21]">
                    <button
                        onClick={() => router.push('/dashboard?tab=help')}
                        className="w-full text-left text-gray-400 hover:text-white hover:bg-white/5 border-l-[3.5px] border-transparent pl-3 pr-4 py-2.5 rounded-r-xl flex items-center transition-all font-semibold text-[13px]"
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

            {/* Main Workspace */}
            <main className="flex-1 p-6 md:p-10 lg:p-12 overflow-y-auto max-h-screen">
                <form onSubmit={handleSubmit} className="max-w-6xl mx-auto space-y-8">
                    
                    {/* Header: Title and Actions */}
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-gray-200/60 pb-5">
                        {/* Breadcrumbs & Title */}
                        <div>
                            <div className="flex items-center space-x-2 text-[10px] font-extrabold uppercase tracking-wider text-gray-400 mb-1.5">
                                <HomeIcon />
                                <span className="text-gray-300">›</span>
                                <span>Create Content</span>
                            </div>
                            <h1 className="text-2xl md:text-3xl font-extrabold text-gray-900 tracking-tight">
                                Create New Post
                            </h1>
                            <p className="text-xs text-gray-500 font-semibold mt-1">
                                Draft, schedule, or publish immediately across your connected platforms.
                            </p>
                        </div>
                        {/* Submit Actions */}
                        <div className="flex items-center gap-2.5 w-full sm:w-auto">
                            <button
                                type="button"
                                onClick={handleSaveDraft}
                                className="flex-1 sm:flex-initial text-xs border border-[#FF4747] text-[#FF4747] hover:bg-[#FF4747]/5 active:scale-[0.98] transition-all px-4 py-3 rounded-xl font-bold cursor-pointer"
                            >
                                Save as Draft
                            </button>
                            <button
                                type="submit"
                                disabled={isSubmitting}
                                className="flex-1 sm:flex-initial text-xs bg-[#FF4747] hover:bg-[#e03e3e] active:scale-[0.98] text-white px-5 py-3 rounded-xl font-bold transition-all shadow-md shadow-[#FF4747]/10 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
                            >
                                {isSubmitting ? (
                                    <>
                                        <svg className="animate-spin h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                        </svg>
                                        <span>{isScheduled ? 'Scheduling' : 'Publishing'} {uploadProgress > 0 && `(${uploadProgress}%)`}</span>
                                    </>
                                ) : (
                                    <>
                                        <svg className="w-3.5 h-3.5 inline-block text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                                        </svg>
                                        <span>{isScheduled ? 'Schedule Post' : 'Publish Now'}</span>
                                    </>
                                )}
                            </button>
                        </div>
                    </div>

                    {/* Columns grid */}
                    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
                        
                        {/* LEFT COLUMN: EDITOR FORM */}
                        <div className="lg:col-span-7 space-y-6">
                            
                            {/* Select Platforms Card */}
                            <div className="bg-white border border-gray-150 p-6 rounded-2xl shadow-sm space-y-3.5">
                                <h3 className="text-xs font-black uppercase tracking-wider text-gray-400">
                                    Select Platforms
                                </h3>
                                
                                {loadingConnections ? (
                                    <p className="text-xs text-gray-400 animate-pulse font-semibold">Checking connected accounts...</p>
                                ) : (
                                    <div className="flex gap-2.5 flex-wrap">
                                        {[
                                            { id: 'facebook', name: 'Facebook', icon: <FacebookIcon /> },
                                            { id: 'instagram', name: 'Instagram', icon: <InstagramIcon /> },
                                            { id: 'linkedin', name: 'LinkedIn', icon: <LinkedInIcon /> },
                                            { id: 'tiktok', name: 'TikTok', icon: <TikTokIcon /> }
                                        ].map(p => {
                                            const isConnected = isPlatformConnected(p.id);
                                            const isSelected = platforms.includes(p.id);
                                            
                                            return (
                                                <button
                                                    key={p.id}
                                                    type="button"
                                                    disabled={!isConnected}
                                                    onClick={() => togglePlatform(p.id)}
                                                    className={`inline-flex items-center px-4 py-2 rounded-full border text-xs font-bold transition-all cursor-pointer select-none active:scale-95 ${
                                                        !isConnected 
                                                            ? 'bg-gray-50 border-gray-200 text-gray-300 cursor-not-allowed opacity-55' 
                                                            : isSelected
                                                                ? 'bg-[#FF4747]/10 border-[#FF4747] text-[#FF4747] ring-1 ring-[#FF4747]/20 shadow-sm'
                                                                : 'bg-white border-gray-200 text-gray-700 hover:border-[#FF4747] hover:text-[#FF4747] hover:bg-slate-50/50'
                                                    }`}
                                                >
                                                    {p.icon}
                                                    <span>{p.name}</span>
                                                    {!isConnected && (
                                                        <span className="ml-1.5 text-[8px] uppercase tracking-wider font-extrabold text-gray-400 bg-gray-100 px-1 py-0.5 rounded">
                                                            Offline
                                                        </span>
                                                    )}
                                                </button>
                                            );
                                        })}
                                    </div>
                                )}
                            </div>

                            {/* Post Scheduling Card */}
                            <div className="bg-white border border-gray-150 p-6 rounded-2xl shadow-sm space-y-4">
                                <div className="flex items-center justify-between">
                                    <div>
                                        <h3 className="text-xs font-black uppercase tracking-wider text-gray-400">
                                            Post Scheduling
                                        </h3>
                                        <p className="text-[10px] text-gray-400 font-semibold mt-0.5">
                                            Schedule this post for later instead of publishing immediately
                                        </p>
                                    </div>
                                    <div className="flex items-center gap-2">
                                        <button
                                            type="button"
                                            onClick={() => setIsScheduled(!isScheduled)}
                                            className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                                                isScheduled ? 'bg-[#FF4747]' : 'bg-gray-200'
                                            }`}
                                        >
                                            <span
                                                className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
                                                    isScheduled ? 'translate-x-5' : 'translate-x-0'
                                                }`}
                                            />
                                        </button>
                                    </div>
                                </div>

                                {isScheduled && (
                                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 animate-fadeIn">
                                        <div>
                                            <label className="block text-[10px] font-black uppercase tracking-wider text-gray-400 mb-1.5">
                                                Scheduled Date & Time
                                            </label>
                                            <input
                                                type="datetime-local"
                                                required={isScheduled}
                                                value={scheduledAt}
                                                onChange={e => setScheduledAt(e.target.value)}
                                                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-[#FF4747]/10 focus:border-[#FF4747] text-xs font-semibold text-gray-700 bg-slate-50/20"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-[10px] font-black uppercase tracking-wider text-gray-400 mb-1.5">
                                                Timezone
                                            </label>
                                            <select
                                                value={timezone}
                                                onChange={e => setTimezone(e.target.value)}
                                                className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-[#FF4747]/10 focus:border-[#FF4747] text-xs font-semibold text-gray-700 bg-white"
                                            >
                                                <option value="UTC">UTC (GMT+0)</option>
                                                <option value="America/New_York">Eastern Time (ET)</option>
                                                <option value="America/Chicago">Central Time (CT)</option>
                                                <option value="America/Denver">Mountain Time (MT)</option>
                                                <option value="America/Los_Angeles">Pacific Time (PT)</option>
                                                <option value="Europe/London">London (GMT/BST)</option>
                                                <option value="Europe/Paris">Paris (CET/CEST)</option>
                                                <option value="Africa/Kigali">Kigali (CAT)</option>
                                                <option value="Asia/Tokyo">Tokyo (JST)</option>
                                                <option value="Asia/Kolkata">India (IST)</option>
                                                <option value="Australia/Sydney">Sydney (AEST)</option>
                                            </select>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Caption Card & Internal Title */}
                            <div className="bg-white border border-gray-150 p-6 rounded-2xl shadow-sm space-y-5">
                                
                                {/* Post Title (Internal) */}
                                <div>
                                    <label className="block text-xs font-black uppercase tracking-wider text-gray-400 mb-2">
                                        Post Title (Internal)
                                    </label>
                                    <input
                                        type="text"
                                        value={title}
                                        onChange={e => setTitle(e.target.value)}
                                        className="w-full px-4 py-3 rounded-xl border border-gray-200 focus:outline-none focus:ring-2 focus:ring-[#FF4747]/10 focus:border-[#FF4747] text-xs font-semibold text-gray-700 bg-slate-50/20"
                                        placeholder="e.g., Q3 Launch Announcement"
                                    />
                                </div>

                                {/* Caption Textarea */}
                                <div>
                                    <div className="flex justify-between items-center mb-2">
                                        <label className="block text-xs font-black uppercase tracking-wider text-gray-400">
                                            Caption
                                        </label>
                                        <span className="text-[10px] font-bold text-gray-400">
                                            {content.length}/2200
                                        </span>
                                    </div>
                                    <div className="border border-gray-200 rounded-xl overflow-hidden focus-within:ring-2 focus-within:ring-[#FF4747]/10 focus-within:border-[#FF4747] bg-white transition-all">
                                        <textarea
                                            value={content}
                                            onChange={e => setContent(e.target.value)}
                                            className="w-full p-4 text-xs font-semibold text-gray-700 focus:outline-none h-40 resize-none placeholder-gray-400 leading-relaxed"
                                            placeholder="Write your caption here..."
                                        />
                                        
                                        {/* Editor Toolbar (Smiley, Hash, Bold, Italic, AI Assist) */}
                                        <div className="flex justify-between items-center p-3 border-t border-gray-100 bg-slate-50/50 rounded-b-xl">
                                            <div className="flex space-x-4 text-gray-500 font-extrabold text-sm select-none">
                                                <button type="button" onClick={() => setContent(prev => prev + "😊")} className="hover:text-gray-800 transition cursor-pointer" title="Add emoji">😊</button>
                                                <button type="button" onClick={() => setContent(prev => prev + " #")} className="hover:text-gray-800 transition cursor-pointer font-black" title="Add hashtag">#</button>
                                                <button type="button" onClick={() => setContent(prev => prev + " **bold**")} className="hover:text-gray-800 transition cursor-pointer font-black" title="Insert bold text">B</button>
                                                <button type="button" onClick={() => setContent(prev => prev + " *italic*")} className="hover:text-gray-800 transition cursor-pointer italic font-black" title="Insert italic text">I</button>
                                            </div>
                                            <button
                                                type="button"
                                                onClick={handleAIAssist}
                                                className="text-xs font-extrabold text-[#FF4747] hover:text-[#e03e3e] transition cursor-pointer active:scale-95 flex items-center gap-1"
                                            >
                                                <span>✨</span> AI Assist
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>

                            {/* Media Upload Card */}
                            <div className="bg-white border border-gray-150 p-6 rounded-2xl shadow-sm space-y-4">
                                <h3 className="text-xs font-black uppercase tracking-wider text-gray-400">
                                    Media
                                </h3>

                                {/* Upload Trigger Box */}
                                <div 
                                    onClick={() => fileInputRef.current?.click()}
                                    className="border-2 border-dashed border-red-100 hover:border-[#FF4747]/60 rounded-2xl p-8 text-center bg-red-50/5 hover:bg-red-50/15 transition duration-300 cursor-pointer flex flex-col items-center justify-center space-y-3"
                                >
                                    <input
                                        type="file"
                                        multiple
                                        ref={fileInputRef}
                                        onChange={handleFileChange}
                                        accept="image/*,video/*"
                                        className="hidden"
                                    />
                                    <div className="w-12 h-12 rounded-full bg-[#FF4747]/5 flex items-center justify-center border border-[#FF4747]/10 shrink-0">
                                        <svg className="w-6 h-6 text-[#FF4747]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                            <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v3m0 0v3m0-3h3m-3 0H9m12 0a9 9 0 11-18 0 9 9 0 0118 0z" />
                                        </svg>
                                    </div>
                                    <div>
                                        <p className="text-xs font-bold text-gray-800">Upload Media</p>
                                        <p className="text-[10px] text-gray-400 font-semibold mt-1">
                                            Drag and drop images, videos, or click to browse
                                        </p>
                                        <p className="text-[9px] text-gray-400 font-medium mt-1">
                                            Supports JPG, PNG, MP4 up to 500MB
                                        </p>
                                    </div>
                                </div>

                                {/* Thumbnail Grid (preserves reordering and remove) */}
                                {selectedFiles.length > 0 && (
                                    <div className="border-t border-gray-100 pt-4 mt-2">
                                        <p className="text-[10px] font-extrabold uppercase tracking-wider text-gray-400 mb-3">
                                            Selected Media Order ({selectedFiles.length})
                                        </p>
                                        <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 gap-3">
                                            {selectedFiles.map((file, index) => {
                                                const key = `${file.name}-${file.size}`;
                                                const previewUrl = filePreviews[key];
                                                const isImage = file.type.startsWith('image/');
                                                
                                                return (
                                                    <div key={key} className="relative group border border-gray-200 rounded-xl p-1 bg-gray-50 flex flex-col justify-between aspect-square overflow-hidden shadow-sm">
                                                        <div className="w-full h-full bg-black rounded-lg overflow-hidden flex items-center justify-center relative">
                                                            {isImage && previewUrl ? (
                                                                <img src={previewUrl} alt="Thumbnail preview" className="w-full h-full object-cover" />
                                                            ) : (
                                                                <div className="text-white text-lg">🎥</div>
                                                            )}
                                                            {/* Index Badge */}
                                                            <div className="absolute top-1 left-1 bg-[#FF4747] text-white text-[10px] font-black w-4.5 h-4.5 rounded-full flex items-center justify-center shadow">
                                                                {index + 1}
                                                            </div>
                                                        </div>
                                                        {/* Reorder and Delete controls overlay on group hover */}
                                                        <div className="absolute inset-0 bg-black/60 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-between p-1.5 text-white">
                                                            <button
                                                                type="button"
                                                                onClick={() => removeFile(index)}
                                                                className="text-[9px] bg-[#FF4747] text-white px-1.5 py-0.5 rounded font-bold self-end active:scale-95 transition"
                                                            >
                                                                Remove
                                                            </button>
                                                            <div className="flex justify-between w-full">
                                                                <button
                                                                    type="button"
                                                                    disabled={index === 0}
                                                                    onClick={() => moveFileUp(index)}
                                                                    className="px-1 py-0.5 rounded bg-white/20 text-white disabled:opacity-30 disabled:hover:bg-white/20 hover:bg-white/40 text-[9px] transition"
                                                                >
                                                                    ←
                                                                </button>
                                                                <button
                                                                    type="button"
                                                                    disabled={index === selectedFiles.length - 1}
                                                                    onClick={() => moveFileDown(index)}
                                                                    className="px-1 py-0.5 rounded bg-white/20 text-white disabled:opacity-30 disabled:hover:bg-white/20 hover:bg-white/40 text-[9px] transition"
                                                                >
                                                                    →
                                                                </button>
                                                            </div>
                                                        </div>
                                                    </div>
                                                );
                                            })}
                                            {/* Plus button to append more files */}
                                            <button
                                                type="button"
                                                onClick={() => fileInputRef.current?.click()}
                                                className="border border-dashed border-gray-300 hover:border-[#FF4747] rounded-xl flex items-center justify-center text-gray-400 hover:text-[#FF4747] bg-white aspect-square text-xl transition cursor-pointer"
                                                title="Add more files"
                                            >
                                                +
                                            </button>
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* ADVANCED SETTINGS ACCORDION */}
                            <div className="bg-white border border-gray-150 rounded-2xl shadow-sm overflow-hidden">
                                <button
                                    type="button"
                                    onClick={() => setIsAdvancedOpen(!isAdvancedOpen)}
                                    className="w-full flex justify-between items-center p-5 font-bold text-xs uppercase tracking-wider text-gray-400 bg-slate-50/30 hover:bg-slate-50/70 border-b border-gray-150/40 focus:outline-none cursor-pointer transition-colors"
                                >
                                    <span className="flex items-center gap-2">
                                        ⚙️ Advanced Settings (Reels, Slideshows & Pages)
                                    </span>
                                    <span>{isAdvancedOpen ? '▲' : '▼'}</span>
                                </button>
                                
                                {isAdvancedOpen && (
                                    <div className="p-6 space-y-5 animate-slideDown">
                                        
                                        {/* Reel Toggle */}
                                        <div className="flex items-start space-x-3 bg-red-50/10 p-4 rounded-xl border border-red-100/40">
                                            <input
                                                type="checkbox"
                                                id="isReel"
                                                checked={isReel}
                                                onChange={e => setIsReel(e.target.checked)}
                                                className="h-4 w-4 text-[#FF4747] focus:ring-[#FF4747] border-gray-300 rounded cursor-pointer mt-0.5"
                                            />
                                            <div>
                                                <label htmlFor="isReel" className="block text-xs font-bold text-gray-800 cursor-pointer">
                                                    Publish Video as Reel / Short
                                                </label>
                                                <span className="block text-[10px] text-gray-400 font-semibold mt-0.5 leading-relaxed">
                                                    If enabled, video uploads will be published as Reels (Facebook) instead of standard feed posts.
                                                </span>
                                            </div>
                                        </div>

                                        {/* Background Music & Slideshow Settings */}
                                        {(isReel || selectedFiles.some(f => f.type.startsWith('video/'))) && (
                                            <div className="bg-gray-50/60 p-4 rounded-xl border border-gray-200/60 space-y-4">
                                                <h4 className="text-xs font-bold text-gray-700 flex items-center gap-1.5">
                                                    🎵 Background Music & Slideshow
                                                </h4>
                                                
                                                {/* Background Music Upload */}
                                                <div>
                                                    <label className="block text-[10px] font-black uppercase tracking-wider text-gray-400 mb-1.5">
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
                                                        className="w-full text-xs text-gray-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-md file:border-0 file:text-xs file:font-bold file:bg-[#FF4747]/5 file:text-[#FF4747] hover:file:bg-[#FF4747]/10"
                                                    />
                                                    {audioFile && (
                                                        <p className="text-[10px] text-green-600 font-bold mt-1.5">
                                                            ✓ Selected: {audioFile.name}
                                                        </p>
                                                    )}
                                                </div>

                                                {/* Volume Sliders */}
                                                {audioFile && (
                                                    <div className="grid grid-cols-2 gap-4">
                                                        <div>
                                                            <label className="block text-[9px] font-black uppercase tracking-wider text-gray-400 mb-1">
                                                                Music Volume: {Math.round(musicVolume * 100)}%
                                                            </label>
                                                            <input
                                                                type="range"
                                                                min="0"
                                                                max="1"
                                                                step="0.05"
                                                                value={musicVolume}
                                                                onChange={e => setMusicVolume(parseFloat(e.target.value))}
                                                                className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#FF4747]"
                                                            />
                                                        </div>
                                                        <div>
                                                            <label className="block text-[9px] font-black uppercase tracking-wider text-gray-400 mb-1">
                                                                Video Volume: {Math.round(videoVolume * 100)}%
                                                            </label>
                                                            <input
                                                                type="range"
                                                                min="0"
                                                                max="1"
                                                                step="0.05"
                                                                value={videoVolume}
                                                                onChange={e => setVideoVolume(parseFloat(e.target.value))}
                                                                className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#FF4747]"
                                                            />
                                                        </div>
                                                    </div>
                                                )}

                                                {/* Slideshow Duration (Only if we have images and are compiling to Reel) */}
                                                {isReel && selectedFiles.length > 0 && selectedFiles.every(f => f.type.startsWith('image/')) && (
                                                    <div>
                                                        <label className="block text-[9px] font-black uppercase tracking-wider text-gray-400 mb-1">
                                                            Slideshow Duration (seconds): {slideshowDuration}s
                                                        </label>
                                                        <input
                                                            type="range"
                                                            min="3"
                                                            max="30"
                                                            step="1"
                                                            value={slideshowDuration}
                                                            onChange={e => setSlideshowDuration(parseInt(e.target.value))}
                                                            className="w-full h-1 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-[#FF4747]"
                                                        />
                                                        <p className="text-[9px] text-gray-400 font-semibold mt-1">
                                                            Images will compile into a {slideshowDuration}s slideshow Reel video.
                                                        </p>
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {/* Facebook Page Selection */}
                                        {platforms.includes('facebook') && (
                                            <div className="bg-slate-50/60 border border-gray-200 rounded-xl p-4 space-y-2">
                                                <label className="block text-[10px] font-black uppercase tracking-wider text-gray-400">
                                                    Publishing Target for Facebook
                                                </label>
                                                {loadingPages ? (
                                                    <p className="text-xs text-gray-400 animate-pulse font-semibold">Loading pages...</p>
                                                ) : facebookPages.length > 0 ? (
                                                    <select
                                                        value={selectedFacebookPage}
                                                        onChange={e => setSelectedFacebookPage(e.target.value)}
                                                        className="w-full p-2.5 bg-white border border-gray-200 rounded-lg text-xs font-semibold focus:ring-2 focus:ring-[#FF4747]/10"
                                                    >
                                                        {facebookPages.map(page => (
                                                            <option key={page.target_id} value={page.target_id}>
                                                                {page.target_name} ({page.target_id})
                                                            </option>
                                                        ))}
                                                    </select>
                                                ) : (
                                                    <div className="text-[10px] text-amber-700 bg-amber-50 border border-amber-200 p-3 rounded-lg font-bold">
                                                        No connected Facebook Pages found. Try reconnecting under "Connect Accounts" to verify page permissions.
                                                    </div>
                                                )}
                                            </div>
                                        )}

                                        {/* Manual URL Input */}
                                        <div className="space-y-2">
                                            <label className="block text-[10px] font-black uppercase tracking-wider text-gray-400">
                                                Or Use Media URL
                                            </label>
                                            <input
                                                type="url"
                                                value={mediaUrl}
                                                onChange={e => setMediaUrl(e.target.value)}
                                                disabled={selectedFiles.length > 0}
                                                className="w-full px-4 py-2.5 rounded-lg border border-gray-200 text-xs font-semibold text-gray-700 disabled:bg-gray-100"
                                                placeholder="https://example.com/image.jpg"
                                            />
                                        </div>
                                    </div>
                                )}
                            </div>

                            {/* Status Message */}
                            {message && (
                                <div className={`p-4 rounded-xl text-center text-xs font-bold ${message.includes('Error') || message.includes('Failed') ? 'bg-red-50 text-red-700 border border-red-100' : 'bg-blue-50 text-blue-700 border border-blue-100'}`}>
                                    {message}
                                </div>
                            )}

                        </div>

                        {/* RIGHT COLUMN: LIVE PREVIEW */}
                        <div className="lg:col-span-5 space-y-6 lg:sticky lg:top-8 bg-white border border-gray-150 p-6 rounded-2xl shadow-sm flex flex-col items-center">
                            
                            {/* Live Preview Header with Tabs */}
                            <div className="w-full flex items-center justify-between border-b border-gray-100 pb-3.5 mb-2">
                                <h2 className="text-xs font-black uppercase tracking-wider text-gray-400 flex items-center gap-1.5">
                                    <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                                    </svg>
                                    Live Preview
                                </h2>
                                
                                {/* Platform Tabs for Preview */}
                                <div className="flex gap-2">
                                    {(platforms.length > 0 ? platforms : ['instagram']).map((p) => (
                                        <button
                                            key={p}
                                            type="button"
                                            onClick={() => setPreviewPlatformTab(p)}
                                            className={`pb-1 text-xs font-black uppercase tracking-wider border-b-2 transition cursor-pointer ${
                                                previewPlatformTab === p 
                                                    ? 'border-[#FF4747] text-[#FF4747]' 
                                                    : 'border-transparent text-gray-400 hover:text-gray-600'
                                            }`}
                                        >
                                            {p}
                                        </button>
                                    ))}
                                </div>
                            </div>

                            {/* Phone Mockup Frame */}
                            <div className="w-full max-w-[290px] bg-white rounded-3xl border border-gray-200/80 shadow-xl overflow-hidden relative flex flex-col justify-between">
                                
                                {/* Mockup Top Bar details */}
                                <div className="p-3 border-b border-gray-50 flex items-center justify-between shrink-0 bg-white">
                                    <div className="flex items-center space-x-2">
                                        <div className="w-6 h-6 rounded-full bg-[#FF4747] text-white flex items-center justify-center font-black text-[10px]">
                                            R
                                        </div>
                                        <div>
                                            <p className="text-[10px] font-black text-gray-900 leading-tight">rhongi_social</p>
                                            <p className="text-[8px] text-gray-400 font-bold leading-tight">Sponsored</p>
                                        </div>
                                    </div>
                                    <span className="text-gray-400 text-xs font-black select-none">•••</span>
                                </div>

                                {/* Mockup Main Media display */}
                                <div className="relative w-full aspect-square bg-slate-950 flex items-center justify-center text-gray-400 overflow-hidden shrink-0">
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
                                            <div className="w-full h-full relative">
                                                <img
                                                    src={imageLocalUrls[currentSlideIndex]}
                                                    alt={`Slide ${currentSlideIndex + 1}`}
                                                    className="w-full h-full object-cover transition-all duration-500"
                                                />
                                                <div className="absolute top-2 right-2 bg-black/60 px-1.5 py-0.5 rounded text-[8px] text-white font-mono z-10 font-bold">
                                                    Reels slideshow: {currentSlideIndex + 1}/{imageLocalUrls.length}
                                                </div>
                                            </div>
                                        ) : (
                                            <div className="w-full h-full relative group">
                                                <img
                                                    src={imageLocalUrls[manualSlideIndex]}
                                                    alt={`Carousel Slide ${manualSlideIndex + 1}`}
                                                    className="w-full h-full object-cover"
                                                />
                                                <div className="absolute top-2 right-2 bg-black/65 px-1.5 py-0.5 rounded text-[8px] text-white font-bold z-10">
                                                    Slide {manualSlideIndex + 1}/{imageLocalUrls.length}
                                                </div>
                                                
                                                {/* Swipe indicator arrows inside preview */}
                                                {imageLocalUrls.length > 1 && (
                                                    <>
                                                        <button
                                                            type="button"
                                                            onClick={() => setManualSlideIndex(prev => (prev - 1 + imageLocalUrls.length) % imageLocalUrls.length)}
                                                            className="absolute left-1.5 top-1/2 transform -translate-y-1/2 bg-black/50 hover:bg-black/75 p-1 rounded-full text-white text-[9px] z-10 cursor-pointer pointer-events-auto"
                                                        >
                                                            ◀
                                                        </button>
                                                        <button
                                                            type="button"
                                                            onClick={() => setManualSlideIndex(prev => (prev + 1) % imageLocalUrls.length)}
                                                            className="absolute right-1.5 top-1/2 transform -translate-y-1/2 bg-black/50 hover:bg-black/75 p-1 rounded-full text-white text-[9px] z-10 cursor-pointer pointer-events-auto"
                                                        >
                                                            ▶
                                                        </button>
                                                    </>
                                                )}
                                            </div>
                                        )
                                    ) : mediaUrl ? (
                                        <img src={mediaUrl} alt="Preview link" className="w-full h-full object-cover" />
                                    ) : (
                                        <div className="p-6 text-center text-[10px] space-y-1 select-none font-semibold text-gray-500">
                                            <div className="text-2xl mb-1">📭</div>
                                            <p>No media uploaded yet</p>
                                            <p className="text-[8px] text-gray-600 font-medium">Select images or videos to preview in real-time</p>
                                        </div>
                                    )}

                                    {/* Audio Element */}
                                    {audioLocalUrl && (
                                        <audio
                                            ref={audioRef}
                                            src={audioLocalUrl}
                                            loop
                                            playsInline
                                            className="hidden"
                                        />
                                    )}
                                </div>

                                {/* Mockup Bottom section */}
                                <div className="p-3 bg-white space-y-1.5 border-t border-gray-50">
                                    {/* Interaction Icons row */}
                                    <div className="flex justify-between items-center text-gray-700 text-xs">
                                        <div className="flex space-x-3.5">
                                            <span className="hover:text-red-500 cursor-pointer select-none">❤️</span>
                                            <span className="hover:text-blue-500 cursor-pointer select-none">💬</span>
                                            <span className="hover:text-green-500 cursor-pointer select-none">✈️</span>
                                        </div>
                                        <span className="hover:text-yellow-500 cursor-pointer select-none">🔖</span>
                                    </div>

                                    {/* Likes metrics display */}
                                    <p className="text-[10px] font-black text-gray-900 leading-tight">1,204 likes</p>

                                    {/* Caption content */}
                                    <div className="text-[10px] leading-relaxed text-gray-800 break-words font-medium">
                                        <span className="font-black text-gray-900 mr-1.5">rhongi_social</span>
                                        {content || "Exciting news! We are launching our new feature suite today. Stay tuned for more updates on how you can supercharge your workflow..."}
                                    </div>

                                    {/* Spinner audio tag details if exists */}
                                    {audioFile && (
                                        <div className="flex items-center gap-1 text-[8px] text-gray-400 font-mono mt-1 pt-1.5 border-t border-gray-50">
                                            <span className={isPreviewPlaying ? 'animate-spin' : ''}>🎵</span>
                                            <span className="truncate max-w-[150px]">{audioFile.name}</span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            {/* Preview Audio Mixer Controls */}
                            {(videoLocalUrl || (imageLocalUrls.length > 0 && isReel)) && (
                                <div className="w-full max-w-[290px] mx-auto bg-slate-50/60 border border-gray-200/80 rounded-xl p-3.5 mt-4 space-y-2">
                                    <div className="flex items-center justify-between">
                                        <span className="text-[10px] font-bold text-gray-500 uppercase tracking-wide">Preview Mixer</span>
                                        <button
                                            type="button"
                                            onClick={togglePlayPreview}
                                            className={`px-3 py-1 rounded-lg text-[10px] font-bold transition cursor-pointer active:scale-95 ${
                                                isPreviewPlaying 
                                                    ? 'bg-amber-100 text-amber-700 hover:bg-amber-200' 
                                                    : 'bg-green-100 text-green-700 hover:bg-green-200'
                                            }`}
                                        >
                                            {isPreviewPlaying ? '⏸ Pause' : '▶ Play'}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>

                    </div>
                </form>
            </main>
        </div>
    );
}
