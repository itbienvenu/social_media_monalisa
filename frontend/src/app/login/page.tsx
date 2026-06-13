'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

// Beautiful SVG Icons
const MailIcon = () => (
  <svg className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
  </svg>
);

const LockIcon = () => (
  <svg className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 00-2 2zM9 11V7a3 3 0 016 0v4" />
  </svg>
);

const EyeIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
    <path strokeLinecap="round" strokeLinejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
  </svg>
);

const EyeOffIcon = () => (
  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.542-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l18 18" />
  </svg>
);

const Logo = () => (
  <div className="flex justify-center mb-6">
    <div className="w-16 h-16 bg-[#FF4747] rounded-2xl flex items-center justify-center shadow-lg shadow-[#FF4747]/20 relative">
      <span className="text-[#F7E998] text-3xl font-extrabold tracking-tight select-none">R</span>
      <div className="absolute bottom-1 right-1 bg-[#F7E998] text-[#FF4747] w-5 h-5 rounded-full flex items-center justify-center font-bold text-xs shadow-sm">
        +
      </div>
    </div>
  </div>
);

export default function LoginPage() {
    const router = useRouter();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');

    useEffect(() => {
        // Check for URL errors from Google Auth
        const params = new URLSearchParams(window.location.search);
        const urlError = params.get('error');

        if (urlError) {
            setError(urlError);
        }
    }, [router]);

    const handleLogin = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/login`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'ngrok-skip-browser-warning': 'true'
                },
                body: JSON.stringify({ email, password }),
                credentials: 'include', // Important for cookies
            });

            if (res.ok) {
                router.push('/dashboard');
            } else {
                const data = await res.json();
                setError(data.detail || 'Login failed');
            }
        } catch (err) {
            setError('An error occurred. Please try again.');
        }
    };

    const handleGoogleLogin = async () => {
        setError('');
        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/google/url`, {
                headers: {
                    'ngrok-skip-browser-warning': 'true'
                },
                credentials: 'include'
            });
            const data = await res.json();
            if (data.url) {
                window.location.href = data.url;
            } else {
                setError('Failed to get Google login URL');
            }
        } catch (err) {
            setError('An error occurred getting Google login URL.');
        }
    };

    return (
        <div className="min-h-screen relative overflow-hidden flex items-center justify-center p-6 bg-slate-50/50">
            {/* Soft, premium background blur blobs */}
            <div className="absolute -left-40 top-1/4 w-[450px] h-[450px] rounded-full bg-[#F7E998]/35 blur-[120px] pointer-events-none -z-10" />
            <div className="absolute -right-40 -top-20 w-[450px] h-[450px] rounded-full bg-[#FF4747]/10 blur-[120px] pointer-events-none -z-10" />

            <div className="w-full max-w-[460px] p-8 md:p-10 bg-white rounded-3xl border border-gray-100 shadow-[0_20px_50px_rgba(0,0,0,0.04)] transition-all duration-300">
                {/* Logo and Headings */}
                <Logo />
                <div className="text-center mb-8">
                    <h1 className="text-3xl font-extrabold text-gray-900 tracking-tight mb-2">
                        Welcome Back
                    </h1>
                    <p className="text-sm text-gray-500 font-medium">
                        Log in to manage your growth agency
                    </p>
                </div>

                {/* Form */}
                <form className="space-y-5" onSubmit={handleLogin}>
                    {/* Google Login */}
                    <div>
                        <button
                            type="button"
                            onClick={handleGoogleLogin}
                            className="w-full flex items-center justify-center gap-3 py-3 px-4 border border-gray-200 hover:border-gray-300 rounded-xl text-sm font-semibold text-gray-700 bg-white hover:bg-gray-50/80 transition-all duration-200 ease-in-out shadow-sm active:scale-[0.98] cursor-pointer"
                        >
                            <svg viewBox="0 0 24 24" className="w-5 h-5 flex-shrink-0" xmlns="http://www.w3.org/2000/svg">
                                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z" fill="#FBBC05"/>
                                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z" fill="#EA4335"/>
                            </svg>
                            Login with Google
                        </button>
                    </div>

                    {/* Divider */}
                    <div className="flex items-center justify-center my-6">
                        <div className="flex-grow border-t border-gray-200/70"></div>
                        <span className="flex-shrink mx-4 text-xs font-semibold uppercase tracking-wider text-gray-400/90">
                            or continue with email
                        </span>
                        <div className="flex-grow border-t border-gray-200/70"></div>
                    </div>

                    {/* Email Input */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-bold uppercase tracking-wider text-gray-500 block">
                            Email Address
                        </label>
                        <div className="relative">
                            <input
                                type="email"
                                required
                                className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#FF4747]/20 focus:border-[#FF4747] text-gray-900 transition-all duration-200 placeholder:text-gray-400/80 bg-white"
                                placeholder="name@agency.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                            />
                            <MailIcon />
                        </div>
                    </div>

                    {/* Password Input */}
                    <div className="space-y-1.5">
                        <div className="flex justify-between items-center">
                            <label className="text-xs font-bold uppercase tracking-wider text-gray-500 block">
                                Password
                            </label>
                            <a href="#" className="text-xs font-semibold text-[#FF4747] hover:text-[#e03e3e] transition-colors duration-150">
                                Forgot password?
                            </a>
                        </div>
                        <div className="relative">
                            <input
                                type={showPassword ? 'text' : 'password'}
                                required
                                className="w-full pl-11 pr-11 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#FF4747]/20 focus:border-[#FF4747] text-gray-900 transition-all duration-200 placeholder:text-gray-400/80 bg-white"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                            />
                            <LockIcon />
                            <button
                                type="button"
                                onClick={() => setShowPassword(!showPassword)}
                                className="absolute right-3 top-1/2 -translate-y-1/2 p-1.5 hover:bg-gray-50 rounded-lg transition-colors text-gray-400 hover:text-gray-600 focus:outline-none cursor-pointer"
                            >
                                {showPassword ? <EyeOffIcon /> : <EyeIcon />}
                            </button>
                        </div>
                    </div>

                    {/* Error message */}
                    {error && (
                        <div className="p-3 bg-red-50 border border-red-100 rounded-xl text-red-600 text-xs font-semibold text-center transition-all duration-200 animate-fadeIn">
                            {error}
                        </div>
                    )}

                    {/* Action Button */}
                    <div className="pt-2">
                        <button
                            type="submit"
                            className="w-full py-3.5 px-4 bg-[#FF4747] hover:bg-[#e03e3e] active:scale-[0.99] text-white font-bold rounded-xl shadow-lg shadow-[#FF4747]/10 hover:shadow-[#FF4747]/20 transition-all duration-200 text-sm tracking-wide cursor-pointer"
                        >
                            Login to Dashboard
                        </button>
                    </div>

                    {/* Footer */}
                    <div className="text-center pt-3">
                        <p className="text-xs font-semibold text-gray-500">
                            Don't have an account?{' '}
                            <Link href="/register" className="text-[#FF4747] hover:text-[#e03e3e] transition-colors duration-150">
                                Register here
                            </Link>
                        </p>
                    </div>
                </form>
            </div>
        </div>
    );
}
