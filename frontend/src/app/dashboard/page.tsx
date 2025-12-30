"use client";

import { useSearchParams } from "next/navigation";
import { Suspense } from "react";

function DashboardContent() {
    const searchParams = useSearchParams();
    // const status = searchParams.get("status");

    return (
        <div className="flex flex-col items-center justify-center min-h-screen p-8 font-[family-name:var(--font-geist-sans)]">
            <main className="flex flex-col gap-8 row-start-2 items-center sm:items-start text-center">
                <h1 className="text-4xl font-bold">Dashboard</h1>

                <div className="p-6 bg-green-100 dark:bg-green-900 rounded-lg border border-green-300 dark:border-green-700">
                    <h2 className="text-2xl mb-2">Connection Successful!</h2>
                    <p>Your social media account has been connected.</p>
                </div>

                <div className="flex gap-4 items-center flex-col sm:flex-row">
                    <a
                        className="rounded-full border border-solid border-transparent transition-colors flex items-center justify-center bg-foreground text-background gap-2 hover:bg-[#383838] dark:hover:bg-[#ccc] text-sm sm:text-base h-10 sm:h-12 px-4 sm:px-5"
                        href="/"
                    >
                        Back to Home
                    </a>
                </div>
            </main>
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
