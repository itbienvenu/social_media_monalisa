'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

// Beautiful SVG Icons
const UserIcon = () => (
  <svg className="w-5 h-5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
  </svg>
);

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

export default function RegisterPage() {
    const router = useRouter();
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState('');

    const handleRegister = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');

        if (password.length < 8) {
            setError('Password must be at least 8 characters.');
            return;
        }

        try {
            const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/auth/register`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'ngrok-skip-browser-warning': 'true'
                },
                body: JSON.stringify({ 
                    email, 
                    password,
                    full_name: fullName 
                }),
            });

            const data = await res.json();

            if (res.ok) {
                // Redirect to login after successful registration
                router.push('/login');
            } else {
                setError(data.detail || 'Registration failed');
            }
        } catch (err) {
            setError('An error occurred. Please try again.');
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
                        Join Rhongi
                    </h1>
                    <p className="text-sm text-gray-500 font-medium">
                        Create your account to get started.
                    </p>
                </div>

                {/* Form */}
                <form className="space-y-5" onSubmit={handleRegister}>
                    {/* Full Name Input */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-bold uppercase tracking-wider text-gray-500 block">
                            Full Name
                        </label>
                        <div className="relative">
                            <input
                                type="text"
                                required
                                className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#FF4747]/20 focus:border-[#FF4747] text-gray-900 transition-all duration-200 placeholder:text-gray-400/80 bg-white"
                                placeholder="Jane Doe"
                                value={fullName}
                                onChange={(e) => setFullName(e.target.value)}
                            />
                            <UserIcon />
                        </div>
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
                                placeholder="jane@example.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                            />
                            <MailIcon />
                        </div>
                    </div>

                    {/* Password Input */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-bold uppercase tracking-wider text-gray-500 block">
                            Password
                        </label>
                        <div className="relative">
                            <input
                                type="password"
                                required
                                className="w-full pl-11 pr-4 py-3 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#FF4747]/20 focus:border-[#FF4747] text-gray-900 transition-all duration-200 placeholder:text-gray-400/80 bg-white"
                                placeholder="••••••••"
                                value={password}
                                onChange={(e) => setPassword(e.target.value)}
                            />
                            <LockIcon />
                        </div>
                        <p className="text-[10px] font-semibold text-gray-400">
                            Must be at least 8 characters.
                        </p>
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
                            Sign Up
                        </button>
                    </div>

                    {/* Footer */}
                    <div className="text-center pt-3">
                        <p className="text-xs font-semibold text-gray-500">
                            Already have an account?{' '}
                            <Link href="/login" className="text-[#FF4747] hover:text-[#e03e3e] transition-colors duration-150">
                                Log in
                            </Link>
                        </p>
                    </div>
                </form>
            </div>
        </div>
    );
}
